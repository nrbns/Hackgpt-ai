$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
}

$content = Get-Content ".env" -Raw
if ($content -notmatch "(?m)^UNSLOTH_MODEL=") {
    $content = $content.TrimEnd() + "`r`nUNSLOTH_MODEL=unsloth/Qwen2.5-0.5B-Instruct-bnb-4bit`r`n"
}
if ($content -notmatch "(?m)^UNSLOTH_ADAPTER_DIR=") {
    $content = $content.TrimEnd() + "`r`nUNSLOTH_ADAPTER_DIR=./models/securaiq-unsloth`r`n"
}
if ($content -notmatch "(?m)^UNSLOTH_MAX_SEQ_LENGTH=") {
    $content = $content.TrimEnd() + "`r`nUNSLOTH_MAX_SEQ_LENGTH=2048`r`n"
}
if ($content -notmatch "(?m)^UNSLOTH_LOAD_IN_4BIT=") {
    $content = $content.TrimEnd() + "`r`nUNSLOTH_LOAD_IN_4BIT=true`r`n"
}
if ($content -notmatch "(?m)^HF_TOKEN=") {
    $content = $content.TrimEnd() + "`r`nHF_TOKEN=`r`n"
}
$content = $content -replace "(?m)^MODEL_BACKEND=.*", "MODEL_BACKEND=unsloth"
$content = $content -replace "(?m)^UNSLOTH_MODEL=.*", "UNSLOTH_MODEL=unsloth/Qwen2.5-0.5B-Instruct-bnb-4bit"
$content = $content -replace "(?m)^UNSLOTH_ADAPTER_DIR=.*", "UNSLOTH_ADAPTER_DIR=./models/securaiq-unsloth"
$content = $content -replace "(?m)^UNSLOTH_MAX_SEQ_LENGTH=.*", "UNSLOTH_MAX_SEQ_LENGTH=2048"
$content = $content -replace "(?m)^UNSLOTH_LOAD_IN_4BIT=.*", "UNSLOTH_LOAD_IN_4BIT=true"
Set-Content ".env" -Value $content -NoNewline

Write-Host "Configured .env for Unsloth backend."
Write-Host ""
Write-Host "Install (GPU + CUDA recommended):"
Write-Host "  .\.venv\Scripts\pip install unsloth"
Write-Host "  .\.venv\Scripts\pip install datasets trl peft accelerate bitsandbytes"
Write-Host ""
Write-Host "Set HF_TOKEN in the UI Settings panel (or .env) for gated models."
Write-Host "Train: python -m app.fine_tune.train_unsloth --epochs 1"
Write-Host "  or use Settings → Start Unsloth train in the UI"
Write-Host "Run: .\scripts\start.ps1"
Write-Host ""
Write-Host "Repo: https://github.com/unslothai/unsloth"
