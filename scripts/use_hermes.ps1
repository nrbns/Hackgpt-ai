$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
}

$content = Get-Content ".env" -Raw
foreach ($pair in @(
    @{k='HERMES_BASE_URL';v='http://127.0.0.1:8642/v1'},
    @{k='HERMES_MODEL';v='hermes-agent'},
    @{k='HERMES_API_KEY';v='change-me-local-dev'},
    @{k='HERMES_SESSION_KEY';v='securaiq-pentest'},
    @{k='HERMES_SHOW_TOOL_PROGRESS';v='true'}
)) {
    if ($content -notmatch "(?m)^$($pair.k)=") {
        $content = $content.TrimEnd() + "`r`n$($pair.k)=$($pair.v)`r`n"
    }
}
$content = $content -replace "(?m)^MODEL_BACKEND=.*", "MODEL_BACKEND=hermes"
$content = $content -replace "(?m)^HERMES_BASE_URL=.*", "HERMES_BASE_URL=http://127.0.0.1:8642/v1"
$content = $content -replace "(?m)^HERMES_MODEL=.*", "HERMES_MODEL=hermes-agent"
$content = $content -replace "(?m)^HERMES_API_KEY=.*", "HERMES_API_KEY=change-me-local-dev"
$content = $content -replace "(?m)^HERMES_SESSION_KEY=.*", "HERMES_SESSION_KEY=securaiq-pentest"
$content = $content -replace "(?m)^HERMES_SHOW_TOOL_PROGRESS=.*", "HERMES_SHOW_TOOL_PROGRESS=true"
Set-Content ".env" -Value $content -NoNewline

# Best-effort: enable Hermes API server env if Hermes home exists
$hermesEnvCandidates = @(
    (Join-Path $env:LOCALAPPDATA "hermes\.env"),
    (Join-Path $env:USERPROFILE ".hermes\.env")
)
foreach ($he in $hermesEnvCandidates) {
    if (Test-Path $he) {
        $ht = Get-Content $he -Raw
        if ($ht -notmatch "(?m)^API_SERVER_ENABLED=") { $ht = $ht.TrimEnd() + "`r`nAPI_SERVER_ENABLED=true`r`n" }
        else { $ht = $ht -replace "(?m)^API_SERVER_ENABLED=.*", "API_SERVER_ENABLED=true" }
        if ($ht -notmatch "(?m)^API_SERVER_KEY=") { $ht = $ht.TrimEnd() + "`r`nAPI_SERVER_KEY=change-me-local-dev`r`n" }
        else { $ht = $ht -replace "(?m)^API_SERVER_KEY=.*", "API_SERVER_KEY=change-me-local-dev" }
        Set-Content $he -Value $ht -NoNewline
        Write-Host "Updated Hermes API server flags in $he"
        break
    }
}

Write-Host ""
Write-Host "Configured SecuraIQ for full Hermes Agent integration."
Write-Host "Repo: https://github.com/NousResearch/hermes-agent"
Write-Host ""
Write-Host "1. Install (once): iex (irm https://hermes-agent.nousresearch.com/install.ps1)"
Write-Host "2. hermes setup   OR   hermes setup --portal"
Write-Host "3. hermes gateway   # API on http://127.0.0.1:8642/v1"
Write-Host "4. .\scripts\start.ps1  then select Hermes Agent (or already MODEL_BACKEND=hermes)"
Write-Host "5. UI: Settings → Hermes status / New Hermes session / tool progress"
Write-Host ""
Write-Host "Features wired: chat completions, session id/key, tool progress, /api/hermes/status"
