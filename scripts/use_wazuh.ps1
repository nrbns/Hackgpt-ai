# Configure .env for Wazuh SIEM (Windows PowerShell 5.1+ safe)
# Passwords are prompted securely (SecureString) - never pass plaintext on the command line.
# Usage:
#   .\scripts\use_wazuh.ps1 -BaseUrl https://wazuh.example:55000 -User wazuh-wui
# Optional Indexer:
#   .\scripts\use_wazuh.ps1 ... -IndexerUrl https://indexer.example:9200 -IndexerUser admin

param(
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [Parameter(Mandatory = $true)][string]$User,
    [SecureString]$Password,
    [string]$IndexerUrl = "",
    [string]$IndexerUser = "",
    [SecureString]$IndexerPassword,
    [switch]$VerifySsl
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

function ConvertFrom-SecureStringPlain {
    param([SecureString]$Secure)
    if (-not $Secure) { return "" }
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if (-not $Password) {
    $Password = Read-Host "Wazuh password" -AsSecureString
}
$plainPassword = ConvertFrom-SecureStringPlain $Password
if (-not $plainPassword) {
    throw "Wazuh password is required."
}

$plainIndexerPassword = ""
if ($IndexerUrl -and -not $IndexerPassword) {
    $IndexerPassword = Read-Host "Wazuh Indexer password (Enter to skip)" -AsSecureString
}
if ($IndexerPassword) {
    $plainIndexerPassword = ConvertFrom-SecureStringPlain $IndexerPassword
}

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
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

$lines = Get-Content ".env" -Encoding UTF8
$lines = Set-EnvLine $lines "WAZUH_BASE_URL" $BaseUrl
$lines = Set-EnvLine $lines "WAZUH_USER" $User
$lines = Set-EnvLine $lines "WAZUH_PASSWORD" $plainPassword
$lines = Set-EnvLine $lines "WAZUH_VERIFY_SSL" ($(if ($VerifySsl) { "true" } else { "false" }))
if ($IndexerUrl) {
    $lines = Set-EnvLine $lines "WAZUH_INDEXER_URL" $IndexerUrl
}
if ($IndexerUser) {
    $lines = Set-EnvLine $lines "WAZUH_INDEXER_USER" $IndexerUser
}
if ($plainIndexerPassword) {
    $lines = Set-EnvLine $lines "WAZUH_INDEXER_PASSWORD" $plainIndexerPassword
}

# Clear plaintext from memory as soon as written
$plainPassword = $null
$plainIndexerPassword = $null

# UTF-8 with BOM so Windows PowerShell 5.1 reloads Unicode safely next time
$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllLines((Join-Path (Get-Location) ".env"), $lines, $utf8Bom)

Write-Host "Configured Wazuh in .env (password stored in .env only - not printed)"
Write-Host "  Manager: $BaseUrl"
Write-Host "  User:    $User"
Write-Host "  Password: ********"
if ($IndexerUrl) { Write-Host "  Indexer: $IndexerUrl" }
Write-Host "Restart SecuraIQ, then open Incidents (SOC) -> Sync Wazuh"
Write-Host "Or: .\scripts\start.ps1"
