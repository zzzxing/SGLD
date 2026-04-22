@echo off
cd /d %~dp0

python scripts\bootstrap.py
if errorlevel 1 (
  echo Bootstrap failed.
)

if not exist .venv\Scripts\python.exe (
  echo Missing venv python. Abort.
  pause
  exit /b 1
)

.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
