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

REM -- Verifica Windows Terminal
wt --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Windows Terminal non trovato.
    echo Installalo da: https://aka.ms/terminal
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

REM -- Comandi per ogni pannello
set ROOT=%~dp0

set CMD_BACKEND=cd /d "%ROOT%" ^&^& echo. ^&^& echo  === DMGDesk Backend === ^&^& echo. ^&^& uvicorn api.main:app --host 0.0.0.0 --port 8000

set CMD_STEP=cd /d "%ROOT%step_analyzer" ^&^& echo. ^&^& echo  === STEP Analyzer === ^&^& echo. ^&^& uvicorn main:app --host 127.0.0.1 --port 8002

set CMD_CAM=cd /d "%ROOT%cam_tracker" ^&^& echo. ^&^& echo  === CAM Tracker === ^&^& echo. ^&^& python cam_tracker.py

REM -- Apri Windows Terminal
REM   Layout: Backend (sinistra grande) | STEP Analyzer (destra alta)
REM                                     | CAM Tracker   (destra bassa)
wt --maximized ^
   new-tab --title "DMGDesk Backend" --tabColor "#0d2d5e" cmd /k "%CMD_BACKEND%" ^
   ; split-pane --vertical --size 0.35 --title "STEP Analyzer" --tabColor "#1a4a2e" cmd /k "%CMD_STEP%" ^
   ; split-pane --horizontal --title "CAM Tracker" --tabColor "#4a2e1a" cmd /k "%CMD_CAM%"

REM -- Apri browser dopo che i servizi sono partiti
timeout /t 5 /nobreak >nul
start "" http://localhost:8000

echo.
echo  Servizi avviati. Browser aperto su http://localhost:8000
echo.
echo  Comandi:
echo    R + Invio  = git pull + riavvio tutto
echo    S + Invio  = riavvio solo server
echo    U + Invio  = git pull + riavvio solo backend
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
    wt --maximized ^
       new-tab --title "DMGDesk Backend" --tabColor "#0d2d5e" cmd /k "%CMD_BACKEND%" ^
       ; split-pane --vertical --size 0.35 --title "STEP Analyzer" --tabColor "#1a4a2e" cmd /k "%CMD_STEP%" ^
       ; split-pane --horizontal --title "CAM Tracker" --tabColor "#4a2e1a" cmd /k "%CMD_CAM%"
    echo Backend riavviato.
    goto wait_input
)

goto wait_input
