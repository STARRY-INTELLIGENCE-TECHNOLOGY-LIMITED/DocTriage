# RAG 入库

先跑首轮分析：

```powershell
.\.venv\Scripts\python.exe main.py `
  --source-dir "D:\example_docs" `
  --output-root ".\data\rag_run" `
  --llm-endpoint http://localhost:11434/api/generate `
  --llm-model gemma4:e4b `
  --plan-only `
  --no-ocr `
  --skip-manifest-analysis
```

导出 RAG 候选 JSONL：

```powershell
.\.venv\Scripts\python.exe workflow_adapter.py export-manifest `
  --output-root ".\data\rag_run" `
  --purpose rag `
  --jsonl `
  --output ".\data\rag_run\rag_candidates.jsonl"
```

常用调参：

- 降低 `--rag-min-quality` 可扩大召回。
- 降低 `--internal-max-sensitivity-risk` 可减少敏感资料进入后续索引。
