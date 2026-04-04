@echo off
cd /d "%~dp0"
echo Avvio STEP Analyzer su http://localhost:8001
uvicorn main:app --host 127.0.0.1 --port 8002 --reload
pause
