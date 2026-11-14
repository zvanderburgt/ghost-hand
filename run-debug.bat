@echo off
rem Launch with a console so tracebacks are visible.
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" "src\main.py" %*
