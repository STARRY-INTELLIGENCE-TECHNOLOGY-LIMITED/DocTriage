# 预训练语料过滤

目标：保留知识密度较高、重复/低质较少、敏感风险可控的文档。

```powershell
.\.venv\Scripts\python.exe workflow_adapter.py export-manifest `
  --output-root ".\data\real_run_plan" `
  --purpose pretraining `
  --pretraining-min-quality 70 `
  --pretraining-min-uniqueness 55 `
  --internal-max-sensitivity-risk 50 `
  --jsonl `
  --output ".\data\real_run_plan\pretraining_candidates.jsonl"
```

建议先人工抽样检查：

```powershell
Get-Content ".\data\real_run_plan\pretraining_candidates.jsonl" -TotalCount 20
```

