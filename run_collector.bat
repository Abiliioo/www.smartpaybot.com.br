@echo off

cd /d C:\Python\SmartPayBot

.venv\Scripts\python.exe scripts\local_collector_push.py --pages 10 >> logs\collector.log 2>&1