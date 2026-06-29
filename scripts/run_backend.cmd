@echo off
setlocal

cd /d "%~dp0.."
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo Backend runtime was not found at %PYTHON_EXE%.
  echo Create it first, then install backend/requirements.txt.
  exit /b 1
)

"%PYTHON_EXE%" -m uvicorn backend.app.main:app --app-dir "%CD%" --host 127.0.0.1 --port 8001 --reload
