@echo off
REM SecuraIQ PowerShell launcher - always runs (Bypass + Unblock).
REM Usage: _ps.cmd script.ps1 [args...]
REM IMPORTANT: Do not use "shift" then "%*" - on Windows, %* is NOT updated by SHIFT,
REM so "-Lan" would never reach the .ps1 (or the script name would be passed twice).
setlocal EnableExtensions
cd /d "%~dp0.."

if "%~1"=="" (
  echo Usage: %~nx0 ^<script.ps1^> [args...]
  exit /b 1
)

set "SCRIPT=%~dp0%~1"
if not exist "%SCRIPT%" (
  echo Script not found: %SCRIPT%
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Unblock-File -LiteralPath '%SCRIPT%' -ErrorAction SilentlyContinue" >nul 2>&1

REM Forward only user args (%2..%9). Enough for our switches (-Lan, -NoBrowser, etc.).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%
