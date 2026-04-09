@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul
title DMGDesk V2 — SANDBOX

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   DMGDesk V2 — SANDBOX MODE                 ║
echo  ║   Backend  → http://localhost:8010           ║
echo  ║   Docs API → http://localhost:8010/docs      ║
echo  ║   Telegram → MOCKATO (console)               ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 ( echo [ERRORE] Python non trovato. & pause & exit /b 1 )

:: Genera dati mock se non esistono
if not exist "sandbox\data\DMGDesk_principale.csv" (
    echo Generazione dati mock...
    python sandbox\genera_dati_mock.py
    if errorlevel 1 ( echo [ERRORE] Generazione dati mock fallita & pause & exit /b 1 )
)

:: Pulizia porte sandbox
echo Pulizia porte 8010 e 8012...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8010 "') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8012 "') do taskkill /F /PID %%p >nul 2>&1
timeout /t 1 /nobreak >nul

set PROJ=%~dp0
set PROJ=%PROJ:~0,-1%

:: Crea script backend sandbox
(
    echo @echo off
    echo cd /d "%PROJ%"
    echo title Backend SANDBOX :8010
    echo set SANDBOX_MODE=1
    echo set DMGDESK_CONFIG=%PROJ%\sandbox\sandbox_config.json
    echo set TELEGRAM_BOT_TOKEN=SANDBOX_MOCK
    echo set TELEGRAM_CHAT_ID=0
    echo echo === DMGDesk Backend SANDBOX porta 8010 ===
    echo uvicorn api.main:app --host 0.0.0.0 --port 8010 --reload
) > "%PROJ%\_run_sandbox_backend.cmd"

:: Crea script step analyzer sandbox
(
    echo @echo off
    echo cd /d "%PROJ%\step_analyzer"
    echo title STEP Analyzer SANDBOX :8012
    echo echo === STEP Analyzer SANDBOX porta 8012 ===
    echo uvicorn main:app --host 127.0.0.1 --port 8012
) > "%PROJ%\_run_sandbox_step.cmd"

:: Crea script mock opcua
(
    echo @echo off
    echo cd /d "%PROJ%"
    echo title Mock OpcUa Macchina
    echo echo === Simulatore macchina OpcUa ===
    echo python sandbox\mock_opcua_generator.py
) > "%PROJ%\_run_sandbox_opcua.cmd"

:: Build frontend sandbox (porta 8010)
if not exist "%PROJ%\frontend\dist\index.html" (
    echo Build frontend...
    cd "%PROJ%\frontend"
    call npm install
    call npm run build
    cd "%PROJ%"
)

echo Avvio servizi sandbox...

:: Prova Windows Terminal, fallback a cmd separati
wt --title "SANDBOX" new-tab --title "Backend:8010" --tabColor "#8B0000" cmd /k "%PROJ%\_run_sandbox_backend.cmd" ^; new-tab --title "STEP:8012" --tabColor "#4a1a4a" cmd /k "%PROJ%\_run_sandbox_step.cmd" ^; new-tab --title "MockOpcUa" --tabColor "#1a4a4a" cmd /k "%PROJ%\_run_sandbox_opcua.cmd" 2>nul

if errorlevel 1 (
    echo Windows Terminal non trovato — avvio finestre cmd separate...
    start "Backend SANDBOX" cmd /k "%PROJ%\_run_sandbox_backend.cmd"
    start "STEP SANDBOX"    cmd /k "%PROJ%\_run_sandbox_step.cmd"
    start "Mock OpcUa"      cmd /k "%PROJ%\_run_sandbox_opcua.cmd"
)

timeout /t 4 /nobreak >nul
start "" http://localhost:8010
echo.
echo Sandbox avviata su http://localhost:8010
echo Produzione ancora attiva su http://localhost:8000
echo.
