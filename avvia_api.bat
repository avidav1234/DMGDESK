@echo off
:: ─────────────────────────────────────────────────────────
::  Avvia il backend Tool Manager API
::  Accessibile da qualsiasi PC in rete su http://IP:8000
:: ─────────────────────────────────────────────────────────

title Tool Manager API — Server

echo.
echo  ==========================================
echo   Tool Manager V14 — Backend API
echo  ==========================================
echo.
echo  Installazione dipendenze...
pip install -r requirements.txt --quiet

echo.
echo  Avvio server...
echo  Dashboard API:  http://localhost:8000/docs
echo  Dalla rete:     http://%COMPUTERNAME%:8000/docs
echo.
echo  Premi CTRL+C per fermare il server.
echo.

:: --reload si aggiorna automaticamente quando salvi un file (ottimo in sviluppo)
:: Rimuovi --reload in produzione per prestazioni migliori
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

pause
