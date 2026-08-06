@echo off
REM Start SecuraIQ (localhost). Use: start.cmd -Lan  for phones on Wi-Fi
cd /d "%~dp0"
call "%~dp0_ps.cmd" start.ps1 %*
