@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title DMGDesk Web

echo.
echo DMGDesk - Avvio versione web
echo ==============================
echo.

echo [1/3] Dipendenze Python...
pip install fastapi "uvicorn[standard]" pandas numpy python-multipart --quiet
if errorlevel 1 ( echo ERRORE pip & pause & exit /b 1 )

:rebuild
echo [2/3] Rebuild frontend...
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

:start_server
echo.
echo [3/3] Avvio server...
echo.
echo   http://localhost:8000
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if defined IP echo   http://!IP!:8000
)
echo.
echo   R + Invio  = git pull + rebuild + riavvio
echo   S + Invio  = riavvio solo server (senza rebuild)
echo   CTRL+C     = ferma tutto
echo.

REM Avvia uvicorn e salva il PID
start "" /b cmd /c "uvicorn api.main:app --host 0.0.0.0 --port 8000 & echo DONE"

REM Aspetta che il server sia su
timeout /t 2 /nobreak >nul

:wait_input
set /p CMD="Comando: "

if /i "!CMD!"=="r" (
    echo.
    echo Pulling aggiornamenti...
    git pull origin main
    echo.
    echo Killing server sulla porta 8000...
    for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do (
        taskkill /F /PID %%p >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
    goto rebuild
)

if /i "!CMD!"=="s" (
    echo.
    echo Killing server sulla porta 8000...
    for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do (
        taskkill /F /PID %%p >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
    goto start_server
)

goto wait_input
