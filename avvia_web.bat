@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title DMGDesk Web

echo.
echo  DMGDesk - Versione Web
echo  ======================
echo.

:: Installa dipendenze Python se mancano
pip install fastapi uvicorn[standard] pandas numpy python-multipart --quiet

:: Build frontend se non esiste o se i sorgenti sono piu recenti
if not exist "frontend\dist\index.html" (
    echo  Build frontend in corso...
    cd frontend
    call npm install --silent
    call npm run build
    cd ..
    echo  Build completata.
    echo.
)

:: Mostra indirizzi
echo  Indirizzi di accesso:
echo    http://localhost:8000
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if defined IP if not "!IP!"=="" echo    http://!IP!:8000
)
echo.
echo  Premi CTRL+C per fermare.
echo.

:: Avvia — un solo processo, una sola porta
uvicorn api.main:app --host 0.0.0.0 --port 8000

pause
