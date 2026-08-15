# Start SecuraIQ (Windows) - zero-config: no manual .env. Localhost by default; -Lan for Wi-Fi devices.
param(
    [switch]$Lan,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

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

function Ensure-EnvFile {
    if (-not (Test-Path ".env.example")) {
        throw "Missing .env.example - clone the full SecuraIQ repo."
    }
    if (-not (Test-Path ".env")) {
        Copy-Item .env.example .env
        Write-Host "Created .env from .env.example (no manual editing needed)"
    }
}

$py = Find-Python
$pyInvoke = {
    param([string[]]$ExtraArgs)
    if ($py.Args.Count) {
        & $py.Exe @($py.Args + $ExtraArgs)
    } else {
        & $py.Exe @ExtraArgs
    }
}

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
    Write-Host "Installing dependencies (first run may take a few minutes)..."
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
    & .\.venv\Scripts\pip.exe install -r requirements.txt
}

Ensure-EnvFile

$lines = @(Get-Content ".env" -Encoding UTF8)
if ($Lan) {
    $lines = Set-EnvLine $lines "HOST" "0.0.0.0"
} else {
    $lines = Set-EnvLine $lines "HOST" "127.0.0.1"
    $lines = Set-EnvLine $lines "CORS_ORIGINS" "http://127.0.0.1:8080,http://localhost:8080"
}
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    $lines = Set-EnvLine $lines "MODEL_BACKEND" "ollama"
}
# Sensible zero-config defaults if missing from an old .env
$lines = Set-EnvLine $lines "AUTH_ALLOW_REGISTER" "false"
$lines = Set-EnvLine $lines "WORKSPACE_ZERO_START" "true"
$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllLines((Join-Path (Get-Location) ".env"), $lines, $utf8Bom)

$portLine = ($lines | Where-Object { $_ -match "^PORT=" } | Select-Object -First 1)
$port = 8080
if ($portLine -match "^PORT=(\d+)") { $port = [int]$Matches[1] }
$appUrl = "http://127.0.0.1:$port"

Write-Host ""
if ($Lan) {
    Write-Host "Starting SecuraIQ (LAN mode)" -ForegroundColor Yellow
    Write-Host "  This PC:     $appUrl"
    try {
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
            Select-Object -ExpandProperty IPAddress -Unique |
            ForEach-Object { Write-Host "  Phone/other: http://${_}:$port" }
    } catch { }
} else {
    Write-Host "Starting SecuraIQ (localhost)" -ForegroundColor Green
    Write-Host "  LAN:   .\start.cmd -Lan"
}
Write-Host "No .env editing required. Optional keys: Settings in the UI."

$proc = Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-u", "run.py" -WorkingDirectory (Get-Location) -PassThru -NoNewWindow
$ready = $false
for ($i = 0; $i -lt 45; $i++) {
    try {
        $health = Invoke-WebRequest -Uri "$appUrl/api/health" -UseBasicParsing -TimeoutSec 3
        if ($health.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if ($ready) {
    Write-Host "  Ready: $appUrl" -ForegroundColor Green
    if (-not $NoBrowser) {
        Start-Process $appUrl
    }
} else {
    Write-Host "  Server starting — open $appUrl when ready" -ForegroundColor Yellow
}
Wait-Process -Id $proc.Id
