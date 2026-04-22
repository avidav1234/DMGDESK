@echo off
cd /d "C:\Tool_App\tool_manager_v2\ToolManager_V14_Fase1\tool_manager"
echo === DMGDesk Backend ===
uvicorn api.main:app --host 0.0.0.0 --port 8000
