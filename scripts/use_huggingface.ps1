$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
}

$content = Get-Content ".env"
$content = $content -replace "^MODEL_BACKEND=.*", "MODEL_BACKEND=huggingface"
$content = $content -replace "^HF_MODEL=.*", "HF_MODEL=Qwen/Qwen2.5-0.5B-Instruct"
$content | Set-Content ".env"

Write-Host "Configured .env for direct Hugging Face local inference."
Write-Host "Install optional packages if needed:"
Write-Host "  .\.venv\Scripts\pip install torch transformers accelerate"
Write-Host "Then start the app: .\scripts\start.ps1"
