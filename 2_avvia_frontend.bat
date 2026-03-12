@echo off
setlocal enabledelayedexpansion
:: ─────────────────────────────────────────────────────────
::  AVVIA FRONTEND — Tool Manager Dashboard Web
::  Porta: 9191 (non standard, non richiede admin)
:: ─────────────────────────────────────────────────────────
title Tool Manager — Dashboard Web :9191

cd /d "%~dp0"

if not exist "frontend\dist\index.html" (
    echo  Frontend non compilato. Esegui prima 0_build_frontend.bat
    pause & exit /b 1
)

echo.
echo  ==========================================
echo   Tool Manager V14 — Dashboard Web
echo  ==========================================
echo.
echo  Indirizzi di accesso:
echo    http://localhost:9191
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4 Address"') do (
    set RAW=%%a
    set IP=!RAW: =!
    if not "!IP!"=="" echo    http://!IP!:9191
)
echo.
echo  Premi CTRL+C per fermare.
echo.

python server_frontend.py --port 9191

pause
