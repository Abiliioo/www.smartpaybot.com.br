@echo off
setlocal

cd /d "%~dp0"

if not exist "logs" mkdir "logs"

rem Forca a saida do Python em UTF-8
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

>> "logs\collector.log" echo.
>> "logs\collector.log" echo ============================================================
>> "logs\collector.log" echo [%DATE% %TIME%] INICIO DO COLETOR
>> "logs\collector.log" echo ============================================================

".venv\Scripts\python.exe" -X utf8 -u "scripts\local_collector_push.py" --pages 10 >> "logs\collector.log" 2>&1

set "EXIT_CODE=%ERRORLEVEL%"

>> "logs\collector.log" echo ------------------------------------------------------------
>> "logs\collector.log" echo [%DATE% %TIME%] FIM DO COLETOR - EXIT_CODE=%EXIT_CODE%
>> "logs\collector.log" echo ------------------------------------------------------------

endlocal & exit /b %EXIT_CODE%