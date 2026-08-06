$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
}

$content = @(Get-Content ".env" -Encoding UTF8)
$content = $content -replace "^MODEL_BACKEND=.*", "MODEL_BACKEND=ollama"
$content = $content -replace "^OLLAMA_BASE_URL=.*", "OLLAMA_BASE_URL=http://localhost:11434"
$content = $content -replace "^OLLAMA_MODEL=.*", "OLLAMA_MODEL=tinyllama"
$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllLines((Join-Path (Get-Location) ".env"), $content, $utf8Bom)

Write-Host "Configured .env for Ollama."
Write-Host "Next steps:"
Write-Host "  1. Install/start Ollama"
Write-Host "  2. Run: ollama pull tinyllama"
Write-Host "  3. Start the app: .\scripts\start.ps1"
