@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul
title DMGDesk - Launcher

python --version >nul 2>&1
if errorlevel 1 ( echo [ERRORE] Python non trovato. & pause & exit /b 1 )

:start_services

echo Pulizia porte 8000 e 8002...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8002 "') do taskkill /F /PID %%p >nul 2>&1
timeout /t 1 /nobreak >nul

if not exist "%~dp0frontend\dist\index.html" (
    echo Build frontend...
    if not exist "%~dp0frontend\node_modules" ( cd "%~dp0frontend" && call npm install && cd "%~dp0" )
    cd "%~dp0frontend" && call npm run build && cd "%~dp0"
    if not exist "%~dp0frontend\dist\index.html" ( echo [ERRORE] Build fallita & pause & exit /b 1 )
)

REM -- Scrive i 3 script di servizio usando PowerShell (evita problemi con echo e path con spazi)
powershell -NoProfile -Command "$r='%~dp0'; [IO.File]::WriteAllText($r+'_run_backend.cmd', \"@echo off`r`ncd /d \`\"$r\`\"`r`necho === DMGDesk Backend ===\"+\"`r`nuvicorn api.main:app --host 0.0.0.0 --port 8000`r`n\"); [IO.File]::WriteAllText($r+'_run_step.cmd', \"@echo off`r`ncd /d \`\"$($r)step_analyzer\`\"`r`necho === STEP Analyzer ===\"+\"`r`nuvicorn main:app --host 127.0.0.1 --port 8002`r`n\"); [IO.File]::WriteAllText($r+'_run_cam.cmd', \"@echo off`r`ncd /d \`\"$($r)cam_tracker\`\"`r`necho === CAM Tracker ===\"+\"`r`npython cam_tracker.py`r`n\")"

echo Avvio servizi in Windows Terminal...
wt --maximized new-tab --title "Backend" --tabColor "#0d2d5e" cmd /k "%~dp0_run_backend.cmd" ^; new-tab --title "STEP" --tabColor "#1a4a2e" cmd /k "%~dp0_run_step.cmd" ^; new-tab --title "CAM" --tabColor "#4a2e1a" cmd /k "%~dp0_run_cam.cmd" ^; new-tab --title "Launcher" --tabColor "#2e1a4a" cmd /k "%~dp0_run_launcher.cmd"

timeout /t 4 /nobreak >nul
start "" http://localhost:8000
exit
