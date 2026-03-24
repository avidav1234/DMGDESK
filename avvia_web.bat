@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title DMGDesk Web

echo.
echo DMGDesk - Avvio versione web
echo ==============================
echo.

echo [1/4] Dipendenze Python...
pip install fastapi "uvicorn[standard]" pandas numpy python-multipart --quiet
if errorlevel 1 ( echo ERRORE pip & pause & exit /b 1 )

echo [2/4] Rebuild frontend...
if not exist "frontend\node_modules" (
    cd frontend & call npm install & cd ..
)
if exist "frontend\dist" rmdir /s /q "frontend\dist"
cd frontend
call npm run build
if errorlevel 1 ( echo ERRORE build & cd .. & pause & exit /b 1 )
cd ..

if not exist "frontend\dist\index.html" (
    echo ERRORE: index.html non trovato
    pause & exit /b 1
)

echo [3/4] Server in avvio...
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

uvicorn api.main:app --host 0.0.0.0 --port 8000

pause
