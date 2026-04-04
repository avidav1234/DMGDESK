@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title DMGDesk — Avvio completo

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       DMGDesk — Avvio completo       ║
echo  ╚══════════════════════════════════════╝
echo.

REM ── Verifica Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato nel PATH.
    pause & exit /b 1
)

REM ── Kill servizi già in esecuzione (pulizia prima del riavvio) ───────────────
echo [0/4] Pulizia porte 8000 e 8002...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do (
    taskkill /F /PID %%p >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8002 "') do (
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 1 /nobreak >nul

REM ── 1. STEP Analyzer (porta 8002) ────────────────────────────────────────────
echo [1/4] Avvio STEP Analyzer (porta 8002)...
if not exist "%~dp0step_analyzer\main.py" (
    echo        ATTENZIONE: step_analyzer\main.py non trovato — servizio saltato
    echo        Esegui: git pull origin main
) else (
    start "STEP Analyzer :8002" /min cmd /c "cd /d "%~dp0step_analyzer" && uvicorn main:app --host 127.0.0.1 --port 8002 2>&1 | tee step_analyzer.log"
    timeout /t 3 /nobreak >nul
    REM Verifica che sia partito
    curl -s http://127.0.0.1:8002/stato >nul 2>&1
    if errorlevel 1 (
        echo        ATTENZIONE: STEP Analyzer non risponde ancora — potrebbe impiegare qualche secondo
    ) else (
        echo        OK — http://127.0.0.1:8002
    )
)

REM ── 2. Frontend build (se necessario) ────────────────────────────────────────
echo [2/4] Frontend...
if not exist "%~dp0frontend\dist\index.html" (
    echo        Build necessaria...
    if not exist "%~dp0frontend\node_modules" (
        cd "%~dp0frontend" && call npm install && cd "%~dp0"
    )
    cd "%~dp0frontend" && call npm run build && cd "%~dp0"
    if not exist "%~dp0frontend\dist\index.html" (
        echo [ERRORE] Build frontend fallita
        pause & exit /b 1
    )
    echo        OK — build completata
) else (
    echo        OK — dist già presente
)

REM ── 3. Backend DMGDesk (porta 8000) ──────────────────────────────────────────
echo [3/4] Avvio backend DMGDesk (porta 8000)...
start "DMGDesk Backend :8000" /min cmd /c "cd /d "%~dp0" && uvicorn api.main:app --host 0.0.0.0 --port 8000 2>&1 | tee dmgdesk_server.log & echo DONE"
timeout /t 3 /nobreak >nul
echo        OK — http://localhost:8000

REM ── 4. Apri browser ──────────────────────────────────────────────────────────
echo [4/4] Apertura browser...
timeout /t 2 /nobreak >nul
start "" http://localhost:8000

REM ── Info rete ────────────────────────────────────────────────────────────────
echo.
echo  ┌─────────────────────────────────────────┐
echo  │  Servizi attivi:                        │
echo  │    DMGDesk      → http://localhost:8000 │
echo  │    STEP Analyzer→ http://localhost:8002 │
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if defined IP echo  │    Rete         → http://!IP!:8000
)
echo  └─────────────────────────────────────────┘
echo.
echo  Comandi:
echo    R + Invio  = git pull + rebuild + riavvio tutto
echo    S + Invio  = riavvio solo server (senza rebuild)
echo    U + Invio  = aggiorna solo backend (senza rebuild frontend)
echo    CTRL+C     = ferma tutto
echo.

:wait_input
set /p CMD="Comando: "

if /i "!CMD!"=="r" (
    echo.
    echo  Aggiornamento completo in corso...
    git pull origin main
    if errorlevel 1 (
        echo [ERRORE] git pull fallito
        goto wait_input
    )
    echo  Riavvio servizi...
    call "%~f0"
    exit /b
)

if /i "!CMD!"=="s" (
    echo.
    echo  Riavvio server...
    for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do taskkill /F /PID %%p >nul 2>&1
    for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8002 "') do taskkill /F /PID %%p >nul 2>&1
    timeout /t 1 /nobreak >nul
    call "%~f0"
    exit /b
)

if /i "!CMD!"=="u" (
    echo.
    echo  Aggiornamento backend...
    git pull origin main
    for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do taskkill /F /PID %%p >nul 2>&1
    for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8002 "') do taskkill /F /PID %%p >nul 2>&1
    timeout /t 1 /nobreak >nul
    start "STEP Analyzer :8002" /min cmd /c "cd /d "%~dp0step_analyzer" && uvicorn main:app --host 127.0.0.1 --port 8002"
    start "DMGDesk Backend :8000" /min cmd /c "cd /d "%~dp0" && uvicorn api.main:app --host 0.0.0.0 --port 8000 & echo DONE"
    echo  OK — backend riavviato
    goto wait_input
)

goto wait_input
