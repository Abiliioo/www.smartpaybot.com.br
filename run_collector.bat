@echo off
setlocal

cd /d "%~dp0"

if not exist "logs" mkdir "logs"

".venv\Scripts\python.exe" "scripts\local_collector_push.py" --pages 10 >> "logs\collector.log" 2>&1

set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
