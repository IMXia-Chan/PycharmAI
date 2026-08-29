@echo off
title Python Assistant Backend
cd /d "%~dp0"
if exist "D:\AI\python.exe" (
    "D:\AI\python.exe" -m backend.main
) else (
    python -m backend.main
)
echo.
echo Backend stopped. Press any key to close.
pause >nul
