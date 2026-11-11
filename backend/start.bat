@echo off
REM Starts the voice agent API on port 8000
cd /d "%~dp0"
call venv\Scripts\activate.bat
uvicorn app.main:app --host 127.0.0.1 --port 8000
