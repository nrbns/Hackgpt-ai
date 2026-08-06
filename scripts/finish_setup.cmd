@echo off
cd /d "%~dp0"
call "%~dp0_ps.cmd" finish_setup.ps1 %*
