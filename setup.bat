@echo off
REM Local development: sets up all three parts (MCP server, backend, frontend)
call "%~dp0mcp-server\setup.bat"
call "%~dp0backend\setup.bat"
cd /d "%~dp0frontend"
call npm install
