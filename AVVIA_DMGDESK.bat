@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul
title DMGDesk - Launcher

REM -- Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato nel PATH.
    pause & exit /b 1
)

:start_services

REM -- Kill servizi gia in esecuzione
echo Pulizia porte 8000 e 8002...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8002 "') do taskkill /F /PID %%p >nul 2>&1
timeout /t 1 /nobreak >nul

REM -- Frontend build se necessario
if not exist "%~dp0frontend\dist\index.html" (
    echo Build frontend necessaria...
    if not exist "%~dp0frontend\node_modules" (
        cd "%~dp0frontend" && call npm install && cd "%~dp0"
    )
    cd "%~dp0frontend" && call npm run build && cd "%~dp0"
    if not exist "%~dp0frontend\dist\index.html" (
        echo [ERRORE] Build frontend fallita
        pause & exit /b 1
    )
    echo Build completata.
)

REM -- Crea script temporanei per ogni servizio
echo @echo off > "%~dp0_run_backend.cmd"
echo cd /d "%~dp0" >> "%~dp0_run_backend.cmd"
echo echo === DMGDesk Backend === >> "%~dp0_run_backend.cmd"
echo uvicorn api.main:app --host 0.0.0.0 --port 8000 >> "%~dp0_run_backend.cmd"

echo @echo off > "%~dp0_run_step.cmd"
echo cd /d "%~dp0step_analyzer" >> "%~dp0_run_step.cmd"
echo echo === STEP Analyzer === >> "%~dp0_run_step.cmd"
echo uvicorn main:app --host 127.0.0.1 --port 8002 >> "%~dp0_run_step.cmd"

echo @echo off > "%~dp0_run_cam.cmd"
echo cd /d "%~dp0cam_tracker" >> "%~dp0_run_cam.cmd"
echo echo === CAM Tracker === >> "%~dp0_run_cam.cmd"
echo python cam_tracker.py >> "%~dp0_run_cam.cmd"

REM -- Avvia Windows Terminal con 4 tab
echo Avvio servizi...
wt --maximized new-tab --title "Backend" --tabColor "#0d2d5e" cmd /k "%~dp0_run_backend.cmd" ^; new-tab --title "STEP" --tabColor "#1a4a2e" cmd /k "%~dp0_run_step.cmd" ^; new-tab --title "CAM" --tabColor "#4a2e1a" cmd /k "%~dp0_run_cam.cmd" ^; new-tab --title "Launcher" --tabColor "#2e1a4a" cmd /k "%~dp0_run_launcher.cmd"

REM -- Apri browser
timeout /t 4 /nobreak >nul
start "" http://localhost:8000

echo.
echo  Servizi avviati.
echo  Browser: http://localhost:8000

REM -- Chiudi questa finestra, il launcher e' nel tab wt
exit
echo  S = riavvio solo server
echo  U = git pull + riavvio solo backend
echo.

:wait_input
set /p CMD="Comando (R/S/U): "

if /i "!CMD!"=="r" (
    echo Aggiornamento + riavvio...
    git pull origin main
    if errorlevel 1 ( echo [ERRORE] git pull fallito & goto wait_input )
    goto start_services
)

if /i "!CMD!"=="s" (
    echo Riavvio server...
    goto start_services
)

if /i "!CMD!"=="u" (
    echo Aggiornamento backend...
    git pull origin main
    for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do taskkill /F /PID %%p >nul 2>&1
    timeout /t 1 /nobreak >nul
    start "Backend" cmd /k "%~dp0_run_backend.cmd"
    echo Backend riavviato.
    goto wait_input
)

goto wait_input
