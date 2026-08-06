@echo off
cd /d "%~dp0"
call "%~dp0_ps.cmd" enable_secure_mode.ps1 %*
