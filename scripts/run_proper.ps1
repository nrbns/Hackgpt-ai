# One-command setup + start for PentestGPT (Windows)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

Write-Host "PentestGPT setup" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing dependencies..."
& .\.venv\Scripts\pip install -r requirements.txt -q
& .\.venv\Scripts\pip install torch transformers accelerate -q

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example"
}

Write-Host "Indexing RAG knowledge base..."
& .\.venv\Scripts\python scripts\ingest_rag.py

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollama) {
    Write-Host "Ollama found — configuring ollama backend."
    & .\scripts\use_ollama.ps1 | Out-Null
    $models = & ollama list 2>$null
    if ($models -match "tinyllama") {
        Write-Host "TinyLlama model ready."
    } else {
        Write-Host "Pulling tinyllama model (one-time download)..."
        & ollama pull tinyllama
    }
} else {
    Write-Host "Ollama not found — using HuggingFace CPU model (Qwen2.5-0.5B)." -ForegroundColor Yellow
    $content = Get-Content ".env"
    $content = $content -replace "^MODEL_BACKEND=.*", "MODEL_BACKEND=huggingface"
    $content = $content -replace "^HF_MODEL=.*", "HF_MODEL=Qwen/Qwen2.5-0.5B-Instruct"
    $content | Set-Content ".env"
}

$portUsers = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
foreach ($conn in $portUsers) {
    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Starting PentestGPT at http://localhost:8080" -ForegroundColor Green
& .\.venv\Scripts\python run.py
