@echo off
:: ─────────────────────────────────────────────────────────
::  BUILD FRONTEND — esegui una sola volta (o dopo aggiornamenti)
::  Richiede Node.js installato: https://nodejs.org
:: ─────────────────────────────────────────────────────────
title Tool Manager — Build Frontend

echo.
echo  ==========================================
echo   Tool Manager V14 — Build Frontend React
echo  ==========================================
echo.

cd /d "%~dp0"

:: Controlla Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo  ⚠  Node.js non trovato.
    echo     Scaricalo da: https://nodejs.org ^(versione LTS^)
    echo     Dopo l'installazione, riapri questo file.
    echo.
    pause
    exit /b 1
)

echo  Node.js trovato: 
node --version

cd frontend

echo.
echo  Installazione dipendenze npm...
call npm install

echo.
echo  Compilazione React...
call npm run build

if errorlevel 1 (
    echo.
    echo  ⚠  Build fallita. Controlla gli errori sopra.
    pause
    exit /b 1
)

echo.
echo  ✅ Build completata! File in: frontend\dist\
echo     Ora puoi avviare con: 2_avvia_frontend.bat
echo.
pause
