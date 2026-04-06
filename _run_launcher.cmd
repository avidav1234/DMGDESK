@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  === DMGDesk Launcher ===
echo.
echo  Browser: http://localhost:8000
echo.
echo  R = git pull + riavvio tutto
echo  S = riavvio solo server
echo  U = git pull + riavvio solo backend
echo.

:loop
set /p CMD="Comando (R/S/U): "

if /i "!CMD!"=="r" (
    echo Aggiornamento + riavvio...
    git pull origin main
    if errorlevel 1 ( echo [ERRORE] git pull fallito & goto loop )
    echo Riavvio servizi...
    start "" cmd /c "%~dp0AVVIA_DMGDESK.bat"
    exit
)

if /i "!CMD!"=="s" (
    echo Riavvio server...
    start "" cmd /c "%~dp0AVVIA_DMGDESK.bat"
    exit
)

if /i "!CMD!"=="u" (
    echo Aggiornamento backend...
    git pull origin main
    if errorlevel 1 ( echo [ERRORE] git pull fallito & goto loop )
    for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do taskkill /F /PID %%p >nul 2>&1
    timeout /t 1 /nobreak >nul
    start "DMGDesk Backend" cmd /k "%~dp0_run_backend.cmd"
    echo Backend riavviato.
    goto loop
)

goto loop
