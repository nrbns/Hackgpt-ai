# Start HackGPT (Windows)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

if (-not (Test-Path ".venv")) {
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt
}

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
}

Write-Host "Starting HackGPT at http://localhost:8080"
.\.venv\Scripts\python run.py
