from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DEFAULT_SUPPORTED_EXTENSIONS
from runtime_encoding import (
    configure_utf8_runtime,
    decode_process_output,
    utf8_subprocess_env,
)
from reading_tracker import (
    MARKABLE_STATUSES,
    ReadingPaths,
    append_reading_event,
    build_reading_rows,
    filter_rows,
    load_latest_decisions,
    load_latest_reading_events,
    materialized_target_path,
    parse_categories,
)


@dataclass(slots=True)
class AppState:
    paths: ReadingPaths | None = None
    process: subprocess.Popen | None = None
    process_command: list[str] | None = None
    relationship_process: subprocess.Popen | None = None
    relationship_process_kind: str | None = None
    relationship_process_command: list[str] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


SOURCE_FILE_SCAN_CACHE_TTL_SECONDS = 2.0
_SOURCE_FILE_SCAN_CACHE: dict[Path, tuple[float, list[Path]]] = {}
_SOURCE_FILE_SCAN_CACHE_LOCK = threading.Lock()


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocTriage Console</title>
  <style>
    :root { color-scheme: light; --line:#d7dde8; --muted:#5f6b7a; --bg:#f6f8fb; --text:#172033; --blue:#1d4ed8; --green:#15803d; --red:#b91c1c; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Segoe UI", system-ui, sans-serif; color: var(--text); background: var(--bg); }
    header { padding: 16px 20px; background: #fff; border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 2; }
    .header-top { display: flex; align-items: center; gap: 12px; padding-right: 132px; }
    .ui-language-switch { position: absolute; top: 14px; right: 20px; display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 6px; border: 1px solid var(--line); border-radius: 6px; background: #fff; }
    .ui-language-switch .language-icon { color: var(--muted); font-size: 12px; font-weight: 600; line-height: 1; }
    .ui-language-switch select { width: 74px; height: 24px; border: 0; padding: 0 2px; background: transparent; font-size: 12px; }
    h1 { margin: 0 0 12px; font-size: 20px; }
    .tabs { display: flex; gap: 8px; margin-bottom: 12px; }
    .tab { border: 1px solid var(--line); background: #fff; border-radius: 6px; padding: 8px 12px; cursor: pointer; }
    .tab.active { background: var(--blue); border-color: var(--blue); color: #fff; }
    .filters, .run-grid { display: grid; grid-template-columns: repeat(8, minmax(96px, 1fr)); gap: 8px; align-items: end; }
    .run-grid { grid-template-columns: repeat(6, minmax(120px, 1fr)); }
    .reading-filters { grid-template-columns: minmax(120px, 150px) minmax(110px, 140px) minmax(100px, 120px) minmax(190px, 1fr) minmax(190px, 1fr) minmax(160px, 1fr) minmax(100px, 120px) minmax(120px, 140px) auto; align-items: start; }
    .reading-target { display: grid; grid-template-columns: minmax(260px, 1fr) auto auto minmax(220px, 1fr); gap: 8px; align-items: end; }
    label { display: grid; gap: 4px; font-size: 12px; color: var(--muted); }
    .label-row { display: inline-flex; align-items: center; gap: 4px; min-height: 16px; }
    .help { display: inline-grid; place-items: center; width: 16px; height: 16px; border: 1px solid var(--line); border-radius: 50%; color: var(--muted); background: #fff; font-size: 11px; line-height: 1; cursor: help; position: relative; }
    .floating-tip { position: fixed; left: 0; top: 0; display: none; max-width: 320px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 6px; background: #172033; color: #fff; font-size: 12px; line-height: 1.45; white-space: pre-line; z-index: 20; box-shadow: 0 8px 20px rgba(15, 23, 42, 0.18); }
    input, select, button { height: 32px; border: 1px solid var(--line); background: #fff; border-radius: 6px; padding: 0 8px; font: inherit; }
    select[multiple] { height: 72px; padding: 4px 6px; min-width: 0; }
    input[type=checkbox] { width: 18px; height: 18px; }
    button { cursor: pointer; color: var(--text); }
    button.primary { background: var(--blue); border-color: var(--blue); color: #fff; }
    button.danger { background: var(--red); border-color: var(--red); color: #fff; }
    .toggle-inline { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .toggle-inline > input[type=text] { flex: 1 1 220px; min-width: 0; }
    .advanced-run { display: none; }
    main { padding: 16px 20px; }
    section { display: none; }
    section.active { display: block; }
    .panel { background: #fff; border: 1px solid var(--line); padding: 12px; margin-bottom: 12px; }
    .stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
    .stats .pill { max-width: 100%; white-space: normal; overflow-wrap: anywhere; }
    .summary-bar { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 12px; }
    .summary-bar .stats { margin-bottom: 0; }
    .graph-layout { display: grid; grid-template-columns: minmax(260px, 320px) minmax(460px, 1.6fr) minmax(280px, 0.9fr); gap: 12px; align-items: start; }
    .graph-toolbar { display: grid; grid-template-columns: minmax(260px, 1fr) auto auto minmax(220px, 1fr) minmax(120px, 150px) auto; gap: 8px; align-items: end; }
    .graph-clusters { display: grid; gap: 8px; max-height: calc(100vh - 280px); overflow: auto; }
    .graph-cluster-item { width: 100%; height: auto; text-align: left; padding: 10px; display: grid; gap: 6px; }
    .graph-cluster-item.active { border-color: var(--blue); box-shadow: inset 0 0 0 1px var(--blue); background: #eef4ff; }
    .graph-cluster-title { font-size: 13px; font-weight: 600; color: var(--text); }
    .graph-cluster-preview { font-size: 12px; color: var(--muted); word-break: break-word; }
    .graph-canvas { min-height: 460px; border: 1px solid var(--line); border-radius: 6px; background: #fbfcfe; overflow: auto; }
    .graph-svg { width: 100%; height: 460px; display: block; }
    .graph-edge-list { display: grid; gap: 8px; margin-top: 10px; max-height: 220px; overflow: auto; }
    .graph-edge-item { border: 1px solid var(--line); border-radius: 6px; padding: 8px; background: #fff; font-size: 12px; }
    .graph-detail { display: grid; gap: 10px; }
    .graph-detail-card { border: 1px solid var(--line); border-radius: 6px; padding: 10px; background: #fff; }
    .graph-detail-card p { margin: 0; }
    .graph-actions { display: flex; gap: 6px; flex-wrap: wrap; }
    .graph-actions button { height: 28px; padding: 0 8px; font-size: 12px; }
    .graph-empty { display: grid; place-items: center; min-height: 180px; color: var(--muted); font-size: 13px; text-align: center; }
    .pager { display: flex; gap: 6px; align-items: center; justify-content: flex-end; flex-wrap: wrap; font-size: 13px; }
    .pager input { width: 64px; }
    .pager button { height: 28px; padding: 0 7px; }
    .multi-actions { display: flex; gap: 4px; }
    .multi-actions button { height: 24px; padding: 0 6px; font-size: 12px; }
    .pill { background: #fff; border: 1px solid var(--line); border-radius: 999px; padding: 6px 10px; font-size: 13px; }
    .progress { height: 12px; border: 1px solid var(--line); background: #eef2f7; border-radius: 999px; overflow: hidden; margin: 8px 0; }
    .progress > div { height: 100%; width: 0%; background: var(--green); }
    pre { background: #101827; color: #e5e7eb; padding: 12px; overflow: auto; max-height: 360px; border-radius: 6px; white-space: pre-wrap; }
    .table-wrap { background: #fff; border: 1px solid var(--line); overflow: auto; max-height: calc(100vh - 250px); }
    table { width: 100%; border-collapse: collapse; min-width: 1200px; }
    th, td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; font-size: 13px; }
    th { background: #f2f5fa; position: sticky; top: 0; z-index: 3; }
    .th-sort { display: inline-flex; align-items: center; gap: 4px; height: auto; padding: 0; border: 0; background: transparent; color: inherit; font-weight: 600; cursor: pointer; }
    .sort-mark { color: var(--blue); font-size: 11px; min-width: 10px; }
    td.name { max-width: 420px; word-break: break-word; }
    .doc-name { display: inline; font-weight: 600; color: var(--text); }
    .doc-name.has-summary { cursor: help; text-decoration: underline dotted var(--muted); text-underline-offset: 3px; }
    .doc-path { display: block; margin-top: 3px; color: var(--muted); font-size: 11px; line-height: 1.35; overflow-wrap: anywhere; user-select: text; }
    .muted { color: var(--muted); }
    .actions { display: flex; gap: 4px; flex-wrap: wrap; min-width: 300px; }
    .actions button { height: 28px; font-size: 12px; padding: 0 6px; }
    .status-unread { color: #b45309; font-weight: 600; }
    .status-reading { color: #1d4ed8; font-weight: 600; }
    .status-read { color: #15803d; font-weight: 600; }
    .status-reread_needed { color: #be123c; font-weight: 600; }
    .status-failed { color: var(--red); font-weight: 600; }
    .toast { position: fixed; right: 16px; bottom: 16px; background: #172033; color: #fff; padding: 10px 12px; border-radius: 6px; display: none; max-width: 520px; }
    @media (max-width: 1200px) { .graph-layout { grid-template-columns: 1fr; } }
    @media (max-width: 1000px) { .filters, .run-grid, .reading-filters, .reading-target, .graph-toolbar { grid-template-columns: repeat(2, minmax(120px, 1fr)); } .summary-bar { align-items: stretch; flex-direction: column; } }
  </style>
</head>
<body>
  <header>
    <div class="header-top">
      <h1 data-i18n="app_title">DocTriage 控制台</h1>
    </div>
    <div class="ui-language-switch" title="UI language">
      <span class="language-icon" aria-hidden="true">A/文</span>
      <select id="ui_language" onchange="setUiLanguage(this.value)" aria-label="UI language">
        <option value="zh-CN">中文</option>
        <option value="en">EN</option>
      </select>
    </div>
    <div class="tabs">
      <button id="tab-analysis" class="tab active" onclick="switchTab('analysis')" data-i18n="tab_analysis">分析执行</button>
      <button id="tab-reading" class="tab" onclick="switchTab('reading')" data-i18n="tab_reading">阅读台</button>
      <button id="tab-graph" class="tab" onclick="switchTab('graph')" data-i18n="tab_graph">关系图谱</button>
    </div>
  </header>
  <main>
    <section id="section-analysis" class="active">
      <div class="panel">
        <div class="run-grid">
          <label><span class="label-row"><span data-i18n="source_dir">源目录</span> <span class="help" tabindex="0" data-i18n-tip="tip_source_dir" data-tip="待分析的原始文档目录。程序会递归扫描其下支持的文件类型。不要把输出目录放到这个目录里面。">?</span></span><input id="run_source_dir" placeholder="请选择源文档目录" data-i18n-placeholder="ph_source_dir" /></label>
          <button id="pick_source_btn" onclick="pickFolder('run_source_dir')" data-i18n="pick_source_dir">选择源目录</button>
          <label><span class="label-row"><span data-i18n="output_dir">输出目录</span> <span class="help" tabindex="0" data-i18n-tip="tip_output_dir" data-tip="写入进度、日志、评分结果和可选复制结果的目录。同一输出目录会自动续跑；同一时间只允许一个分析进程写入。">?</span></span><input id="run_output_root" placeholder="请选择输出目录" data-i18n-placeholder="ph_output_dir" /></label>
          <button id="pick_output_btn" onclick="pickFolder('run_output_root')" data-i18n="pick_output_dir">选择输出目录</button>
          <label><span class="label-row">LLM Endpoint <span class="help" tabindex="0" data-i18n-tip="tip_llm_endpoint" data-tip="文档评分调用的文本模型接口。Ollama 默认是 /api/generate；如果你切换服务地址，这里要一起改。">?</span></span><input id="run_llm_endpoint" value="http://localhost:11434/api/generate" /></label>
          <label><span class="label-row"><span data-i18n="model">模型</span> <span class="help" tabindex="0" data-i18n-tip="tip_model" data-tip="用于文档分类、打分和摘要理解的模型名。关系挖掘若开启 embedding，但未单独指定 embedding 模型，也会回退使用这里的模型名。">?</span></span><input id="run_llm_model" value="gemma4:e4b" /></label>
          <label><span class="label-row"><span data-i18n="output_language">输出语言</span> <span class="help" tabindex="0" data-i18n-tip="tip_output_language" data-tip="摘要和原因的输出语言。自动会根据文档主体语言推断；也可以强制指定一种语言。">?</span></span>
            <select id="run_output_language">
              <option value="auto" data-i18n="lang_auto">自动</option>
              <option value="zh-CN" data-i18n="lang_zh">中文</option>
              <option value="en" data-i18n="lang_en">English</option>
              <option value="ja" data-i18n="lang_ja">日本語</option>
              <option value="ko" data-i18n="lang_ko">한국어</option>
              <option value="de" data-i18n="lang_de">Deutsch</option>
              <option value="fr" data-i18n="lang_fr">Français</option>
              <option value="es" data-i18n="lang_es">Español</option>
            </select>
          </label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="concurrency">并发</span> <span class="help" tabindex="0" data-i18n-tip="tip_concurrency" data-tip="同时向 LLM 发起的请求数。大目录和本地模型首跑建议 1；模型空闲且显存足够时再逐步上调。">?</span></span><input id="run_concurrency" type="number" value="1" min="1" max="64" /></label>
          <label class="advanced-run"><span class="label-row">Limit <span class="help" tabindex="0" data-i18n-tip="tip_limit" data-tip="只处理前 N 个候选文件，适合小样本验证提示词、速度和分类效果。留空表示全量。">?</span></span><input id="run_limit" type="number" min="1" placeholder="空为全量" data-i18n-placeholder="ph_limit" /></label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="max_mb">最大 MB</span> <span class="help" tabindex="0" data-i18n-tip="tip_max_mb" data-tip="跳过超过这个体积的候选文件，避免极大 PDF 或 Office 文档拖慢首轮筛选。">?</span></span><input id="run_max_file_size_mb" type="number" value="80" min="1" /></label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="quality_threshold">质量阈值</span> <span class="help" tabindex="0" data-i18n-tip="tip_quality_threshold" data-tip="达到这个分数的文档会被视为高价值候选。plan-only 模式下用于评分分层和后续筛选，不生成分类目录。">?</span></span><input id="run_quality_threshold" type="number" value="75" min="0" max="100" /></label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="timeout_seconds">超时秒</span> <span class="help" tabindex="0" data-i18n-tip="tip_timeout_seconds" data-tip="单个 LLM 请求最长等待时间。模型较慢或文档较大时可以调高；过高会让失败请求卡更久。">?</span></span><input id="run_timeout_seconds" type="number" value="240" min="5" /></label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="summary">摘要</span> <span class="help" tabindex="0" data-i18n-tip="tip_summary" data-tip="把本地短摘要写入 decisions.jsonl，后续做关系挖掘、公开写作筛选和人工复核时更有用。会多占一点状态文件空间。">?</span></span><input id="run_document_summary" type="checkbox" checked /></label>
          <label class="advanced-run"><span class="label-row">Plan only <span class="help" tabindex="0" data-i18n-tip="tip_plan_only" data-tip="只写评分、分类、进度和决策日志，不复制源文件。适合首轮摸底、大目录试跑和不想改动文件布局的场景。">?</span></span><input id="run_plan_only" type="checkbox" checked /></label>
          <label class="advanced-run"><span class="label-row">No OCR <span class="help" tabindex="0" data-i18n-tip="tip_no_ocr" data-tip="关闭 OCR。对有文本层的 PDF 和 Office 文档更快；纯图片或扫描版 PDF 可能提取不到正文。建议首轮勾选，后续对扫描件分批取消。">?</span></span><input id="run_no_ocr" type="checkbox" checked /></label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="skip_manifest">跳过 Manifest</span> <span class="help" tabindex="0" data-i18n-tip="tip_skip_manifest" data-tip="跳过目录级系列/集合分析，直接进入文件级评分。大目录首跑通常建议开启，先拿到全局评分结果。">?</span></span><input id="run_skip_manifest" type="checkbox" checked /></label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="force_reprocess">强制重跑</span> <span class="help" tabindex="0" data-i18n-tip="tip_force_reprocess" data-tip="忽略已处理记录，按当前参数重新处理匹配文件。适合你调整模型、阈值或提示词后重算。">?</span></span><input id="run_force_reprocess" type="checkbox" /></label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="content_hash">内容 Hash</span> <span class="help" tabindex="0" data-i18n-tip="tip_content_hash" data-tip="变更检测除了时间和大小，还计算文件内容哈希。更准，但大目录和大文件会更慢。">?</span></span><input id="run_content_hash" type="checkbox" /></label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="mine_relationships">挖掘关系</span> <span class="help" tabindex="0" data-i18n-tip="tip_mine_relationships" data-tip="在全部评分完成后，额外生成文档关系和聚类结果，输出到 _relationships/relations.jsonl 与 clusters.json。适合做去重、系列识别、主题聚类和后续 RAG 分组。">?</span></span><input id="run_mine_relationships" type="checkbox" /></label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="title_citations">标题引用</span> <span class="help" tabindex="0" data-i18n-tip="tip_title_citations" data-tip="启用轻量标题/路径引用信号，不额外调用 embedding 模型。成本低，适合默认开启，帮助发现同系列、互相提及或命名相近的文档。">?</span></span><input id="run_relationship_text" type="checkbox" /></label>
          <label class="advanced-run"><span class="label-row"><span data-i18n="embedding_relationships">Embedding 关系</span> <span class="help" tabindex="0" data-i18n-tip="tip_embedding_relationships" data-tip="给摘要、标题、类别等文本生成向量，用语义相似度找跨目录同主题、标题不相似但内容接近、近重复或演进关系。更耗时、也更吃模型资源。建议在首轮评分稳定后、关系质量比速度更重要时再勾选。">?</span></span><div class="toggle-inline"><input id="run_relationship_embeddings" type="checkbox" onchange="syncEmbeddingModelVisibility()" /><input id="run_embedding_model" type="text" placeholder="向量模型可留空沿用主模型" data-i18n-placeholder="ph_embedding_model" style="display:none;" disabled /></div></label>
        </div>
        <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
          <select id="run_template">
            <option value="" data-i18n="choose_template">选择模板</option>
            <option value="sample" data-i18n="template_sample">小样本试跑</option>
            <option value="overnight" data-i18n="template_overnight">过夜全量</option>
            <option value="relationships" data-i18n="template_relationships">评分+关系挖掘</option>
            <option value="strict" data-i18n="template_strict">严格小样本重跑</option>
          </select>
          <button onclick="applyTemplate()" data-i18n="apply_template">应用模板</button>
          <button id="toggle_advanced_btn" onclick="toggleAdvancedRunOptions()">显示高级参数</button>
          <button onclick="applyPaths()" data-i18n="apply_paths">应用路径</button>
          <button id="start_analysis_btn" class="primary" onclick="startAnalysis()" data-i18n="start_analysis">开始分析</button>
          <button onclick="loadAnalysis()" data-i18n="refresh_status">刷新状态</button>
          <button id="stop_analysis_btn" class="danger" onclick="stopAnalysis()" data-i18n="stop_analysis">停止分析</button>
          <button id="reset_analysis_btn" class="danger" onclick="resetAnalysis()" data-i18n="reset_analysis">重置分析</button>
        </div>
      </div>
      <div class="panel">
        <div id="analysisStats" class="stats"></div>
        <div class="progress"><div id="analysisBar"></div></div>
        <pre id="analysisLog"></pre>
      </div>
    </section>
    <section id="section-reading">
      <div class="panel reading-target">
        <label><span data-i18n="reading_output_root">阅读目标输出目录</span> <input id="reading_output_root" placeholder="选择或输入已分析输出目录" data-i18n-placeholder="ph_reading_output_root" /></label>
        <button id="pick_reading_output_btn" onclick="pickFolder('reading_output_root')" data-i18n="pick_folder">选择目录</button>
        <button onclick="applyReadingOutput()" data-i18n="apply_reading_output">应用阅读目录</button>
        <span class="muted" data-i18n="reading_target_hint">分析输出目录会单向回填这里；切换阅读目录不会影响分析执行。</span>
      </div>
      <div class="panel filters reading-filters">
        <label><span data-i18n="reading_scope">阅读范围</span>
          <select id="reading_scope">
            <option value="analysis" data-i18n="scope_analysis">分析结果</option>
            <option value="source" data-i18n="scope_source">全部源文件</option>
          </select>
        </label>
        <label><span data-i18n="status">状态</span>
          <select id="status">
            <option value="" data-i18n="status_all">全部</option>
            <option value="unread" data-i18n="status_unread">未读</option>
            <option value="reading" data-i18n="status_reading">在读</option>
            <option value="read" data-i18n="status_read">已读</option>
            <option value="reread_needed" data-i18n="status_reread_needed">需重读</option>
            <option value="failed" data-i18n="status_failed">失败</option>
            <option value="skipped" data-i18n="status_skipped">跳过</option>
            <option value="deferred" data-i18n="status_deferred">稍后</option>
          </select>
        </label>
        <label><span data-i18n="min_quality">最低质量</span> <input id="min_quality" type="number" value="80" min="0" max="100" /></label>
        <label><span data-i18n="category">分类</span>
          <select id="categories" multiple></select>
          <span class="multi-actions"><button onclick="selectMulti('categories', true)" data-i18n="select_all">全选</button><button onclick="invertMulti('categories')" data-i18n="invert">反选</button></span>
        </label>
        <label><span data-i18n="keywords">关键词</span>
          <select id="topic_tags" multiple></select>
          <span class="multi-actions"><button onclick="selectMulti('topic_tags', true)" data-i18n="select_all">全选</button><button onclick="invertMulti('topic_tags')" data-i18n="invert">反选</button></span>
        </label>
        <label><span data-i18n="search">搜索</span> <input id="q" placeholder="名称/路径/备注" data-i18n-placeholder="ph_text_search" /></label>
        <label><span data-i18n="max_sensitivity">最高敏感</span> <input id="max_sensitivity_risk" type="number" min="0" max="100" /></label>
        <label><span data-i18n="min_public">最低公开适配</span> <input id="min_public_writing_suitability" type="number" min="0" max="100" /></label>
        <button class="primary" onclick="loadRows()" data-i18n="refresh">刷新</button>
      </div>
      <div class="summary-bar">
        <div id="stats" class="stats"></div>
        <div id="pagerTop" class="pager"></div>
      </div>
      <div class="panel" style="display:flex; gap:8px; flex-wrap:wrap;">
        <button onclick="toggleAllRows(true)" data-i18n="select_current_page">全选当前页</button>
        <button onclick="toggleAllRows(false)" data-i18n="clear_selection">取消选择</button>
        <button onclick="bulkMark('reading')" data-i18n="bulk_reading">批量在读</button>
        <button onclick="bulkMark('read')" data-i18n="bulk_read">批量已读</button>
        <button onclick="bulkMark('deferred')" data-i18n="bulk_deferred">批量稍后</button>
        <button onclick="bulkMark('skipped')" data-i18n="bulk_skipped">批量跳过</button>
        <button onclick="bulkMark('unread')" data-i18n="bulk_unread">批量未读</button>
        <button class="primary" onclick="openNextVisible()" data-i18n="open_next">打开下一篇</button>
        <button onclick="exportFilteredRows('csv')" data-i18n="export_filtered_csv">导出当前筛选 CSV</button>
        <button onclick="exportFilteredRows('jsonl')" data-i18n="export_filtered_jsonl">导出当前筛选 JSONL</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th data-i18n="table_select">选择</th>
              <th><button class="th-sort" onclick="setSort('status')"><span data-i18n="status">状态</span> <span class="sort-mark" data-sort-mark="status"></span></button></th>
              <th><button class="th-sort" onclick="setSort('quality')"><span data-i18n="table_quality">质量</span> <span class="sort-mark" data-sort-mark="quality"></span></button></th>
              <th><button class="th-sort" onclick="setSort('category')"><span data-i18n="category">分类</span> <span class="sort-mark" data-sort-mark="category"></span></button></th>
              <th><button class="th-sort" onclick="setSort('document_kind')"><span data-i18n="table_type">类型</span> <span class="sort-mark" data-sort-mark="document_kind"></span></button></th>
              <th><button class="th-sort" onclick="setSort('sensitivity')"><span data-i18n="table_sensitivity_public">敏感/公开</span> <span class="sort-mark" data-sort-mark="sensitivity"></span></button></th>
              <th><button class="th-sort" onclick="setSort('path')"><span data-i18n="table_name">名称</span> <span class="sort-mark" data-sort-mark="path"></span></button></th>
              <th><button class="th-sort" onclick="setSort('source_mtime')"><span data-i18n="table_modified">修改时间</span> <span class="sort-mark" data-sort-mark="source_mtime"></span></button></th>
              <th data-i18n="table_tags">标签</th>
              <th data-i18n="table_actions">操作</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
      <div id="pagerBottom" class="pager" style="margin-top:10px;"></div>
    </section>
    <section id="section-graph">
      <div class="panel">
        <div class="graph-toolbar">
          <label><span data-i18n="graph_output_root">图谱分析目录</span> <input id="graph_output_root" placeholder="选择或输入已分析输出目录" data-i18n-placeholder="ph_graph_output_root" /></label>
          <button id="pick_graph_output_btn" onclick="pickFolder('graph_output_root')" data-i18n="pick_folder">选择目录</button>
          <button onclick="applyGraphOutput()" data-i18n="apply_graph_output">应用图谱目录</button>
          <label><span data-i18n="graph_search">簇搜索</span> <input id="graph_q" placeholder="路径/分类/标签" data-i18n-placeholder="ph_graph_search" /></label>
          <label><span data-i18n="graph_min_size">最小簇大小</span> <input id="graph_min_size" type="number" min="2" value="2" /></label>
          <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
            <button id="graph_mine_btn" class="primary" onclick="startGraphTask('mine')" data-i18n="generate_relationships">生成关系结果</button>
            <button id="graph_export_graph_btn" onclick="startGraphTask('export_graph')" data-i18n="export_kg">导出知识图谱</button>
            <button id="graph_export_bundle_btn" onclick="startGraphTask('export_bundle')" data-i18n="export_bundle">导出 Bundle</button>
            <button onclick="loadGraph()" data-i18n="refresh_graph">刷新图谱</button>
          </div>
        </div>
        <div id="graphTaskStats" class="stats" style="margin-top:10px;"></div>
      </div>
      <div class="graph-layout">
        <div class="panel">
          <div id="graphStats" class="stats"></div>
          <div id="graphClusters" class="graph-clusters"></div>
        </div>
        <div class="panel">
          <div id="graphClusterTitle" class="stats"></div>
          <div id="graphCanvas" class="graph-canvas"></div>
          <div id="graphEdges" class="graph-edge-list"></div>
        </div>
        <div class="panel">
          <div id="graphDocDetail" class="graph-detail"></div>
        </div>
      </div>
    </section>
  </main>
  <div id="tooltip" class="floating-tip"></div>
  <div id="toast" class="toast"></div>
  <script>
    const $ = (id) => document.getElementById(id);
    const I18N = {
      "zh-CN": {
        app_title: "DocTriage 控制台",
        tab_analysis: "分析执行",
        tab_reading: "阅读台",
        tab_graph: "关系图谱",
        source_dir: "源目录",
        output_dir: "输出目录",
        pick_source_dir: "选择源目录",
        pick_output_dir: "选择输出目录",
        model: "模型",
        output_language: "输出语言",
        lang_auto: "自动",
        lang_zh: "中文",
        lang_en: "English",
        lang_ja: "日本語",
        lang_ko: "한국어",
        lang_de: "Deutsch",
        lang_fr: "Français",
        lang_es: "Español",
        choose_template: "选择模板",
        template_sample: "小样本试跑",
        template_overnight: "过夜全量",
        template_relationships: "评分+关系挖掘",
        template_strict: "严格小样本重跑",
        apply_template: "应用模板",
        apply_paths: "应用路径",
        start_analysis: "开始分析",
        refresh_status: "刷新状态",
        stop_analysis: "停止分析",
        reset_analysis: "重置分析",
        reading_output_root: "阅读目标输出目录",
        graph_output_root: "图谱分析目录",
        pick_folder: "选择目录",
        apply_reading_output: "应用阅读目录",
        apply_graph_output: "应用图谱目录",
        reading_target_hint: "分析输出目录会单向回填这里；切换阅读目录不会影响分析执行。",
        reading_scope: "阅读范围",
        scope_analysis: "分析结果",
        scope_source: "全部源文件",
        scope_source_unscored: "未分析",
        status: "状态",
        min_quality: "最低质量",
        category: "分类",
        keywords: "关键词",
        search: "搜索",
        max_sensitivity: "最高敏感",
        min_public: "最低公开适配",
        refresh: "刷新",
        select_all: "全选",
        invert: "反选",
        select_current_page: "全选当前页",
        clear_selection: "取消选择",
        bulk_reading: "批量在读",
        bulk_read: "批量已读",
        bulk_deferred: "批量稍后",
        bulk_skipped: "批量跳过",
        bulk_unread: "批量未读",
        open_next: "打开下一篇",
        export_filtered_csv: "导出当前筛选 CSV",
        export_filtered_jsonl: "导出当前筛选 JSONL",
        open: "打开",
        reveal: "定位",
        mark_reading: "在读",
        mark_read: "已读",
        mark_deferred: "稍后",
        mark_skipped: "跳过",
        mark_unread: "未读",
        disabled_open_title: "当前环境不支持调用系统默认阅读器",
        disabled_reveal_title: "当前环境不支持文件管理器定位",
        missing_source_title: "源文件不存在，无法打开或定位",
        table_select: "选择",
        table_quality: "质量",
        table_type: "类型",
        table_sensitivity_public: "敏感/公开",
        table_name: "名称",
        table_modified: "修改时间",
        table_tags: "标签",
        table_actions: "操作",
        graph_search: "簇搜索",
        graph_min_size: "最小簇大小",
        generate_relationships: "生成关系结果",
        export_kg: "导出知识图谱",
        export_bundle: "导出 Bundle",
        refresh_graph: "刷新图谱",
        concurrency: "并发",
        max_mb: "最大 MB",
        quality_threshold: "质量阈值",
        timeout_seconds: "超时秒",
        summary: "摘要",
        skip_manifest: "跳过 Manifest",
        force_reprocess: "强制重跑",
        content_hash: "内容 Hash",
        mine_relationships: "挖掘关系",
        title_citations: "标题引用",
        embedding_relationships: "Embedding 关系",
        status_unread: "未读",
        status_reading: "在读",
        status_read: "已读",
        status_reread_needed: "需重读",
        status_failed: "失败",
        status_skipped: "跳过",
        status_deferred: "稍后",
        status_all: "全部",
        show_advanced: "显示高级参数",
        hide_advanced: "隐藏高级参数",
        no_summary: "无摘要",
        empty_graph: "暂无关系结果",
        graph_need_paths: "请先选择图谱分析目录",
        graph_no_match: "没有匹配的关系簇",
        graph_select_cluster: "选择一个关系簇查看文档详情",
        graph_no_docs: "这个关系簇没有可展示的文档",
        graph_no_edges: "当前文档没有可展示的关系边",
        related_documents: "关联文档",
        no_related_edges: "当前文档没有命中的关系边",
        no_explicit_signal: "无显式信号",
        uncategorized: "未分类",
        no_preview_path: "无预览路径",
        cluster: "簇",
        documents_unit: "篇",
        edges_unit: "条边",
        sensitive: "敏感",
        public_label: "公开",
        match_prefix: "匹配",
        all_prefix: "全部",
        first_page: "首页",
        previous_page: "上一页",
        next_page: "下一页",
        last_page: "末页",
        page_label: "第",
        page_suffix: "页",
        page_size_label: "数量",
        requested_open: "已请求打开",
        requested_reveal: "已请求定位",
        exported_rows: "已导出当前筛选",
        pick_failed: "选择失败",
        paths_apply_failed: "路径应用失败",
        paths_applied: "路径已应用",
        need_reading_output: "请先输入阅读目标输出目录",
        need_graph_output: "请先输入图谱分析目录",
        reading_output_apply_failed: "阅读目录应用失败",
        reading_output_applied: "阅读目录已应用",
        graph_output_apply_failed: "图谱目录应用失败",
        graph_output_applied: "图谱目录已应用",
        template_applied: "已应用模板",
        analysis_start_failed: "启动失败",
        analysis_started: "已启动分析",
        stop_requested: "已请求停止",
        stop_failed: "停止失败",
        need_source_output: "请先应用源目录和输出目录",
        reset_confirm: "将清空输出目录中的日志、状态和关系结果：\n{output}\n\n如果该目录中存在已复制的分类文件，也会一并清理。该操作不可恢复，确认继续？",
        reset_failed: "重置失败",
        output_reset: "输出目录已重置",
        status_load_failed: "状态加载失败",
        rows_load_failed: "加载失败",
        graph_load_failed: "图谱加载失败",
        graph_relations_exists: "存在 relations.jsonl",
        graph_clusters_exists: "存在 clusters.json",
        graph_decisions_exists: "存在 decisions.jsonl",
        graph_task_mine: "关系结果生成",
        graph_task_export_graph: "知识图谱导出",
        graph_task_export_bundle: "Bundle 导出",
        graph_task_running: "{task}中",
        graph_need_analysis_once: "先完成至少一次文档分析",
        graph_can_generate_relationships: "可直接生成关系结果",
        graph_task_start_failed: "关系任务启动失败",
        graph_task_started: "已启动{task}",
        graph_cluster_load_failed: "关系簇加载失败",
        graph_task_running_refresh: "{task}中，请稍后刷新",
        graph_need_analysis_before_graph: "先完成一次文档分析，再生成关系图谱",
        graph_no_relationships_generate: "还没有关系结果，可点击“生成关系结果”",
        graph_task_running_detail: "后台任务运行中，完成后这里会显示局部图和证据。",
        graph_generate_then_detail: "生成关系结果后，这里会显示局部图、证据和文档详情。",
        mark_failed: "标记失败",
        marked_status: "已标记：{status}",
        select_documents_first: "请先选择文档",
        bulk_mark_failed: "批量标记失败",
        bulk_marked: "已批量标记 {count} 篇",
        current_list_empty: "当前列表为空",
        sort_public_desc: "公开↓",
        sort_public_asc: "公开↑",
        plan_only_pill: "Plan only：仅评分与阅读标记，不复制文件",
        running_pill: "运行中",
        not_running_pill: "未运行",
        progress_pill: "进度",
        completed_pill: "完成",
        concurrency_pill: "并发",
        eta_waiting_pill: "ETA 等待连续规划",
        speed_pill: "速度",
        speed_waiting_pill: "速度等待连续规划",
        unresolved_failures_pill: "未解决失败",
        retry_recovered_pill: "重试恢复",
        stale_lock_pid_pill: "陈旧锁 PID",
        phase_not_started: "未启动",
        phase_relationship_mining: "关系挖掘中",
        phase_resume_preparing: "续传准备中",
        phase_resume_skipping: "续传跳过中",
        phase_scoring: "文档评分中",
        phase_scanning: "扫描准备中",
        phase_completed_with_failures: "分析完成，仍有失败",
        phase_completed_relationships: "分析完成，关系已生成",
        phase_completed_no_relationships: "分析完成，关系未生成",
        phase_completed: "分析完成",
        phase_stopped_resume: "已停止，可续传",
        activity_resume_skipped: "续传跳过",
        activity_planned: "已规划",
        activity_progress_write: "进度写入",
        activity_relationships: "关系挖掘",
        activity_recent_log: "最近日志",
        activity_relationships_started: "开始生成关系结果",
        activity_done: "已完成",
        explain_summary: "摘要",
        explain_reason: "评分理由",
        explain_dimensions: "维度",
        explain_failure: "失败",
        explain_failure_stage: "阶段",
        explain_failure_reason: "原因",
        explain_failure_attempts: "尝试",
        explain_failure_error: "错误",
        dim_knowledge_density: "知识密度",
        dim_implementation_specificity: "实现细节",
        dim_logical_structure: "逻辑结构",
        dim_evidence_richness: "证据",
        dim_actionability: "可执行",
        dim_strategic_value: "战略",
        dim_freshness: "新鲜",
        dim_uniqueness: "独特",
        folder_picker_unavailable: "当前环境不支持图形目录选择，请手工输入路径",
        operation_failed: "操作失败",
        tip_source_dir: "待分析的原始文档目录。程序会递归扫描其下支持的文件类型。不要把输出目录放到这个目录里面。",
        tip_output_dir: "写入进度、日志、评分结果和可选复制结果的目录。同一输出目录会自动续跑；同一时间只允许一个分析进程写入。",
        tip_llm_endpoint: "文档评分调用的文本模型接口。Ollama 默认是 /api/generate；如果你切换服务地址，这里要一起改。",
        tip_model: "用于文档分类、打分和摘要理解的模型名。关系挖掘若开启 embedding，但未单独指定 embedding 模型，也会回退使用这里的模型名。",
        tip_output_language: "摘要和原因的输出语言。自动会根据文档主体语言推断；也可以强制指定一种语言。",
        tip_concurrency: "同时向 LLM 发起的请求数。大目录和本地模型首跑建议 1；模型空闲且显存足够时再逐步上调。",
        tip_limit: "只处理前 N 个候选文件，适合小样本验证提示词、速度和分类效果。留空表示全量。",
        tip_max_mb: "跳过超过这个体积的候选文件，避免极大 PDF 或 Office 文档拖慢首轮筛选。",
        tip_quality_threshold: "达到这个分数的文档会被视为高价值候选。plan-only 模式下用于评分分层和后续筛选，不生成分类目录。",
        tip_timeout_seconds: "单个 LLM 请求最长等待时间。模型较慢或文档较大时可以调高；过高会让失败请求卡更久。",
        tip_summary: "把本地短摘要写入 decisions.jsonl，后续做关系挖掘、公开写作筛选和人工复核时更有用。会多占一点状态文件空间。",
        tip_plan_only: "只写评分、分类、进度和决策日志，不复制源文件。适合首轮摸底、大目录试跑和不想改动文件布局的场景。",
        tip_no_ocr: "关闭 OCR。对有文本层的 PDF 和 Office 文档更快；纯图片或扫描版 PDF 可能提取不到正文。建议首轮勾选，后续对扫描件分批取消。",
        tip_skip_manifest: "跳过目录级系列/集合分析，直接进入文件级评分。大目录首跑通常建议开启，先拿到全局评分结果。",
        tip_force_reprocess: "忽略已处理记录，按当前参数重新处理匹配文件。适合你调整模型、阈值或提示词后重算。",
        tip_content_hash: "变更检测除了时间和大小，还计算文件内容哈希。更准，但大目录和大文件会更慢。",
        tip_mine_relationships: "在全部评分完成后，额外生成文档关系和聚类结果，输出到 _relationships/relations.jsonl 与 clusters.json。适合做去重、系列识别、主题聚类和后续 RAG 分组。",
        tip_title_citations: "启用轻量标题/路径引用信号，不额外调用 embedding 模型。成本低，适合默认开启，帮助发现同系列、互相提及或命名相近的文档。",
        tip_embedding_relationships: "给摘要、标题、类别等文本生成向量，用语义相似度找跨目录同主题、标题不相似但内容接近、近重复或演进关系。更耗时、也更吃模型资源。建议在首轮评分稳定后、关系质量比速度更重要时再勾选。",
        ph_source_dir: "请选择源文档目录",
        ph_output_dir: "请选择输出目录",
        ph_reading_output_root: "选择或输入已分析输出目录",
        ph_graph_output_root: "选择或输入已分析输出目录",
        ph_text_search: "名称/路径/备注",
        ph_graph_search: "路径/分类/标签",
        ph_limit: "空为全量",
        ph_embedding_model: "向量模型可留空沿用主模型"
      },
      en: {
        app_title: "DocTriage Console",
        tab_analysis: "Analysis",
        tab_reading: "Reading",
        tab_graph: "Graph",
        source_dir: "Source directory",
        output_dir: "Output directory",
        pick_source_dir: "Pick source",
        pick_output_dir: "Pick output",
        model: "Model",
        output_language: "Output language",
        lang_auto: "Auto",
        lang_zh: "Chinese",
        lang_en: "English",
        lang_ja: "Japanese",
        lang_ko: "Korean",
        lang_de: "German",
        lang_fr: "French",
        lang_es: "Spanish",
        choose_template: "Choose template",
        template_sample: "Sample run",
        template_overnight: "Overnight full run",
        template_relationships: "Scoring + relationships",
        template_strict: "Strict sample rerun",
        apply_template: "Apply template",
        apply_paths: "Apply paths",
        start_analysis: "Start analysis",
        refresh_status: "Refresh status",
        stop_analysis: "Stop analysis",
        reset_analysis: "Reset analysis",
        reading_output_root: "Reading output directory",
        graph_output_root: "Graph analysis directory",
        pick_folder: "Pick folder",
        apply_reading_output: "Apply reading directory",
        apply_graph_output: "Apply graph directory",
        reading_target_hint: "The analysis output directory fills this field one way. Switching the reading directory does not affect analysis execution.",
        reading_scope: "Reading scope",
        scope_analysis: "Analysis results",
        scope_source: "All source files",
        scope_source_unscored: "Unscored",
        status: "Status",
        min_quality: "Min quality",
        category: "Category",
        keywords: "Keywords",
        search: "Search",
        max_sensitivity: "Max sensitivity",
        min_public: "Min public suitability",
        refresh: "Refresh",
        select_all: "Select all",
        invert: "Invert",
        select_current_page: "Select current page",
        clear_selection: "Clear selection",
        bulk_reading: "Bulk reading",
        bulk_read: "Bulk read",
        bulk_deferred: "Bulk defer",
        bulk_skipped: "Bulk skip",
        bulk_unread: "Bulk unread",
        open_next: "Open next",
        export_filtered_csv: "Export filtered CSV",
        export_filtered_jsonl: "Export filtered JSONL",
        open: "Open",
        reveal: "Reveal",
        mark_reading: "Reading",
        mark_read: "Read",
        mark_deferred: "Defer",
        mark_skipped: "Skip",
        mark_unread: "Unread",
        disabled_open_title: "System default file opening is unavailable in this environment",
        disabled_reveal_title: "File-manager reveal is unavailable in this environment",
        missing_source_title: "Source file does not exist",
        table_select: "Select",
        table_quality: "Quality",
        table_type: "Type",
        table_sensitivity_public: "Sensitivity/public",
        table_name: "Name",
        table_modified: "Modified",
        table_tags: "Tags",
        table_actions: "Actions",
        graph_search: "Cluster search",
        graph_min_size: "Min cluster size",
        generate_relationships: "Generate relationships",
        export_kg: "Export graph",
        export_bundle: "Export bundle",
        refresh_graph: "Refresh graph",
        concurrency: "Concurrency",
        max_mb: "Max MB",
        quality_threshold: "Quality threshold",
        timeout_seconds: "Timeout seconds",
        summary: "Summary",
        skip_manifest: "Skip manifest",
        force_reprocess: "Force reprocess",
        content_hash: "Content hash",
        mine_relationships: "Mine relationships",
        title_citations: "Title citations",
        embedding_relationships: "Embedding relationships",
        status_unread: "Unread",
        status_reading: "Reading",
        status_read: "Read",
        status_reread_needed: "Reread needed",
        status_failed: "Failed",
        status_skipped: "Skipped",
        status_deferred: "Deferred",
        status_all: "All",
        show_advanced: "Show advanced",
        hide_advanced: "Hide advanced",
        no_summary: "No summary",
        empty_graph: "No relationship results",
        graph_need_paths: "Select a graph analysis directory first",
        graph_no_match: "No matching relationship clusters",
        graph_select_cluster: "Select a relationship cluster to inspect documents",
        graph_no_docs: "This cluster has no displayable documents",
        graph_no_edges: "The selected document has no displayable relationship edges",
        related_documents: "Related documents",
        no_related_edges: "The selected document has no matching relationship edges",
        no_explicit_signal: "No explicit signal",
        uncategorized: "Uncategorized",
        no_preview_path: "No preview path",
        cluster: "Cluster",
        documents_unit: "docs",
        edges_unit: "edges",
        sensitive: "Sensitive",
        public_label: "Public",
        match_prefix: "Matched",
        all_prefix: "All",
        first_page: "First",
        previous_page: "Previous",
        next_page: "Next",
        last_page: "Last",
        page_label: "Page",
        page_suffix: "",
        page_size_label: "Page size",
        requested_open: "Open requested",
        requested_reveal: "Reveal requested",
        exported_rows: "Filtered rows exported",
        pick_failed: "Selection failed",
        paths_apply_failed: "Failed to apply paths",
        paths_applied: "Paths applied",
        need_reading_output: "Enter a reading output directory first",
        need_graph_output: "Enter a graph analysis directory first",
        reading_output_apply_failed: "Failed to apply reading directory",
        reading_output_applied: "Reading directory applied",
        graph_output_apply_failed: "Failed to apply graph directory",
        graph_output_applied: "Graph directory applied",
        template_applied: "Template applied",
        analysis_start_failed: "Failed to start analysis",
        analysis_started: "Analysis started",
        stop_requested: "Stop requested",
        stop_failed: "Failed to stop",
        need_source_output: "Apply source and output directories first",
        reset_confirm: "This will clear logs, status, and relationship results in the output directory:\n{output}\n\nCopied routed files in that directory will also be removed. This cannot be undone. Continue?",
        reset_failed: "Reset failed",
        output_reset: "Output directory reset",
        status_load_failed: "Failed to load status",
        rows_load_failed: "Failed to load rows",
        graph_load_failed: "Failed to load graph",
        graph_relations_exists: "relations.jsonl exists",
        graph_clusters_exists: "clusters.json exists",
        graph_decisions_exists: "decisions.jsonl exists",
        graph_task_mine: "Relationship generation",
        graph_task_export_graph: "Graph export",
        graph_task_export_bundle: "Bundle export",
        graph_task_running: "{task} running",
        graph_need_analysis_once: "Complete at least one document analysis first",
        graph_can_generate_relationships: "Relationship generation is available",
        graph_task_start_failed: "Failed to start relationship task",
        graph_task_started: "Started {task}",
        graph_cluster_load_failed: "Failed to load relationship cluster",
        graph_task_running_refresh: "{task} is running. Refresh later.",
        graph_need_analysis_before_graph: "Complete one document analysis before generating the graph",
        graph_no_relationships_generate: "No relationship results yet. Click Generate relationships.",
        graph_task_running_detail: "The background task is running. Local graph and evidence will appear here after it finishes.",
        graph_generate_then_detail: "After relationship generation, local graph, evidence, and document details will appear here.",
        mark_failed: "Failed to mark document",
        marked_status: "Marked: {status}",
        select_documents_first: "Select documents first",
        bulk_mark_failed: "Failed to mark selected documents",
        bulk_marked: "Marked {count} docs",
        current_list_empty: "The current list is empty",
        sort_public_desc: "Public↓",
        sort_public_asc: "Public↑",
        plan_only_pill: "Plan only: score and mark reading status without copying files",
        running_pill: "Running",
        not_running_pill: "Not running",
        progress_pill: "Progress",
        completed_pill: "Completed",
        concurrency_pill: "Concurrency",
        eta_waiting_pill: "ETA waiting for steady planning",
        speed_pill: "Speed",
        speed_waiting_pill: "Speed waiting for steady planning",
        unresolved_failures_pill: "Unresolved failures",
        retry_recovered_pill: "Retry recovered",
        stale_lock_pid_pill: "Stale lock PID",
        phase_not_started: "Not started",
        phase_relationship_mining: "Mining relationships",
        phase_resume_preparing: "Preparing resume",
        phase_resume_skipping: "Resume skipping",
        phase_scoring: "Scoring documents",
        phase_scanning: "Preparing scan",
        phase_completed_with_failures: "Analysis complete, failures remain",
        phase_completed_relationships: "Analysis complete, relationships generated",
        phase_completed_no_relationships: "Analysis complete, relationships not generated",
        phase_completed: "Analysis complete",
        phase_stopped_resume: "Stopped, resumable",
        activity_resume_skipped: "Resume skipped",
        activity_planned: "Planned",
        activity_progress_write: "Progress written",
        activity_relationships: "Relationships",
        activity_recent_log: "Recent log",
        activity_relationships_started: "Started relationship generation",
        activity_done: "Done",
        explain_summary: "Summary",
        explain_reason: "Scoring reason",
        explain_dimensions: "Dimensions",
        explain_failure: "Failure",
        explain_failure_stage: "Stage",
        explain_failure_reason: "Reason",
        explain_failure_attempts: "Attempts",
        explain_failure_error: "Error",
        dim_knowledge_density: "Knowledge",
        dim_implementation_specificity: "Implementation",
        dim_logical_structure: "Structure",
        dim_evidence_richness: "Evidence",
        dim_actionability: "Actionability",
        dim_strategic_value: "Strategic",
        dim_freshness: "Freshness",
        dim_uniqueness: "Uniqueness",
        folder_picker_unavailable: "Folder picker is unavailable here; type the path manually",
        operation_failed: "Operation failed",
        tip_source_dir: "Original document directory. DocTriage recursively scans supported file types under this folder.",
        tip_output_dir: "Directory for progress, logs, scoring results, and optional routed copies. A run can resume from the same output directory.",
        tip_llm_endpoint: "Text model endpoint for document scoring. Ollama defaults to /api/generate.",
        tip_model: "Model name for classification, scoring, and summaries. Relationship embedding can reuse it when no embedding model is set.",
        tip_output_language: "Language for generated summaries and reasons. Auto infers from the document body; explicit choices force that language.",
        tip_concurrency: "Maximum concurrent LLM requests. Start with 1 for large local runs.",
        tip_limit: "Process only the first N candidate files. Leave empty for all files.",
        tip_max_mb: "Skip files larger than this size to keep the first pass responsive.",
        tip_quality_threshold: "Documents at or above this score are treated as high-value candidates. Plan-only mode uses it for scoring layers, not copied folders.",
        tip_timeout_seconds: "Maximum wait time for one LLM request.",
        tip_summary: "Persist short summaries to decisions.jsonl for relationship mining, public-writing review, and manual triage.",
        tip_plan_only: "Record scoring, categories, progress, and decisions without copying source files.",
        tip_no_ocr: "Disable OCR. Faster for PDFs with text layers; scanned documents may extract little or no text.",
        tip_skip_manifest: "Skip directory-level series analysis and start file-level scoring directly.",
        tip_force_reprocess: "Ignore processed records and rerun matching files with current settings.",
        tip_content_hash: "Use content hashes in addition to timestamps and sizes. More accurate, slower on large folders.",
        tip_mine_relationships: "Generate document relations and clusters after scoring.",
        tip_title_citations: "Use lightweight title/path citation signals without calling an embedding model.",
        tip_embedding_relationships: "Generate embeddings for summaries, titles, and categories to find semantic relationships.",
        ph_source_dir: "Select source document directory",
        ph_output_dir: "Select output directory",
        ph_reading_output_root: "Select or enter an analyzed output directory",
        ph_graph_output_root: "Select or enter an analyzed output directory",
        ph_text_search: "Name/path/note",
        ph_graph_search: "Path/category/tag",
        ph_limit: "empty means all",
        ph_embedding_model: "empty reuses main model"
      }
    };
    let uiLanguage = localStorage.getItem("doctriage_ui_language") || "zh-CN";
    let allRows = [];
    let filteredRows = [];
    let currentRows = [];
    let capabilities = {};
    let currentPage = 1;
    let pageSize = Number(localStorage.getItem("doctriage_page_size") || 100);
    let readingScope = localStorage.getItem("doctriage_reading_scope") || "analysis";
    let sortKey = localStorage.getItem(sortStorageKey(readingScope)) || defaultSortForScope(readingScope);
    let graphMeta = {};
    let graphClusters = [];
    let filteredGraphClusters = [];
    let graphSelectedClusterId = null;
    let graphClusterData = null;
    let graphSelectedDocPath = "";
    let graphClearMessageKey = "empty_graph";
    let tooltipTarget = null;
    let readingSourceDir = "";
    let lastSyncedRunOutputRoot = "";
    let graphSourceDir = "";
    let lastSyncedGraphOutputRoot = "";
    const RUN_FORM_STORAGE_KEY = "doctriage_run_form";
    const READING_TARGET_STORAGE_KEY = "doctriage_reading_target";
    const GRAPH_TARGET_STORAGE_KEY = "doctriage_graph_target";
    const RUN_FORM_VALUE_FIELDS = [
      "run_source_dir",
      "run_output_root",
      "run_llm_endpoint",
      "run_llm_model",
      "run_output_language",
      "run_embedding_model",
      "run_concurrency",
      "run_limit",
      "run_max_file_size_mb",
      "run_quality_threshold",
      "run_timeout_seconds",
      "run_template"
    ];
    const RUN_FORM_CHECKBOX_FIELDS = [
      "run_document_summary",
      "run_plan_only",
      "run_no_ocr",
      "run_skip_manifest",
      "run_force_reprocess",
      "run_content_hash",
      "run_mine_relationships",
      "run_relationship_text",
      "run_relationship_embeddings"
    ];
    const RUN_FORM_ALLOW_EMPTY_FIELDS = new Set([
      "run_limit",
      "run_embedding_model",
      "run_template"
    ]);
    const EXPLANATION_DIMENSIONS = [
      ["knowledge_density", "dim_knowledge_density"],
      ["implementation_specificity", "dim_implementation_specificity"],
      ["logical_structure", "dim_logical_structure"],
      ["evidence_richness", "dim_evidence_richness"],
      ["actionability", "dim_actionability"],
      ["strategic_value", "dim_strategic_value"],
      ["freshness", "dim_freshness"],
      ["uniqueness", "dim_uniqueness"]
    ];

    function readingParams() {
      const pairs = new URLSearchParams();
      pairs.set("sort", sortKey);
      pairs.set("scope", readingScope);
      const paths = readingPathPayload();
      if (paths.source_dir) pairs.set("source_dir", paths.source_dir);
      if (paths.output_root) pairs.set("output_root", paths.output_root);
      return pairs.toString();
    }

    function sortStorageKey(scope) {
      return scope === "source" ? "doctriage_reading_sort_source" : "doctriage_reading_sort_analysis";
    }

    function defaultSortForScope(scope) {
      return scope === "source" ? "source_path_asc" : "quality_desc";
    }

    function tr(key) {
      return (I18N[uiLanguage] && I18N[uiLanguage][key]) || I18N["zh-CN"][key] || key;
    }

    function trf(key, values = {}) {
      let text = tr(key);
      for (const [name, value] of Object.entries(values)) {
        text = text.split(`{${name}}`).join(String(value ?? ""));
      }
      return text;
    }

    function readStoredRunFormState() {
      try {
        const raw = localStorage.getItem(RUN_FORM_STORAGE_KEY);
        if (!raw) return {};
        const payload = JSON.parse(raw);
        return payload && typeof payload === "object" ? payload : {};
      } catch (error) {
        return {};
      }
    }

    function currentRunFormState() {
      const state = {};
      for (const id of RUN_FORM_VALUE_FIELDS) {
        const element = $(id);
        if (element) state[id] = element.value;
      }
      for (const id of RUN_FORM_CHECKBOX_FIELDS) {
        const element = $(id);
        if (element) state[id] = !!element.checked;
      }
      return state;
    }

    function saveRunFormState() {
      try {
        localStorage.setItem(RUN_FORM_STORAGE_KEY, JSON.stringify(currentRunFormState()));
      } catch (error) {
        // Browser storage can be disabled or full; the form still works without persistence.
      }
    }

    function readStoredReadingTargetState() {
      try {
        const raw = localStorage.getItem(READING_TARGET_STORAGE_KEY);
        if (!raw) return {};
        const payload = JSON.parse(raw);
        return payload && typeof payload === "object" ? payload : {};
      } catch (error) {
        return {};
      }
    }

    function saveReadingTargetState() {
      try {
        localStorage.setItem(READING_TARGET_STORAGE_KEY, JSON.stringify(readingPathPayload()));
      } catch (error) {
        // Browser storage can be disabled or full; reading still works without persistence.
      }
    }

    function readStoredGraphTargetState() {
      try {
        const raw = localStorage.getItem(GRAPH_TARGET_STORAGE_KEY);
        if (!raw) return {};
        const payload = JSON.parse(raw);
        return payload && typeof payload === "object" ? payload : {};
      } catch (error) {
        return {};
      }
    }

    function saveGraphTargetState() {
      try {
        localStorage.setItem(GRAPH_TARGET_STORAGE_KEY, JSON.stringify(currentGraphTargetState()));
      } catch (error) {
        // Browser storage can be disabled or full; graph still works without persistence.
      }
    }

    function applyStoredReadingTargetState() {
      const state = readStoredReadingTargetState();
      let applied = false;
      if (Object.prototype.hasOwnProperty.call(state, "source_dir")) {
        readingSourceDir = String(state.source_dir || "");
        applied = true;
      }
      if (Object.prototype.hasOwnProperty.call(state, "output_root")) {
        const outputRoot = String(state.output_root || "");
        if (outputRoot && $("reading_output_root")) {
          $("reading_output_root").value = outputRoot;
          if (outputRoot === $("run_output_root").value.trim()) {
            lastSyncedRunOutputRoot = outputRoot;
          }
          applied = true;
        }
      }
      return applied;
    }

    function applyStoredGraphTargetState() {
      const state = readStoredGraphTargetState();
      let applied = false;
      if (Object.prototype.hasOwnProperty.call(state, "source_dir")) {
        graphSourceDir = String(state.source_dir || "");
        applied = true;
      }
      if (Object.prototype.hasOwnProperty.call(state, "output_root")) {
        const outputRoot = String(state.output_root || "");
        if (outputRoot && $("graph_output_root")) {
          $("graph_output_root").value = outputRoot;
          if (
            outputRoot === $("reading_output_root").value.trim() ||
            outputRoot === $("run_output_root").value.trim()
          ) {
            lastSyncedGraphOutputRoot = outputRoot;
          }
          applied = true;
        }
      }
      return applied;
    }

    function setReadingTarget(sourceDir, outputRoot, {persist = true} = {}) {
      readingSourceDir = String(sourceDir || "");
      if ($("reading_output_root")) $("reading_output_root").value = String(outputRoot || "");
      if (String(outputRoot || "") === $("run_output_root").value.trim()) {
        lastSyncedRunOutputRoot = String(outputRoot || "");
      }
      if (persist) saveReadingTargetState();
      syncGraphTargetFrom(sourceDir, outputRoot, {force: true});
    }

    function setGraphTarget(sourceDir, outputRoot, {persist = true} = {}) {
      graphSourceDir = String(sourceDir || "");
      if ($("graph_output_root")) $("graph_output_root").value = String(outputRoot || "");
      if (
        String(outputRoot || "") === $("reading_output_root").value.trim() ||
        String(outputRoot || "") === $("run_output_root").value.trim()
      ) {
        lastSyncedGraphOutputRoot = String(outputRoot || "");
      }
      if (persist) saveGraphTargetState();
    }

    function currentGraphTargetState() {
      return {
        source_dir: graphSourceDir,
        output_root: $("graph_output_root").value.trim()
      };
    }

    function syncGraphTargetFrom(sourceDir, outputRoot, {force = false} = {}) {
      const outputText = String(outputRoot || "").trim();
      if (!outputText) return;
      const currentGraphOutput = $("graph_output_root").value.trim();
      const shouldSync = force || !currentGraphOutput || currentGraphOutput === lastSyncedGraphOutputRoot;
      if (!shouldSync) return;
      graphSourceDir = String(sourceDir || "");
      $("graph_output_root").value = outputText;
      lastSyncedGraphOutputRoot = outputText;
      saveGraphTargetState();
    }

    function syncGraphTargetFromReadingOutput({force = false} = {}) {
      const paths = readingPathPayload();
      syncGraphTargetFrom(paths.source_dir, paths.output_root, {force});
    }

    function syncReadingTargetFromRunOutput({force = false, syncGraph = true} = {}) {
      const sourceDir = $("run_source_dir").value.trim();
      const outputRoot = $("run_output_root").value.trim();
      if (!outputRoot) return;
      const currentReadingOutput = $("reading_output_root").value.trim();
      const shouldSync = force || !currentReadingOutput || currentReadingOutput === lastSyncedRunOutputRoot;
      if (!shouldSync) return;
      readingSourceDir = sourceDir;
      $("reading_output_root").value = outputRoot;
      lastSyncedRunOutputRoot = outputRoot;
      saveReadingTargetState();
      if (syncGraph) syncGraphTargetFrom(sourceDir, outputRoot, {force});
    }

    function syncReadingSourceFromRunIfLinked() {
      const runOutputRoot = $("run_output_root").value.trim();
      const readingOutputRoot = $("reading_output_root").value.trim();
      if (readingOutputRoot && readingOutputRoot !== runOutputRoot && readingOutputRoot !== lastSyncedRunOutputRoot) return;
      readingSourceDir = $("run_source_dir").value.trim();
      saveReadingTargetState();
      syncGraphTargetFrom(readingSourceDir, readingOutputRoot || runOutputRoot);
    }

    function applyStoredRunFormState() {
      const state = readStoredRunFormState();
      for (const id of RUN_FORM_VALUE_FIELDS) {
        if (!Object.prototype.hasOwnProperty.call(state, id)) continue;
        const element = $(id);
        if (!element) continue;
        const value = String(state[id] ?? "");
        if (!value && !RUN_FORM_ALLOW_EMPTY_FIELDS.has(id)) continue;
        element.value = value;
      }
      for (const id of RUN_FORM_CHECKBOX_FIELDS) {
        if (!Object.prototype.hasOwnProperty.call(state, id)) continue;
        const element = $(id);
        if (element) element.checked = !!state[id];
      }
      syncEmbeddingModelVisibility();
    }

    function initRunFormPersistence() {
      for (const id of [...RUN_FORM_VALUE_FIELDS, ...RUN_FORM_CHECKBOX_FIELDS]) {
        const element = $(id);
        if (!element) continue;
        const eventName = element.tagName === "INPUT" && element.type !== "checkbox" ? "input" : "change";
        element.addEventListener(eventName, () => {
          if (id === "run_relationship_embeddings") syncEmbeddingModelVisibility();
          if (id === "run_output_root") syncReadingTargetFromRunOutput({force: true});
          if (id === "run_source_dir") syncReadingSourceFromRunIfLinked();
          saveRunFormState();
        });
      }
    }

    function initReadingTargetPersistence() {
      const element = $("reading_output_root");
      if (!element) return;
      element.addEventListener("input", () => {
        readingSourceDir = "";
        saveReadingTargetState();
        syncGraphTargetFrom("", element.value.trim(), {force: true});
      });
    }

    function initGraphTargetPersistence() {
      const element = $("graph_output_root");
      if (!element) return;
      element.addEventListener("input", () => {
        graphSourceDir = "";
        saveGraphTargetState();
      });
    }

    function setUiLanguage(language) {
      uiLanguage = I18N[language] ? language : "zh-CN";
      localStorage.setItem("doctriage_ui_language", uiLanguage);
      applyI18n();
    }

    function applyI18n() {
      document.documentElement.lang = uiLanguage;
      if ($("ui_language")) $("ui_language").value = uiLanguage;
      document.querySelectorAll("[data-i18n]").forEach(item => {
        item.textContent = tr(item.dataset.i18n);
      });
      document.querySelectorAll("[data-i18n-placeholder]").forEach(item => {
        item.setAttribute("placeholder", tr(item.dataset.i18nPlaceholder));
      });
      document.querySelectorAll("[data-i18n-tip]").forEach(item => {
        item.dataset.tip = tr(item.dataset.i18nTip);
      });
      if ($("reading_scope")) $("reading_scope").value = readingScope;
      setAdvancedRunOptionsVisible(localStorage.getItem("doctriage_run_advanced") === "1");
      renderStatsFromRows(filteredRows, allRows.length);
      renderPager();
      renderRows(currentRows);
      if (hasGraphPayload()) {
        renderGraphStats(graphMeta);
        renderGraphTaskStats(graphMeta);
        if (graphClusterData) renderGraphCluster();
        else if (filteredGraphClusters.length) renderGraphClusterList();
        else renderGraphEmptyState();
      } else {
        renderClearedGraphState();
      }
    }

    function switchTab(name) {
      for (const id of ["analysis", "reading", "graph"]) {
        $("tab-" + id).classList.toggle("active", id === name);
        $("section-" + id).classList.toggle("active", id === name);
      }
      if (name === "analysis") loadAnalysis();
      if (name === "reading") {
        if (readingPathPayload().output_root) loadRows();
      }
      if (name === "graph") {
        if (graphPathPayload().output_root) loadGraph();
        else clearGraphState("graph_need_paths");
      }
      localStorage.setItem("doctriage_tab", name);
    }

    async function loadConfig() {
      const response = await fetch("/api/config");
      const payload = await response.json();
      if (!response.ok) return;
      capabilities = payload.capabilities || {};
      $("run_source_dir").value = payload.source_dir || "";
      $("run_output_root").value = payload.output_root || "";
      $("reading_output_root").value = payload.output_root || "";
      $("graph_output_root").value = payload.output_root || "";
      readingSourceDir = payload.source_dir || "";
      lastSyncedRunOutputRoot = payload.output_root || "";
      graphSourceDir = payload.source_dir || "";
      lastSyncedGraphOutputRoot = payload.output_root || "";
      applyStoredRunFormState();
      const readingApplied = applyStoredReadingTargetState();
      const graphApplied = applyStoredGraphTargetState();
      if (!readingApplied) syncReadingTargetFromRunOutput({force: true, syncGraph: !graphApplied});
      if (!graphApplied) syncGraphTargetFromReadingOutput({force: true});
      for (const id of ["pick_source_btn", "pick_output_btn", "pick_reading_output_btn", "pick_graph_output_btn"]) {
        if ($(id)) {
          $(id).disabled = capabilities.folder_picker === false;
          $(id).title = capabilities.folder_picker === false ? tr("folder_picker_unavailable") : "";
        }
      }
      if (capabilities.headless_hint) {
        showToast(capabilities.headless_hint);
      }
      applyI18n();
      loadAnalysis();
    }

    async function pickFolder(targetId) {
      const response = await fetch("/api/pick-folder", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({target: targetId})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("pick_failed"));
      if (payload.path) $(targetId).value = payload.path;
      if (targetId === "run_output_root") syncReadingTargetFromRunOutput({force: true});
      if (targetId === "run_source_dir") syncReadingSourceFromRunIfLinked();
      if (targetId.startsWith("run_")) saveRunFormState();
      if (targetId === "reading_output_root") {
        readingSourceDir = "";
        saveReadingTargetState();
        syncGraphTargetFrom("", payload.path || "", {force: true});
      }
      if (targetId === "graph_output_root") {
        graphSourceDir = "";
        saveGraphTargetState();
      }
    }

    async function applyPaths() {
      saveRunFormState();
      const response = await fetch("/api/paths", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          source_dir: $("run_source_dir").value.trim(),
          output_root: $("run_output_root").value.trim()
        })
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("paths_apply_failed"));
      syncReadingTargetFromRunOutput({force: true});
      showToast(tr("paths_applied"));
      loadAnalysis();
      loadRows();
      if ($("section-graph").classList.contains("active")) loadGraph();
    }

    async function applyReadingOutput() {
      const outputRoot = $("reading_output_root").value.trim();
      if (!outputRoot) return showToast(tr("need_reading_output"));
      const response = await fetch("/api/reading-output", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({output_root: outputRoot})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("reading_output_apply_failed"));
      setReadingTarget(payload.source_dir || "", payload.output_root || outputRoot);
      showToast(tr("reading_output_applied"));
      loadRows();
      if ($("section-graph").classList.contains("active")) loadGraph();
    }

    async function applyGraphOutput() {
      const outputRoot = $("graph_output_root").value.trim();
      if (!outputRoot) return showToast(tr("need_graph_output"));
      const response = await fetch("/api/graph-output", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({output_root: outputRoot})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("graph_output_apply_failed"));
      setGraphTarget(payload.source_dir || "", payload.output_root || outputRoot);
      showToast(tr("graph_output_applied"));
      loadGraph();
    }

    function runPayload() {
      return {
        source_dir: $("run_source_dir").value.trim(),
        output_root: $("run_output_root").value.trim(),
        llm_endpoint: $("run_llm_endpoint").value.trim(),
        llm_model: $("run_llm_model").value.trim(),
        output_language: $("run_output_language").value,
        embedding_model: $("run_relationship_embeddings").checked ? $("run_embedding_model").value.trim() : "",
        concurrency: $("run_concurrency").value,
        limit: $("run_limit").value,
        max_file_size_mb: $("run_max_file_size_mb").value,
        quality_threshold: $("run_quality_threshold").value,
        timeout_seconds: $("run_timeout_seconds").value,
        document_summary: $("run_document_summary").checked,
        plan_only: $("run_plan_only").checked,
        no_ocr: $("run_no_ocr").checked,
        skip_manifest_analysis: $("run_skip_manifest").checked,
        force_reprocess: $("run_force_reprocess").checked,
        content_hash: $("run_content_hash").checked,
        mine_relationships: $("run_mine_relationships").checked,
        relationship_use_text_citations: $("run_relationship_text").checked,
        relationship_use_embeddings: $("run_relationship_embeddings").checked,
        template: $("run_template").value
      };
    }

    function pathPayload() {
      return {
        source_dir: $("run_source_dir").value.trim(),
        output_root: $("run_output_root").value.trim()
      };
    }

    function readingPathPayload() {
      const sourceDir = readingSourceDir;
      const outputRoot = $("reading_output_root").value.trim() || $("run_output_root").value.trim();
      return {
        source_dir: sourceDir,
        output_root: outputRoot
      };
    }

    function graphPathPayload() {
      const sourceDir = graphSourceDir;
      const outputRoot = $("graph_output_root").value.trim();
      return {
        source_dir: sourceDir,
        output_root: outputRoot
      };
    }

    function pathQuery() {
      const query = new URLSearchParams(pathPayload());
      return query.toString();
    }

    function graphQuery() {
      const query = new URLSearchParams(graphPathPayload());
      return query.toString();
    }

    function syncEmbeddingModelVisibility() {
      const enabled = $("run_relationship_embeddings").checked;
      $("run_embedding_model").style.display = enabled ? "" : "none";
      $("run_embedding_model").disabled = !enabled;
    }

    function setAdvancedRunOptionsVisible(visible) {
      document.querySelectorAll(".advanced-run").forEach(item => item.style.display = visible ? "grid" : "none");
      $("toggle_advanced_btn").textContent = visible ? tr("hide_advanced") : tr("show_advanced");
      localStorage.setItem("doctriage_run_advanced", visible ? "1" : "0");
    }

    function toggleAdvancedRunOptions() {
      const visible = localStorage.getItem("doctriage_run_advanced") === "1";
      setAdvancedRunOptionsVisible(!visible);
    }

    function applyTemplate() {
      const name = $("run_template").value;
      if (!name) return;
      $("run_limit").value = "";
      $("run_max_file_size_mb").value = "80";
      $("run_quality_threshold").value = "75";
      $("run_timeout_seconds").value = "240";
      $("run_document_summary").checked = true;
      $("run_plan_only").checked = true;
      $("run_no_ocr").checked = true;
      $("run_skip_manifest").checked = true;
      $("run_force_reprocess").checked = false;
      $("run_content_hash").checked = false;
      $("run_mine_relationships").checked = false;
      $("run_relationship_text").checked = false;
      $("run_relationship_embeddings").checked = false;
      if (name === "sample") $("run_limit").value = "200";
      if (name === "relationships") {
        $("run_mine_relationships").checked = true;
        $("run_relationship_text").checked = true;
      }
      if (name === "strict") {
        $("run_limit").value = "200";
        $("run_force_reprocess").checked = true;
        $("run_content_hash").checked = true;
      }
      syncEmbeddingModelVisibility();
      saveRunFormState();
      showToast(tr("template_applied"));
    }

    async function startAnalysis() {
      saveRunFormState();
      const response = await fetch("/api/analysis/start", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(runPayload())
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("analysis_start_failed"));
      showToast(tr("analysis_started"));
      loadAnalysis();
    }

    async function stopAnalysis() {
      const response = await fetch("/api/analysis/stop", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(pathPayload())
      });
      const payload = await response.json();
      showToast(response.ok ? tr("stop_requested") : (payload.error || tr("stop_failed")));
      loadAnalysis();
    }

    function clearReadingRows() {
      allRows = [];
      filteredRows = [];
      currentRows = [];
      populateFacetOptions([]);
      renderStatsFromRows([], 0);
      renderPager();
      renderSortMarks();
      renderRows([]);
    }

    function hasGraphPayload() {
      return !!(graphMeta && Object.keys(graphMeta).length);
    }

    function renderClearedGraphState() {
      const message = tr(graphClearMessageKey || "empty_graph");
      $("graphStats").innerHTML = `<span class="pill">${escapeHtml(message)}</span>`;
      $("graphTaskStats").innerHTML = "";
      $("graphClusters").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
      $("graphClusterTitle").innerHTML = "";
      $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
      $("graphEdges").innerHTML = "";
      $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
    }

    function clearGraphState(messageKey = "empty_graph") {
      graphClearMessageKey = messageKey;
      graphMeta = {};
      graphClusters = [];
      filteredGraphClusters = [];
      graphSelectedClusterId = null;
      graphClusterData = null;
      graphSelectedDocPath = "";
      renderClearedGraphState();
    }

    async function resetAnalysis() {
      const sourceDir = $("run_source_dir").value.trim();
      const outputRoot = $("run_output_root").value.trim();
      if (!sourceDir || !outputRoot) return showToast(tr("need_source_output"));
      if (!window.confirm(trf("reset_confirm", {output: outputRoot}))) return;
      const response = await fetch("/api/analysis/reset", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({source_dir: sourceDir, output_root: outputRoot})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("reset_failed"));
      clearReadingRows();
      clearGraphState("output_reset");
      showToast(tr("output_reset"));
      loadAnalysis();
    }

    async function loadAnalysis() {
      const query = pathQuery();
      const response = await fetch("/api/analysis/status" + (query ? "?" + query : ""));
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("status_load_failed"));
      renderAnalysis(payload);
    }

    function renderAnalysis(payload) {
      syncReadingTarget(payload);
      const progress = payload.progress || {};
      const activity = payload.activity || {};
      const latest = activity.latest_activity || {};
      const lock = payload.run_lock || {};
      const summary = payload.run_summary || {};
      const unresolvedFailures = Number(summary.unresolved_failures ?? progress.failed ?? 0);
      const retryAttempted = Number(summary.retry_attempted || 0);
      const retrySucceeded = Number(summary.retry_succeeded || 0);
      const phaseText = localizedPhase(payload.phase);
      const rateReady = !!progress.rate_window_active && Number(progress.rate_window_completed || 0) > 0;
      const parts = [
        phaseText,
        payload.plan_only ? tr("plan_only_pill") : "",
        payload.running ? tr("running_pill") : tr("not_running_pill"),
        payload.pid ? "PID " + payload.pid : "",
        payload.effective_concurrency ? `${tr("concurrency_pill")} ${payload.effective_concurrency}` : "",
        progress.percent !== undefined ? `${tr("progress_pill")} ${progress.percent}%` : "",
        progress.completed !== undefined ? `${tr("completed_pill")} ${progress.completed}/${progress.total || 0}` : "",
        rateReady && progress.eta_human && progress.eta_human !== "unknown" ? `ETA ${progress.eta_human}` : (payload.running ? tr("eta_waiting_pill") : ""),
        rateReady && progress.files_per_minute !== undefined && Number(progress.files_per_minute) > 0 ? `${tr("speed_pill")} ${progress.files_per_minute}/min` : (payload.running ? tr("speed_waiting_pill") : ""),
        unresolvedFailures > 0 ? `${tr("unresolved_failures_pill")} ${unresolvedFailures}` : "",
        retryAttempted > 0 ? `${tr("retry_recovered_pill")} ${retrySucceeded}/${retryAttempted}` : "",
        lock.exists && !lock.active && lock.pid ? `${tr("stale_lock_pid_pill")} ${lock.pid}` : "",
        activityPillText(latest)
      ].filter(Boolean);
      $("analysisStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
      $("analysisBar").style.width = Math.max(0, Math.min(100, Number(progress.percent || 0))) + "%";
      $("analysisLog").textContent = payload.log_tail || "";
      $("start_analysis_btn").disabled = !!payload.running;
      $("stop_analysis_btn").disabled = !payload.running;
      $("reset_analysis_btn").disabled = !!payload.running;
    }

    function activityPillText(latest) {
      if (!latest || !latest.label) return "";
      const label = localizedActivityLabel(latest.label);
      const detail = localizedActivityDetail(latest.detail || "").trim();
      return detail ? `${label}: ${detail}` : label;
    }

    function localizedPhase(phase) {
      if (phase === "文档评分中") return "";
      const key = {
        "未启动": "phase_not_started",
        "关系挖掘中": "phase_relationship_mining",
        "续传准备中": "phase_resume_preparing",
        "续传跳过中": "phase_resume_skipping",
        "扫描准备中": "phase_scanning",
        "分析完成，仍有失败": "phase_completed_with_failures",
        "分析完成，关系已生成": "phase_completed_relationships",
        "分析完成，关系未生成": "phase_completed_no_relationships",
        "分析完成": "phase_completed",
        "已停止，可续传": "phase_stopped_resume"
      }[phase];
      return key ? tr(key) : (phase || "");
    }

    function localizedActivityLabel(label) {
      const key = {
        "续传跳过": "activity_resume_skipped",
        "已规划": "activity_planned",
        "进度写入": "activity_progress_write",
        "关系挖掘": "activity_relationships",
        "最近日志": "activity_recent_log"
      }[label];
      return key ? tr(key) : (label || "");
    }

    function localizedActivityDetail(detail) {
      const key = {
        "开始生成关系结果": "activity_relationships_started",
        "已完成": "activity_done"
      }[detail];
      return key ? tr(key) : (detail || "");
    }

    async function loadRows() {
      syncReadingScopeControls();
      const response = await fetch("/api/state?" + readingParams());
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("rows_load_failed"));
      allRows = payload.rows || [];
      populateFacetOptions(allRows);
      currentPage = 1;
      applyClientFilters();
    }

    function syncReadingScopeControls() {
      if ($("reading_scope")) $("reading_scope").value = readingScope;
      const disabled = readingScope === "source";
      for (const id of ["min_quality", "categories", "topic_tags", "max_sensitivity_risk", "min_public_writing_suitability"]) {
        const element = $(id);
        if (element) element.disabled = disabled;
      }
    }

    function syncReadingTarget(payload) {
      if (!payload) return;
      let changed = false;
      if (payload.source_dir && $("run_source_dir").value !== payload.source_dir) {
        $("run_source_dir").value = payload.source_dir;
        changed = true;
      }
      if (payload.output_root && $("run_output_root").value !== payload.output_root) {
        $("run_output_root").value = payload.output_root;
        changed = true;
      }
      if (changed) {
        syncReadingTargetFromRunOutput();
        saveRunFormState();
      } else if (!$("reading_output_root").value.trim()) {
        syncReadingTargetFromRunOutput();
      }
    }

    async function loadGraph(preserveSelection = true) {
      if (!graphPathPayload().output_root) {
        clearGraphState("graph_need_paths");
        return;
      }
      const query = graphQuery();
      const response = await fetch("/api/relationships" + (query ? "?" + query : ""));
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("graph_load_failed"));
      graphMeta = payload;
      graphClusters = payload.clusters || [];
      renderGraphStats(payload);
      renderGraphTaskStats(payload);
      applyGraphFilters(preserveSelection);
    }

    function renderGraphStats(payload) {
      const parts = [];
      if (payload.cluster_count !== undefined) parts.push(`${tr("cluster")} ${payload.cluster_count}`);
      if (payload.relations_exists) parts.push(tr("graph_relations_exists"));
      if (payload.clusters_exists) parts.push(tr("graph_clusters_exists"));
      if (payload.decisions_exists) parts.push(tr("graph_decisions_exists"));
      if (!payload.available) parts.push(tr("empty_graph"));
      $("graphStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
    }

    function graphTaskKindLabel(kind) {
      return {
        mine: tr("graph_task_mine"),
        export_graph: tr("graph_task_export_graph"),
        export_bundle: tr("graph_task_export_bundle")
      }[kind] || kind || "";
    }

    function localGraphTaskLabel(label, taskName = "") {
      const reverse = {
        "关系结果生成": "graph_task_mine",
        "知识图谱导出": "graph_task_export_graph",
        "Bundle 导出": "graph_task_export_bundle"
      };
      if (label && reverse[label]) return tr(reverse[label]);
      return graphTaskKindLabel(taskName || label);
    }

    function renderGraphTaskStats(payload) {
      const task = payload.task || {};
      const parts = [];
      if (task.running) parts.push(trf("graph_task_running", {task: graphTaskKindLabel(task.kind)}));
      if (task.pid) parts.push(`PID ${task.pid}`);
      if (!payload.decisions_exists) {
        parts.push(tr("graph_need_analysis_once"));
      } else if (!payload.relations_exists && !task.running) {
        parts.push(tr("graph_can_generate_relationships"));
      }
      $("graphTaskStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
      $("graph_mine_btn").disabled = !!task.running || !payload.decisions_exists;
      $("graph_export_graph_btn").disabled = !!task.running || !payload.relations_exists;
      $("graph_export_bundle_btn").disabled = !!task.running || !payload.relations_exists;
    }

    async function startGraphTask(taskName) {
      if (!graphPathPayload().output_root) {
        return showToast(tr("graph_need_paths"));
      }
      const response = await fetch(`/api/relationships/${taskName.replace("_", "-")}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({...runPayload(), ...graphPathPayload()})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("graph_task_start_failed"));
      showToast(trf("graph_task_started", {task: localGraphTaskLabel(payload.label, taskName)}));
      loadGraph();
    }

    function renderGraphEmptyState() {
      const message = graphEmptyMessage(graphMeta);
      $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
      $("graphEdges").innerHTML = "";
      $("graphClusterTitle").innerHTML = "";
      $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(graphDetailEmptyMessage(graphMeta))}</div>`;
    }

    function graphMatchesFilters(cluster) {
      const minSize = Number($("graph_min_size").value || 2);
      if (Number(cluster.size || 0) < minSize) return false;
      const q = $("graph_q").value.trim().toLowerCase();
      if (!q) return true;
      const haystack = [
        ...(cluster.categories || []),
        ...(cluster.preview_paths || [])
      ].join(" ").toLowerCase();
      return haystack.includes(q);
    }

    function applyGraphFilters(preserveSelection = true) {
      filteredGraphClusters = graphClusters.filter(graphMatchesFilters);
      renderGraphClusterList();
      if (!filteredGraphClusters.length) {
        graphSelectedClusterId = null;
        graphClusterData = null;
        graphSelectedDocPath = "";
        if (graphClusters.length) {
          $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(tr("graph_no_match"))}</div>`;
          $("graphEdges").innerHTML = "";
          $("graphClusterTitle").innerHTML = "";
          $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(graphDetailEmptyMessage(graphMeta))}</div>`;
        } else {
          renderGraphEmptyState();
        }
        return;
      }
      const hasSelection = preserveSelection && filteredGraphClusters.some(item => item.cluster_id === graphSelectedClusterId);
      if (hasSelection) {
        renderGraphClusterList();
        if (graphClusterData && graphClusterData.cluster_id === graphSelectedClusterId) {
          renderGraphCluster();
          return;
        }
      }
      loadGraphCluster(filteredGraphClusters[0].cluster_id, false);
    }

    async function loadGraphCluster(clusterId, preserveDocSelection = true) {
      graphSelectedClusterId = clusterId;
      renderGraphClusterList();
      const query = new URLSearchParams(graphPathPayload());
      query.set("cluster", String(clusterId));
      const response = await fetch("/api/relationships?" + query.toString());
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("graph_cluster_load_failed"));
      graphClusterData = payload.selected_cluster;
      if (!graphClusterData) {
        graphSelectedDocPath = "";
      } else if (!preserveDocSelection || !graphClusterData.files.some(item => item.relative_path === graphSelectedDocPath)) {
        graphSelectedDocPath = graphClusterData.files[0] ? graphClusterData.files[0].relative_path : "";
      }
      renderGraphCluster();
    }

    function renderGraphClusterList() {
      if (!filteredGraphClusters.length) {
        $("graphClusters").innerHTML = `<div class="graph-empty">${escapeHtml(graphEmptyMessage(graphMeta))}</div>`;
        return;
      }
      $("graphClusters").innerHTML = filteredGraphClusters.map(cluster => `
        <button class="graph-cluster-item ${cluster.cluster_id === graphSelectedClusterId ? "active" : ""}" onclick="loadGraphCluster(${cluster.cluster_id}, false)">
          <div class="graph-cluster-title">${tr("cluster")} ${cluster.cluster_id + 1} · ${cluster.size} ${tr("documents_unit")}</div>
          <div class="graph-cluster-preview">${escapeHtml((cluster.categories || []).join(", ") || tr("uncategorized"))}</div>
          <div class="graph-cluster-preview">${escapeHtml((cluster.preview_paths || []).join(" / ") || tr("no_preview_path"))}</div>
        </button>
      `).join("");
    }

    function renderGraphCluster() {
      if (!graphClusterData) {
        $("graphClusterTitle").innerHTML = "";
        $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(graphEmptyMessage(graphMeta))}</div>`;
        $("graphEdges").innerHTML = "";
        $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(graphDetailEmptyMessage(graphMeta))}</div>`;
        return;
      }
      const categories = (graphClusterData.categories || []).join(", ") || tr("uncategorized");
      $("graphClusterTitle").innerHTML = [
        `<span class="pill">${tr("cluster")} ${graphClusterData.cluster_id + 1}</span>`,
        `<span class="pill">${graphClusterData.size} ${tr("documents_unit")}</span>`,
        `<span class="pill">${graphClusterData.edge_count} ${tr("edges_unit")}</span>`,
        `<span class="pill">${escapeHtml(categories)}</span>`
      ].join("");
      renderGraphCanvas();
      renderGraphEdges();
      renderGraphDetail();
    }

    function graphDisplayName(relativePath) {
      const value = String(relativePath || "");
      const parts = value.split(/[\\\\/]/);
      return parts[parts.length - 1] || value;
    }

    function graphShortLabel(relativePath, maxLength = 18) {
      const name = graphDisplayName(relativePath).replace(/\.[^.]+$/, "");
      return name.length <= maxLength ? name : name.slice(0, maxLength - 1) + "…";
    }

    function graphColorForCategory(category) {
      const value = String(category || "Unknown");
      let hash = 0;
      for (const ch of value) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
      return `hsl(${hash}, 68%, 55%)`;
    }

    function graphNodePositionMap(files, selectedPath) {
      const width = 760;
      const height = 460;
      const centerX = width / 2;
      const centerY = height / 2;
      const positions = {};
      const ordered = files.map(item => item.relative_path);
      const anchor = selectedPath && ordered.includes(selectedPath) ? selectedPath : ordered[0];
      if (!anchor) return {width, height, positions};
      positions[anchor] = {x: centerX, y: centerY};
      const others = ordered.filter(path => path !== anchor);
      const radius = Math.min(width, height) * 0.34;
      others.forEach((path, index) => {
        const angle = -Math.PI / 2 + (index * 2 * Math.PI) / Math.max(others.length, 1);
        positions[path] = {
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
        };
      });
      return {width, height, positions};
    }

    function renderGraphCanvas() {
      const files = graphClusterData.files || [];
      if (!files.length) {
        $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(tr("graph_no_docs"))}</div>`;
        return;
      }
      const selectedPath = graphSelectedDocPath || files[0].relative_path;
      const layout = graphNodePositionMap(files, selectedPath);
      const edges = (graphClusterData.edges || []).map(edge => {
        const left = layout.positions[edge.left_path];
        const right = layout.positions[edge.right_path];
        if (!left || !right) return "";
        const active = edge.left_path === selectedPath || edge.right_path === selectedPath;
        const stroke = active ? "#2563eb" : "#94a3b8";
        const opacity = active ? 0.9 : 0.45;
        const width = Math.max(1.5, Number(edge.relation_score || 0) * 3);
        const title = `${edge.left_path} ↔ ${edge.right_path} | score=${edge.relation_score} | ${(edge.signals || []).join(", ")}`;
        return `<line x1="${left.x}" y1="${left.y}" x2="${right.x}" y2="${right.y}" stroke="${stroke}" stroke-width="${width}" opacity="${opacity}"><title>${escapeHtml(title)}</title></line>`;
      }).join("");
      const nodes = files.map(file => {
        const point = layout.positions[file.relative_path];
        const selected = file.relative_path === selectedPath;
        const radius = selected ? 22 : 18;
        const fill = graphColorForCategory(file.category);
        const stroke = selected ? "#172033" : "#ffffff";
        const title = `${file.relative_path} | ${file.category} | q=${file.quality} | ${labelStatus(file.status)}`;
        return `
          <g onclick='selectGraphDoc(${JSON.stringify(file.relative_path)})' style="cursor:pointer">
            <circle cx="${point.x}" cy="${point.y}" r="${radius}" fill="${fill}" stroke="${stroke}" stroke-width="${selected ? 3 : 2}"><title>${escapeHtml(title)}</title></circle>
            <text x="${point.x}" y="${point.y + radius + 16}" text-anchor="middle" font-size="11" fill="#172033">${escapeHtml(graphShortLabel(file.relative_path))}</text>
          </g>
        `;
      }).join("");
      $("graphCanvas").innerHTML = `<svg class="graph-svg" viewBox="0 0 ${layout.width} ${layout.height}" preserveAspectRatio="xMidYMid meet">${edges}${nodes}</svg>`;
    }

    function selectGraphDoc(relativePath) {
      graphSelectedDocPath = relativePath;
      renderGraphCanvas();
      renderGraphEdges();
      renderGraphDetail();
    }

    function renderGraphEdges() {
      if (!graphClusterData) {
        $("graphEdges").innerHTML = "";
        return;
      }
      const selectedPath = graphSelectedDocPath;
      let edges = graphClusterData.edges || [];
      if (selectedPath) {
        edges = edges.filter(edge => edge.left_path === selectedPath || edge.right_path === selectedPath);
      }
      edges = [...edges].sort((a, b) => Number(b.relation_score || 0) - Number(a.relation_score || 0)).slice(0, 18);
      if (!edges.length) {
        $("graphEdges").innerHTML = `<div class="graph-empty">${escapeHtml(tr("graph_no_edges"))}</div>`;
        return;
      }
      $("graphEdges").innerHTML = edges.map(edge => {
        const title = `${graphDisplayName(edge.left_path)} ↔ ${graphDisplayName(edge.right_path)}`;
        const signals = (edge.signals || []).join(", ") || tr("no_explicit_signal");
        return `
          <div class="graph-edge-item">
            <div class="graph-cluster-title">${escapeHtml(title)}</div>
            <div class="muted">score ${edge.relation_score} · ${escapeHtml(signals)}</div>
          </div>
        `;
      }).join("");
    }

    function graphNeighborPath(edge, relativePath) {
      return edge.left_path === relativePath ? edge.right_path : edge.left_path;
    }

    function graphEmptyMessage(payload) {
      const task = (payload && payload.task) || {};
      if (task.running) return trf("graph_task_running_refresh", {task: graphTaskKindLabel(task.kind)});
      if (payload && !payload.decisions_exists) return tr("graph_need_analysis_before_graph");
      if (payload && payload.decisions_exists && !payload.relations_exists) return tr("graph_no_relationships_generate");
      return tr("empty_graph");
    }

    function graphDetailEmptyMessage(payload) {
      const task = (payload && payload.task) || {};
      if (task.running) return tr("graph_task_running_detail");
      if (payload && payload.decisions_exists && !payload.relations_exists) return tr("graph_generate_then_detail");
      return tr("graph_select_cluster");
    }

    async function graphMarkDoc(relativePath, status) {
      await markDoc(relativePath, status);
      if (graphSelectedClusterId !== null) {
        await loadGraphCluster(graphSelectedClusterId, true);
      }
    }

    function renderGraphDetail() {
      if (!graphClusterData || !graphClusterData.files || !graphClusterData.files.length) {
        $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(tr("graph_select_cluster"))}</div>`;
        return;
      }
      const selected = graphClusterData.files.find(item => item.relative_path === graphSelectedDocPath) || graphClusterData.files[0];
      graphSelectedDocPath = selected.relative_path;
      const relatedEdges = (graphClusterData.edges || [])
        .filter(edge => edge.left_path === selected.relative_path || edge.right_path === selected.relative_path)
        .sort((a, b) => Number(b.relation_score || 0) - Number(a.relation_score || 0));
      $("graphDocDetail").innerHTML = `
        <div class="graph-detail-card">
          <div class="graph-cluster-title">${escapeHtml(graphDisplayName(selected.relative_path))}</div>
          <div class="muted">${escapeHtml(selected.relative_path)}</div>
          <div class="stats">
            <span class="pill">${escapeHtml(labelStatus(selected.status))}</span>
            <span class="pill">q ${selected.quality}</span>
            <span class="pill">${escapeHtml(selected.category)}</span>
            <span class="pill">${escapeHtml(selected.document_kind || "Unknown")}</span>
          </div>
          <div class="stats">
            <span class="pill">${tr("sensitive")} ${selected.sensitivity_risk}</span>
            <span class="pill">${tr("public_label")} ${selected.public_writing_suitability}</span>
          </div>
          <p class="muted">${escapeHtml(selected.summary || tr("no_summary"))}</p>
          <div class="graph-actions">
            <button ${capabilities.open_file === false ? "disabled" : ""} onclick='openDoc(${JSON.stringify(selected.relative_path)})'>${tr("open")}</button>
            <button ${capabilities.reveal_file === false ? "disabled" : ""} onclick='revealDoc(${JSON.stringify(selected.relative_path)})'>${tr("reveal")}</button>
            <button onclick='graphMarkDoc(${JSON.stringify(selected.relative_path)}, "reading")'>${tr("mark_reading")}</button>
            <button onclick='graphMarkDoc(${JSON.stringify(selected.relative_path)}, "read")'>${tr("mark_read")}</button>
            <button onclick='graphMarkDoc(${JSON.stringify(selected.relative_path)}, "deferred")'>${tr("mark_deferred")}</button>
          </div>
        </div>
        <div class="graph-detail-card">
          <div class="graph-cluster-title">${tr("related_documents")}</div>
          ${relatedEdges.length ? relatedEdges.map(edge => {
            const neighbor = graphNeighborPath(edge, selected.relative_path);
            return `
              <div style="display:grid; gap:4px; margin-top:8px;">
                <button class="graph-cluster-item" style="padding:8px;" onclick='selectGraphDoc(${JSON.stringify(neighbor)})'>
                  <div class="graph-cluster-title">${escapeHtml(graphDisplayName(neighbor))}</div>
                  <div class="muted">score ${edge.relation_score} · ${escapeHtml((edge.signals || []).join(", ") || tr("no_explicit_signal"))}</div>
                </button>
              </div>
            `;
          }).join("") : `<div class="muted" style="margin-top:8px;">${escapeHtml(tr("no_related_edges"))}</div>`}
        </div>
      `;
    }

    function applyClientFilters() {
      filteredRows = sortRowsClient(allRows.filter(rowMatchesFilters), sortKey);
      const pageCount = pageCountFor(filteredRows.length);
      currentPage = Math.min(Math.max(currentPage, 1), pageCount);
      renderStatsFromRows(filteredRows, allRows.length);
      renderPager();
      renderSortMarks();
      renderPageRows();
    }

    function renderPageRows() {
      const start = (currentPage - 1) * pageSize;
      currentRows = filteredRows.slice(start, start + pageSize);
      renderRows(currentRows);
    }

    function renderStatsFromRows(rows, totalCount) {
      const counts = countStatus(rows);
      const parts = [`${tr("match_prefix")} ${rows.length} / ${tr("all_prefix")} ${totalCount}`];
      for (const key of ["failed","unread","reading","read","reread_needed","skipped","deferred"]) {
        if (counts[key]) parts.push(`${labelStatus(key)} ${counts[key]}`);
      }
      $("stats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
    }

    function renderPager() {
      const pageCount = pageCountFor(filteredRows.length);
      const start = filteredRows.length ? ((currentPage - 1) * pageSize + 1) : 0;
      const end = Math.min(currentPage * pageSize, filteredRows.length);
      const html = `
        <span class="muted">${start}-${end} / ${filteredRows.length}</span>
        <button onclick="setPage(1)" ${currentPage <= 1 ? "disabled" : ""}>${tr("first_page")}</button>
        <button onclick="setPage(${currentPage - 1})" ${currentPage <= 1 ? "disabled" : ""}>${tr("previous_page")}</button>
        <span>${tr("page_label")} <input value="${currentPage}" onchange="setPage(Number(this.value))" /> / ${pageCount} ${tr("page_suffix")}</span>
        <button onclick="setPage(${currentPage + 1})" ${currentPage >= pageCount ? "disabled" : ""}>${tr("next_page")}</button>
        <button onclick="setPage(${pageCount})" ${currentPage >= pageCount ? "disabled" : ""}>${tr("last_page")}</button>
        <label style="display:inline-flex; align-items:center; gap:4px;">${tr("page_size_label")} <input value="${pageSize}" min="1" onchange="setPageSize(Number(this.value))" /></label>`;
      $("pagerTop").innerHTML = html;
      $("pagerBottom").innerHTML = html;
    }

    function rowMatchesFilters(row) {
      const status = $("status").value;
      if (status && row.status !== status) return false;
      const q = $("q").value.trim().toLowerCase();
      if (readingScope === "source" || row.source_only || row.status === "failed") {
        return !q || rowMatchesSearch(row, q);
      }
      const minQuality = Number($("min_quality").value || 0);
      if (Number(row.quality || 0) < minQuality) return false;
      const maxSensitivity = $("max_sensitivity_risk").value.trim();
      if (maxSensitivity && Number(row.sensitivity_risk || 0) > Number(maxSensitivity)) return false;
      const minPublic = $("min_public_writing_suitability").value.trim();
      if (minPublic && Number(row.public_writing_suitability || 0) < Number(minPublic)) return false;

      const selectedCategories = selectedValues("categories");
      if (selectedCategories.length && selectedCategories.length < $("categories").options.length && !selectedCategories.includes(row.category)) return false;

      const selectedTags = selectedValues("topic_tags");
      if (selectedTags.length && selectedTags.length < $("topic_tags").options.length) {
        const rowTags = row.topic_tags || [];
        if (!selectedTags.some(tag => rowTags.includes(tag))) return false;
      }

      if (q && !rowMatchesSearch(row, q)) return false;
      return true;
    }

    function rowMatchesSearch(row, q) {
      const haystack = [
        row.relative_path || "",
        row.source_path || "",
        row.category || "",
        row.document_kind || "",
        row.summary || "",
        row.reason || "",
        row.failure_stage || "",
        row.failure_reason || "",
        row.failure_error || "",
        (row.topic_tags || []).join(" "),
        row.note || ""
      ].join(" ").toLowerCase();
      return haystack.includes(q);
    }

    function exportFilteredRows(format) {
      const rows = filteredRows || [];
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      const extension = format === "jsonl" ? "jsonl" : "csv";
      const filename = `doctriage-${readingScope}-${timestamp}.${extension}`;
      const content = format === "jsonl" ? rowsToJsonl(rows) : rowsToCsv(rows);
      const mime = format === "jsonl" ? "application/x-ndjson;charset=utf-8" : "text/csv;charset=utf-8";
      downloadText(filename, content, mime);
      showToast(`${tr("exported_rows")} ${rows.length}`);
    }

    function exportRow(row) {
      return {
        relative_path: row.relative_path || "",
        source_path: row.source_path || "",
        status: row.status || "",
        quality: row.quality ?? "",
        category: row.category || "",
        document_kind: row.document_kind || "",
        topic_tags: (row.topic_tags || []).join(", "),
        sensitivity_risk: row.sensitivity_risk ?? "",
        public_writing_suitability: row.public_writing_suitability ?? "",
        source_mtime: row.source_mtime || "",
        source_size_bytes: row.source_size_bytes ?? "",
        summary: row.summary || "",
        reason: row.reason || "",
        knowledge_density: row.knowledge_density ?? "",
        implementation_specificity: row.implementation_specificity ?? "",
        logical_structure: row.logical_structure ?? "",
        evidence_richness: row.evidence_richness ?? "",
        actionability: row.actionability ?? "",
        strategic_value: row.strategic_value ?? "",
        freshness: row.freshness ?? "",
        uniqueness: row.uniqueness ?? "",
        note: row.note || "",
        attempts: row.attempts ?? "",
        failure_stage: row.failure_stage || "",
        failure_reason: row.failure_reason || "",
        failure_error: row.failure_error || ""
      };
    }

    function rowsToJsonl(rows) {
      return rows.map(row => JSON.stringify(exportRow(row))).join("\n") + (rows.length ? "\n" : "");
    }

    function rowsToCsv(rows) {
      const headers = [
        "relative_path",
        "source_path",
        "status",
        "quality",
        "category",
        "document_kind",
        "topic_tags",
        "sensitivity_risk",
        "public_writing_suitability",
        "source_mtime",
        "source_size_bytes",
        "summary",
        "reason",
        "knowledge_density",
        "implementation_specificity",
        "logical_structure",
        "evidence_richness",
        "actionability",
        "strategic_value",
        "freshness",
        "uniqueness",
        "note",
        "attempts",
        "failure_stage",
        "failure_reason",
        "failure_error"
      ];
      const lines = [headers.join(",")];
      for (const row of rows) {
        const item = exportRow(row);
        lines.push(headers.map(header => csvCell(item[header])).join(","));
      }
      return lines.join("\n") + "\n";
    }

    function csvCell(value) {
      const text = String(value ?? "");
      return `"${text.replace(/"/g, '""')}"`;
    }

    function downloadText(filename, content, mime) {
      const blob = new Blob([content], {type: mime});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    function populateFacetOptions(rows) {
      const categories = Array.from(new Set(rows.map(row => row.category).filter(Boolean))).sort();
      const tags = Array.from(new Set(rows.flatMap(row => row.topic_tags || []).filter(Boolean))).sort();
      populateMultiSelect("categories", categories);
      populateMultiSelect("topic_tags", tags);
    }

    function populateMultiSelect(id, values) {
      const select = $(id);
      const selected = new Set(selectedValues(id));
      select.innerHTML = values.map(value =>
        `<option value="${escapeAttrValue(value)}" ${selected.has(value) ? "selected" : ""}>${escapeHtml(value)}</option>`
      ).join("");
    }

    function selectedValues(id) {
      return Array.from($(id).selectedOptions || []).map(option => option.value);
    }

    function selectMulti(id, checked) {
      Array.from($(id).options).forEach(option => option.selected = checked);
      currentPage = 1;
      applyClientFilters();
    }

    function invertMulti(id) {
      Array.from($(id).options).forEach(option => option.selected = !option.selected);
      currentPage = 1;
      applyClientFilters();
    }

    function countStatus(rows) {
      const counts = {};
      rows.forEach(row => counts[row.status] = (counts[row.status] || 0) + 1);
      return counts;
    }

    function setSort(field) {
      const next = {
        quality: sortKey === "quality_desc" ? "quality_asc" : "quality_desc",
        path: sortKey === "source_path_asc" || sortKey === "path_asc" ? "source_path_desc" : "source_path_asc",
        source_mtime: sortKey === "source_mtime_desc" ? "source_mtime_asc" : "source_mtime_desc",
        category: sortKey === "category_asc" ? "category_desc" : "category_asc",
        status: sortKey === "status_asc" ? "status_desc" : "status_asc",
        document_kind: sortKey === "kind_asc" ? "kind_desc" : "kind_asc",
        sensitivity: sortKey === "sensitivity_asc" ? "sensitivity_desc" : "sensitivity_asc",
        public: sortKey === "public_desc" ? "public_asc" : "public_desc"
      };
      sortKey = next[field] || defaultSortForScope(readingScope);
      localStorage.setItem(sortStorageKey(readingScope), sortKey);
      currentPage = 1;
      applyClientFilters();
    }

    function sortRowsClient(rows, key) {
      const sorted = [...rows];
      const text = value => String(value || "").toLowerCase();
      const num = value => Number(value || 0);
      const sourcePath = row => text(row.source_path || row.relative_path);
      const sourceMtime = row => Number(row.source_mtime_epoch || 0);
      const comparators = {
        quality_desc: (a, b) => num(b.quality) - num(a.quality) || text(a.relative_path).localeCompare(text(b.relative_path)),
        quality_asc: (a, b) => num(a.quality) - num(b.quality) || text(a.relative_path).localeCompare(text(b.relative_path)),
        path_asc: (a, b) => sourcePath(a).localeCompare(sourcePath(b)),
        path_desc: (a, b) => sourcePath(b).localeCompare(sourcePath(a)),
        source_path_asc: (a, b) => sourcePath(a).localeCompare(sourcePath(b)),
        source_path_desc: (a, b) => sourcePath(b).localeCompare(sourcePath(a)),
        source_mtime_desc: (a, b) => sourceMtime(b) - sourceMtime(a) || sourcePath(a).localeCompare(sourcePath(b)),
        source_mtime_asc: (a, b) => sourceMtime(a) - sourceMtime(b) || sourcePath(a).localeCompare(sourcePath(b)),
        category_asc: (a, b) => text(a.category).localeCompare(text(b.category)) || num(b.quality) - num(a.quality),
        category_desc: (a, b) => text(b.category).localeCompare(text(a.category)) || num(b.quality) - num(a.quality),
        status_asc: (a, b) => text(a.status).localeCompare(text(b.status)) || num(b.quality) - num(a.quality),
        status_desc: (a, b) => text(b.status).localeCompare(text(a.status)) || num(b.quality) - num(a.quality),
        kind_asc: (a, b) => text(a.document_kind).localeCompare(text(b.document_kind)) || num(b.quality) - num(a.quality),
        kind_desc: (a, b) => text(b.document_kind).localeCompare(text(a.document_kind)) || num(b.quality) - num(a.quality),
        sensitivity_asc: (a, b) => num(a.sensitivity_risk) - num(b.sensitivity_risk) || num(b.quality) - num(a.quality),
        sensitivity_desc: (a, b) => num(b.sensitivity_risk) - num(a.sensitivity_risk) || num(b.quality) - num(a.quality),
        public_desc: (a, b) => num(b.public_writing_suitability) - num(a.public_writing_suitability) || num(b.quality) - num(a.quality),
        public_asc: (a, b) => num(a.public_writing_suitability) - num(b.public_writing_suitability) || num(b.quality) - num(a.quality)
      };
      sorted.sort(comparators[key] || comparators.quality_desc);
      return sorted;
    }

    function renderSortMarks() {
      document.querySelectorAll("[data-sort-mark]").forEach(item => item.textContent = "");
      const map = {
        quality_desc: ["quality", "↓"],
        quality_asc: ["quality", "↑"],
        path_asc: ["path", "↑"],
        path_desc: ["path", "↓"],
        source_path_asc: ["path", "↑"],
        source_path_desc: ["path", "↓"],
        source_mtime_desc: ["source_mtime", "↓"],
        source_mtime_asc: ["source_mtime", "↑"],
        category_asc: ["category", "↑"],
        category_desc: ["category", "↓"],
        status_asc: ["status", "↑"],
        status_desc: ["status", "↓"],
        kind_asc: ["document_kind", "↑"],
        kind_desc: ["document_kind", "↓"],
        sensitivity_asc: ["sensitivity", "↑"],
        sensitivity_desc: ["sensitivity", "↓"],
        public_desc: ["sensitivity", tr("sort_public_desc")],
        public_asc: ["sensitivity", tr("sort_public_asc")]
      };
      const mark = map[sortKey];
      if (!mark) return;
      const target = document.querySelector(`[data-sort-mark="${mark[0]}"]`);
      if (target) target.textContent = mark[1];
    }

    function pageCountFor(total) {
      return Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
    }

    function setPage(page) {
      if (!Number.isFinite(page)) return;
      currentPage = Math.min(Math.max(Math.floor(page), 1), pageCountFor(filteredRows.length));
      renderPager();
      renderPageRows();
    }

    function setPageSize(value) {
      if (!Number.isFinite(value) || value < 1) return;
      pageSize = Math.max(1, Math.floor(value));
      localStorage.setItem("doctriage_page_size", String(pageSize));
      currentPage = 1;
      renderPager();
      renderPageRows();
    }

    function rowExplanation(row) {
      const parts = [];
      const summary = String(row.summary || "").trim();
      const reason = String(row.reason || "").trim();
      if (summary) parts.push(`${tr("explain_summary")}: ${summary}`);
      if (reason) parts.push(`${tr("explain_reason")}: ${reason}`);
      const dimensions = EXPLANATION_DIMENSIONS
        .map(([field, labelKey]) => {
          const value = Number(row[field]);
          if (!Number.isFinite(value) || value <= 0) return "";
          return `${tr(labelKey)} ${value}`;
        })
        .filter(Boolean);
      if (dimensions.length) parts.push(`${tr("explain_dimensions")}: ${dimensions.join(" / ")}`);
      if (row.failure) {
        const failureParts = [];
        if (row.failure_stage) failureParts.push(`${tr("explain_failure_stage")} ${row.failure_stage}`);
        if (row.failure_reason) failureParts.push(`${tr("explain_failure_reason")} ${row.failure_reason}`);
        if (row.attempts) failureParts.push(`${tr("explain_failure_attempts")} ${row.attempts}`);
        if (row.failure_error && row.failure_error !== summary) {
          failureParts.push(`${tr("explain_failure_error")} ${row.failure_error}`);
        }
        if (failureParts.length) parts.push(`${tr("explain_failure")}: ${failureParts.join(" / ")}`);
      }
      return parts.join("\n");
    }

    function renderRows(rows) {
      $("rows").innerHTML = rows.map(row => {
        const explanation = rowExplanation(row);
        return `
        <tr>
          <td>${isPureFailureRow(row) ? "" : `<input type="checkbox" class="rowcheck" value="${escapeHtml(row.relative_path)}" />`}</td>
          <td class="status-${escapeAttr(row.status)}">${labelStatus(row.status)}</td>
          <td>${formatQuality(row)}</td>
          <td>${escapeHtml(displayCategory(row))}</td>
          <td>${escapeHtml(displayKind(row))}</td>
          <td>${formatSensitivityPublic(row)}</td>
          <td class="name">
            <span class="doc-name ${explanation ? "has-summary" : ""}" tabindex="${explanation ? "0" : "-1"}" data-tip="${escapeAttrValue(explanation)}">${escapeHtml(row.relative_path || "")}</span>
            ${row.source_path ? `<span class="doc-path">${escapeHtml(row.source_path)}</span>` : ""}
            ${row.note ? `<br><span class="muted">${escapeHtml(row.note)}</span>` : ""}
          </td>
          <td>${escapeHtml(row.source_mtime_label || "")}${row.source_size_label ? `<br><span class="muted">${escapeHtml(row.source_size_label)}</span>` : ""}</td>
          <td>${escapeHtml((row.topic_tags || []).join(", "))}</td>
          <td class="actions">${renderRowActions(row)}</td>
        </tr>`;
      }).join("");
      bindSummaryTooltips();
    }

    function isPureFailureRow(row) {
      return row.failure && !row.source_scope;
    }

    function formatQuality(row) {
      return Number.isFinite(Number(row.quality)) && row.quality !== null && row.quality !== undefined ? escapeHtml(row.quality) : "—";
    }

    function displayCategory(row) {
      if (row.category) return row.category;
      return row.source_only ? tr("scope_source_unscored") : "";
    }

    function displayKind(row) {
      if (row.document_kind && row.document_kind !== "Unscored") return row.document_kind;
      return row.source_only ? tr("scope_source_unscored") : (row.document_kind || "");
    }

    function formatSensitivityPublic(row) {
      if (row.failure && !row.source_scope) return "—";
      if (row.sensitivity_risk === null || row.sensitivity_risk === undefined || row.public_writing_suitability === null || row.public_writing_suitability === undefined) return "—";
      return `${row.sensitivity_risk} / ${row.public_writing_suitability}`;
    }

    function renderRowActions(row) {
      if (isPureFailureRow(row)) {
        const missing = row.exists === false;
        const missingTitle = missing ? ` title='${escapeAttrValue(tr("missing_source_title"))}'` : "";
        return `
          <button ${missing || capabilities.open_file === false ? `disabled${missingTitle || ` title='${escapeAttrValue(tr("disabled_open_title"))}'`}` : ""} onclick='openFailure(${JSON.stringify(row.source_path)})'>${tr("open")}</button>
          <button ${missing || capabilities.reveal_file === false ? `disabled${missingTitle || ` title='${escapeAttrValue(tr("disabled_reveal_title"))}'`}` : ""} onclick='revealFailure(${JSON.stringify(row.source_path)})'>${tr("reveal")}</button>
        `;
      }
      const missing = row.exists === false;
      const missingTitle = missing ? ` title='${escapeAttrValue(tr("missing_source_title"))}'` : "";
      return `
        <button ${missing || capabilities.open_file === false ? `disabled${missingTitle || ` title='${escapeAttrValue(tr("disabled_open_title"))}'`}` : ""} onclick='openDoc(${JSON.stringify(row.relative_path)})'>${tr("open")}</button>
        <button ${missing || capabilities.reveal_file === false ? `disabled${missingTitle || ` title='${escapeAttrValue(tr("disabled_reveal_title"))}'`}` : ""} onclick='revealDoc(${JSON.stringify(row.relative_path)})'>${tr("reveal")}</button>
        <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "reading")'>${tr("mark_reading")}</button>
        <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "read")'>${tr("mark_read")}</button>
        <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "deferred")'>${tr("mark_deferred")}</button>
        <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "skipped")'>${tr("mark_skipped")}</button>
        <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "unread")'>${tr("mark_unread")}</button>
      `;
    }

    async function markDoc(relativePath, status) {
      const note = status === "read" ? "" : "";
      const response = await fetch("/api/mark", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({relative_path: relativePath, status, note, ...readingPathPayload()})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("mark_failed"));
      showToast(trf("marked_status", {status: labelStatus(status)}));
      loadRows();
    }

    function selectedPaths() {
      return Array.from(document.querySelectorAll(".rowcheck:checked")).map(item => item.value);
    }

    function toggleAllRows(checked) {
      document.querySelectorAll(".rowcheck").forEach(item => item.checked = checked);
    }

    async function bulkMark(status) {
      const paths = selectedPaths();
      if (!paths.length) return showToast(tr("select_documents_first"));
      const response = await fetch("/api/mark-batch", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({relative_paths: paths, status, ...readingPathPayload()})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || tr("bulk_mark_failed"));
      showToast(trf("bulk_marked", {count: payload.count || 0}));
      loadRows();
    }

    function openNextVisible() {
      const row = currentRows.find(item => item.status === "unread" || item.status === "reread_needed") || currentRows[0];
      if (!row) return showToast(tr("current_list_empty"));
      openDoc(row.relative_path);
    }

    async function openDoc(relativePath) {
      await postAction("/api/open", relativePath, tr("requested_open"));
    }

    async function revealDoc(relativePath) {
      await postAction("/api/reveal", relativePath, tr("requested_reveal"));
    }

    async function openFailure(sourcePath) {
      await postSourceAction("/api/open-failure", sourcePath, tr("requested_open"));
    }

    async function revealFailure(sourcePath) {
      await postSourceAction("/api/reveal-failure", sourcePath, tr("requested_reveal"));
    }

    async function postAction(url, relativePath, okText) {
      const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({relative_path: relativePath, ...readingPathPayload()})
      });
      const payload = await response.json();
      showToast(response.ok ? okText : (payload.error || tr("operation_failed")));
    }

    async function postSourceAction(url, sourcePath, okText) {
      const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({source_path: sourcePath, ...readingPathPayload()})
      });
      const payload = await response.json();
      showToast(response.ok ? okText : (payload.error || tr("operation_failed")));
    }

    function labelStatus(status) {
      return {
        unread: tr("status_unread"),
        reading: tr("status_reading"),
        read: tr("status_read"),
        reread_needed: tr("status_reread_needed"),
        failed: tr("status_failed"),
        skipped: tr("status_skipped"),
        deferred: tr("status_deferred")
      }[status] || status;
    }

    function showToast(text) {
      const toast = $("toast");
      toast.textContent = text;
      toast.style.display = "block";
      setTimeout(() => toast.style.display = "none", 2600);
    }

    function hideHelpTooltip() {
      tooltipTarget = null;
      $("tooltip").style.display = "none";
    }

    function positionHelpTooltip(target) {
      const tooltip = $("tooltip");
      const tip = target && target.dataset ? String(target.dataset.tip || "") : "";
      if (!tip) {
        hideHelpTooltip();
        return;
      }
      tooltip.textContent = tip;
      tooltip.style.display = "block";
      tooltip.style.visibility = "hidden";
      const margin = 12;
      tooltip.style.maxWidth = Math.min(320, Math.max(180, window.innerWidth - margin * 2)) + "px";
      const targetRect = target.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();
      const left = Math.min(
        Math.max(margin, targetRect.left + targetRect.width / 2 - tooltipRect.width / 2),
        window.innerWidth - tooltipRect.width - margin
      );
      const top = Math.max(margin, targetRect.top - tooltipRect.height - 10);
      tooltip.style.left = left + "px";
      tooltip.style.top = top + "px";
      tooltip.style.visibility = "visible";
    }

    function showHelpTooltip(target) {
      tooltipTarget = target;
      positionHelpTooltip(target);
    }

    function refreshHelpTooltip() {
      if (tooltipTarget) positionHelpTooltip(tooltipTarget);
    }

    function bindSummaryTooltips(root = document) {
      root.querySelectorAll("[data-tip]").forEach(item => {
        if (item.dataset.tooltipBound === "1") return;
        item.dataset.tooltipBound = "1";
        item.addEventListener("mouseenter", () => showHelpTooltip(item));
        item.addEventListener("mouseleave", hideHelpTooltip);
        item.addEventListener("focus", () => showHelpTooltip(item));
        item.addEventListener("blur", hideHelpTooltip);
      });
    }

    function initHelpTooltips() {
      bindSummaryTooltips();
      window.addEventListener("scroll", hideHelpTooltip, true);
      window.addEventListener("resize", refreshHelpTooltip);
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }

    function escapeAttr(value) {
      return String(value ?? "").replace(/[^a-zA-Z0-9_-]/g, "_");
    }

    function escapeAttrValue(value) {
      return escapeHtml(value);
    }

    function initReadingControls() {
      const scopeSelect = $("reading_scope");
      if (scopeSelect) {
        scopeSelect.value = readingScope;
        scopeSelect.addEventListener("change", () => {
          const previousScope = readingScope;
          readingScope = scopeSelect.value || "analysis";
          localStorage.setItem("doctriage_reading_scope", readingScope);
          sortKey = localStorage.getItem(sortStorageKey(readingScope)) || defaultSortForScope(readingScope);
          currentPage = 1;
          loadRows();
        });
      }
      for (const id of ["status","min_quality","q","max_sensitivity_risk","min_public_writing_suitability","categories","topic_tags"]) {
        const element = $(id);
        if (!element) continue;
        element.addEventListener("change", () => {
          currentPage = 1;
          applyClientFilters();
        });
      }
      $("q").addEventListener("input", () => {
        currentPage = 1;
        applyClientFilters();
      });
    }

    function initGraphControls() {
      for (const id of ["graph_q", "graph_min_size"]) {
        const element = $(id);
        if (!element) continue;
        const eventName = id === "graph_q" ? "input" : "change";
        element.addEventListener(eventName, () => applyGraphFilters(true));
      }
    }

    initReadingControls();
    initGraphControls();
    initRunFormPersistence();
    initReadingTargetPersistence();
    initGraphTargetPersistence();
    initHelpTooltips();
    applyStoredRunFormState();
    const readingApplied = applyStoredReadingTargetState();
    const graphApplied = applyStoredGraphTargetState();
    if (!readingApplied) syncReadingTargetFromRunOutput({force: true, syncGraph: !graphApplied});
    if (!graphApplied) syncGraphTargetFromReadingOutput({force: true});
    clearGraphState("empty_graph");
    applyI18n();
    loadConfig();
    switchTab(localStorage.getItem("doctriage_tab") || "analysis");
    setInterval(() => {
      if ($("section-analysis").classList.contains("active")) loadAnalysis();
    }, 3000);
  </script>
</body>
</html>
"""


def build_state_payload(paths: ReadingPaths, query: dict[str, str]) -> dict[str, Any]:
    scope = normalize_reading_scope(query.get("scope"))
    try:
        decisions = load_latest_decisions(paths.decisions_path)
    except FileNotFoundError:
        decisions = {}
    events = load_latest_reading_events(paths.reading_status_path)
    reading_rows = decorate_reading_rows(build_reading_rows(decisions, events))
    failure_rows = build_failure_rows(paths)
    if scope == "source":
        rows = build_source_file_rows(paths, decisions, events, reading_rows, failure_rows)
    else:
        rows = reading_rows + failure_rows
    status_counts = count_by(rows, "status")
    if scope == "source":
        filtered = filter_source_scope_rows(rows, status=query.get("status") or None)
    else:
        filtered = filter_rows(
            reading_rows,
            status=query.get("status") or None,
            min_quality=parse_int(query.get("min_quality"), 0),
            categories=parse_categories(query.get("categories")),
            max_sensitivity_risk=parse_optional_int(query.get("max_sensitivity_risk")),
            min_public_writing_suitability=parse_optional_int(
                query.get("min_public_writing_suitability")
            ),
        )
        if not query.get("status") or query.get("status") == "failed":
            filtered.extend(failure_rows)
    q = (query.get("q") or "").strip().lower()
    if q:
        filtered = [row for row in filtered if row_matches_query(row, q)]
    filtered = sort_rows(filtered, query.get("sort") or default_sort_for_scope(scope))

    filtered_count = len(filtered)
    page_size = parse_optional_int(query.get("page_size") or query.get("limit"))
    page = max(1, parse_int(query.get("page"), 1))
    limit = parse_optional_int(query.get("limit"))
    if limit is not None:
        filtered = filtered[:limit]

    return {
        "scope": scope,
        "total_count": len(rows),
        "filtered_count": filtered_count,
        "status_counts": status_counts,
        "available_categories": sorted(
            {str(row.get("category") or "") for row in rows if row.get("category")}
        ),
        "available_topic_tags": sorted(
            {
                str(tag)
                for row in rows
                for tag in (row.get("topic_tags") or [])
                if tag
            }
        ),
        "page": page,
        "page_size": page_size,
        "rows": filtered,
    }


def normalize_reading_scope(value: str | None) -> str:
    return "source" if value == "source" else "analysis"


def default_sort_for_scope(scope: str) -> str:
    return "source_path_asc" if scope == "source" else "quality_desc"


def decorate_reading_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [decorate_analysis_row(row) for row in rows]


def decorate_analysis_row(row: dict[str, Any]) -> dict[str, Any]:
    decorated = dict(row)
    source_path = Path(str(decorated.get("source_path") or ""))
    metadata = source_metadata_for_row(source_path, decorated)
    decorated.update(metadata)
    decorated["analyzed"] = True
    decorated["source_only"] = False
    decorated["failure"] = False
    decorated["exists"] = bool(metadata.get("exists"))
    return decorated


def build_source_file_rows(
    paths: ReadingPaths,
    decisions: dict[str, dict[str, Any]],
    events: dict[str, dict[str, Any]],
    reading_rows: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_relative: dict[str, dict[str, Any]] = {}
    reading_by_relative: dict[str, dict[str, Any]] = {
        str(row.get("relative_path") or ""): dict(row)
        for row in reading_rows
        if row.get("relative_path")
    }
    failures_by_relative = {
        str(row.get("relative_path") or ""): row
        for row in failure_rows
        if row.get("relative_path")
    }

    for source_path in iter_supported_source_files(paths.source_dir):
        relative_path = source_relative_path(paths, source_path)
        if not relative_path:
            continue
        row = reading_by_relative.get(relative_path)
        if row is None:
            row = build_source_only_row(paths, source_path, relative_path, events)
        else:
            row = dict(row)
            row.update(source_metadata_for_row(source_path, row))
        failure_row = failures_by_relative.pop(relative_path, None)
        if failure_row:
            row = merge_failure_into_source_row(row, failure_row)
        row["source_scope"] = True
        rows_by_relative[relative_path] = row

    for relative_path, row in failures_by_relative.items():
        source_text = str(row.get("source_path") or "")
        source_path = Path(source_text) if source_text else None
        if source_path is None or not source_path.exists():
            continue
        source_relative = source_relative_path(paths, source_path)
        if not source_relative:
            continue
        source_row = build_source_only_row(paths, source_path, source_relative, events)
        source_row = merge_failure_into_source_row(source_row, row)
        source_row["source_scope"] = True
        rows_by_relative[source_relative] = source_row

    return list(rows_by_relative.values())


def iter_supported_source_files(source_dir: Path) -> list[Path]:
    try:
        cache_key = source_dir.expanduser().resolve()
    except OSError:
        return []
    now = time.monotonic()
    with _SOURCE_FILE_SCAN_CACHE_LOCK:
        cached = _SOURCE_FILE_SCAN_CACHE.get(cache_key)
        if cached is not None:
            cached_at, cached_files = cached
            if now - cached_at <= SOURCE_FILE_SCAN_CACHE_TTL_SECONDS:
                return list(cached_files)

    extensions = {suffix.lower() for suffix in DEFAULT_SUPPORTED_EXTENSIONS}
    files: list[Path] = []
    try:
        if not cache_key.exists():
            return []
        iterator = cache_key.rglob("*")
        for path in iterator:
            try:
                if path.is_file() and path.suffix.lower() in extensions:
                    files.append(path)
            except OSError:
                continue
    except OSError:
        return files
    with _SOURCE_FILE_SCAN_CACHE_LOCK:
        _SOURCE_FILE_SCAN_CACHE[cache_key] = (now, list(files))
    return files


def clear_source_file_scan_cache(source_dir: Path | None = None) -> None:
    with _SOURCE_FILE_SCAN_CACHE_LOCK:
        if source_dir is None:
            _SOURCE_FILE_SCAN_CACHE.clear()
            return
        try:
            cache_key = source_dir.expanduser().resolve()
        except OSError:
            cache_key = source_dir
        _SOURCE_FILE_SCAN_CACHE.pop(cache_key, None)


def build_source_only_row(
    paths: ReadingPaths,
    source_path: Path,
    relative_path: str,
    events: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    event = events.get(relative_path)
    status = str(event.get("status") if event else "unread")
    if status not in MARKABLE_STATUSES:
        status = "unread"
    metadata = source_metadata_for_row(source_path, {})
    return {
        "relative_path": relative_path,
        "display_name": source_path.name,
        "source_path": str(source_path),
        "target_path": "",
        "status": status,
        "marked_status": status,
        "updated_at": str(event.get("updated_at") if event else ""),
        "quality": None,
        "category": "",
        "document_kind": "Unscored",
        "topic_tags": [],
        "sensitivity_risk": None,
        "public_writing_suitability": None,
        "summary": "",
        "note": str(event.get("note") if event else ""),
        "analyzed": False,
        "source_only": True,
        "failure": False,
        **metadata,
    }


def merge_failure_into_source_row(
    row: dict[str, Any], failure_row: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(row)
    if not merged.get("updated_at"):
        merged["status"] = "failed"
        merged["marked_status"] = "failed"
    merged["failure"] = True
    merged["analysis_failure"] = True
    merged["source_only"] = bool(not merged.get("analyzed"))
    for key in (
        "failure_stage",
        "failure_reason",
        "failure_error",
        "attempts",
        "summary",
        "note",
    ):
        merged[key] = failure_row.get(key)
    merged["category"] = failure_row.get("category") or merged.get("category") or ""
    merged["document_kind"] = (
        failure_row.get("document_kind") or merged.get("document_kind") or ""
    )
    merged["topic_tags"] = failure_row.get("topic_tags") or merged.get("topic_tags") or []
    return merged


def filter_source_scope_rows(
    rows: list[dict[str, Any]], *, status: str | None
) -> list[dict[str, Any]]:
    if not status:
        return list(rows)
    return [row for row in rows if row.get("status") == status]


def source_relative_path(paths: ReadingPaths, source_path: Path) -> str:
    try:
        return source_path.resolve().relative_to(paths.source_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return ""


def source_metadata_for_row(source_path: Path, row: dict[str, Any]) -> dict[str, Any]:
    stat_payload = stat_source_file(source_path)
    source_size_bytes = first_present_int(
        row.get("source_size_bytes"),
        nested_fingerprint_value(row, "size_bytes"),
        stat_payload.get("source_size_bytes"),
    )
    source_mtime_ns = first_present_int(
        row.get("source_mtime_ns"),
        nested_fingerprint_value(row, "mtime_ns"),
        stat_payload.get("source_mtime_ns"),
    )
    source_ctime_ns = first_present_int(
        row.get("source_ctime_ns"),
        nested_fingerprint_value(row, "ctime_ns"),
        stat_payload.get("source_ctime_ns"),
    )
    metadata = {
        **stat_payload,
        "source_size_bytes": source_size_bytes,
        "source_size_label": format_size(source_size_bytes or 0),
        "source_mtime_ns": source_mtime_ns,
        "source_ctime_ns": source_ctime_ns,
        "source_mtime_epoch": ns_to_epoch(source_mtime_ns),
        "source_mtime": ns_to_iso(source_mtime_ns),
        "source_mtime_label": ns_to_local_label(source_mtime_ns),
    }
    if not stat_payload.get("exists") and row.get("source_mtime"):
        metadata["source_mtime"] = str(row.get("source_mtime") or "")
    return metadata


def stat_source_file(source_path: Path) -> dict[str, Any]:
    if not source_path.exists() or source_path.is_dir():
        return {
            "exists": False,
            "source_size_bytes": 0,
            "source_mtime_ns": None,
            "source_ctime_ns": None,
        }
    try:
        stat = source_path.stat()
    except OSError:
        return {
            "exists": False,
            "source_size_bytes": 0,
            "source_mtime_ns": None,
            "source_ctime_ns": None,
        }
    return {
        "exists": True,
        "source_size_bytes": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "source_ctime_ns": stat.st_ctime_ns,
    }


def nested_fingerprint_value(row: dict[str, Any], key: str) -> Any:
    fingerprint = row.get("fingerprint")
    if isinstance(fingerprint, dict):
        return fingerprint.get(key)
    return None


def first_present_int(*values: Any) -> int | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def ns_to_epoch(value: int | None) -> float | None:
    if value is None:
        return None
    return value / 1_000_000_000


def ns_to_iso(value: int | None) -> str:
    epoch = ns_to_epoch(value)
    if epoch is None:
        return ""
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def ns_to_local_label(value: int | None) -> str:
    epoch = ns_to_epoch(value)
    if epoch is None:
        return ""
    return datetime.fromtimestamp(epoch, timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M"
    )


def failed_files_path(paths: ReadingPaths) -> Path:
    return paths.output_root / "_state" / "failed_files.jsonl"


def processed_files_path(paths: ReadingPaths) -> Path:
    return paths.output_root / "_state" / "processed_files.jsonl"


def build_failure_rows(paths: ReadingPaths) -> list[dict[str, Any]]:
    path = failed_files_path(paths)
    if not path.exists():
        return []

    recovered_sources = load_processed_source_keys(processed_files_path(paths))
    rows_by_source: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            source_text = str(record.get("source_path") or "").strip()
            if not source_text:
                continue
            source_path = Path(source_text)
            source_key = source_path_key(source_path)
            if source_key in recovered_sources:
                continue

            row = rows_by_source.get(source_key)
            if row is None:
                row = build_failure_row_base(paths, source_path)
                rows_by_source[source_key] = row
            row["attempts"] = int(row.get("attempts") or 0) + 1
            row["failure_stage"] = str(record.get("stage") or "")
            row["failure_error"] = str(record.get("error") or "")
            row["failure_reason"] = failure_reason_category(row["failure_error"])
            row["category"] = row["failure_reason"]
            row["document_kind"] = row["failure_stage"] or "failure"
            row["topic_tags"] = [
                item
                for item in ("失败", row["failure_stage"], row["failure_reason"])
                if item
            ]
            row["summary"] = row["failure_error"]
            row["note"] = failure_note(row)

    return sorted(
        rows_by_source.values(),
        key=lambda row: (
            str(row.get("failure_reason") or ""),
            str(row.get("failure_stage") or ""),
            str(row.get("relative_path") or ""),
        ),
    )


def load_processed_source_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            source_text = str(record.get("source_path") or "").strip()
            if not source_text:
                continue
            path_obj = Path(source_text)
            keys.add(source_text)
            keys.add(source_path_key(path_obj))
    return keys


def source_path_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def build_failure_row_base(paths: ReadingPaths, source_path: Path) -> dict[str, Any]:
    relative_path = failure_relative_path(paths, source_path)
    exists = source_path.exists()
    is_dir = exists and source_path.is_dir()
    size_bytes = 0
    if exists and not is_dir:
        try:
            size_bytes = source_path.stat().st_size
        except OSError:
            size_bytes = 0
    metadata = source_metadata_for_row(source_path, {})
    return {
        **metadata,
        "relative_path": relative_path,
        "display_name": source_path.name or relative_path,
        "source_path": str(source_path),
        "target_path": "",
        "status": "failed",
        "marked_status": "failed",
        "updated_at": "",
        "quality": 0,
        "category": "失败文件",
        "document_kind": "failure",
        "topic_tags": ["失败"],
        "sensitivity_risk": 0,
        "public_writing_suitability": 0,
        "summary": "",
        "note": "",
        "failure": True,
        "failure_stage": "",
        "failure_reason": "其他",
        "failure_error": "",
        "attempts": 0,
        "exists": exists,
        "is_dir": is_dir,
        "size_bytes": size_bytes,
        "size_label": failure_size_label(exists, is_dir, size_bytes),
    }


def failure_relative_path(paths: ReadingPaths, source_path: Path) -> str:
    try:
        return source_path.resolve().relative_to(paths.source_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return source_path.name or str(source_path)


def failure_size_label(exists: bool, is_dir: bool, size_bytes: int) -> str:
    if not exists:
        return "不存在"
    if is_dir:
        return "目录"
    return format_size(size_bytes)


def format_size(size_bytes: int) -> str:
    value = float(max(0, size_bytes))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def failure_note(row: dict[str, Any]) -> str:
    parts = [
        f"阶段：{row.get('failure_stage') or 'unknown'}",
        f"原因：{row.get('failure_reason') or '其他'}",
        f"尝试：{row.get('attempts') or 0}",
        f"大小：{row.get('size_label') or ''}",
    ]
    error = str(row.get("failure_error") or "").strip()
    if error:
        parts.append(f"错误：{error}")
    return "；".join(parts)


def failure_reason_category(error: str) -> str:
    text = error.lower()
    if "legacy .ppt ingestion requires libreoffice" in text:
        return "旧 PPT 需 LibreOffice"
    if "pdf text fallback produced empty text" in text:
        return "PDF 无文本层/需 OCR"
    if "input document is empty" in text:
        return "空文件"
    if "file format not allowed" in text:
        return "格式不支持/文件异常"
    if "cryptography>=3.1 is required for aes algorithm" in text:
        return "加密 PDF 依赖缺失"
    if "not valid" in text:
        return "Office 文件无效"
    return "其他"


def relationship_dir(paths: ReadingPaths) -> Path:
    return paths.output_root / "_relationships"


def relationship_clusters_path(paths: ReadingPaths) -> Path:
    return relationship_dir(paths) / "clusters.json"


def relationship_relations_path(paths: ReadingPaths) -> Path:
    return relationship_dir(paths) / "relations.jsonl"


def coerce_int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def coerce_float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def coerce_string_list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def load_relationship_clusters(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return []
    clusters = payload.get("clusters")
    if not isinstance(clusters, list):
        return []
    return [cluster for cluster in clusters if isinstance(cluster, dict)]


def build_relationship_payload(
    app_state: AppState, paths: ReadingPaths, query: dict[str, str]
) -> dict[str, Any]:
    clusters = load_relationship_clusters(relationship_clusters_path(paths))
    summaries = [
        build_cluster_summary(index, cluster) for index, cluster in enumerate(clusters)
    ]
    cluster_id = parse_optional_int(query.get("cluster"))
    selected_cluster = None
    if cluster_id is not None and 0 <= cluster_id < len(clusters):
        selected_cluster = build_cluster_payload(paths, cluster_id, clusters[cluster_id])
    return {
        "available": bool(clusters),
        "decisions_exists": paths.decisions_path.exists(),
        "clusters_exists": relationship_clusters_path(paths).exists(),
        "relations_exists": relationship_relations_path(paths).exists(),
        "cluster_count": len(clusters),
        "clusters": summaries,
        "selected_cluster": selected_cluster,
        "task": relationship_task_status(app_state, paths),
    }


def build_cluster_summary(cluster_id: int, cluster: dict[str, Any]) -> dict[str, Any]:
    files = [item for item in cluster.get("files") or [] if isinstance(item, dict)]
    preview_paths = [
        str(item.get("relative_path") or "")
        for item in files[:3]
        if str(item.get("relative_path") or "")
    ]
    return {
        "cluster_id": cluster_id,
        "size": coerce_int_value(cluster.get("size"), len(files)),
        "categories": sorted(
            {str(category) for category in cluster.get("categories") or [] if str(category)}
        ),
        "preview_paths": preview_paths,
    }


def build_cluster_payload(
    paths: ReadingPaths, cluster_id: int, cluster: dict[str, Any]
) -> dict[str, Any]:
    decisions = load_latest_decisions(paths.decisions_path)
    events = load_latest_reading_events(paths.reading_status_path)
    rows_by_path = {
        str(row.get("relative_path") or ""): row
        for row in build_reading_rows(decisions, events)
    }
    cluster_files = [item for item in cluster.get("files") or [] if isinstance(item, dict)]
    files: list[dict[str, Any]] = []
    member_paths: set[str] = set()
    for item in cluster_files:
        relative_path = str(item.get("relative_path") or "")
        if not relative_path:
            continue
        row = rows_by_path.get(relative_path, {})
        decision = decisions.get(relative_path, {})
        files.append(
            {
                "relative_path": relative_path,
                "status": str(row.get("status") or "unread"),
                "quality": coerce_int_value(
                    row.get("quality"), coerce_int_value(item.get("quality"), 0)
                ),
                "category": str(row.get("category") or item.get("category") or ""),
                "document_kind": str(
                    row.get("document_kind") or item.get("document_kind") or "Unknown"
                ),
                "topic_tags": coerce_string_list_value(
                    row.get("topic_tags") or item.get("topic_tags")
                ),
                "sensitivity_risk": coerce_int_value(row.get("sensitivity_risk"), 0),
                "public_writing_suitability": coerce_int_value(
                    row.get("public_writing_suitability"), 0
                ),
                "note": str(row.get("note") or ""),
                "source_path": str(row.get("source_path") or decision.get("source_path") or ""),
                "target_path": str(row.get("target_path") or materialized_target_path(decision)),
                "summary": str(decision.get("summary") or ""),
            }
        )
        member_paths.add(relative_path)

    edges = load_cluster_edges(relationship_relations_path(paths), member_paths)
    return {
        "cluster_id": cluster_id,
        "size": coerce_int_value(cluster.get("size"), len(files)),
        "categories": sorted(
            {str(category) for category in cluster.get("categories") or [] if str(category)}
        ),
        "files": files,
        "edge_count": len(edges),
        "edges": edges,
    }


def load_cluster_edges(path: Path, member_paths: set[str]) -> list[dict[str, Any]]:
    if not path.exists() or not member_paths:
        return []

    edges: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            left = payload.get("left")
            right = payload.get("right")
            if not isinstance(left, dict) or not isinstance(right, dict):
                continue
            left_path = str(left.get("relative_path") or "")
            right_path = str(right.get("relative_path") or "")
            if not left_path or not right_path:
                continue
            if left_path not in member_paths or right_path not in member_paths:
                continue
            edges.append(
                {
                    "left_path": left_path,
                    "right_path": right_path,
                    "relation_score": round(
                        coerce_float_value(payload.get("relation_score"), 0.0), 4
                    ),
                    "signals": coerce_string_list_value(payload.get("signals")),
                    "filename_similarity": round(
                        coerce_float_value(payload.get("filename_similarity"), 0.0), 4
                    ),
                    "time_proximity": round(
                        coerce_float_value(payload.get("time_proximity"), 0.0), 4
                    ),
                    "path_proximity": round(
                        coerce_float_value(payload.get("path_proximity"), 0.0), 4
                    ),
                    "embedding_similarity": round(
                        coerce_float_value(payload.get("embedding_similarity"), 0.0), 4
                    ),
                    "type_compatibility": round(
                        coerce_float_value(payload.get("type_compatibility"), 0.0), 4
                    ),
                    "citation_count": coerce_int_value(payload.get("citation_count"), 0),
                }
            )

    edges.sort(key=lambda edge: edge["relation_score"], reverse=True)
    return edges


def relationship_task_status(
    app_state: AppState, paths: ReadingPaths | None = None
) -> dict[str, Any]:
    with app_state.lock:
        process = app_state.relationship_process
        kind = app_state.relationship_process_kind
        command = app_state.relationship_process_command
        matches_paths = paths is None or paths_match_command(command, paths)
        running = process is not None and process.poll() is None and matches_paths
        pid = process.pid if process is not None and matches_paths else None
        return_code = None if process is None or not matches_paths else process.poll()
        if process is not None and process.poll() is not None:
            app_state.relationship_process = None
            app_state.relationship_process_kind = None
            app_state.relationship_process_command = None
    return {
        "running": running,
        "pid": pid,
        "kind": kind if matches_paths else None,
        "command": command if matches_paths else None,
        "return_code": return_code,
    }


def relationship_task_command(
    task_name: str, payload: dict[str, Any], paths: ReadingPaths
) -> list[str]:
    llm_endpoint = str(payload.get("llm_endpoint") or "http://localhost:11434/api/generate")
    llm_model = str(payload.get("llm_model") or "").strip()
    embedding_model = str(payload.get("embedding_model") or "").strip()
    command_map = {
        "mine": [sys.executable, str(PROJECT_ROOT / "relationship_miner.py")],
        "export_graph": [sys.executable, str(PROJECT_ROOT / "knowledge_graph.py")],
        "export_bundle": [sys.executable, str(PROJECT_ROOT / "bundle_exporter.py")],
    }
    command = command_map.get(task_name)
    if command is None:
        raise ValueError(f"Unsupported relationship task: {task_name}")
    command.extend(
        [
            "--source-dir",
            str(paths.source_dir),
            "--output-root",
            str(paths.output_root),
            "--llm-endpoint",
            llm_endpoint,
        ]
    )
    if llm_model:
        command.extend(["--llm-model", llm_model])
    if task_name == "mine":
        concurrency = str(payload.get("concurrency") or "").strip()
        if concurrency:
            command.extend(["--concurrency", concurrency])
        if bool(payload.get("relationship_use_text_citations", True)):
            command.append("--use-text-citations")
        if bool(payload.get("relationship_use_embeddings")):
            command.append("--use-embeddings")
        if embedding_model:
            command.extend(["--embedding-model", embedding_model])
    return command


def start_relationship_task(
    app_state: AppState, payload: dict[str, Any], task_name: str
) -> dict[str, Any]:
    paths = reading_paths_from_payload(app_state, payload) or require_paths(app_state)
    output_root = paths.output_root
    task_labels = {
        "mine": "关系结果生成",
        "export_graph": "知识图谱导出",
        "export_bundle": "Bundle 导出",
    }
    label = task_labels.get(task_name, task_name)

    with app_state.lock:
        process = app_state.process
        if process is not None and process.poll() is None:
            raise RuntimeError("Cannot start relationship task while analysis is running.")
        if app_state.relationship_process is not None and app_state.relationship_process.poll() is None:
            raise RuntimeError("Another relationship task is already running.")
        if task_name != "mine" and not relationship_relations_path(paths).exists():
            raise RuntimeError("No relationship results found. Generate relations first.")

        output_root.mkdir(parents=True, exist_ok=True)
        paths.log_dir.mkdir(parents=True, exist_ok=True)
        command = relationship_task_command(task_name, payload, paths)
        with paths.application_log_path.open("a", encoding="utf-8", errors="ignore") as log_handle:
            task_process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=utf8_subprocess_env(),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        app_state.relationship_process = task_process
        app_state.relationship_process_kind = task_name
        app_state.relationship_process_command = command
    return {
        "started": True,
        "task": task_name,
        "label": label,
        "pid": task_process.pid,
        "command": command,
    }


def row_matches_query(row: dict[str, Any], q: str) -> bool:
    haystack = " ".join(
        [
            str(row.get("relative_path") or ""),
            str(row.get("source_path") or ""),
            str(row.get("category") or ""),
            str(row.get("document_kind") or ""),
            str(row.get("summary") or ""),
            str(row.get("reason") or ""),
            str(row.get("failure_stage") or ""),
            str(row.get("failure_reason") or ""),
            str(row.get("failure_error") or ""),
            " ".join(str(tag) for tag in row.get("topic_tags") or []),
            str(row.get("note") or ""),
        ]
    ).lower()
    return q in haystack


def sort_rows(rows: list[dict[str, Any]], sort_key: str) -> list[dict[str, Any]]:
    key_map = {
        "quality_desc": lambda row: (-int(row.get("quality") or 0), row.get("relative_path") or ""),
        "quality_asc": lambda row: (int(row.get("quality") or 0), row.get("relative_path") or ""),
        "path_asc": lambda row: (source_sort_path(row),),
        "path_desc": lambda row: (source_sort_path(row),),
        "source_path_asc": lambda row: (source_sort_path(row),),
        "source_path_desc": lambda row: (source_sort_path(row),),
        "source_mtime_desc": lambda row: (-source_mtime_sort_value(row), source_sort_path(row)),
        "source_mtime_asc": lambda row: (source_mtime_sort_value(row), source_sort_path(row)),
        "category_asc": lambda row: (str(row.get("category") or ""), -int(row.get("quality") or 0)),
        "category_desc": lambda row: (str(row.get("category") or ""), int(row.get("quality") or 0)),
        "status_asc": lambda row: (str(row.get("status") or ""), -int(row.get("quality") or 0)),
        "status_desc": lambda row: (str(row.get("status") or ""), int(row.get("quality") or 0)),
        "kind_asc": lambda row: (str(row.get("document_kind") or ""), -int(row.get("quality") or 0)),
        "kind_desc": lambda row: (str(row.get("document_kind") or ""), int(row.get("quality") or 0)),
        "updated_desc": lambda row: (str(row.get("updated_at") or ""),),
        "sensitivity_asc": lambda row: (int(row.get("sensitivity_risk") or 0), -int(row.get("quality") or 0)),
        "sensitivity_desc": lambda row: (int(row.get("sensitivity_risk") or 0), int(row.get("quality") or 0)),
        "public_desc": lambda row: (-int(row.get("public_writing_suitability") or 0), -int(row.get("quality") or 0)),
        "public_asc": lambda row: (int(row.get("public_writing_suitability") or 0), -int(row.get("quality") or 0)),
    }
    key_func = key_map.get(sort_key, key_map["quality_desc"])
    reverse = sort_key in {
        "updated_desc",
        "path_desc",
        "source_path_desc",
        "category_desc",
        "status_desc",
        "kind_desc",
        "sensitivity_desc",
    }
    return sorted(rows, key=key_func, reverse=reverse)


def source_sort_path(row: dict[str, Any]) -> str:
    return str(row.get("source_path") or row.get("relative_path") or "").lower()


def source_mtime_sort_value(row: dict[str, Any]) -> float:
    value = row.get("source_mtime_epoch")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def config_payload(paths: ReadingPaths | None) -> dict[str, Any]:
    return {
        "source_dir": "" if paths is None else str(paths.source_dir),
        "output_root": "" if paths is None else str(paths.output_root),
        "capabilities": environment_capabilities(),
    }


def environment_capabilities() -> dict[str, Any]:
    return {
        "platform": sys.platform,
        "os_name": os.name,
        "folder_picker": can_use_folder_picker(),
        "open_file": can_open_file(),
        "reveal_file": can_reveal_file(),
        "headless_hint": (
            "Folder picker and system default file opening may be unavailable on headless servers. "
            "Manual path input and analysis execution still work."
            if is_probably_headless()
            else ""
        ),
    }


def is_probably_headless() -> bool:
    if os.name == "nt":
        return False
    if sys.platform == "darwin":
        return False
    return not bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def can_use_folder_picker() -> bool:
    if is_probably_headless():
        return False
    if os.name == "nt":
        return windows_folder_picker_command() is not None
    try:
        import tkinter  # noqa: F401
        root = tkinter.Tk()
        root.withdraw()
        root.destroy()
    except Exception:
        return False
    return True


def can_open_file() -> bool:
    if os.name == "nt":
        return True
    if sys.platform == "darwin":
        return macos_open_command_available()
    if is_probably_headless():
        return False
    return linux_open_command_available()


def can_reveal_file() -> bool:
    if os.name == "nt":
        return True
    if sys.platform == "darwin":
        return macos_open_command_available()
    return can_open_file()


def start_analysis(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    with app_state.lock:
        process = app_state.process
        if process is not None and process.poll() is None:
            raise RuntimeError(f"Analysis is already running with PID {process.pid}")

        source_dir, output_root = resolve_payload_paths(payload)
        clear_source_file_scan_cache(source_dir)
        app_state.paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
        active_pid = find_active_run_pid(app_state.paths)
        if active_pid is not None:
            raise RuntimeError(f"Analysis is already running with PID {active_pid}")
        command = build_analysis_command(payload, source_dir, output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "_state").mkdir(parents=True, exist_ok=True)
        (output_root / "_logs").mkdir(parents=True, exist_ok=True)
        with app_state.paths.application_log_path.open(
            "a", encoding="utf-8", errors="ignore"
        ) as log_handle:
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=utf8_subprocess_env(),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        app_state.process = process
        app_state.process_command = command
        return {
            "started": True,
            "pid": process.pid,
            "command": command,
            "plan_only": is_plan_only_command(command),
            "source_dir": str(source_dir),
            "output_root": str(output_root),
        }


def set_active_paths(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    source_dir, output_root = resolve_payload_paths(payload)
    with app_state.lock:
        process = app_state.process
        if process is not None and process.poll() is None:
            raise RuntimeError("Cannot change active paths while analysis is running.")
        clear_source_file_scan_cache(source_dir)
        app_state.paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    return {"source_dir": str(source_dir), "output_root": str(output_root)}


def set_reading_output(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    output_text = str(payload.get("output_root") or "").strip()
    if not output_text:
        raise ValueError("Output directory is required.")
    output_root = Path(output_text).expanduser().resolve()
    if not output_root.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_root}")
    source_dir = infer_source_dir_for_output(app_state, output_root)
    clear_source_file_scan_cache(source_dir)
    return {"source_dir": str(source_dir), "output_root": str(output_root)}


def infer_source_dir_for_output(app_state: AppState, output_root: Path) -> Path:
    with app_state.lock:
        active_paths = app_state.paths
        process = app_state.process
        running = process is not None and process.poll() is None
    if active_paths is not None and active_paths.output_root.resolve() == output_root:
        return active_paths.source_dir

    decision_source = infer_source_dir_from_decisions(output_root)
    if decision_source is not None:
        return decision_source

    if running and active_paths is not None:
        return active_paths.source_dir
    return output_root


def infer_source_dir_from_decisions(output_root: Path) -> Path | None:
    decisions_path = output_root / "_state" / "decisions.jsonl"
    if not decisions_path.exists():
        return None
    try:
        with decisions_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                source_path = str(payload.get("source_path") or "")
                relative_path = str(payload.get("relative_path") or "")
                if not source_path:
                    continue
                path = Path(source_path).expanduser().resolve()
                if relative_path:
                    relative = Path(relative_path)
                    parts = relative.parts
                    if parts:
                        for _ in parts:
                            path = path.parent
                        return path
                return path.parent
    except OSError:
        return None
    return None


def resolve_payload_paths(payload: dict[str, Any]) -> tuple[Path, Path]:
    source_text = str(payload.get("source_dir") or "").strip()
    output_text = str(payload.get("output_root") or "").strip()
    if not source_text:
        raise ValueError("Source directory is required.")
    if not output_text:
        raise ValueError("Output directory is required.")
    source_dir = Path(source_text).expanduser().resolve()
    output_root = Path(output_text).expanduser().resolve()
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")
    return source_dir, output_root


def paths_from_payload(payload: dict[str, Any]) -> ReadingPaths | None:
    source_text = str(payload.get("source_dir") or "").strip()
    output_text = str(payload.get("output_root") or "").strip()
    if not source_text and not output_text:
        return None
    source_dir, output_root = resolve_payload_paths(payload)
    return ReadingPaths(source_dir=source_dir, output_root=output_root)


def reading_paths_from_payload(
    app_state: AppState, payload: dict[str, Any]
) -> ReadingPaths | None:
    source_text = str(payload.get("source_dir") or "").strip()
    output_text = str(payload.get("output_root") or "").strip()
    if not source_text and not output_text:
        return None
    if source_text:
        source_dir, output_root = resolve_payload_paths(payload)
        return ReadingPaths(source_dir=source_dir, output_root=output_root)
    output_root = Path(output_text).expanduser().resolve()
    if not output_root.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_root}")
    return ReadingPaths(
        source_dir=infer_source_dir_for_output(app_state, output_root),
        output_root=output_root,
    )


def reading_request_paths(app_state: AppState, payload: dict[str, Any]) -> ReadingPaths:
    return reading_paths_from_payload(app_state, payload) or require_paths(app_state)


def paths_match_command(command: list[str] | None, paths: ReadingPaths) -> bool:
    if not command:
        return False
    command_output = command_option_path(command, "--output-root")
    if command_output is None:
        return False
    try:
        return command_output.resolve() == paths.output_root.resolve()
    except OSError:
        return False


def command_option_path(command: list[str], option: str) -> Path | None:
    value = command_option_value(command, option)
    return Path(value).expanduser() if value else None


def command_option_value(command: list[str], option: str) -> str | None:
    try:
        index = command.index(option)
    except ValueError:
        return None
    if index + 1 >= len(command):
        return None
    return command[index + 1]


def build_analysis_command(
    payload: dict[str, Any], source_dir: Path, output_root: Path
) -> list[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "main.py"),
        "--source-dir",
        str(source_dir),
        "--output-root",
        str(output_root),
        "--llm-endpoint",
        str(payload.get("llm_endpoint") or "http://localhost:11434/api/generate"),
    ]
    llm_model = str(payload.get("llm_model") or "").strip()
    if llm_model:
        command.extend(["--llm-model", llm_model])
    output_language = str(payload.get("output_language") or "auto").strip()
    if output_language:
        command.extend(["--output-language", output_language])
    embedding_model = str(payload.get("embedding_model") or "").strip()
    if embedding_model:
        command.extend(["--embedding-model", embedding_model])

    option_map = {
        "concurrency": "--concurrency",
        "limit": "--limit",
        "max_file_size_mb": "--max-file-size-mb",
        "quality_threshold": "--quality-threshold",
        "timeout_seconds": "--timeout-seconds",
    }
    for payload_key, option_name in option_map.items():
        value = str(payload.get(payload_key) or "").strip()
        if value:
            command.extend([option_name, value])

    flag_map = {
        "plan_only": "--plan-only",
        "no_ocr": "--no-ocr",
        "skip_manifest_analysis": "--skip-manifest-analysis",
        "document_summary": "--document-summary",
        "force_reprocess": "--force-reprocess",
        "content_hash": "--content-hash",
        "mine_relationships": "--mine-relationships",
        "relationship_use_text_citations": "--relationship-use-text-citations",
        "relationship_use_embeddings": "--relationship-use-embeddings",
    }
    for payload_key, option_name in flag_map.items():
        if bool(payload.get(payload_key)):
            command.append(option_name)
    return command


def is_plan_only_command(command: list[str] | None) -> bool:
    return bool(command and "--plan-only" in command)


def run_lock_path(output_root: Path) -> Path:
    return output_root / "_state" / "run.lock"


def read_run_lock(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return {}


def coerce_pid(value: Any) -> int | None:
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return True
        output = decode_process_output(result.stdout)
        return str(pid) in output
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def find_active_run_pid(paths: ReadingPaths) -> int | None:
    lock_info = read_run_lock(run_lock_path(paths.output_root))
    pid = coerce_pid(lock_info.get("pid"))
    if pid is None or not is_process_alive(pid):
        return None
    return pid


def run_lock_status(paths: ReadingPaths) -> dict[str, Any]:
    path = run_lock_path(paths.output_root)
    info = read_run_lock(path)
    pid = coerce_pid(info.get("pid"))
    active = pid is not None and is_process_alive(pid)
    return {
        "exists": path.exists(),
        "pid": pid,
        "active": active,
        "source_dir": str(info.get("source_dir") or ""),
        "output_root": str(info.get("output_root") or ""),
        "created_epoch": info.get("created_epoch"),
    }


def terminate_process_id(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0 or not is_process_alive(pid)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    return True


def path_contains(parent: Path, child: Path) -> bool:
    return parent == child or parent in child.parents


def validate_reset_output_root(source_dir: Path, output_root: Path) -> None:
    if output_root == output_root.parent:
        raise ValueError(f"Refusing to reset filesystem root: {output_root}")
    if source_dir == output_root:
        raise ValueError(
            "Refusing to reset because source directory and output directory are the same."
        )
    if path_contains(source_dir, output_root):
        raise ValueError(
            "Refusing to reset because output directory is inside the source directory."
        )
    if path_contains(output_root, source_dir):
        raise ValueError(
            "Refusing to reset because output directory contains the source directory."
        )


def clear_output_root_contents(output_root: Path) -> None:
    if not output_root.exists():
        return
    for child in output_root.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
            continue
        if child.is_dir():
            shutil.rmtree(child)
            continue
        child.unlink()


def reset_analysis_output(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    source_dir, output_root = resolve_payload_paths(payload)
    validate_reset_output_root(source_dir, output_root)
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    clear_source_file_scan_cache(source_dir)

    with app_state.lock:
        process = app_state.process
        if process is not None and process.poll() is None:
            raise RuntimeError("Cannot reset output while analysis is running.")
        active_pid = find_active_run_pid(paths)
        if active_pid is not None:
            raise RuntimeError(
                f"Cannot reset output while analysis is running with PID {active_pid}."
            )

        clear_output_root_contents(output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "_state").mkdir(parents=True, exist_ok=True)
        (output_root / "_logs").mkdir(parents=True, exist_ok=True)
        app_state.paths = paths
        app_state.process = None
        app_state.process_command = None

    return {
        "reset": True,
        "source_dir": str(source_dir),
        "output_root": str(output_root),
    }


def stop_analysis(app_state: AppState, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    requested_paths = paths_from_payload(payload or {})
    with app_state.lock:
        process = app_state.process
        paths = requested_paths or app_state.paths
        if paths is not None:
            clear_source_file_scan_cache(paths.source_dir)
        process_matches_paths = (
            requested_paths is None
            or paths_match_command(app_state.process_command, requested_paths)
        )
        if process is not None and process.poll() is None and process_matches_paths:
            process.terminate()
            stopped = wait_for_process_exit(process, timeout_seconds=5.0)
            if not stopped:
                stopped = kill_process(process)
            return {
                "stopped": stopped,
                "running": process.poll() is None,
                "pid": process.pid,
            }
        if paths is None:
            return {"stopped": False, "running": False}
        pid = find_active_run_pid(paths)
        if pid is None:
            return {"stopped": False, "running": False}
        stopped = terminate_process_id(pid)
        return {"stopped": stopped, "running": is_process_alive(pid), "pid": pid}


def wait_for_process_exit(process: subprocess.Popen, timeout_seconds: float) -> bool:
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return False
    return True


def kill_process(process: subprocess.Popen) -> bool:
    try:
        process.kill()
        process.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return process.poll() is not None


def infer_analysis_phase(
    *,
    running: bool,
    progress: dict[str, Any],
    log_tail: str,
    decisions_exists: bool,
    relations_exists: bool = False,
    clusters_exists: bool = False,
    run_summary: dict[str, Any] | None = None,
) -> str:
    completed = coerce_int_value(progress.get("completed"), 0)
    remaining = coerce_int_value(progress.get("remaining"), 0)
    total = coerce_int_value(progress.get("total"), 0)
    submitted = coerce_int_value(progress.get("submitted"), 0)
    planned = coerce_int_value(progress.get("planned"), 0)
    succeeded = coerce_int_value(progress.get("succeeded"), 0)
    skipped_resumed = coerce_int_value(progress.get("skipped_resumed"), 0)

    if running:
        if log_tail.rfind("Starting relationship mining") > log_tail.rfind(
            "Relationship mining completed"
        ):
            return "关系挖掘中"
        if decisions_exists and completed == 0 and submitted == 0 and skipped_resumed == 0:
            return "续传准备中"
        if skipped_resumed > 0 and submitted == 0:
            return "续传跳过中"
        if submitted > 0 or planned > 0 or succeeded > 0:
            return "文档评分中"
        return "扫描准备中"

    summary = run_summary or {}
    unresolved_failures = coerce_int_value(
        summary.get("unresolved_failures"), coerce_int_value(progress.get("failed"), 0)
    )
    if total > 0 and remaining == 0:
        if unresolved_failures > 0:
            return "分析完成，仍有失败"
        if relations_exists and clusters_exists:
            return "分析完成，关系已生成"
        if decisions_exists:
            return "分析完成，关系未生成"
        return "分析完成"
    if completed > 0 or decisions_exists:
        return "已停止，可续传"
    return "未启动"


def analysis_status(
    app_state: AppState, paths: ReadingPaths | None = None
) -> dict[str, Any]:
    with app_state.lock:
        process = app_state.process
        command = app_state.process_command
        active_paths = app_state.paths
        paths = paths or active_paths
        local_running = (
            process is not None
            and process.poll() is None
            and (paths is None or paths_match_command(command, paths))
        )
        local_pid = process.pid if process is not None else None
        return_code = None if process is None else process.poll()

    if paths is None:
        return {
            "running": local_running,
            "plan_only": False,
            "phase": "未启动",
            "pid": local_pid,
            "return_code": return_code,
            "command": command,
            "source_dir": "",
            "output_root": "",
            "progress": {},
            "log_tail": "",
            "decisions_exists": False,
            "run_lock": {"exists": False, "pid": None, "active": False},
            "activity": {
                "state_counts": {},
                "state_files": {},
                "latest_activity": {"label": "", "detail": "", "line": ""},
            },
            "run_summary": {},
        }

    active_pid = find_active_run_pid(paths)
    running = local_running or active_pid is not None
    pid = local_pid if local_running else active_pid
    if running and not local_running:
        return_code = None
    effective_concurrency = infer_effective_concurrency(command)
    progress = read_json_file(paths.progress_path)
    run_summary = read_json_file(paths.output_root / "_state" / "run_summary.json")
    log_tail = read_text_tail(paths.application_log_path, max_lines=80)
    plan_only = infer_plan_only_mode(command, progress, run_summary)
    decisions_exists = paths.decisions_path.exists()
    lock_status = run_lock_status(paths)

    return {
        "running": running,
        "plan_only": plan_only,
        "phase": infer_analysis_phase(
            running=running,
            progress=progress,
            log_tail=log_tail,
            decisions_exists=decisions_exists,
            relations_exists=relationship_relations_path(paths).exists(),
            clusters_exists=relationship_clusters_path(paths).exists(),
            run_summary=run_summary,
        ),
        "pid": pid,
        "return_code": return_code,
        "command": command,
        "effective_concurrency": effective_concurrency,
        "source_dir": str(paths.source_dir),
        "output_root": str(paths.output_root),
        "progress": progress,
        "log_tail": log_tail,
        "decisions_exists": decisions_exists,
        "run_lock": lock_status,
        "activity": build_analysis_activity(paths, log_tail),
        "run_summary": run_summary,
    }


def infer_plan_only_mode(
    command: list[str] | None,
    progress: dict[str, Any] | None = None,
    run_summary: dict[str, Any] | None = None,
) -> bool:
    if is_plan_only_command(command):
        return True
    for payload in (progress, run_summary):
        if isinstance(payload, dict) and isinstance(payload.get("plan_only"), bool):
            return bool(payload["plan_only"])
    return False


def infer_effective_concurrency(command: list[str] | None) -> str:
    if command:
        value = command_option_value(command, "--concurrency")
        if value:
            return value
    return ""


def require_paths(app_state: AppState) -> ReadingPaths:
    paths = app_state.paths
    if paths is None:
        raise ValueError("Please select and apply source/output directories first.")
    return paths


def pick_folder() -> dict[str, str]:
    if not can_use_folder_picker():
        raise RuntimeError(
            "Folder picker is unavailable in this environment. "
            "Please type the folder path manually."
        )
    if os.name == "nt":
        return {"path": pick_folder_windows()}
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(f"Folder picker is unavailable: {exc}") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory()
    finally:
        root.destroy()
    return {"path": selected or ""}


def windows_folder_picker_command() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def pick_folder_windows() -> str:
    command = windows_folder_picker_command()
    if command is None:
        raise RuntimeError(
            "Windows folder picker requires PowerShell. "
            "Please type the folder path manually."
        )
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dialog.Description = 'Select DocTriage folder'; "
        "$dialog.ShowNewFolderButton = $true; "
        "$result = $dialog.ShowDialog(); "
        "if ($result -eq [System.Windows.Forms.DialogResult]::OK) { "
        "Write-Output $dialog.SelectedPath }"
    )
    try:
        result = subprocess.run(
            [command, "-NoProfile", "-STA", "-Command", script],
            capture_output=True,
            text=False,
            timeout=None,
        )
    except OSError as exc:
        raise RuntimeError(f"Windows folder picker failed to start: {exc}") from exc
    stdout = decode_process_output(result.stdout)
    stderr = decode_process_output(result.stderr)
    if result.returncode != 0:
        error = (stderr or stdout).strip()
        raise RuntimeError(f"Windows folder picker failed: {error}")
    return stdout.strip()


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_text_tail(path: Path, max_lines: int) -> str:
    if not path.exists():
        return ""
    try:
        data = read_tail_bytes(path)
    except OSError:
        return ""
    lines = data.splitlines(keepends=True)
    return "".join(decode_log_line(line) for line in lines[-max_lines:])


def read_tail_bytes(path: Path, max_bytes: int = 1024 * 1024) -> bytes:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(size - max_bytes)
            handle.readline()
        return handle.read()


def decode_log_line(line: bytes) -> str:
    return decode_process_output(line)


def file_activity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "size": 0, "updated_at": "", "age_seconds": None}
    try:
        stat = path.stat()
    except OSError:
        return {"exists": False, "size": 0, "updated_at": "", "age_seconds": None}
    updated_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone()
    age_seconds = max(0.0, datetime.now(timezone.utc).timestamp() - stat.st_mtime)
    return {
        "exists": True,
        "size": stat.st_size,
        "updated_at": updated_at.isoformat(),
        "age_seconds": round(age_seconds, 1),
    }


def count_nonempty_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def latest_log_activity(log_tail: str) -> dict[str, str]:
    lines = [line.strip() for line in log_tail.splitlines() if line.strip()]
    if not lines:
        return {"label": "", "detail": "", "line": ""}

    selected = ""
    for line in reversed(lines):
        if " doctriage - " in line:
            selected = line
            break
    if not selected:
        selected = lines[-1]

    message = selected.split(" - ", 1)[1] if " - " in selected else selected
    if "Skipping resumed item already materialized:" in message:
        return {
            "label": "续传跳过",
            "detail": message.split("Skipping resumed item already materialized:", 1)[1].strip(),
            "line": selected,
        }
    if message.startswith("Planned "):
        detail = message.removeprefix("Planned ").strip()
        return {
            "label": "已规划",
            "detail": detail,
            "line": selected,
        }
    if message.startswith("Progress "):
        return {"label": "进度写入", "detail": "", "line": selected}
    if message.startswith("Starting relationship mining"):
        return {"label": "关系挖掘", "detail": "开始生成关系结果", "line": selected}
    if message.startswith("Relationship mining completed"):
        return {"label": "关系挖掘", "detail": "已完成", "line": selected}
    return {"label": "最近日志", "detail": message, "line": selected}


def build_analysis_activity(paths: ReadingPaths, log_tail: str) -> dict[str, Any]:
    return {
        "state_counts": {
            "decisions": count_nonempty_lines(paths.decisions_path),
            "processed": count_nonempty_lines(paths.output_root / "_state" / "processed_files.jsonl"),
            "failed": count_nonempty_lines(paths.output_root / "_state" / "failed_files.jsonl"),
        },
        "state_files": {
            "decisions": file_activity(paths.decisions_path),
            "processed": file_activity(paths.output_root / "_state" / "processed_files.jsonl"),
            "failed": file_activity(paths.output_root / "_state" / "failed_files.jsonl"),
            "progress": file_activity(paths.progress_path),
            "log": file_activity(paths.application_log_path),
        },
        "latest_activity": latest_log_activity(log_tail),
    }


def mark_document(paths: ReadingPaths, payload: dict[str, Any]) -> dict[str, Any]:
    decisions = safe_load_decisions(paths)
    relative_path = str(payload.get("relative_path") or payload.get("path") or "")
    status = str(payload.get("status") or "")
    note = str(payload.get("note") or "")
    if status not in MARKABLE_STATUSES:
        raise ValueError(f"Unsupported reading status: {status}")
    if resolves_to_decision(relative_path, paths, decisions):
        return append_reading_event(
            paths,
            decisions,
            requested_path=relative_path,
            status=status,
            note=note,
        )
    source_path, source_relative_path = resolve_source_document(paths, payload, decisions)
    return append_source_reading_event(
        paths,
        source_path=source_path,
        relative_path=source_relative_path,
        status=status,
        note=note,
    )


def mark_document_request(
    app_state: AppState, payload: dict[str, Any]
) -> dict[str, Any]:
    return mark_document(reading_request_paths(app_state, payload), payload)


def safe_load_decisions(paths: ReadingPaths) -> dict[str, dict[str, Any]]:
    try:
        return load_latest_decisions(paths.decisions_path)
    except FileNotFoundError:
        return {}


def resolves_to_decision(
    requested_path: str,
    paths: ReadingPaths,
    decisions: dict[str, dict[str, Any]],
) -> bool:
    try:
        append_relative_path = resolve_relative_path_for_decisions(
            requested_path, paths, decisions
        )
    except ValueError:
        return False
    return append_relative_path in decisions


def resolve_relative_path_for_decisions(
    requested_path: str,
    paths: ReadingPaths,
    decisions: dict[str, dict[str, Any]],
) -> str:
    from reading_tracker import resolve_relative_path

    return resolve_relative_path(requested_path, paths.source_dir, decisions)


def append_source_reading_event(
    paths: ReadingPaths,
    *,
    source_path: Path,
    relative_path: str,
    status: str,
    note: str = "",
) -> dict[str, Any]:
    stat_payload = stat_source_file(source_path)
    fingerprint = {
        "size_bytes": stat_payload.get("source_size_bytes"),
        "mtime_ns": stat_payload.get("source_mtime_ns"),
        "ctime_ns": stat_payload.get("source_ctime_ns"),
    }
    event = {
        "relative_path": relative_path,
        "source_path": str(source_path),
        "status": status,
        "note": note,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": fingerprint,
        "quality": None,
        "category": None,
    }
    paths.reading_status_path.parent.mkdir(parents=True, exist_ok=True)
    with paths.reading_status_path.open("a", encoding="utf-8", errors="ignore") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def resolve_source_document(
    paths: ReadingPaths,
    payload: dict[str, Any],
    decisions: dict[str, dict[str, Any]] | None = None,
) -> tuple[Path, str]:
    if decisions is None:
        decisions = safe_load_decisions(paths)
    relative_path = str(payload.get("relative_path") or payload.get("path") or "").strip()
    source_text = str(payload.get("source_path") or "").strip()
    requested = source_text or relative_path
    if not requested:
        raise ValueError("Missing document path")

    if relative_path:
        decision = decisions.get(relative_path)
        if decision and decision.get("source_path"):
            source_path = Path(str(decision["source_path"]))
            return source_path, relative_path

    source_dir = paths.source_dir.resolve()
    candidates: list[Path] = []
    raw_path = Path(requested)
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.append(source_dir / requested)
        normalized = requested.replace("\\", "/")
        if normalized != requested:
            candidates.append(source_dir / normalized)

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(source_dir)
        except (OSError, ValueError):
            continue
        if resolved.exists() and resolved.is_file():
            return resolved, resolved.relative_to(source_dir).as_posix()

    normalized_requested = requested.replace("\\", "/")
    matches: list[Path] = []
    for path in iter_supported_source_files(source_dir):
        relative = source_relative_path(paths, path)
        if relative == normalized_requested or relative.endswith(normalized_requested) or path.name == requested:
            matches.append(path)
    if len(matches) == 1:
        resolved = matches[0].resolve()
        return resolved, resolved.relative_to(source_dir).as_posix()
    if len(matches) > 1:
        raise ValueError(f"Ambiguous source document path: {requested}")
    raise ValueError(f"Unknown source document: {requested}")


def mark_documents(paths: ReadingPaths, payload: dict[str, Any]) -> dict[str, Any]:
    decisions = safe_load_decisions(paths)
    raw_paths = payload.get("relative_paths") or []
    if not isinstance(raw_paths, list):
        raise ValueError("relative_paths must be a list")
    status = str(payload.get("status") or "")
    note = str(payload.get("note") or "")
    if status not in MARKABLE_STATUSES:
        raise ValueError(f"Unsupported reading status: {status}")

    events = []
    for relative_path in raw_paths:
        text = str(relative_path)
        if resolves_to_decision(text, paths, decisions):
            events.append(
                append_reading_event(
                    paths,
                    decisions,
                    requested_path=text,
                    status=status,
                    note=note,
                )
            )
            continue
        source_path, source_relative_path = resolve_source_document(
            paths, {"relative_path": text}, decisions
        )
        events.append(
            append_source_reading_event(
                paths,
                source_path=source_path,
                relative_path=source_relative_path,
                status=status,
                note=note,
            )
        )
    return {"count": len(events), "events": events}


def mark_documents_request(
    app_state: AppState, payload: dict[str, Any]
) -> dict[str, Any]:
    return mark_documents(reading_request_paths(app_state, payload), payload)


def open_document(paths: ReadingPaths, payload: dict[str, Any], *, reveal: bool) -> dict[str, Any]:
    source_path, _relative_path = resolve_source_document(paths, payload)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file does not exist: {source_path}")

    if reveal:
        reveal_path(source_path)
    else:
        open_path(source_path)
    return {"ok": True, "source_path": str(source_path)}


def open_document_request(
    app_state: AppState, payload: dict[str, Any], *, reveal: bool
) -> dict[str, Any]:
    return open_document(reading_request_paths(app_state, payload), payload, reveal=reveal)


def open_failure_document(
    paths: ReadingPaths, payload: dict[str, Any], *, reveal: bool
) -> dict[str, Any]:
    source_path = resolve_failure_source(paths, payload)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file does not exist: {source_path}")

    if reveal:
        reveal_path(source_path)
    else:
        open_path(source_path)
    return {"ok": True, "source_path": str(source_path)}


def open_failure_document_request(
    app_state: AppState, payload: dict[str, Any], *, reveal: bool
) -> dict[str, Any]:
    return open_failure_document(
        reading_request_paths(app_state, payload),
        payload,
        reveal=reveal,
    )


def resolve_decision(paths: ReadingPaths, relative_path: str) -> dict[str, Any]:
    decisions = load_latest_decisions(paths.decisions_path)
    decision = decisions.get(relative_path)
    if decision:
        return decision
    raise ValueError(f"Unknown relative_path: {relative_path}")


def resolve_failure_source(paths: ReadingPaths, payload: dict[str, Any]) -> Path:
    source_text = str(payload.get("source_path") or "").strip()
    relative_path = str(payload.get("relative_path") or "").strip()
    source_key = source_path_key(Path(source_text)) if source_text else ""
    relative_matches: list[Path] = []
    for row in build_failure_rows(paths):
        row_source_text = str(row.get("source_path") or "")
        row_source_path = Path(row_source_text)
        if source_text and (
            row_source_text == source_text or source_path_key(row_source_path) == source_key
        ):
            return row_source_path
        if relative_path and str(row.get("relative_path") or "") == relative_path:
            relative_matches.append(row_source_path)

    if len(relative_matches) == 1:
        return relative_matches[0]
    if len(relative_matches) > 1:
        raise ValueError(f"Ambiguous failed document path: {relative_path}")
    requested = source_text or relative_path
    raise ValueError(f"Unknown failed document: {requested}")


def open_path(path: Path) -> None:
    if os.name == "nt":
        shell_execute(str(path))
        return
    if sys.platform == "darwin":
        command = macos_open_command(path, reveal=False)
        if command is None:
            raise RuntimeError("macOS opener 'open' was not found.")
        launch_desktop_command(command)
        return
    if is_probably_headless():
        raise RuntimeError(
            "System default file opening is unavailable on this headless server. "
            f"Use this source path manually: {path}"
        )
    command = linux_open_command(path)
    if command is None:
        raise RuntimeError(
            "No supported Linux desktop opener was found. "
            "Install xdg-utils, gio, KDE open, or GNOME open."
        )
    launch_desktop_command(command)


def reveal_path(path: Path) -> None:
    if os.name == "nt":
        subprocess.Popen(
            ["explorer.exe", f"/select,{path}"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return
    if sys.platform == "darwin":
        command = macos_open_command(path, reveal=True)
        if command is None:
            raise RuntimeError("macOS opener 'open' was not found.")
        launch_desktop_command(command)
        return
    open_path(path.parent)


def macos_open_command_available() -> bool:
    return find_macos_open() is not None


def macos_open_command(path: Path, *, reveal: bool) -> list[str] | None:
    opener = find_macos_open()
    if opener is None:
        return None
    if reveal:
        return [opener, "-R", str(path)]
    return [opener, str(path)]


def find_macos_open() -> str | None:
    return shutil.which("open") or ("/usr/bin/open" if Path("/usr/bin/open").exists() else None)


def linux_open_command_available() -> bool:
    return linux_open_command(Path(".")) is not None


def linux_open_command(path: Path) -> list[str] | None:
    opener = shutil.which("xdg-open")
    if opener:
        return [opener, str(path)]
    gio = shutil.which("gio")
    if gio:
        return [gio, "open", str(path)]
    for command_name in ("kde-open6", "kde-open5", "kde-open", "gnome-open"):
        opener = shutil.which(command_name)
        if opener:
            return [opener, str(path)]
    return None


def launch_desktop_command(command: list[str]) -> None:
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def shell_execute(path: str) -> None:
    import ctypes

    result = ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
        None,
        "open",
        path,
        None,
        None,
        1,
    )
    if result <= 32:
        raise OSError(f"ShellExecute failed with code {result}: {path}")


def count_by(rows: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field_name) or "")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def parse_int(value: str | None, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def parse_optional_int(value: str | None) -> int | None:
    if value in {None, ""}:
        return None
    return parse_int(value, 0)


class ReadingRequestHandler(BaseHTTPRequestHandler):
    state: AppState

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = self.parse_query(parsed.query)
        if parsed.path == "/":
            self.send_html(HTML_PAGE)
            return
        if parsed.path == "/api/config":
            self.send_json(lambda: config_payload(self.state.paths))
            return
        if parsed.path == "/api/analysis/status":
            self.send_json(
                lambda: analysis_status(
                    self.state,
                    paths_from_payload(query) or self.state.paths,
                )
            )
            return
        if parsed.path == "/api/relationships":
            self.send_json(
                lambda: build_relationship_payload(
                    self.state,
                    reading_paths_from_payload(self.state, query)
                    or require_paths(self.state),
                    query,
                )
            )
            return
        if parsed.path == "/api/state":
            self.send_json(
                lambda: build_state_payload(
                    reading_paths_from_payload(self.state, query)
                    or require_paths(self.state),
                    query,
                )
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/api/pick-folder":
            self.send_json(pick_folder)
            return
        if self.path == "/api/paths":
            self.send_json(lambda: set_active_paths(self.state, self.read_json()))
            return
        if self.path == "/api/reading-output":
            self.send_json(lambda: set_reading_output(self.state, self.read_json()))
            return
        if self.path == "/api/graph-output":
            self.send_json(lambda: set_reading_output(self.state, self.read_json()))
            return
        if self.path == "/api/analysis/start":
            self.send_json(lambda: start_analysis(self.state, self.read_json()))
            return
        if self.path == "/api/analysis/stop":
            self.send_json(lambda: stop_analysis(self.state, self.read_json()))
            return
        if self.path == "/api/analysis/reset":
            self.send_json(lambda: reset_analysis_output(self.state, self.read_json()))
            return
        if self.path == "/api/relationships/mine":
            self.send_json(
                lambda: start_relationship_task(self.state, self.read_json(), "mine")
            )
            return
        if self.path == "/api/relationships/export-graph":
            self.send_json(
                lambda: start_relationship_task(
                    self.state, self.read_json(), "export_graph"
                )
            )
            return
        if self.path == "/api/relationships/export-bundle":
            self.send_json(
                lambda: start_relationship_task(
                    self.state, self.read_json(), "export_bundle"
                )
            )
            return
        if self.path == "/api/mark":
            self.send_json(lambda: mark_document_request(self.state, self.read_json()))
            return
        if self.path == "/api/mark-batch":
            self.send_json(lambda: mark_documents_request(self.state, self.read_json()))
            return
        if self.path == "/api/open":
            self.send_json(lambda: open_document_request(self.state, self.read_json(), reveal=False))
            return
        if self.path == "/api/reveal":
            self.send_json(lambda: open_document_request(self.state, self.read_json(), reveal=True))
            return
        if self.path == "/api/open-failure":
            self.send_json(lambda: open_failure_document_request(self.state, self.read_json(), reveal=False))
            return
        if self.path == "/api/reveal-failure":
            self.send_json(lambda: open_failure_document_request(self.state, self.read_json(), reveal=True))
            return
        self.send_error(404)

    @staticmethod
    def parse_query(query: str) -> dict[str, str]:
        return {
            key: values[-1]
            for key, values in urllib.parse.parse_qs(query).items()
            if values
        }

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", errors="ignore")
        payload = json.loads(body or "{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def send_html(self, html: str) -> None:
        encoded = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, builder) -> None:
        try:
            payload = builder()
            status = 200
        except Exception as exc:
            payload = {"error": str(exc)}
            status = 400
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


def build_handler(app_state: AppState):
    class BoundReadingRequestHandler(ReadingRequestHandler):
        pass

    BoundReadingRequestHandler.state = app_state
    return BoundReadingRequestHandler


def serve(paths: ReadingPaths | None, host: str, port: int, *, open_browser: bool) -> None:
    app_state = AppState(paths=paths)
    server = ThreadingHTTPServer((host, port), build_handler(app_state))
    url = f"http://{host}:{server.server_port}/"
    print(f"DocTriage Console: {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doctriage-reading-ui",
        description="Open a local browser UI for DocTriage reading status.",
    )
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open-browser", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_utf8_runtime()
    args = build_parser().parse_args(argv)
    paths = None
    if args.source_dir is not None or args.output_root is not None:
        if args.source_dir is None or args.output_root is None:
            raise SystemExit("--source-dir and --output-root must be provided together.")
        paths = ReadingPaths(
            source_dir=args.source_dir.expanduser().resolve(),
            output_root=args.output_root.expanduser().resolve(),
        )
    serve(paths, args.host, args.port, open_browser=not args.no_open_browser)


if __name__ == "__main__":
    main()
