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

REM -- Avvia 3 finestre separate
echo Avvio servizi...
start "DMGDesk Backend :8000" cmd /k "cd /d "%~dp0" && echo === DMGDesk Backend === && uvicorn api.main:app --host 0.0.0.0 --port 8000"
timeout /t 2 /nobreak >nul
start "STEP Analyzer :8002" cmd /k "cd /d "%~dp0step_analyzer" && echo === STEP Analyzer === && uvicorn main:app --host 127.0.0.1 --port 8002"
start "CAM Tracker" cmd /k "cd /d "%~dp0cam_tracker" && echo === CAM Tracker === && python cam_tracker.py"

REM -- Apri browser
timeout /t 4 /nobreak >nul
start "" http://localhost:8000

echo.
echo  Servizi avviati.
echo  Browser: http://localhost:8000
echo.
echo  R = git pull + riavvio tutto
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
    start "DMGDesk Backend :8000" cmd /k "cd /d "%~dp0" && echo === DMGDesk Backend === && uvicorn api.main:app --host 0.0.0.0 --port 8000"
    echo Backend riavviato.
    goto wait_input
)

goto wait_input
