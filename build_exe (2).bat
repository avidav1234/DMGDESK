@echo off
REM ========================================
REM Tool Manager V14 - Build Script
REM Crea eseguibile .exe con PyInstaller
REM ========================================

echo.
echo ========================================
echo   TOOL MANAGER V14 - BUILD EXE
echo ========================================
echo.

REM Controlla se PyInstaller è installato
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [1/4] Installazione PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERRORE: Impossibile installare PyInstaller
        pause
        exit /b 1
    )
) else (
    echo [1/4] PyInstaller già installato
)

echo.
echo [2/4] Pulizia build precedenti...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

echo.
echo [3/4] Build in corso...
echo.

REM Build con PyInstaller
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "ToolManager" ^
    --icon "app_icon.ico" ^
    --add-data "config;config" ^
    --add-data "database;database" ^
    --add-data "ui;ui" ^
    --add-data "logic;logic" ^
    --add-data "utils;utils" ^
    --hidden-import customtkinter ^
    --hidden-import pandas ^
    --hidden-import PIL ^
    --hidden-import PIL._tkinter_finder ^
    --collect-all customtkinter ^
    main.py

if errorlevel 1 (
    echo.
    echo ERRORE durante la build!
    pause
    exit /b 1
)

echo.
echo [4/4] Build completata!
echo.
echo ========================================
echo   ESEGUIBILE CREATO
echo ========================================
echo.
echo Percorso: dist\ToolManager.exe
echo.

REM Apri cartella dist
if exist dist (
    explorer dist
)

echo.
pause
