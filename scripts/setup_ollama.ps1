# Ollama setup helper for SecuraIQ (Windows PowerShell)
# Usage: .\scripts\setup_ollama.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

Write-Host "SecuraIQ Ollama Setup" -ForegroundColor Green
Write-Host ""

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama not found. Install from: https://ollama.com/download" -ForegroundColor Yellow
    Write-Host "After install, re-run this script."
    exit 1
}

Write-Host "Ollama found: $(ollama --version)"
Write-Host ""

Write-Host "Pulling tinyllama (fast CPU default)..." -ForegroundColor Cyan
ollama pull tinyllama

Write-Host ""
Write-Host "Installed models:" -ForegroundColor Green
ollama list

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
}

$content = Get-Content ".env"
$content = $content -replace "^MODEL_BACKEND=.*", "MODEL_BACKEND=ollama"
$content = $content -replace "^OLLAMA_MODEL=.*", "OLLAMA_MODEL=tinyllama"
$content | Set-Content ".env"

Write-Host ""
Write-Host "Configured .env for Ollama + tinyllama."
Write-Host "Optional larger models: ollama pull mistral | ollama pull llama3"
Write-Host "Start SecuraIQ: .\scripts\start.ps1"
Write-Host "Open: http://localhost:8080"
