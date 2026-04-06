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

REM -- Scrive script backend usando set per il path
set PROJ=%~dp0
set PROJ=%PROJ:~0,-1%

(
    echo @echo off
    echo cd /d "%PROJ%"
    echo echo === DMGDesk Backend ===
    echo uvicorn api.main:app --host 0.0.0.0 --port 8000
) > "%~dp0_run_backend.cmd"

(
    echo @echo off
    echo cd /d "%PROJ%\step_analyzer"
    echo echo === STEP Analyzer ===
    echo uvicorn main:app --host 127.0.0.1 --port 8002
) > "%~dp0_run_step.cmd"

(
    echo @echo off
    echo cd /d "%PROJ%\cam_tracker"
    echo echo === CAM Tracker ===
    echo python cam_tracker.py
) > "%~dp0_run_cam.cmd"

echo Avvio servizi...
wt --maximized new-tab --title "Backend" --tabColor "#0d2d5e" cmd /k "%~dp0_run_backend.cmd" ^; new-tab --title "STEP" --tabColor "#1a4a2e" cmd /k "%~dp0_run_step.cmd" ^; new-tab --title "CAM" --tabColor "#4a2e1a" cmd /k "%~dp0_run_cam.cmd" ^; new-tab --title "Launcher" --tabColor "#2e1a4a" cmd /k "%~dp0_run_launcher.cmd"

timeout /t 4 /nobreak >nul
start "" http://localhost:8000
exit
