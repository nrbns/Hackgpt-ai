@echo off
REM Double-click to start SecuraIQ reachable by phones / other PCs on the same Wi‑Fi.
REM Prints http://YOUR-LAN-IP:8080 — open that URL on the other device.
cd /d "%~dp0"
call "%~dp0scripts\start.cmd" -Lan %*
