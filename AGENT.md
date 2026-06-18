# DocTriage

DocTriage 是面向 RAG / Agent 入库前的本地文档预处理中间件。

## 当前职责

- 扫描源目录中的候选文档。
- 将 PDF、Office、Markdown、文本、HTML 和常见图片转为可评分文本。
- 基于本地 LLM 对文档做质量分级和类别判断。
- 将处理状态写入 `OUTPUT_ROOT/_state/`，支持断点续跑和变更重跑。
- 可选复制高价值文档到分类目录；源目录只读，不删除、不移动源文件。
- 可选挖掘文件名、时间、路径和 embedding 关系。
- 可导出 `knowledge_graph.json` 和 `doctriage_bundle.v2` 供下游系统消费。

## 工程边界

- 源文档目录必须保持只读。
- 生成物统一写入 `OUTPUT_ROOT`，且 `OUTPUT_ROOT` 不能位于 `SOURCE_DIR` 内。
- 默认优先大目录首跑效率：跳过目录级 manifest、不持久化正文摘要、不提取 PDF 原生元数据。
- embedding、OCR、manifest 分析都是可选增强，不应成为基础流程必需条件。
- 下游项目应优先消费 `doctriage_bundle.v2`，不要直接依赖内部 JSONL 日志结构。

## 主要入口

- `main.py` / `doctriage`：扫描、解析、评分、复制或 plan-only。
- `relationship_miner.py` / `doctriage-relationships`：关系挖掘。
- `knowledge_graph.py` / `doctriage-graph`：知识图谱导出。
- `bundle_exporter.py` / `doctriage-bundle`：下游 bundle 导出。

## 维护原则

- 优先保持简单的文件协议和 CLI，不引入数据库或重型服务依赖。
- 先补测试再改续跑、复制、状态日志等核心语义。
- 不为追求“智能”把所有步骤耦合到 LLM；能用本地规则完成的预筛选应保持本地规则。
