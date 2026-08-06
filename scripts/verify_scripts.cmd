@echo off
cd /d "%~dp0"
call "%~dp0_ps.cmd" verify_scripts.ps1 %*
