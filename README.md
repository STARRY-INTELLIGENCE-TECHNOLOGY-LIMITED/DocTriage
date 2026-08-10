# DocTriage

面向大型本地文档库的本地优先筛选、阅读和关系挖掘工具，适合传统文档筛选、关联学习、RAG 和 Agent 工作流。

[English README](README.en.md)

DocTriage 会扫描源目录、提取正文、调用本地 LLM 给每个文档评分并解释原因，然后提供浏览器控制台完成阅读复核、状态标记、失败处理、关系挖掘和导出。它既能服务现代 AI 管线，也能服务传统的文档筛选、按目录连续阅读和关联学习。

源目录只读。所有状态、日志、关系结果以及可选的复制产物都会写入 `OUTPUT_ROOT`。

<p align="center">
  <img src="https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/raw/main/sample_pictures/triage.jpg" alt="DocTriage 总览" width="900">
</p>

DocTriage 围绕一个清晰的闭环设计：先本地分析，再在阅读台复核和标记文档，最后在需要关联学习或下游导出时生成关系簇。

## 核心架构

![DocTriage 核心架构](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/raw/main/sample_pictures/architecture_zh.png)

## 产品亮点与知识闭环

DocTriage 的核心价值不是简单转换文件，而是在 RAG 或 Agent 入库前回答“哪些资料值得进入知识库、为什么值得、边界是什么”。它把来源只读、质量分级、人工复核、关系挖掘、RAG 索引和可审计导出放在同一条本地优先链路中，适合作为个人或团队私域知识的上游治理层。

- **知识资产治理**：用正文质量、文档类型、主题、敏感性和可公开性代替仅按目录或文件名入库。
- **可解释筛选**：阅读台、RAG 与 Agent Bundle 各自保留显式阈值；筛选数量和占比可见，不会隐式互相干扰。
- **稳定下游契约**：`doctriage_bundle.v2` 携带来源路径、质量分、分类、摘要、关系和健康状态，下游不需要耦合内部日志。
- **私域写作基础**：先在 DocTriage 中区分事实资料、观点资料、案例和风格样本，再把可信工作集交给下游生成论点、提纲和文章。

可与 [AnyDocsToAgents](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/AnyDocsToAgents) 组成可选闭环：DocTriage 负责“治理与入库”，AnyDocsToAgents 负责“混合检索、执行拓扑、证据问答与文章写作”。两者通过 Bundle 和启动 URL 联动，仍可独立部署和使用。

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

**文档分析**

![文档分析](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/raw/main/sample_pictures/analysis_chi.png)

在同一界面配置源目录、输出目录、本地模型、plan-only、续跑策略、进度、日志和失败状态。

**阅读台**

![阅读台](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/raw/main/sample_pictures/reading_chi.png)

既可以复核已评分文档，也可以按源目录顺序浏览全部文件，并直接打开、定位、标记、筛选和导出当前工作集。

**关系图谱**

![关系图谱](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/raw/main/sample_pictures/graph_chi.png)

关系簇用于近重复识别、系列发现、关联学习、知识图谱导出和 bundle 生成。

**RAG 索引与检索**

![RAG 索引与检索](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/raw/main/sample_pictures/rag_chi.png)

**Agent Bundle 交接**

![Agent Bundle 交接](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/raw/main/sample_pictures/agents_eng.png)

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
doctriage-reading-ui --host 127.0.0.1 --port 18765
```

打开 `http://127.0.0.1:18765/`。

控制台前端以包内静态文件发布，服务启动时一次性载入内存，不执行运行时构建。
修改 `doctriage_ui` 中的 HTML、CSS 或 JavaScript 后，重启服务即可生效。

### 可信局域网部署

```powershell
doctriage-reading-ui --host 0.0.0.0 --port 18765 --no-open-browser
```

局域网客户端访问 `http://<服务器 IP>:18765/`。服务没有内置身份验证，只应绑定到
可信本机或可信局域网；如需提供给不受信任用户或更大网络，应在前置代理中增加身份验证、
TLS 和访问控制。

### 文件夹输入与跨平台路径

- “选择源目录”读取 DocTriage 服务所在机器的目录，并递归扫描所有子目录。
- “上传文档”通过受管工作区接收操作者电脑中的文件或文件夹。浏览器支持时可一次多选，也可以重复添加；同名根目录自动改为 `目录 (2)`，不会覆盖已有内容。
- 已完成的上传内容和已选择的源目录会在同一次任务中取并集。状态、日志和可选复制产物始终写入分析表单指定的输出目录；上传内容使用 `_uploads/` 相对路径命名空间避免冲突。
- CLI 支持重复传入 `--source-dir`。第一个目录作为主根目录，后续目录作为附加根目录；扫描会按真实路径去重，未变化文件仍可续跑。
- 浏览器上传会发送操作者电脑中的文件内容；选择的源目录必须能被服务器访问，应根据文件实际所在位置选择输入方式。
- Windows 路径示例为 `D:\资料`，Linux 为 `/home/name/documents`，macOS 为 `/Users/name/Documents`。Linux 无图形桌面时可直接填写路径；macOS 优先使用系统目录对话框，Linux 优先使用 Zenity/KDialog，并在不可用时回退 Tk。

大型目录建议首轮使用 plan-only：

```powershell
doctriage `
  --source-dir "D:\example_docs" `
  --source-dir "D:\additional_docs" `
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
.\.venv\Scripts\python.exe reading_ui.py --host 127.0.0.1 --port 18765
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
    qdrant/
```

下游集成应优先读取 `doctriage_bundle.json`，不要直接依赖内部 JSONL 日志。

### Qdrant 本地 RAG

RAG 索引支持 `local_jsonl` 和嵌入式 `qdrant_local`。选择 Qdrant 本地后，向量会实际写入 `OUTPUT_ROOT/_rag/qdrant` 并由 Qdrant 执行相似度检索；`vectors.jsonl` 仍作为可审计副本和故障回退。该模式不启动 HTTP 服务。

```powershell
doctriage-rag build `
  --output-root "D:\doctriage_run" `
  --embedding-endpoint http://127.0.0.1:11434/api/embed `
  --embedding-model qwen3-embedding:8b `
  --vector-store qdrant_local `
  --qdrant-collection doctriage_rag
```

也可以在控制台的 **RAG 索引 > 向量存储** 中选择 **Qdrant 本地**。存储路径留空时使用上述默认目录；远程 Qdrant、Chroma 和 HTTP 选项仅用于连接测试。

## 交给 AnyDocsToAgents

浏览器控制台提供 **Agent 编译** 页，可选对接 [AnyDocsToAgents](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/AnyDocsToAgents)。它会导出 `OUTPUT_ROOT/_relationships/doctriage_bundle.json`，把通过校验的副本上传到所配置的 AnyDocsToAgents 服务，再由操作者当前浏览器打开下游页面。启动 URL 使用下游服务器上的托管路径，例如：

```text
http://192.168.1.20:18766/?doctriage_bundle_path=D:\anydocs_data\uploads\doctriage_bundles\...json#view-planner
```

DocTriage 会在打开联动地址前检查 AnyDocsToAgents 服务。未检测到服务时，控制台会显示提示，并在操作者当前浏览器打开 GitHub 项目页。DocTriage 与 AnyDocsToAgents 可以部署在不同局域网主机上，Bundle 本身不再要求共享盘符；Bundle 中的原文路径仍指向 DocTriage 主机，跨主机部署若未共享原文，下游会使用导出的摘要并标记原文不可读。

对于已经完成的长耗时分析，只需导出 bundle，不会重新执行分类：

```powershell
doctriage-bundle `
  --source-dir "D:\example_docs" `
  --output-root "D:\doctriage_run" `
  --llm-endpoint http://localhost:11434/api/generate `
  --llm-model gemma4:e4b `
  --min-quality 75
```

bundle 默认不排除任何类别，因此 `--min-quality 0` 也会包含 `LowQuality` 文档。只有下游明确需要时才使用 `--exclude-categories LowQuality`。`is_partial` 与 `warnings` 只表示必需文档数据不完整；关系、RAG 或摘要等可选能力缺失或失败会写入 `advisories`，不会阻止导出。下游应同时展示两种信息，但不应把可选能力缺失误判为 bundle 失败。

## 语言

DocTriage 有两个独立语言控制：

- 输出语言控制摘要和评分理由。`Auto` 会根据文档主体语言推断。
- 界面语言只改变控制台标签，不影响 LLM 输出。

## 更多文档

- [Bundle schema](docs/bundle_schema.md)
- [Knowledge graph abstraction](docs/knowledge_graph.md)
- [Recipes](recipes/README.md)
- [English README](README.en.md)

## 注意事项

- 不要把 `OUTPUT_ROOT` 放在 `SOURCE_DIR` 内部。
- 打开和定位文件依赖本机桌面环境。
- 无桌面服务器仍可运行分析和 Web UI，但目录选择器、打开和定位动作可能不可用。

## 许可证

本项目采用 [Apache License 2.0](LICENSE) 许可证。
