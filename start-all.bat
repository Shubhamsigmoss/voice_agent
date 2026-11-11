@echo off
REM Local development: starts all three services in separate windows
start "1 - Sales MCP Server (8001)" /D "%~dp0mcp-server" cmd /k "venv\Scripts\activate.bat && python -m app.mcp_server"
timeout /t 3 /nobreak >nul
start "2 - Voice Agent API (8000)" /D "%~dp0backend" cmd /k "venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"
start "3 - React UI (5173)" /D "%~dp0frontend" cmd /k "npm run dev"
timeout /t 6 /nobreak >nul
start "" http://localhost:5173
