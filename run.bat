@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Setting up NetSpeedTray...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

if /I "%~1"=="--console" (
  ".venv\Scripts\python.exe" main.py
) else (
  start "" ".venv\Scripts\pythonw.exe" main.py
)
