@echo off
cd /d %~dp0

set BOOTSTRAP_CMD=python scripts\bootstrap.py
where python >nul 2>nul
if errorlevel 1 (
  set BOOTSTRAP_CMD=py -3 scripts\bootstrap.py
)

%BOOTSTRAP_CMD%
if errorlevel 1 (
  echo [ERROR] Bootstrap failed. Abort.
  echo [TIP] If .venv is broken, delete it and retry:
  echo       rmdir /s /q .venv
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo [ERROR] Missing .venv\Scripts\python.exe. Abort.
  pause
  exit /b 1
)

.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
