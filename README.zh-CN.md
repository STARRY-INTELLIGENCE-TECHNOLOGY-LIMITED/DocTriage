# DocTriage

面向大型本地文档库的本地优先筛选、阅读和关系挖掘工具，适合古法文档择优、关联学习、RAG 和 Agent 工作流。

[English README](README.md)

DocTriage 会扫描源目录、提取正文、调用本地 LLM 给每个文档评分并解释原因，然后提供浏览器控制台完成阅读复核、状态标记、失败处理、关系挖掘和导出。它既能服务现代 AI 管线，也能服务传统的文档择优、按目录连续阅读和关联式学习。

源目录只读。所有状态、日志、关系结果以及可选的复制产物都会写入 `OUTPUT_ROOT`。

<p align="center">
  <img src="https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/blob/main/sample_pictures/triage.jpg?raw=true" alt="DocTriage 总览" width="900">
</p>

DocTriage 围绕一个实用闭环设计：先进行本地分析，再在阅读台复核和标记文档，最后在需要关联学习或下游导出时生成关系簇。

## 为什么使用

- 不改动原始目录，也能对大型混乱文件夹做首轮摸底。
- 按质量、路径顺序、修改时间和阅读状态进行人工文档择优。
- 不只依赖文件名，而是基于正文给出分数、摘要、理由和维度分。
- 在阅读台中直接打开、定位、标记已读、稍后、跳过。
- 失败文件不会沉到日志里，而是作为可操作的行继续展示。
- 通过近重复、系列文章、同主题聚类和源目录上下文进行关联学习。
- 需要接入 RAG 或 Agent 时，下游工具可以读取稳定 bundle。

## 核心能力

- 基于输出目录锁的可续跑分析。
- `--plan-only` 只评分不复制，不生成误导性的 `HQ`、`LQ` 实体目录。
- 阅读台支持“分析结果”和“全部源文件”两种范围。
- 文档行可解释：摘要、评分理由、多个维度分。
- 失败文件展示阶段、原因、尝试次数，并支持直接打开和定位。
- 当前筛选结果可导出 CSV/JSONL。
- 可配置摘要和理由的输出语言。
- 右上角有独立界面语言切换，不影响 LLM 输出语言。
- 关系图谱可服务关联学习、去重和下游 bundle 导出。

## 界面预览

**分析执行**

![分析执行](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/blob/main/sample_pictures/analysis_chi.png?raw=true)

在同一界面配置源目录、输出目录、本地模型、plan-only、续跑策略、进度、日志和失败状态。

**阅读台**

![阅读台](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/blob/main/sample_pictures/reading_chi.png?raw=true)

既可以复核已评分文档，也可以按源目录顺序浏览全部文件，并直接打开、定位、标记、筛选和导出当前工作集。

**关系图谱**

![关系图谱](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/blob/main/sample_pictures/graph_chi.png?raw=true)

关系簇用于近重复识别、系列发现、关联学习、知识图谱导出和 bundle 生成。

## 环境要求

- Python `>=3.11,<3.15`
- LLM 接口：本地 Ollama，或 OpenAI-compatible REST 接口
- 可选：LibreOffice，用于旧 `.ppt` 文件解析

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
Copy-Item .env.example .env
```

Linux 和 macOS 使用同样流程，将激活命令换成 `source .venv/bin/activate`，复制环境文件用 `cp .env.example .env`。

## 快速开始

启动浏览器控制台：

```powershell
doctriage-reading-ui --host 127.0.0.1 --port 8765
```

打开 `http://127.0.0.1:8765/`。

大型目录建议首轮使用 plan-only：

```powershell
doctriage `
  --source-dir "D:\example_docs" `
  --output-root "D:\doctriage_run" `
  --llm-endpoint http://localhost:11434/api/generate `
  --llm-model gemma4:e4b `
  --concurrency 1 `
  --plan-only `
  --no-ocr `
  --skip-manifest-analysis `
  --timeout-seconds 240
```

如果命令行入口没有进入 `PATH`，可以直接从仓库运行：

```powershell
.\.venv\Scripts\python.exe reading_ui.py --host 127.0.0.1 --port 8765
.\.venv\Scripts\python.exe main.py --help
```

## 模型接口

DocTriage 可以不依赖 Ollama，只要云厂商提供 OpenAI-compatible REST 协议：

- 评分/分类：将 `LLM_ENDPOINT` 设为 `/v1/chat/completions`，填写 `LLM_MODEL` 和 `LLM_API_KEY`；
- 关系/RAG 向量：将 `EMBEDDING_ENDPOINT` 设为 `/v1/embeddings`，填写 `EMBEDDING_MODEL`，必要时填写 `EMBEDDING_API_KEY`；
- `EMBEDDING_API_KEY` 为空时，向量请求会复用 `LLM_API_KEY`。

浏览器控制台也提供 API Key 输入框，用于临时运行。密钥只通过环境变量传给后台任务，不会保存到浏览器本地存储。

## 推荐流程

1. **先跑 plan-only**

   只得到评分、分类、摘要和理由，不复制源文件，也不会生成实体 `HQ` 或 `LQ` 目录。

2. **在阅读台复核**

   用“分析结果”查看已评分文档，用“全部源文件”按源目录完整路径和修改时间进行传统文件夹式翻阅。

3. **闭环处理失败文件**

   失败文件会作为 `failed` 行展示，包含阶段、原因、尝试次数、大小和打开/定位按钮。

4. **沿着关系和目录上下文阅读**

   先按源目录顺序连续阅读，再用关系簇跳转到相关文档。

5. **导出当前筛选**

   在阅读台完成筛选后导出 CSV 或 JSONL，用于审计、写作、RAG 规划或外部复核。

6. **评分稳定后挖掘关系**

   再生成关系簇、知识图谱和 bundle，避免早期低质量评分污染关系结果。

## 命令行

| 命令 | 用途 |
| --- | --- |
| `doctriage` | 执行文档分析 |
| `doctriage-reading-ui` | 启动浏览器控制台 |
| `doctriage-reading` | 通过 CLI 读取或更新阅读状态 |
| `doctriage-relationships` | 挖掘文档关系 |
| `doctriage-graph` | 导出知识图谱 |
| `doctriage-bundle` | 导出稳定下游 bundle |
| `doctriage-rag` | 构建或检索可续跑的 RAG 切片索引 |
| `doctriage-workflow` | 工作流适配入口 |

每个命令都支持 `--help`。

## 输出结构

```text
OUTPUT_ROOT/
  _state/
    progress.json
    run_summary.json
    decisions.jsonl
    processed_files.jsonl
    failed_files.jsonl
    reading_status.jsonl
  _logs/
    doctriage.log
  _relationships/
    relations.jsonl
    clusters.json
    knowledge_graph.json
    doctriage_bundle.json
  _rag/
    progress.json
    manifest.json
    documents.jsonl
    chunks.jsonl
    vectors.jsonl
```

下游集成应优先读取 `doctriage_bundle.json`，不要直接依赖内部 JSONL 日志。

## 交给 AnyDocsToAgents

浏览器控制台提供 **Agent 编译** 页，可选对接 [AnyDocsToAgents](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/AnyDocsToAgents)。它会导出 `OUTPUT_ROOT/_relationships/doctriage_bundle.json`，并用类似下面的 URL 打开 AnyDocsToAgents：

```text
http://127.0.0.1:8000/?doctriage_bundle_path=D:\doctriage_run\_relationships\doctriage_bundle.json&autoplan=1#view-planner
```

这是松耦合桥接：DocTriage 不启动、不嵌入、不依赖 AnyDocsToAgents。两个项目仍可独立运行。

## 语言

DocTriage 有两个独立语言控制：

- 输出语言控制摘要和评分理由。`Auto` 会根据文档主体语言推断。
- 界面语言只改变控制台标签，不影响 LLM 输出。

## 更多文档

- [Bundle schema](docs/bundle_schema.md)
- [Knowledge graph abstraction](docs/knowledge_graph.md)
- [Recipes](recipes/README.md)
- [English README](README.md)

## 注意事项

- 不要把 `OUTPUT_ROOT` 放在 `SOURCE_DIR` 内部。
- 打开和定位文件依赖本机桌面环境。
- 无桌面服务器仍可运行分析和 Web UI，但目录选择器、打开和定位动作可能不可用。
