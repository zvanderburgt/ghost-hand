@echo off
rem Launch the tray app without a console window.
setlocal
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "src\main.py" %*
