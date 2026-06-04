# 公开写作素材

目标：找出适合脱敏、抽象后写博客或文章的资料。

```powershell
.\.venv\Scripts\python.exe workflow_adapter.py export-manifest `
  --output-root ".\data\real_run_plan" `
  --purpose public_writing `
  --public-max-sensitivity-risk 30 `
  --public-min-writing-suitability 75 `
  --jsonl `
  --output ".\data\real_run_plan\public_writing_candidates.jsonl"
```

也可以导出 bundle：

```powershell
.\.venv\Scripts\python.exe bundle_exporter.py `
  --source-dir "D:\example_docs" `
  --output-root ".\data\real_run_plan" `
  --title "Public Writing Candidates" `
  --min-quality 80 `
  --max-sensitivity-risk 30 `
  --min-public-writing-suitability 75 `
  --limit 200
```

