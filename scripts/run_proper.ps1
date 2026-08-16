# One-command setup + start for SecuraIQ (Windows) - zero-config, no manual .env
param(
    [switch]$Lan
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

Write-Host "SecuraIQ setup" -ForegroundColor Cyan

function Find-Python {
    foreach ($cmd in @("python", "py")) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $exe) { continue }
        try {
            if ($cmd -eq "py") {
                $ver = & py -3 -c "import sys; print(sys.version_info[0])" 2>$null
                if ($ver -eq "3") { return @{ Exe = "py"; Args = @("-3") } }
            } else {
                $ver = & python -c "import sys; print(sys.version_info[0])" 2>$null
                if ($ver -eq "3") { return @{ Exe = "python"; Args = @() } }
            }
        } catch { }
    }
    throw "Python 3.11+ not found. Install from https://www.python.org/downloads/ and tick 'Add python.exe to PATH'."
}

function Set-EnvLine {
    param([string[]]$Lines, [string]$Key, [string]$Value)
    $pattern = "^" + [regex]::Escape($Key) + "=.*"
    $replacement = "$Key=$Value"
    $found = $false
    $out = foreach ($line in $Lines) {
        if ($line -match $pattern) {
            $found = $true
            $replacement
        } else {
            $line
        }
    }
    if (-not $found) { $out += $replacement }
    return ,$out
}

$py = Find-Python

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    if ($py.Args.Count) {
        & $py.Exe @($py.Args + @("-m", "venv", ".venv"))
    } else {
        & $py.Exe -m venv .venv
    }
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        throw "Failed to create .venv - check Python install."
    }
}

Write-Host "Installing dependencies..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed." }
& .\.venv\Scripts\python.exe -c "import fastapi, uvicorn"
if ($LASTEXITCODE -ne 0) {
    throw "fastapi/uvicorn missing after install. Delete .venv and re-run .\run_proper.cmd"
}
Write-Host "Dependencies ready." -ForegroundColor Green

if (-not (Test-Path ".env.example")) {
    throw "Missing .env.example - clone the full SecuraIQ repo."
}
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example (no manual editing needed)"
}

Write-Host "Indexing RAG knowledge base..."
& .\.venv\Scripts\python.exe scripts\ingest_rag.py

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollama) {
    Write-Host "Ollama found - configuring ollama backend."
    & .\scripts\use_ollama.ps1 | Out-Null
    $models = & ollama list 2>$null
    if ($models -match "tinyllama") {
        Write-Host "TinyLlama model ready."
    } else {
        Write-Host "Pulling tinyllama model (one-time download)..."
        & ollama pull tinyllama
    }
} else {
    Write-Host "Ollama not found - using configured cloud/local HF backend from .env.example." -ForegroundColor Yellow
}

$envLines = @(Get-Content ".env" -Encoding utf8)
if ($Lan) {
    $envLines = Set-EnvLine $envLines "HOST" "0.0.0.0"
    $envLines = Set-EnvLine $envLines "CORS_ORIGINS" "*"
    $envLines = Set-EnvLine $envLines "WORKSPACE_ZERO_START" "false"
} else {
    $envLines = Set-EnvLine $envLines "HOST" "127.0.0.1"
    $envLines = Set-EnvLine $envLines "CORS_ORIGINS" "http://127.0.0.1:8080,http://localhost:8080"
}
$envLines = Set-EnvLine $envLines "AUTH_ALLOW_REGISTER" "false"
if (-not ($envLines | Where-Object { $_ -match "^WORKSPACE_ZERO_START=" })) {
    $envLines = Set-EnvLine $envLines "WORKSPACE_ZERO_START" "true"
}
$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllLines((Join-Path (Get-Location) ".env"), $envLines, $utf8Bom)

# Only stop processes that look like SecuraIQ / uvicorn on 8080
$portUsers = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" }
foreach ($conn in $portUsers) {
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    if ($proc -and ($proc.ProcessName -match "python|uvicorn")) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
if ($Lan) {
    Write-Host "Starting SecuraIQ (LAN mode)" -ForegroundColor Yellow
    Write-Host "  http://127.0.0.1:8080  (+ LAN IP for phones)"
    Write-Host "  Or double-click start_lan.cmd next time"
} else {
    Write-Host "Starting SecuraIQ (localhost)" -ForegroundColor Green
    Write-Host "  http://127.0.0.1:8080"
    Write-Host "  For phones: .\start_lan.cmd"
}
Write-Host "No .env editing required. Optional keys: Settings in the UI."
& .\.venv\Scripts\python.exe run.py
