@echo off
REM Voice agent backend - one-time setup (own venv, independent from the MCP server)
cd /d "%~dp0"
if not exist venv ( python -m venv venv || goto :err )
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :err
if not exist .env copy .env.example .env
echo.
echo Setup complete. Fill in LLM_API_KEY, MCP_SERVER_URL and MCP_AUTH_TOKEN in backend\.env, then run start.bat
pause
exit /b 0
:err
echo Setup failed. See the error above.
pause
exit /b 1
