# SFT / 微调候选

目标：优先选择可落地、证据充分、敏感风险低的文档。

```powershell
.\.venv\Scripts\python.exe workflow_adapter.py export-manifest `
  --output-root ".\data\real_run_plan" `
  --purpose sft `
  --sft-min-quality 82 `
  --sft-min-actionability 75 `
  --sft-min-evidence-richness 65 `
  --public-max-sensitivity-risk 30 `
  --jsonl `
  --output ".\data\real_run_plan\sft_candidates.jsonl"
```

如果后续要构造问答对，建议优先使用 `document_kind` 为 `ImplementationGuide`、`IncidentReview`、`ArchitectureDecision` 的记录。

