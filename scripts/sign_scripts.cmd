@echo off
REM Create/trust local SecuraIQ code-signing cert and sign all scripts\*.ps1
cd /d "%~dp0"
call "%~dp0_ps.cmd" sign_scripts.ps1 %*
