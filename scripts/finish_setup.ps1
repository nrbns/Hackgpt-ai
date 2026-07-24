# Finish SecuraIQ setup (Windows)
# Usage: .\scripts\finish_setup.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

Write-Host "SecuraIQ Finish Setup" -ForegroundColor Green

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing dependencies..."
& .\.venv\Scripts\pip install -r requirements.txt -q

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example"
}

Write-Host "Indexing RAG knowledge base..."
& .\.venv\Scripts\python scripts\ingest_rag.py

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "Ollama detected. Installed models:"
    ollama list
} else {
    Write-Host "Ollama not installed — get it from https://ollama.com" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting server on http://localhost:8080" -ForegroundColor Cyan
& .\.venv\Scripts\python run.py
