@echo off
REM SecuraIQ PowerShell launcher — always runs (Bypass + Unblock).
REM Usage: _ps.cmd script.ps1 [args...]
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

REM Drop script name from %%* so only user args remain
shift /1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
exit /b %ERRORLEVEL%
