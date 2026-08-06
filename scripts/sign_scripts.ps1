# Create a local SecuraIQ code-signing certificate, trust it for this user,
# and Authenticode-sign every scripts\*.ps1 so AllSigned / RemoteSigned policies accept them.
#
# Usage:
#   .\scripts\sign_scripts.cmd
#   .\scripts\sign_scripts.ps1
#   .\scripts\sign_scripts.ps1 -ForceNewCert
#
# Does NOT require admin. Certificate stays in CurrentUser stores (not exported to the repo).

param(
    [switch]$ForceNewCert,
    [string]$Subject = "CN=SecuraIQ Local Code Signing"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

function Get-SecuraIQCert {
    $existing = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert -ErrorAction SilentlyContinue |
        Where-Object { $_.Subject -eq $Subject -and $_.NotAfter -gt (Get-Date) } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1
    if ($existing -and -not $ForceNewCert) {
        return $existing
    }
    Write-Host "Creating self-signed code-signing certificate: $Subject"
    return New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $Subject `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyExportPolicy Exportable `
        -KeySpec Signature `
        -KeyLength 2048 `
        -HashAlgorithm SHA256 `
        -NotAfter (Get-Date).AddYears(5)
}

function Ensure-Trusted {
    param([System.Security.Cryptography.X509Certificates.X509Certificate2]$Cert)

    foreach ($storeName in @("Root", "TrustedPublisher")) {
        $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($storeName, "CurrentUser")
        $store.Open("ReadWrite")
        try {
            $found = $store.Certificates | Where-Object { $_.Thumbprint -eq $Cert.Thumbprint }
            if (-not $found) {
                Write-Host "Trusting certificate in CurrentUser\$storeName"
                $store.Add($Cert) | Out-Null
            }
        } finally {
            $store.Close()
        }
    }
}

function Remove-AuthenticodeBlock {
    param([string]$Text)
    # Build markers at runtime so this file is never truncated by strip tools
    $begin = "# SIG # Begin" + " signature block"
    $end = "# SIG # End" + " signature block"
    $pattern = "(?ms)\r?\n?" + [regex]::Escape($begin) + ".*" + [regex]::Escape($end) + "\s*$"
    return [regex]::Replace($Text, $pattern, "")
}

$cert = Get-SecuraIQCert
Ensure-Trusted -Cert $cert
Write-Host "Using cert thumbprint: $($cert.Thumbprint)"
Write-Host "Valid until: $($cert.NotAfter.ToString('u'))"

$scripts = Get-ChildItem -Path (Join-Path $root "*.ps1") -File |
    Where-Object { $_.Name -ne "sign_scripts.ps1" }

# Sign the signer last so its own signature is included after edits
$scripts = @($scripts) + @(Get-Item (Join-Path $root "sign_scripts.ps1"))

$ok = 0
$fail = 0
foreach ($file in $scripts) {
    try {
        $content = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
        $stripped = Remove-AuthenticodeBlock -Text $content
        if ($stripped -ne $content) {
            $utf8Bom = New-Object System.Text.UTF8Encoding $true
            [System.IO.File]::WriteAllText($file.FullName, $stripped.TrimEnd() + "`r`n", $utf8Bom)
        }
    } catch {
        Write-Host "  WARN strip $($file.Name): $_" -ForegroundColor Yellow
    }

    Unblock-File -LiteralPath $file.FullName -ErrorAction SilentlyContinue
    $sig = Set-AuthenticodeSignature -FilePath $file.FullName -Certificate $cert -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com" -ErrorAction SilentlyContinue
    if (-not $sig -or $sig.Status -notin @("Valid", "UnknownError")) {
        $sig = Set-AuthenticodeSignature -FilePath $file.FullName -Certificate $cert -HashAlgorithm SHA256
    }
    $status = if ($sig) { $sig.Status.ToString() } else { "Failed" }
    if ($status -eq "Valid") {
        Write-Host "  OK  $($file.Name)" -ForegroundColor Green
        $ok++
    } else {
        $check = Get-AuthenticodeSignature -FilePath $file.FullName
        if ($check.SignerCertificate -and $check.SignerCertificate.Thumbprint -eq $cert.Thumbprint) {
            Write-Host "  OK  $($file.Name) (signed; status=$($check.Status))" -ForegroundColor Green
            $ok++
        } else {
            Write-Host "  FAIL $($file.Name) status=$status" -ForegroundColor Red
            $fail++
        }
    }
}

Write-Host ""
Write-Host "Signed $ok script(s); failures: $fail"
Write-Host "Trusted for CurrentUser. Double-click start.cmd anytime (works even without signing)."
if ($fail -gt 0) { exit 1 }
