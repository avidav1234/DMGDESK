@echo off
chcp 65001 > nul
REM ================================================
REM  DMGDesk V16 — Build Desktop App (.exe)
REM ================================================

echo.
echo  DMGDesk V16 - Build EXE
echo  ========================
echo.

REM Vai nella cartella dello script (importante!)
cd /d "%~dp0"
echo Cartella: %CD%
echo.

REM ── 1. Verifica Python ──────────────────────────
echo [1/5] Verifica Python...
python --version
if errorlevel 1 (
    echo ERRORE: Python non trovato nel PATH.
    echo Installa Python 3.10+ da python.org
    pause
    exit /b 1
)

REM ── 2. Installa dipendenze ──────────────────────
echo.
echo [2/5] Installazione dipendenze...
pip install --upgrade pip
pip install pyinstaller customtkinter pandas openpyxl pillow
if errorlevel 1 (
    echo ERRORE: Installazione dipendenze fallita.
    pause
    exit /b 1
)

REM ── 3. Pulizia ──────────────────────────────────
echo.
echo [3/5] Pulizia build precedenti...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist

REM ── 4. Build ────────────────────────────────────
echo.
echo [4/5] Build in corso (2-5 minuti)...
echo.
pyinstaller --noconfirm DMGDesk.spec
echo.
echo Codice uscita PyInstaller: %ERRORLEVEL%
if errorlevel 1 (
    echo.
    echo ERRORE: Build fallita! Controlla output sopra.
    pause
    exit /b 1
)

REM ── 5. Verifica ─────────────────────────────────
echo.
echo [5/5] Verifica output...
if exist "dist\DMGDesk\DMGDesk.exe" (
    echo.
    echo  ================================
    echo  BUILD COMPLETATA CON SUCCESSO!
    echo  EXE: dist\DMGDesk\DMGDesk.exe
    echo  ================================
    explorer dist\DMGDesk
) else (
    echo ERRORE: exe non trovato in dist\DMGDesk\
)

echo.
pause
