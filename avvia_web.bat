@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title DMGDesk Web

echo.
echo DMGDesk - Avvio versione web
echo ==============================
echo.

:: ── 1. Dipendenze Python ────────────────────────────────────────────────────
echo [1/3] Verifica dipendenze Python...
pip install fastapi "uvicorn[standard]" pandas numpy python-multipart --quiet
if errorlevel 1 (
    echo ERRORE: pip fallito
    pause & exit /b 1
)

:: ── 2. Build frontend ───────────────────────────────────────────────────────
echo [2/3] Build frontend React...
if not exist "frontend\node_modules" (
    echo   Installazione pacchetti npm...
    cd frontend
    call npm install
    cd ..
)
cd frontend
call npm run build
if errorlevel 1 (
    echo ERRORE: npm run build fallito
    cd ..
    pause & exit /b 1
)
cd ..

if not exist "frontend\dist\index.html" (
    echo ERRORE: frontend\dist\index.html non trovato dopo build
    pause & exit /b 1
)
echo   Build OK.
echo.

:: ── 3. Avvio ────────────────────────────────────────────────────────────────
echo [3/3] Avvio server...
echo.
echo   http://localhost:8000
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if defined IP echo   http://!IP!:8000
)
echo.
echo   Premi CTRL+C per fermare.
echo.

uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

pause
