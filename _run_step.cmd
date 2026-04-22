@echo off
cd /d "C:\Tool_App\tool_manager_v2\ToolManager_V14_Fase1\tool_manager\step_analyzer"
echo === STEP Analyzer ===
uvicorn main:app --host 127.0.0.1 --port 8002
