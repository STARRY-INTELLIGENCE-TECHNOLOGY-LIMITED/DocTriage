# 过夜全量分析

目标：长时间无人值守跑完大目录首轮筛选。

```powershell
.\.venv\Scripts\python.exe main.py `
  --source-dir "D:\example_docs" `
  --output-root ".\data\overnight_run" `
  --llm-endpoint http://localhost:11434/api/generate `
  --llm-model gemma4:e4b `
  --concurrency 1 `
  --plan-only `
  --no-ocr `
  --skip-manifest-analysis `
  --document-summary `
  --require-local-llm `
  --timeout-seconds 240
```

查看进度：

```powershell
Get-Content ".\data\overnight_run\_state\progress.json"
Get-Content ".\data\overnight_run\_logs\doctriage.log" -Tail 40 -Wait
```

中断后重新执行同一命令即可续跑。想彻底重置，换一个新的 `--output-root`。

