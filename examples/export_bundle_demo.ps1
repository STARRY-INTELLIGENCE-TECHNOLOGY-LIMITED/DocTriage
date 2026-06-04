param(
    [string]$SourceDir = "D:\example_docs",
    [string]$OutputRoot = ".\data\demo_run",
    [string]$Model = "gemma4:e4b"
)

$ErrorActionPreference = "Stop"

.\.venv\Scripts\python.exe bundle_exporter.py `
    --source-dir $SourceDir `
    --output-root $OutputRoot `
    --llm-endpoint "http://localhost:11434/api/generate" `
    --llm-model $Model `
    --title "Architecture Thinking Bundle" `
    --min-quality 80 `
    --categories Architecture,Thinking,Series `
    --limit 50
