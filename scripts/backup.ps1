# SecuraIQ backup (Windows) — copies SQLite DB + chroma index + uploads.
# Usage: .\scripts\backup.ps1 [-BackupRoot backups]
param(
    [string]$BackupRoot = "backups"
)
Set-Location -Path (Split-Path -Parent $PSScriptRoot)

$DataDir = if ($env:DATA_DIR) { $env:DATA_DIR } else { "data" }
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$OutDir = Join-Path $BackupRoot $Stamp
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$DbPath = Join-Path $DataDir "securaiq.db"
if (Test-Path $DbPath) {
    Write-Host "Backing up SQLite DB..."
    # Prefer the sqlite3 CLI online backup if available (safe under WAL); fall back to file copy.
    $sqlite3 = Get-Command sqlite3 -ErrorAction SilentlyContinue
    if ($sqlite3) {
        & sqlite3 $DbPath ".backup '$OutDir\securaiq.db'"
    } else {
        Write-Warning "sqlite3 CLI not found — falling back to a plain file copy (stop the app first to avoid a WAL-inconsistent copy)."
        Copy-Item $DbPath (Join-Path $OutDir "securaiq.db")
    }
} else {
    Write-Warning "$DbPath not found — skipping DB backup."
}

$ChromaDir = Join-Path $DataDir "chroma"
if (Test-Path $ChromaDir) {
    Write-Host "Archiving Chroma vector index..."
    Compress-Archive -Path $ChromaDir -DestinationPath (Join-Path $OutDir "chroma.zip") -Force
}

$UploadsDir = Join-Path $DataDir "uploads"
if (Test-Path $UploadsDir) {
    Write-Host "Archiving uploaded evidence/files..."
    Compress-Archive -Path $UploadsDir -DestinationPath (Join-Path $OutDir "uploads.zip") -Force
}

Write-Host "NOTE: .env (secrets) is intentionally NOT included — back it up separately."
Write-Host "Backup complete: $OutDir"
