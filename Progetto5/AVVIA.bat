@echo off
title WorkTrack - Avvio in corso...
color 0A

echo.
echo  ========================================
echo    WorkTrack - Gestore Progetti
echo  ========================================
echo.

:: Controlla se Node.js e' installato
node --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo  [ERRORE] Node.js non trovato!
    echo.
    echo  Scaricalo da: https://nodejs.org
    echo  Installa la versione LTS e riprova.
    echo.
    pause
    exit /b 1
)

echo  Node.js trovato: 
node --version

:: Installa dipendenze se node_modules non esiste
if not exist "node_modules" (
    echo.
    echo  Prima installazione - scarico le dipendenze...
    echo  (solo la prima volta, ci vogliono circa 1-2 minuti)
    echo.
    call npm install
    if %errorlevel% neq 0 (
        color 0C
        echo.
        echo  [ERRORE] Installazione fallita.
        echo  Controlla la connessione internet e riprova.
        pause
        exit /b 1
    )
    echo.
    echo  Dipendenze installate!
)

echo.
echo  Avvio WorkTrack...
echo  Apri il browser su: http://localhost:5173
echo.
echo  Per chiudere l'app premi CTRL+C in questa finestra.
echo.

:: Apri automaticamente il browser dopo 2 secondi
start "" timeout /t 2 /nobreak >nul & start "" "http://localhost:5173"

:: Avvia il server
call npm run dev

pause
