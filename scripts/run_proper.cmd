@echo off
REM Full setup + start SecuraIQ. Use: run_proper.cmd -Lan  for phones on Wi-Fi
cd /d "%~dp0"
call "%~dp0_ps.cmd" run_proper.ps1 %*
