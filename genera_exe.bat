@echo off
REM ====================================================================
REM   Script Automatico per Generare ToolManager.exe
REM   Versione: 1.0
REM ====================================================================

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         GENERATORE AUTOMATICO EXE - TOOLMANAGER              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM Controlla se PyInstaller è installato
echo [1/5] Verifico installazione PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo ❌ PyInstaller non trovato. Installazione in corso...
    pip install pyinstaller
    if errorlevel 1 (
        echo ❌ Errore durante l'installazione di PyInstaller
        pause
        exit /b 1
    )
    echo ✅ PyInstaller installato con successo!
) else (
    echo ✅ PyInstaller già installato
)

REM Controlla se esiste l'icona
echo.
echo [2/5] Verifico presenza icona...
if not exist "app_icon.ico" (
    echo ❌ ERRORE: File app_icon.ico non trovato!
    echo    Assicurati che app_icon.ico sia nella stessa cartella di questo script
    pause
    exit /b 1
)
echo ✅ Icona trovata: app_icon.ico

REM Controlla se esiste main.py
echo.
echo [3/5] Cerco file principale...
set MAIN_FILE=
if exist "main.py" set MAIN_FILE=main.py
if exist "app.py" set MAIN_FILE=app.py
if exist "ToolManager.py" set MAIN_FILE=ToolManager.py

if "%MAIN_FILE%"=="" (
    echo ❌ ERRORE: File principale non trovato!
    echo    Cercato: main.py, app.py, ToolManager.py
    pause
    exit /b 1
)
echo ✅ File principale trovato: %MAIN_FILE%

REM Pulisce build precedenti
echo.
echo [4/5] Pulizia file temporanei...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "*.spec" del /q *.spec
echo ✅ Pulizia completata

REM Genera l'exe
echo.
echo [5/5] Generazione EXE in corso...
echo ⏳ Questo processo può richiedere 1-3 minuti...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --icon=app_icon.ico ^
    --name=ToolManager ^
    --add-data "database;database" ^
    --add-data "config;config" ^
    --hidden-import=customtkinter ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --hidden-import=PIL ^
    --clean ^
    %MAIN_FILE%

if errorlevel 1 (
    echo.
    echo ❌ ERRORE durante la generazione dell'exe
    echo    Controlla i messaggi di errore sopra
    pause
    exit /b 1
)

REM Successo
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    ✅ GENERAZIONE COMPLETATA!                ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo 📦 Il tuo file eseguibile è pronto:
echo    dist\ToolManager.exe
echo.
echo 💡 Puoi distribuire solo questo file .exe
echo    Gli utenti NON hanno bisogno di Python installato
echo.

REM Apre la cartella dist
echo 📂 Apertura cartella dist...
start dist

echo.
echo Premi un tasto per chiudere...
pause >nul
