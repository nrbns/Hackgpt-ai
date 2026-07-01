# Ollama setup helper for PentestGPT (Windows PowerShell)
# Usage: .\scripts\setup_ollama.ps1

$ErrorActionPreference = "Stop"

$models = @("llama3", "mistral", "codellama")

Write-Host "PentestGPT Ollama Setup" -ForegroundColor Green
Write-Host ""

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama not found. Install from: https://ollama.com/download" -ForegroundColor Yellow
    Write-Host "After install, re-run this script."
    exit 1
}

Write-Host "Ollama found: $(ollama --version)"
Write-Host ""

foreach ($model in $models) {
    Write-Host "Pulling $model ..." -ForegroundColor Cyan
    ollama pull $model
}

Write-Host ""
Write-Host "Installed models:" -ForegroundColor Green
ollama list

Write-Host ""
Write-Host "Default model set to llama3 in .env.example"
Write-Host "Start PentestGPT: python run.py"
Write-Host "Open: http://localhost:8080"
