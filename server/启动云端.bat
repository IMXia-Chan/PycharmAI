@echo off
title Python Assistant Cloud Server
cd /d "%~dp0"
if exist "D:\AI\python.exe" (
    "D:\AI\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8001
) else (
    python -m uvicorn main:app --host 127.0.0.1 --port 8001
)
echo.
echo Cloud server stopped. Press any key to close.
pause >nul
