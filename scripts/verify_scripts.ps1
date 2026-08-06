# Verify every scripts\*.ps1 parses and (when signed) has a trusted Authenticode signature.
param(
    [switch]$RequireSignature
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$fail = 0

Write-Host "SecuraIQ script verification" -ForegroundColor Cyan
Write-Host "ExecutionPolicy: $(Get-ExecutionPolicy -Scope Process) / LocalMachine=$(Get-ExecutionPolicy -Scope LocalMachine) / CurrentUser=$(Get-ExecutionPolicy -Scope CurrentUser)"

foreach ($file in Get-ChildItem -Path (Join-Path $root "*.ps1") -File) {
    $errs = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$null, [ref]$errs)
    if ($errs -and $errs.Count -gt 0) {
        Write-Host "  PARSE FAIL $($file.Name): $($errs[0].Message)" -ForegroundColor Red
        $fail++
        continue
    }

    $sig = Get-AuthenticodeSignature -FilePath $file.FullName
    $sigLabel = $sig.Status.ToString()
    if ($sig.SignerCertificate) {
        $sigLabel += " [$($sig.SignerCertificate.Subject)]"
    }

    if ($RequireSignature -and $sig.Status -ne "Valid") {
        Write-Host "  SIG FAIL $($file.Name): $sigLabel" -ForegroundColor Red
        $fail++
        continue
    }

    Write-Host "  OK $($file.Name)  parse + $sigLabel" -ForegroundColor Green
}

$cmds = @("_ps.cmd", "start.cmd", "run_proper.cmd", "sign_scripts.cmd")
foreach ($name in $cmds) {
    $p = Join-Path $root $name
    if (Test-Path $p) {
        Write-Host "  OK $name (launcher present)" -ForegroundColor Green
    } else {
        Write-Host "  FAIL missing $name" -ForegroundColor Red
        $fail++
    }
}

foreach ($name in @("start.cmd", "run_proper.cmd")) {
    $p = Join-Path (Join-Path $root "..") $name
    if (Test-Path $p) {
        Write-Host "  OK ../$name (root launcher)" -ForegroundColor Green
    } else {
        Write-Host "  FAIL missing ../$name" -ForegroundColor Red
        $fail++
    }
}

Write-Host ""
if ($fail -gt 0) {
    Write-Host "FAILED checks: $fail" -ForegroundColor Red
    exit 1
}
Write-Host "All checks passed - use start.cmd / run_proper.cmd for no-doubt launches." -ForegroundColor Green
