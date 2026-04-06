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
set ROOT=%~dp0

echo @echo off > "%ROOT%_run_backend.cmd"
echo chcp 65001 ^>nul >> "%ROOT%_run_backend.cmd"
echo cd /d "%ROOT%" >> "%ROOT%_run_backend.cmd"
echo echo  === DMGDesk Backend :8000 === >> "%ROOT%_run_backend.cmd"
echo uvicorn api.main:app --host 0.0.0.0 --port 8000 >> "%ROOT%_run_backend.cmd"

echo @echo off > "%ROOT%_run_step.cmd"
echo chcp 65001 ^>nul >> "%ROOT%_run_step.cmd"
echo cd /d "%ROOT%step_analyzer" >> "%ROOT%_run_step.cmd"
echo echo  === STEP Analyzer :8002 === >> "%ROOT%_run_step.cmd"
echo uvicorn main:app --host 127.0.0.1 --port 8002 >> "%ROOT%_run_step.cmd"

echo @echo off > "%ROOT%_run_cam.cmd"
echo chcp 65001 ^>nul >> "%ROOT%_run_cam.cmd"
echo cd /d "%ROOT%cam_tracker" >> "%ROOT%_run_cam.cmd"
echo echo  === CAM Tracker === >> "%ROOT%_run_cam.cmd"
echo python cam_tracker.py >> "%ROOT%_run_cam.cmd"

REM -- Avvia Windows Terminal con 3 pannelli
REM   Layout: Backend (sinistra) | STEP Analyzer (destra alta)
REM                               | CAM Tracker   (destra bassa)
wt --maximized new-tab --title "DMGDesk" --tabColor "#0d2d5e" cmd /k "%ROOT%_run_backend.cmd" ^; split-pane --vertical --size 0.35 --title "STEP Analyzer" --tabColor "#1a4a2e" cmd /k "%ROOT%_run_step.cmd" ^; split-pane --horizontal --title "CAM Tracker" --tabColor "#4a2e1a" cmd /k "%ROOT%_run_cam.cmd"

REM -- Apri browser
timeout /t 5 /nobreak >nul
start "" http://localhost:8000

echo.
echo  Servizi avviati. Browser: http://localhost:8000
echo.
echo  Comandi:
echo    R = git pull + riavvio tutto
echo    S = riavvio solo server
echo    U = git pull + riavvio solo backend
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
    for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8002 "') do taskkill /F /PID %%p >nul 2>&1
    timeout /t 1 /nobreak >nul
    wt --maximized new-tab --title "DMGDesk" --tabColor "#0d2d5e" cmd /k "%ROOT%_run_backend.cmd" ^; split-pane --vertical --size 0.35 --title "STEP Analyzer" --tabColor "#1a4a2e" cmd /k "%ROOT%_run_step.cmd" ^; split-pane --horizontal --title "CAM Tracker" --tabColor "#4a2e1a" cmd /k "%ROOT%_run_cam.cmd"
    echo Backend riavviato.
    goto wait_input
)

goto wait_input
