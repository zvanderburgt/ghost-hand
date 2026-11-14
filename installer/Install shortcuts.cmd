@echo off
title Ghost Hand - install shortcuts
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-local.ps1" -Launch
if errorlevel 1 (
    echo.
    echo Setup did not finish. The message above explains why.
    pause
)
