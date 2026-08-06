@echo off
REM Double-click first-time setup + start
cd /d "%~dp0"
call "%~dp0scripts\run_proper.cmd" %*
