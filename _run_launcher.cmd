@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  === DMGDesk Launcher ===
echo.
echo  Browser: http://localhost:8000
echo.
echo  R = git pull + rebuild frontend + riavvio tutto
echo  S = riavvio solo server (senza rebuild)
echo  U = git pull + riavvio solo backend (senza rebuild)
echo  F = rebuild frontend + riavvio (senza git pull)
echo.

:loop
set /p CMD="Comando (R/S/U/F): "

if /i "!CMD!"=="r" (
    echo.
    echo  [1/3] git pull...
    git pull origin main
    if errorlevel 1 ( echo [ERRORE] git pull fallito & goto loop )
    echo  [2/3] Rebuild frontend...
    cd /d "%~dp0frontend"
    call npm run build
    cd /d "%~dp0"
    if errorlevel 1 ( echo [ERRORE] Build fallita & goto loop )
    echo  [3/3] Riavvio servizi...
    start "" cmd /c "%~dp0AVVIA_DMGDESK.bat"
    exit
)

if /i "!CMD!"=="s" (
    echo Riavvio server...
    start "" cmd /c "%~dp0AVVIA_DMGDESK.bat"
    exit
)

if /i "!CMD!"=="u" (
    echo.
    echo  [1/2] git pull...
    git pull origin main
    if errorlevel 1 ( echo [ERRORE] git pull fallito & goto loop )
    echo  [2/2] Riavvio backend...
    for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do taskkill /F /PID %%p >nul 2>&1
    timeout /t 1 /nobreak >nul
    start "DMGDesk Backend" cmd /k "%~dp0_run_backend.cmd"
    echo Backend riavviato.
    goto loop
)

if /i "!CMD!"=="f" (
    echo.
    echo  [1/2] Rebuild frontend...
    cd /d "%~dp0frontend"
    call npm run build
    cd /d "%~dp0"
    if errorlevel 1 ( echo [ERRORE] Build fallita & goto loop )
    echo  [2/2] Riavvio servizi...
    start "" cmd /c "%~dp0AVVIA_DMGDESK.bat"
    exit
)

goto loop
