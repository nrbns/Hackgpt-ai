$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
}

$content = Get-Content ".env"
$content = $content -replace "^MODEL_BACKEND=.*", "MODEL_BACKEND=openai_compat"
$content = $content -replace "^OPENAI_COMPAT_BASE_URL=.*", "OPENAI_COMPAT_BASE_URL=http://localhost:1234/v1"
$content = $content -replace "^OPENAI_COMPAT_MODEL=.*", "OPENAI_COMPAT_MODEL=local-model"
$content = $content -replace "^OPENAI_COMPAT_API_KEY=.*", "OPENAI_COMPAT_API_KEY=lm-studio"
$content | Set-Content ".env"

Write-Host "Configured .env for LM Studio / OpenAI-compatible local server."
Write-Host "Start LM Studio local server, then run: .\scripts\start.ps1"
