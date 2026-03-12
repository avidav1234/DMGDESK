@echo off
:: ─────────────────────────────────────────────────────────
::  AVVIA BACKEND — Tool Manager API (FastAPI)
::  Porta: 8000 (usata internamente dal frontend)
:: ─────────────────────────────────────────────────────────
title Tool Manager — Backend API

echo.
echo  ==========================================
echo   Tool Manager V14 — Backend FastAPI
echo   Porta: 8000
echo  ==========================================
echo.

:: Vai nella cartella dello script
cd /d "%~dp0"

:: Installa dipendenze se mancano
pip install fastapi uvicorn[standard] pandas numpy python-multipart --quiet

echo  Avvio backend...
echo  API Docs: http://localhost:8000/docs
echo  Premi CTRL+C per fermare.
echo.

uvicorn api.main:app --host 0.0.0.0 --port 8000

pause
