from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
import threading
import urllib.parse
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reading_tracker import (
    MARKABLE_STATUSES,
    ReadingPaths,
    append_reading_event,
    build_reading_rows,
    filter_rows,
    load_latest_decisions,
    load_latest_reading_events,
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
    h1 { margin: 0 0 12px; font-size: 20px; }
    .tabs { display: flex; gap: 8px; margin-bottom: 12px; }
    .tab { border: 1px solid var(--line); background: #fff; border-radius: 6px; padding: 8px 12px; cursor: pointer; }
    .tab.active { background: var(--blue); border-color: var(--blue); color: #fff; }
    .filters, .run-grid { display: grid; grid-template-columns: repeat(8, minmax(96px, 1fr)); gap: 8px; align-items: end; }
    .run-grid { grid-template-columns: repeat(6, minmax(120px, 1fr)); }
    .reading-filters { grid-template-columns: minmax(110px, 140px) minmax(100px, 120px) minmax(190px, 1fr) minmax(190px, 1fr) minmax(160px, 1fr) minmax(100px, 120px) minmax(120px, 140px) auto; align-items: start; }
    .reading-target { display: grid; grid-template-columns: minmax(260px, 1fr) auto auto minmax(220px, 1fr); gap: 8px; align-items: end; }
    label { display: grid; gap: 4px; font-size: 12px; color: var(--muted); }
    .label-row { display: inline-flex; align-items: center; gap: 4px; min-height: 16px; }
    .help { display: inline-grid; place-items: center; width: 16px; height: 16px; border: 1px solid var(--line); border-radius: 50%; color: var(--muted); background: #fff; font-size: 11px; line-height: 1; cursor: help; position: relative; }
    .floating-tip { position: fixed; left: 0; top: 0; display: none; max-width: 320px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 6px; background: #172033; color: #fff; font-size: 12px; line-height: 1.45; z-index: 20; box-shadow: 0 8px 20px rgba(15, 23, 42, 0.18); }
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
    .summary-bar { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 12px; }
    .summary-bar .stats { margin-bottom: 0; }
    .graph-layout { display: grid; grid-template-columns: minmax(260px, 320px) minmax(460px, 1.6fr) minmax(280px, 0.9fr); gap: 12px; align-items: start; }
    .graph-toolbar { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(120px, 150px) auto; gap: 8px; align-items: end; }
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
    .muted { color: var(--muted); }
    .actions { display: flex; gap: 4px; flex-wrap: wrap; min-width: 300px; }
    .actions button { height: 28px; font-size: 12px; padding: 0 6px; }
    .status-unread { color: #b45309; font-weight: 600; }
    .status-reading { color: #1d4ed8; font-weight: 600; }
    .status-read { color: #15803d; font-weight: 600; }
    .status-reread_needed { color: #be123c; font-weight: 600; }
    .toast { position: fixed; right: 16px; bottom: 16px; background: #172033; color: #fff; padding: 10px 12px; border-radius: 6px; display: none; max-width: 520px; }
    @media (max-width: 1200px) { .graph-layout { grid-template-columns: 1fr; } }
    @media (max-width: 1000px) { .filters, .run-grid, .reading-filters, .reading-target, .graph-toolbar { grid-template-columns: repeat(2, minmax(120px, 1fr)); } .summary-bar { align-items: stretch; flex-direction: column; } }
  </style>
</head>
<body>
  <header>
    <h1>DocTriage 控制台</h1>
    <div class="tabs">
      <button id="tab-analysis" class="tab active" onclick="switchTab('analysis')">分析执行</button>
      <button id="tab-reading" class="tab" onclick="switchTab('reading')">阅读台</button>
      <button id="tab-graph" class="tab" onclick="switchTab('graph')">关系图谱</button>
    </div>
  </header>
  <main>
    <section id="section-analysis" class="active">
      <div class="panel">
        <div class="run-grid">
          <label><span class="label-row">源目录 <span class="help" tabindex="0" data-tip="待分析的原始文档目录。程序会递归扫描其下支持的文件类型。不要把输出目录放到这个目录里面。">?</span></span><input id="run_source_dir" placeholder="请选择源文档目录" /></label>
          <button id="pick_source_btn" onclick="pickFolder('run_source_dir')">选择源目录</button>
          <label><span class="label-row">输出目录 <span class="help" tabindex="0" data-tip="写入进度、日志、评分结果和可选复制结果的目录。同一输出目录会自动续跑；同一时间只允许一个分析进程写入。">?</span></span><input id="run_output_root" placeholder="请选择输出目录" /></label>
          <button id="pick_output_btn" onclick="pickFolder('run_output_root')">选择输出目录</button>
          <label><span class="label-row">LLM Endpoint <span class="help" tabindex="0" data-tip="文档评分调用的文本模型接口。Ollama 默认是 /api/generate；如果你切换服务地址，这里要一起改。">?</span></span><input id="run_llm_endpoint" value="http://localhost:11434/api/generate" /></label>
          <label><span class="label-row">模型 <span class="help" tabindex="0" data-tip="用于文档分类、打分和摘要理解的模型名。关系挖掘若开启 embedding，但未单独指定 embedding 模型，也会回退使用这里的模型名。">?</span></span><input id="run_llm_model" value="gemma4:e4b" /></label>
          <label class="advanced-run"><span class="label-row">并发 <span class="help" tabindex="0" data-tip="同时向 LLM 发起的请求数。大目录和本地模型首跑建议 1；模型空闲且显存足够时再逐步上调。">?</span></span><input id="run_concurrency" type="number" value="1" min="1" max="64" /></label>
          <label class="advanced-run"><span class="label-row">Limit <span class="help" tabindex="0" data-tip="只处理前 N 个候选文件，适合小样本验证提示词、速度和分类效果。留空表示全量。">?</span></span><input id="run_limit" type="number" min="1" placeholder="空为全量" /></label>
          <label class="advanced-run"><span class="label-row">最大 MB <span class="help" tabindex="0" data-tip="跳过超过这个体积的候选文件，避免极大 PDF 或 Office 文档拖慢首轮筛选。">?</span></span><input id="run_max_file_size_mb" type="number" value="80" min="1" /></label>
          <label class="advanced-run"><span class="label-row">质量阈值 <span class="help" tabindex="0" data-tip="达到这个分数的文档会被视为高价值候选。plan-only 模式下主要影响目标分类路径和后续筛选。">?</span></span><input id="run_quality_threshold" type="number" value="75" min="0" max="100" /></label>
          <label class="advanced-run"><span class="label-row">超时秒 <span class="help" tabindex="0" data-tip="单个 LLM 请求最长等待时间。模型较慢或文档较大时可以调高；过高会让失败请求卡更久。">?</span></span><input id="run_timeout_seconds" type="number" value="240" min="5" /></label>
          <label class="advanced-run"><span class="label-row">摘要 <span class="help" tabindex="0" data-tip="把本地短摘要写入 decisions.jsonl，后续做关系挖掘、公开写作筛选和人工复核时更有用。会多占一点状态文件空间。">?</span></span><input id="run_document_summary" type="checkbox" checked /></label>
          <label class="advanced-run"><span class="label-row">Plan only <span class="help" tabindex="0" data-tip="只写评分、分类、进度和决策日志，不复制源文件。适合首轮摸底、大目录试跑和不想改动文件布局的场景。">?</span></span><input id="run_plan_only" type="checkbox" checked /></label>
          <label class="advanced-run"><span class="label-row">No OCR <span class="help" tabindex="0" data-tip="关闭 OCR。对有文本层的 PDF 和 Office 文档更快；纯图片或扫描版 PDF 可能提取不到正文。建议首轮勾选，后续对扫描件分批取消。">?</span></span><input id="run_no_ocr" type="checkbox" checked /></label>
          <label class="advanced-run"><span class="label-row">跳过 Manifest <span class="help" tabindex="0" data-tip="跳过目录级系列/集合分析，直接进入文件级评分。大目录首跑通常建议开启，先拿到全局评分结果。">?</span></span><input id="run_skip_manifest" type="checkbox" checked /></label>
          <label class="advanced-run"><span class="label-row">本地 LLM <span class="help" tabindex="0" data-tip="要求评分模型端点必须是本机地址。适合你只想用本地 Ollama，不接受误连远端服务的场景。">?</span></span><input id="run_require_local_llm" type="checkbox" checked /></label>
          <label class="advanced-run"><span class="label-row">强制重跑 <span class="help" tabindex="0" data-tip="忽略已处理记录，按当前参数重新处理匹配文件。适合你调整模型、阈值或提示词后重算。">?</span></span><input id="run_force_reprocess" type="checkbox" /></label>
          <label class="advanced-run"><span class="label-row">内容 Hash <span class="help" tabindex="0" data-tip="变更检测除了时间和大小，还计算文件内容哈希。更准，但大目录和大文件会更慢。">?</span></span><input id="run_content_hash" type="checkbox" /></label>
          <label class="advanced-run"><span class="label-row">挖掘关系 <span class="help" tabindex="0" data-tip="在全部评分完成后，额外生成文档关系和聚类结果，输出到 _relationships/relations.jsonl 与 clusters.json。适合做去重、系列识别、主题聚类和后续 RAG 分组。">?</span></span><input id="run_mine_relationships" type="checkbox" /></label>
          <label class="advanced-run"><span class="label-row">标题引用 <span class="help" tabindex="0" data-tip="启用轻量标题/路径引用信号，不额外调用 embedding 模型。成本低，适合默认开启，帮助发现同系列、互相提及或命名相近的文档。">?</span></span><input id="run_relationship_text" type="checkbox" /></label>
          <label class="advanced-run"><span class="label-row">Embedding 关系 <span class="help" tabindex="0" data-tip="给摘要、标题、类别等文本生成向量，用语义相似度找跨目录同主题、标题不相似但内容接近、近重复或演进关系。更耗时、也更吃模型资源。建议在首轮评分稳定后、关系质量比速度更重要时再勾选。">?</span></span><div class="toggle-inline"><input id="run_relationship_embeddings" type="checkbox" onchange="syncEmbeddingModelVisibility()" /><input id="run_embedding_model" type="text" placeholder="EMBEDDING_MODEL，可留空沿用主模型" style="display:none;" disabled /></div></label>
        </div>
        <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
          <select id="run_template">
            <option value="">选择模板</option>
            <option value="sample">小样本试跑</option>
            <option value="overnight">过夜全量</option>
            <option value="relationships">评分+关系挖掘</option>
            <option value="strict">严格小样本重跑</option>
          </select>
          <button onclick="applyTemplate()">应用模板</button>
          <button id="toggle_advanced_btn" onclick="toggleAdvancedRunOptions()">显示高级参数</button>
          <button onclick="applyPaths()">应用路径</button>
          <button id="start_analysis_btn" class="primary" onclick="startAnalysis()">开始分析</button>
          <button onclick="loadAnalysis()">刷新状态</button>
          <button id="stop_analysis_btn" class="danger" onclick="stopAnalysis()">停止分析</button>
          <button id="reset_analysis_btn" class="danger" onclick="resetAnalysis()">重置分析</button>
        </div>
      </div>
      <div class="panel">
        <div id="analysisStats" class="stats"></div>
        <div class="progress"><div id="analysisBar"></div></div>
        <pre id="analysisLog"></pre>
        <div id="runHistory" class="stats"></div>
      </div>
    </section>
    <section id="section-reading">
      <div class="panel reading-target">
        <label>阅读目标输出目录 <input id="reading_output_root" placeholder="选择或输入已分析输出目录" /></label>
        <button id="pick_reading_output_btn" onclick="pickFolder('reading_output_root')">选择目录</button>
        <button onclick="applyReadingOutput()">应用阅读目录</button>
        <span class="muted">运行中时默认回填当前任务输出目录；切换阅读目录不会中断分析。</span>
      </div>
      <div class="panel filters reading-filters">
        <label>状态
          <select id="status">
            <option value="">全部</option>
            <option value="unread">未读</option>
            <option value="reading">在读</option>
            <option value="read">已读</option>
            <option value="reread_needed">需重读</option>
            <option value="skipped">跳过</option>
            <option value="deferred">稍后</option>
          </select>
        </label>
        <label>最低质量 <input id="min_quality" type="number" value="80" min="0" max="100" /></label>
        <label>分类
          <select id="categories" multiple></select>
          <span class="multi-actions"><button onclick="selectMulti('categories', true)">全选</button><button onclick="invertMulti('categories')">反选</button></span>
        </label>
        <label>关键词
          <select id="topic_tags" multiple></select>
          <span class="multi-actions"><button onclick="selectMulti('topic_tags', true)">全选</button><button onclick="invertMulti('topic_tags')">反选</button></span>
        </label>
        <label>搜索 <input id="q" placeholder="名称/路径/备注" /></label>
        <label>最高敏感 <input id="max_sensitivity_risk" type="number" min="0" max="100" /></label>
        <label>最低公开适配 <input id="min_public_writing_suitability" type="number" min="0" max="100" /></label>
        <button class="primary" onclick="loadRows()">刷新</button>
      </div>
      <div class="summary-bar">
        <div id="stats" class="stats"></div>
        <div id="pagerTop" class="pager"></div>
      </div>
      <div class="panel" style="display:flex; gap:8px; flex-wrap:wrap;">
        <button onclick="toggleAllRows(true)">全选当前页</button>
        <button onclick="toggleAllRows(false)">取消选择</button>
        <button onclick="bulkMark('reading')">批量在读</button>
        <button onclick="bulkMark('read')">批量已读</button>
        <button onclick="bulkMark('deferred')">批量稍后</button>
        <button onclick="bulkMark('skipped')">批量跳过</button>
        <button onclick="bulkMark('unread')">批量未读</button>
        <button class="primary" onclick="openNextVisible()">打开下一篇</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>选择</th>
              <th><button class="th-sort" onclick="setSort('status')">状态 <span class="sort-mark" data-sort-mark="status"></span></button></th>
              <th><button class="th-sort" onclick="setSort('quality')">质量 <span class="sort-mark" data-sort-mark="quality"></span></button></th>
              <th><button class="th-sort" onclick="setSort('category')">分类 <span class="sort-mark" data-sort-mark="category"></span></button></th>
              <th><button class="th-sort" onclick="setSort('document_kind')">类型 <span class="sort-mark" data-sort-mark="document_kind"></span></button></th>
              <th><button class="th-sort" onclick="setSort('sensitivity')">敏感/公开 <span class="sort-mark" data-sort-mark="sensitivity"></span></button></th>
              <th><button class="th-sort" onclick="setSort('path')">名称 <span class="sort-mark" data-sort-mark="path"></span></button></th>
              <th>标签</th>
              <th>操作</th>
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
          <label>簇搜索 <input id="graph_q" placeholder="路径/分类/标签" /></label>
          <label>最小簇大小 <input id="graph_min_size" type="number" min="2" value="2" /></label>
          <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
            <button id="graph_mine_btn" class="primary" onclick="startGraphTask('mine')">生成关系结果</button>
            <button id="graph_export_graph_btn" onclick="startGraphTask('export_graph')">导出知识图谱</button>
            <button id="graph_export_bundle_btn" onclick="startGraphTask('export_bundle')">导出 Bundle</button>
            <button onclick="loadGraph()">刷新图谱</button>
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
    let allRows = [];
    let filteredRows = [];
    let currentRows = [];
    let capabilities = {};
    let currentPage = 1;
    let pageSize = Number(localStorage.getItem("doctriage_page_size") || 100);
    let sortKey = localStorage.getItem("doctriage_reading_sort") || "quality_desc";
    let graphMeta = {};
    let graphClusters = [];
    let filteredGraphClusters = [];
    let graphSelectedClusterId = null;
    let graphClusterData = null;
    let graphSelectedDocPath = "";
    let tooltipTarget = null;

    function params() {
      const pairs = new URLSearchParams();
      pairs.set("sort", sortKey);
      return pairs.toString();
    }

    function switchTab(name) {
      for (const id of ["analysis", "reading", "graph"]) {
        $("tab-" + id).classList.toggle("active", id === name);
        $("section-" + id).classList.toggle("active", id === name);
      }
      if (name === "analysis") loadAnalysis();
      if (name === "reading") {
        if ($("run_output_root").value.trim()) loadRows();
      }
      if (name === "graph") {
        if ($("run_output_root").value.trim()) loadGraph();
        else clearGraphState("请先应用源目录和输出目录");
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
      for (const id of ["pick_source_btn", "pick_output_btn", "pick_reading_output_btn"]) {
        if ($(id)) {
          $(id).disabled = capabilities.folder_picker === false;
          $(id).title = capabilities.folder_picker === false ? "当前环境不支持图形目录选择，请手工输入路径" : "";
        }
      }
      if (capabilities.headless_hint) {
        showToast(capabilities.headless_hint);
      }
      loadAnalysis();
    }

    async function pickFolder(targetId) {
      const response = await fetch("/api/pick-folder", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({target: targetId})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "选择失败");
      if (payload.path) $(targetId).value = payload.path;
    }

    async function applyPaths() {
      const response = await fetch("/api/paths", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          source_dir: $("run_source_dir").value.trim(),
          output_root: $("run_output_root").value.trim()
        })
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "路径应用失败");
      showToast("路径已应用");
      loadAnalysis();
      loadRows();
      if ($("section-graph").classList.contains("active")) loadGraph();
    }

    async function applyReadingOutput() {
      const outputRoot = $("reading_output_root").value.trim();
      if (!outputRoot) return showToast("请先输入阅读目标输出目录");
      $("run_output_root").value = outputRoot;
      const response = await fetch("/api/reading-output", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({output_root: outputRoot})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "阅读目录应用失败");
      if (payload.source_dir) $("run_source_dir").value = payload.source_dir;
      if (payload.output_root) $("run_output_root").value = payload.output_root;
      showToast("阅读目录已应用");
      loadRows();
      if ($("section-graph").classList.contains("active")) loadGraph();
    }

    function runPayload() {
      return {
        source_dir: $("run_source_dir").value.trim(),
        output_root: $("run_output_root").value.trim(),
        llm_endpoint: $("run_llm_endpoint").value.trim(),
        llm_model: $("run_llm_model").value.trim(),
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
        require_local_llm: $("run_require_local_llm").checked,
        force_reprocess: $("run_force_reprocess").checked,
        content_hash: $("run_content_hash").checked,
        mine_relationships: $("run_mine_relationships").checked,
        relationship_use_text_citations: $("run_relationship_text").checked,
        relationship_use_embeddings: $("run_relationship_embeddings").checked,
        template: $("run_template").value
      };
    }

    function syncEmbeddingModelVisibility() {
      const enabled = $("run_relationship_embeddings").checked;
      $("run_embedding_model").style.display = enabled ? "" : "none";
      $("run_embedding_model").disabled = !enabled;
    }

    function setAdvancedRunOptionsVisible(visible) {
      document.querySelectorAll(".advanced-run").forEach(item => item.style.display = visible ? "grid" : "none");
      $("toggle_advanced_btn").textContent = visible ? "隐藏高级参数" : "显示高级参数";
      localStorage.setItem("doctriage_run_advanced", visible ? "1" : "0");
    }

    function toggleAdvancedRunOptions() {
      const visible = localStorage.getItem("doctriage_run_advanced") === "1";
      setAdvancedRunOptionsVisible(!visible);
    }

    function applyTemplate() {
      const name = $("run_template").value;
      if (!name) return;
      $("run_concurrency").value = "1";
      $("run_limit").value = "";
      $("run_max_file_size_mb").value = "80";
      $("run_quality_threshold").value = "75";
      $("run_timeout_seconds").value = "240";
      $("run_document_summary").checked = true;
      $("run_plan_only").checked = true;
      $("run_no_ocr").checked = true;
      $("run_skip_manifest").checked = true;
      $("run_require_local_llm").checked = true;
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
      showToast("已应用模板");
    }

    async function startAnalysis() {
      const response = await fetch("/api/analysis/start", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(runPayload())
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "启动失败");
      showToast("已启动分析");
      loadAnalysis();
    }

    async function stopAnalysis() {
      const response = await fetch("/api/analysis/stop", {method: "POST"});
      const payload = await response.json();
      showToast(response.ok ? "已请求停止" : (payload.error || "停止失败"));
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

    function clearGraphState(message = "暂无关系结果") {
      graphMeta = {};
      graphClusters = [];
      filteredGraphClusters = [];
      graphSelectedClusterId = null;
      graphClusterData = null;
      graphSelectedDocPath = "";
      $("graphStats").innerHTML = `<span class="pill">${escapeHtml(message)}</span>`;
      $("graphTaskStats").innerHTML = "";
      $("graphClusters").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
      $("graphClusterTitle").innerHTML = "";
      $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
      $("graphEdges").innerHTML = "";
      $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
    }

    async function resetAnalysis() {
      const sourceDir = $("run_source_dir").value.trim();
      const outputRoot = $("run_output_root").value.trim();
      if (!sourceDir || !outputRoot) return showToast("请先应用源目录和输出目录");
      if (!window.confirm(`将清空输出目录中的日志、状态、关系结果和已分类文件：\n${outputRoot}\n\n该操作不可恢复，确认继续？`)) return;
      const response = await fetch("/api/analysis/reset", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({source_dir: sourceDir, output_root: outputRoot})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "重置失败");
      clearReadingRows();
      clearGraphState("输出目录已重置");
      showToast("已重置输出目录");
      loadAnalysis();
    }

    async function loadAnalysis() {
      const response = await fetch("/api/analysis/status");
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "状态加载失败");
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
      const phaseText = payload.phase === "文档评分中" ? "" : (payload.phase || "");
      const rateReady = !!progress.rate_window_active && Number(progress.rate_window_completed || 0) > 0;
      const parts = [
        phaseText,
        payload.running ? "运行中" : "未运行",
        payload.pid ? "PID " + payload.pid : "",
        progress.percent !== undefined ? `进度 ${progress.percent}%` : "",
        progress.completed !== undefined ? `完成 ${progress.completed}/${progress.total || 0}` : "",
        rateReady && progress.eta_human && progress.eta_human !== "unknown" ? `ETA ${progress.eta_human}` : (payload.running ? "ETA 等待连续规划" : ""),
        rateReady && progress.files_per_minute !== undefined && Number(progress.files_per_minute) > 0 ? `速度 ${progress.files_per_minute}/min` : (payload.running ? "速度等待连续规划" : ""),
        unresolvedFailures > 0 ? `未解决失败 ${unresolvedFailures}` : "",
        retryAttempted > 0 ? `重试恢复 ${retrySucceeded}/${retryAttempted}` : "",
        lock.exists && !lock.active && lock.pid ? `陈旧锁 PID ${lock.pid}` : "",
        latest.label ? `${latest.label}: ${shortText(latest.detail || "", 72)}` : ""
      ].filter(Boolean);
      $("analysisStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
      $("analysisBar").style.width = Math.max(0, Math.min(100, Number(progress.percent || 0))) + "%";
      $("analysisLog").textContent = payload.log_tail || "";
      $("start_analysis_btn").disabled = !!payload.running;
      $("stop_analysis_btn").disabled = !payload.running;
      $("reset_analysis_btn").disabled = !!payload.running;
      const history = payload.run_history || [];
      $("runHistory").innerHTML = history.slice(-6).reverse().map(item =>
        `<span class="pill">${escapeHtml((item.started_at || '').replace('T',' ').slice(0,19))} PID ${escapeHtml(item.pid || '')} ${escapeHtml(item.template || '')}</span>`
      ).join("");
    }

    function shortText(value, maxLength) {
      const text = String(value || "");
      return text.length <= maxLength ? text : text.slice(0, maxLength - 1) + "…";
    }

    async function loadRows() {
      const response = await fetch("/api/state?" + params());
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "加载失败");
      allRows = payload.rows || [];
      populateFacetOptions(allRows);
      currentPage = 1;
      applyClientFilters();
    }

    function syncReadingTarget(payload) {
      if (!payload) return;
      if (payload.source_dir) $("run_source_dir").value = payload.source_dir;
      if (payload.output_root && (payload.running || !$("reading_output_root").value.trim())) {
        $("reading_output_root").value = payload.output_root;
        $("run_output_root").value = payload.output_root;
      }
    }

    async function loadGraph(preserveSelection = true) {
      if (!$("run_output_root").value.trim()) {
        clearGraphState("请先应用源目录和输出目录");
        return;
      }
      const response = await fetch("/api/relationships");
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "图谱加载失败");
      graphMeta = payload;
      graphClusters = payload.clusters || [];
      renderGraphStats(payload);
      renderGraphTaskStats(payload);
      applyGraphFilters(preserveSelection);
    }

    function renderGraphStats(payload) {
      const parts = [];
      if (payload.cluster_count !== undefined) parts.push(`簇 ${payload.cluster_count}`);
      if (payload.relations_exists) parts.push("存在 relations.jsonl");
      if (payload.clusters_exists) parts.push("存在 clusters.json");
      if (payload.decisions_exists) parts.push("存在 decisions.jsonl");
      if (!payload.available) parts.push("暂无关系结果");
      $("graphStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
    }

    function graphTaskKindLabel(kind) {
      return {
        mine: "关系结果生成",
        export_graph: "知识图谱导出",
        export_bundle: "Bundle 导出"
      }[kind] || kind || "";
    }

    function renderGraphTaskStats(payload) {
      const task = payload.task || {};
      const parts = [];
      if (task.running) parts.push(`${graphTaskKindLabel(task.kind)}中`);
      if (task.pid) parts.push(`PID ${task.pid}`);
      if (!payload.decisions_exists) {
        parts.push("先完成至少一次文档分析");
      } else if (!payload.relations_exists && !task.running) {
        parts.push("可直接生成关系结果");
      }
      $("graphTaskStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
      $("graph_mine_btn").disabled = !!task.running || !payload.decisions_exists;
      $("graph_export_graph_btn").disabled = !!task.running || !payload.relations_exists;
      $("graph_export_bundle_btn").disabled = !!task.running || !payload.relations_exists;
    }

    async function startGraphTask(taskName) {
      if (!$("run_source_dir").value.trim() || !$("run_output_root").value.trim()) {
        return showToast("请先应用源目录和输出目录");
      }
      const response = await fetch(`/api/relationships/${taskName.replace("_", "-")}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(runPayload())
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "关系任务启动失败");
      showToast(`已启动${payload.label || graphTaskKindLabel(taskName)}`);
      loadGraph();
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
        const message = graphClusters.length ? "没有匹配的关系簇" : graphEmptyMessage(graphMeta);
        $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
        $("graphEdges").innerHTML = "";
        $("graphClusterTitle").innerHTML = "";
        $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(graphDetailEmptyMessage(graphMeta))}</div>`;
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
      const response = await fetch("/api/relationships?cluster=" + encodeURIComponent(String(clusterId)));
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "关系簇加载失败");
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
          <div class="graph-cluster-title">簇 ${cluster.cluster_id + 1} · ${cluster.size} 篇</div>
          <div class="graph-cluster-preview">${escapeHtml((cluster.categories || []).join(", ") || "未分类")}</div>
          <div class="graph-cluster-preview">${escapeHtml((cluster.preview_paths || []).join(" / ") || "无预览路径")}</div>
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
      const categories = (graphClusterData.categories || []).join(", ") || "未分类";
      $("graphClusterTitle").innerHTML = [
        `<span class="pill">簇 ${graphClusterData.cluster_id + 1}</span>`,
        `<span class="pill">${graphClusterData.size} 篇</span>`,
        `<span class="pill">${graphClusterData.edge_count} 条边</span>`,
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
        $("graphCanvas").innerHTML = `<div class="graph-empty">这个关系簇没有可展示的文档</div>`;
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
        $("graphEdges").innerHTML = `<div class="graph-empty">当前文档没有可展示的关系边</div>`;
        return;
      }
      $("graphEdges").innerHTML = edges.map(edge => {
        const title = `${graphDisplayName(edge.left_path)} ↔ ${graphDisplayName(edge.right_path)}`;
        const signals = (edge.signals || []).join(", ") || "无显式信号";
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
      if (task.running) return `${graphTaskKindLabel(task.kind)}中，请稍后刷新`;
      if (payload && !payload.decisions_exists) return "先完成一次文档分析，再生成关系图谱";
      if (payload && payload.decisions_exists && !payload.relations_exists) return "还没有关系结果，可点击“生成关系结果”";
      return "暂无关系结果";
    }

    function graphDetailEmptyMessage(payload) {
      const task = (payload && payload.task) || {};
      if (task.running) return "后台任务运行中，完成后这里会显示局部图和证据。";
      if (payload && payload.decisions_exists && !payload.relations_exists) return "生成关系结果后，这里会显示局部图、证据和文档详情。";
      return "选择一个关系簇查看文档详情";
    }

    async function graphMarkDoc(relativePath, status) {
      await markDoc(relativePath, status);
      if (graphSelectedClusterId !== null) {
        await loadGraphCluster(graphSelectedClusterId, true);
      }
    }

    function renderGraphDetail() {
      if (!graphClusterData || !graphClusterData.files || !graphClusterData.files.length) {
        $("graphDocDetail").innerHTML = `<div class="graph-empty">选择一个关系簇查看文档详情</div>`;
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
            <span class="pill">敏感 ${selected.sensitivity_risk}</span>
            <span class="pill">公开 ${selected.public_writing_suitability}</span>
          </div>
          <p class="muted">${escapeHtml(selected.summary || "无摘要")}</p>
          <div class="graph-actions">
            <button ${capabilities.open_file === false ? "disabled" : ""} onclick='openDoc(${JSON.stringify(selected.relative_path)})'>打开</button>
            <button ${capabilities.reveal_file === false ? "disabled" : ""} onclick='revealDoc(${JSON.stringify(selected.relative_path)})'>定位</button>
            <button onclick='graphMarkDoc(${JSON.stringify(selected.relative_path)}, "reading")'>在读</button>
            <button onclick='graphMarkDoc(${JSON.stringify(selected.relative_path)}, "read")'>已读</button>
            <button onclick='graphMarkDoc(${JSON.stringify(selected.relative_path)}, "deferred")'>稍后</button>
          </div>
        </div>
        <div class="graph-detail-card">
          <div class="graph-cluster-title">关联文档</div>
          ${relatedEdges.length ? relatedEdges.map(edge => {
            const neighbor = graphNeighborPath(edge, selected.relative_path);
            return `
              <div style="display:grid; gap:4px; margin-top:8px;">
                <button class="graph-cluster-item" style="padding:8px;" onclick='selectGraphDoc(${JSON.stringify(neighbor)})'>
                  <div class="graph-cluster-title">${escapeHtml(graphDisplayName(neighbor))}</div>
                  <div class="muted">score ${edge.relation_score} · ${escapeHtml((edge.signals || []).join(", ") || "无显式信号")}</div>
                </button>
              </div>
            `;
          }).join("") : `<div class="muted" style="margin-top:8px;">当前文档没有命中的关系边</div>`}
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
      const parts = [`匹配 ${rows.length} / 全部 ${totalCount}`];
      for (const key of ["unread","reading","read","reread_needed","skipped","deferred"]) {
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
        <button onclick="setPage(1)" ${currentPage <= 1 ? "disabled" : ""}>首页</button>
        <button onclick="setPage(${currentPage - 1})" ${currentPage <= 1 ? "disabled" : ""}>上一页</button>
        <span>第 <input value="${currentPage}" onchange="setPage(Number(this.value))" /> / ${pageCount} 页</span>
        <button onclick="setPage(${currentPage + 1})" ${currentPage >= pageCount ? "disabled" : ""}>下一页</button>
        <button onclick="setPage(${pageCount})" ${currentPage >= pageCount ? "disabled" : ""}>末页</button>
        <label style="display:inline-flex; align-items:center; gap:4px;">数量 <input value="${pageSize}" min="1" onchange="setPageSize(Number(this.value))" /></label>`;
      $("pagerTop").innerHTML = html;
      $("pagerBottom").innerHTML = html;
    }

    function rowMatchesFilters(row) {
      const status = $("status").value;
      if (status && row.status !== status) return false;
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

      const q = $("q").value.trim().toLowerCase();
      if (q) {
        const haystack = [
          row.relative_path || "",
          row.category || "",
          row.document_kind || "",
          (row.topic_tags || []).join(" "),
          row.note || ""
        ].join(" ").toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
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
        path: sortKey === "path_asc" ? "path_desc" : "path_asc",
        category: sortKey === "category_asc" ? "category_desc" : "category_asc",
        status: sortKey === "status_asc" ? "status_desc" : "status_asc",
        document_kind: sortKey === "kind_asc" ? "kind_desc" : "kind_asc",
        sensitivity: sortKey === "sensitivity_asc" ? "sensitivity_desc" : "sensitivity_asc",
        public: sortKey === "public_desc" ? "public_asc" : "public_desc"
      };
      sortKey = next[field] || "quality_desc";
      localStorage.setItem("doctriage_reading_sort", sortKey);
      currentPage = 1;
      applyClientFilters();
    }

    function sortRowsClient(rows, key) {
      const sorted = [...rows];
      const text = value => String(value || "").toLowerCase();
      const num = value => Number(value || 0);
      const comparators = {
        quality_desc: (a, b) => num(b.quality) - num(a.quality) || text(a.relative_path).localeCompare(text(b.relative_path)),
        quality_asc: (a, b) => num(a.quality) - num(b.quality) || text(a.relative_path).localeCompare(text(b.relative_path)),
        path_asc: (a, b) => text(a.relative_path).localeCompare(text(b.relative_path)),
        path_desc: (a, b) => text(b.relative_path).localeCompare(text(a.relative_path)),
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
        category_asc: ["category", "↑"],
        category_desc: ["category", "↓"],
        status_asc: ["status", "↑"],
        status_desc: ["status", "↓"],
        kind_asc: ["document_kind", "↑"],
        kind_desc: ["document_kind", "↓"],
        sensitivity_asc: ["sensitivity", "↑"],
        sensitivity_desc: ["sensitivity", "↓"],
        public_desc: ["sensitivity", "公开↓"],
        public_asc: ["sensitivity", "公开↑"]
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

    function renderRows(rows) {
      $("rows").innerHTML = rows.map(row => `
        <tr>
          <td><input type="checkbox" class="rowcheck" value="${escapeHtml(row.relative_path)}" /></td>
          <td class="status-${escapeAttr(row.status)}">${labelStatus(row.status)}</td>
          <td>${row.quality}</td>
          <td>${escapeHtml(row.category)}</td>
          <td>${escapeHtml(row.document_kind || "")}</td>
          <td>${row.sensitivity_risk} / ${row.public_writing_suitability}</td>
          <td class="name">
            <span class="doc-name ${row.summary ? "has-summary" : ""}" tabindex="${row.summary ? "0" : "-1"}" data-tip="${escapeAttrValue(row.summary || "")}">${escapeHtml(row.relative_path || "")}</span>
            ${row.note ? `<br><span class="muted">${escapeHtml(row.note)}</span>` : ""}
          </td>
          <td>${escapeHtml((row.topic_tags || []).join(", "))}</td>
          <td class="actions">
            <button ${capabilities.open_file === false ? "disabled title='当前环境不支持调用系统默认阅读器'" : ""} onclick='openDoc(${JSON.stringify(row.relative_path)})'>打开</button>
            <button ${capabilities.reveal_file === false ? "disabled title='当前环境不支持文件管理器定位'" : ""} onclick='revealDoc(${JSON.stringify(row.relative_path)})'>定位</button>
            <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "reading")'>在读</button>
            <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "read")'>已读</button>
            <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "deferred")'>稍后</button>
            <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "skipped")'>跳过</button>
            <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "unread")'>未读</button>
          </td>
        </tr>`).join("");
      bindSummaryTooltips();
    }

    async function markDoc(relativePath, status) {
      const note = status === "read" ? "" : "";
      const response = await fetch("/api/mark", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({relative_path: relativePath, status, note})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "标记失败");
      showToast("已标记：" + labelStatus(status));
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
      if (!paths.length) return showToast("请先选择文档");
      const response = await fetch("/api/mark-batch", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({relative_paths: paths, status})
      });
      const payload = await response.json();
      if (!response.ok) return showToast(payload.error || "批量标记失败");
      showToast(`已批量标记 ${payload.count || 0} 篇`);
      loadRows();
    }

    function openNextVisible() {
      const row = currentRows.find(item => item.status === "unread" || item.status === "reread_needed") || currentRows[0];
      if (!row) return showToast("当前列表为空");
      openDoc(row.relative_path);
    }

    async function openDoc(relativePath) {
      await postAction("/api/open", relativePath, "已请求打开");
    }

    async function revealDoc(relativePath) {
      await postAction("/api/reveal", relativePath, "已请求定位");
    }

    async function postAction(url, relativePath, okText) {
      const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({relative_path: relativePath})
      });
      const payload = await response.json();
      showToast(response.ok ? okText : (payload.error || "操作失败"));
    }

    function labelStatus(status) {
      return {
        unread: "未读",
        reading: "在读",
        read: "已读",
        reread_needed: "需重读",
        skipped: "跳过",
        deferred: "稍后"
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
    initHelpTooltips();
    setAdvancedRunOptionsVisible(localStorage.getItem("doctriage_run_advanced") === "1");
    syncEmbeddingModelVisibility();
    clearGraphState();
    loadConfig();
    switchTab(localStorage.getItem("doctriage_tab") || "analysis");
    setInterval(() => {
      if ($("section-analysis").classList.contains("active")) loadAnalysis();
      if ($("section-graph").classList.contains("active")) loadGraph();
    }, 3000);
  </script>
</body>
</html>
"""


def build_state_payload(paths: ReadingPaths, query: dict[str, str]) -> dict[str, Any]:
    decisions = load_latest_decisions(paths.decisions_path)
    events = load_latest_reading_events(paths.reading_status_path)
    rows = build_reading_rows(decisions, events)
    status_counts = count_by(rows, "status")
    filtered = filter_rows(
        rows,
        status=query.get("status") or None,
        min_quality=parse_int(query.get("min_quality"), 0),
        categories=parse_categories(query.get("categories")),
        max_sensitivity_risk=parse_optional_int(query.get("max_sensitivity_risk")),
        min_public_writing_suitability=parse_optional_int(
            query.get("min_public_writing_suitability")
        ),
    )
    q = (query.get("q") or "").strip().lower()
    if q:
        filtered = [row for row in filtered if row_matches_query(row, q)]
    filtered = sort_rows(filtered, query.get("sort") or "quality_desc")

    filtered_count = len(filtered)
    page_size = parse_optional_int(query.get("page_size") or query.get("limit"))
    page = max(1, parse_int(query.get("page"), 1))
    limit = parse_optional_int(query.get("limit"))
    if limit is not None:
        filtered = filtered[:limit]

    return {
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
        "task": relationship_task_status(app_state),
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
                "target_path": str(row.get("target_path") or decision.get("target_path") or ""),
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


def relationship_task_status(app_state: AppState) -> dict[str, Any]:
    with app_state.lock:
        process = app_state.relationship_process
        kind = app_state.relationship_process_kind
        command = app_state.relationship_process_command
        running = process is not None and process.poll() is None
        pid = process.pid if process is not None else None
        return_code = None if process is None else process.poll()
        if process is not None and process.poll() is not None:
            app_state.relationship_process = None
            app_state.relationship_process_kind = None
            app_state.relationship_process_command = None
    return {
        "running": running,
        "pid": pid,
        "kind": kind,
        "command": command,
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
        if bool(payload.get("require_local_llm")):
            command.append("--require-local-llm")
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
    source_dir, output_root = resolve_payload_paths(payload)
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
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
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        app_state.paths = paths
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
            str(row.get("category") or ""),
            str(row.get("document_kind") or ""),
            " ".join(str(tag) for tag in row.get("topic_tags") or []),
            str(row.get("note") or ""),
        ]
    ).lower()
    return q in haystack


def sort_rows(rows: list[dict[str, Any]], sort_key: str) -> list[dict[str, Any]]:
    key_map = {
        "quality_desc": lambda row: (-int(row.get("quality") or 0), row.get("relative_path") or ""),
        "quality_asc": lambda row: (int(row.get("quality") or 0), row.get("relative_path") or ""),
        "path_asc": lambda row: (str(row.get("relative_path") or ""),),
        "path_desc": lambda row: (str(row.get("relative_path") or ""),),
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
        "category_desc",
        "status_desc",
        "kind_desc",
        "sensitivity_desc",
    }
    return sorted(rows, key=key_func, reverse=reverse)


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
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        app_state.process = process
        app_state.process_command = command
        run_record = append_run_history(
            output_root,
            {
                "run_id": uuid.uuid4().hex,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "pid": process.pid,
                "template": str(payload.get("template") or ""),
                "source_dir": str(source_dir),
                "output_root": str(output_root),
                "command": command,
            },
        )
        return {
            "started": True,
            "pid": process.pid,
            "run_id": run_record["run_id"],
            "command": command,
            "source_dir": str(source_dir),
            "output_root": str(output_root),
        }


def set_active_paths(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    source_dir, output_root = resolve_payload_paths(payload)
    with app_state.lock:
        process = app_state.process
        if process is not None and process.poll() is None:
            raise RuntimeError("Cannot change active paths while analysis is running.")
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
    with app_state.lock:
        app_state.paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    return {"source_dir": str(source_dir), "output_root": str(output_root)}


def infer_source_dir_for_output(app_state: AppState, output_root: Path) -> Path:
    with app_state.lock:
        active_paths = app_state.paths
        process = app_state.process
        running = process is not None and process.poll() is None
    if active_paths is not None and active_paths.output_root.resolve() == output_root:
        return active_paths.source_dir

    history_source = infer_source_dir_from_run_history(output_root)
    if history_source is not None:
        return history_source

    decision_source = infer_source_dir_from_decisions(output_root)
    if decision_source is not None:
        return decision_source

    if running and active_paths is not None:
        return active_paths.source_dir
    return output_root


def infer_source_dir_from_run_history(output_root: Path) -> Path | None:
    for record in reversed(load_run_history(output_root, limit=20)):
        value = str(record.get("source_dir") or "").strip()
        if value:
            return Path(value).expanduser().resolve()
    return None


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
        "require_local_llm": "--require-local-llm",
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
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return True
        return str(pid) in result.stdout
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


def find_command_for_pid(records: list[dict[str, Any]], pid: int | None) -> list[str] | None:
    for record in reversed(records):
        record_pid = coerce_pid(record.get("pid"))
        if pid is not None and record_pid != pid:
            continue
        command = record.get("command")
        if isinstance(command, list) and all(isinstance(item, str) for item in command):
            return command
    if pid is not None:
        return find_command_for_pid(records, None)
    return None


def terminate_process_id(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
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


def stop_analysis(app_state: AppState) -> dict[str, Any]:
    with app_state.lock:
        process = app_state.process
        paths = app_state.paths
        if process is not None and process.poll() is None:
            process.terminate()
            return {"stopped": True, "running": True, "pid": process.pid}
        if paths is None:
            return {"stopped": False, "running": False}
        pid = find_active_run_pid(paths)
        if pid is None:
            return {"stopped": False, "running": False}
        stopped = terminate_process_id(pid)
        return {"stopped": stopped, "running": is_process_alive(pid), "pid": pid}


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


def analysis_status(app_state: AppState) -> dict[str, Any]:
    with app_state.lock:
        process = app_state.process
        command = app_state.process_command
        paths = app_state.paths
        local_running = process is not None and process.poll() is None
        local_pid = process.pid if process is not None else None
        return_code = None if process is None else process.poll()

    if paths is None:
        return {
            "running": local_running,
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
            "run_history": [],
        }

    run_history = load_run_history(paths.output_root, limit=20)
    active_pid = find_active_run_pid(paths)
    running = local_running or active_pid is not None
    pid = local_pid if local_running else active_pid
    if running and not local_running:
        return_code = None
    if command is None:
        command = find_command_for_pid(run_history, pid)
    progress = read_json_file(paths.progress_path)
    run_summary = read_json_file(paths.output_root / "_state" / "run_summary.json")
    log_tail = read_text_tail(paths.application_log_path, max_lines=80)
    decisions_exists = paths.decisions_path.exists()
    lock_status = run_lock_status(paths)

    return {
        "running": running,
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
        "source_dir": str(paths.source_dir),
        "output_root": str(paths.output_root),
        "progress": progress,
        "log_tail": log_tail,
        "decisions_exists": decisions_exists,
        "run_lock": lock_status,
        "activity": build_analysis_activity(paths, log_tail),
        "run_summary": run_summary,
        "run_history": run_history,
    }


def run_history_path(output_root: Path) -> Path:
    return output_root / "_state" / "ui_runs.jsonl"


def append_run_history(output_root: Path, record: dict[str, Any]) -> dict[str, Any]:
    path = run_history_path(output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="ignore") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_run_history(output_root: Path, limit: int) -> list[dict[str, Any]]:
    path = run_history_path(output_root)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
    return records[-limit:]


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
            text=True,
            timeout=None,
        )
    except OSError as exc:
        raise RuntimeError(f"Windows folder picker failed to start: {exc}") from exc
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Windows folder picker failed: {error}")
    return result.stdout.strip()


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
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()
    except OSError:
        return ""
    return "".join(lines[-max_lines:])


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
        return {
            "label": "已规划",
            "detail": message.removeprefix("Planned ").strip(),
            "line": selected,
        }
    if message.startswith("Progress "):
        return {"label": "进度写入", "detail": message, "line": selected}
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
    decisions = load_latest_decisions(paths.decisions_path)
    relative_path = str(payload.get("relative_path") or payload.get("path") or "")
    status = str(payload.get("status") or "")
    note = str(payload.get("note") or "")
    if status not in MARKABLE_STATUSES:
        raise ValueError(f"Unsupported reading status: {status}")
    return append_reading_event(
        paths,
        decisions,
        requested_path=relative_path,
        status=status,
        note=note,
    )


def mark_documents(paths: ReadingPaths, payload: dict[str, Any]) -> dict[str, Any]:
    decisions = load_latest_decisions(paths.decisions_path)
    raw_paths = payload.get("relative_paths") or []
    if not isinstance(raw_paths, list):
        raise ValueError("relative_paths must be a list")
    status = str(payload.get("status") or "")
    note = str(payload.get("note") or "")
    if status not in MARKABLE_STATUSES:
        raise ValueError(f"Unsupported reading status: {status}")

    events = []
    for relative_path in raw_paths:
        events.append(
            append_reading_event(
                paths,
                decisions,
                requested_path=str(relative_path),
                status=status,
                note=note,
            )
        )
    return {"count": len(events), "events": events}


def open_document(paths: ReadingPaths, payload: dict[str, Any], *, reveal: bool) -> dict[str, Any]:
    decision = resolve_decision(paths, str(payload.get("relative_path") or ""))
    source_path = Path(str(decision.get("source_path") or ""))
    if not source_path.exists():
        raise FileNotFoundError(f"Source file does not exist: {source_path}")

    if reveal:
        reveal_path(source_path)
    else:
        open_path(source_path)
    return {"ok": True, "source_path": str(source_path)}


def resolve_decision(paths: ReadingPaths, relative_path: str) -> dict[str, Any]:
    decisions = load_latest_decisions(paths.decisions_path)
    decision = decisions.get(relative_path)
    if decision:
        return decision
    raise ValueError(f"Unknown relative_path: {relative_path}")


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
        if parsed.path == "/":
            self.send_html(HTML_PAGE)
            return
        if parsed.path == "/api/config":
            self.send_json(lambda: config_payload(self.state.paths))
            return
        if parsed.path == "/api/analysis/status":
            self.send_json(lambda: analysis_status(self.state))
            return
        if parsed.path == "/api/relationships":
            query = {
                key: values[-1]
                for key, values in urllib.parse.parse_qs(parsed.query).items()
                if values
            }
            self.send_json(
                lambda: build_relationship_payload(
                    self.state, require_paths(self.state), query
                )
            )
            return
        if parsed.path == "/api/state":
            query = {
                key: values[-1]
                for key, values in urllib.parse.parse_qs(parsed.query).items()
                if values
            }
            self.send_json(lambda: build_state_payload(require_paths(self.state), query))
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
        if self.path == "/api/analysis/start":
            self.send_json(lambda: start_analysis(self.state, self.read_json()))
            return
        if self.path == "/api/analysis/stop":
            self.send_json(lambda: stop_analysis(self.state))
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
            self.send_json(lambda: mark_document(require_paths(self.state), self.read_json()))
            return
        if self.path == "/api/mark-batch":
            self.send_json(lambda: mark_documents(require_paths(self.state), self.read_json()))
            return
        if self.path == "/api/open":
            self.send_json(lambda: open_document(require_paths(self.state), self.read_json(), reveal=False))
            return
        if self.path == "/api/reveal":
            self.send_json(lambda: open_document(require_paths(self.state), self.read_json(), reveal=True))
            return
        self.send_error(404)

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
