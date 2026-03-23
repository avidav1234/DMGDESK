@echo off
chcp 65001 > nul
REM ================================================
REM  DMGDesk V16 — Build Desktop App (.exe)
REM  Esegui questo file sul PC operatore (Windows)
REM  Richiede: Python 3.10+, pip
REM ================================================

echo.
echo  ╔══════════════════════════════════════╗
echo  ║     DMGDesk V16  —  Build EXE        ║
echo  ╚══════════════════════════════════════╝
echo.

REM ── 1. Verifica Python ──────────────────────────
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato nel PATH.
    echo          Installa Python 3.10+ da python.org
    pause & exit /b 1
)

REM ── 2. Installa/aggiorna dipendenze ─────────────
echo [1/5] Installazione dipendenze...
pip install --quiet --upgrade pip
pip install --quiet ^
    pyinstaller ^
    customtkinter ^
    pandas ^
    openpyxl ^
    pillow

if errorlevel 1 (
    echo [ERRORE] Installazione dipendenze fallita.
    pause & exit /b 1
)
echo        OK

REM ── 3. Pulizia build precedenti ─────────────────
echo [2/5] Pulizia build precedenti...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
echo        OK

REM ── 4. Build con spec file ──────────────────────
echo [3/5] Build in corso (può richiedere 2-5 minuti)...
echo.

pyinstaller --noconfirm DMGDesk.spec

if errorlevel 1 (
    echo.
    echo [ERRORE] Build fallita. Controlla l'output sopra.
    pause & exit /b 1
)

REM ── 5. Verifica output ──────────────────────────
echo.
echo [4/5] Verifica output...
if not exist "dist\DMGDesk\DMGDesk.exe" (
    echo [ERRORE] dist\DMGDesk\DMGDesk.exe non trovato!
    pause & exit /b 1
)
echo        OK

REM ── 6. Info finali ──────────────────────────────
echo [5/5] Build completata con successo!
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║  EXE:  dist\DMGDesk\DMGDesk.exe          ║
echo  ║                                          ║
echo  ║  DISTRIBUIRE l'intera cartella:          ║
echo  ║  dist\DMGDesk\                           ║
echo  ║  (non solo il file .exe)                 ║
echo  ╚══════════════════════════════════════════╝
echo.

REM Apri cartella output
explorer dist\DMGDesk

pause
