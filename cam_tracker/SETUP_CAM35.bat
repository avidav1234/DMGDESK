@echo off
REM ================================================================
REM  SETUP_CAM35.bat — Setup rapido CAMTracker su CAM35
REM  Eseguire come amministratore!
REM ================================================================

echo.
echo  DMGDesk CAMTracker — Setup CAM35
echo  ==================================
echo.

REM 1. Installa dipendenze Python
echo [1/3] Installazione dipendenze Python...
python -m pip install requests pywin32 --quiet
IF ERRORLEVEL 1 (
    echo [ERRORE] pip install fallito. Verifica che Python sia nel PATH.
    pause & exit /b 1
)
echo        OK

REM 2. Tenta installazione pythonnet (opzionale — richiede manifest Cimatron)
echo [2/3] Tentativo installazione pythonnet (COM API Cimatron)...
python -m pip install pythonnet --quiet
IF ERRORLEVEL 1 (
    echo        ATTENZIONE: pythonnet non installato.
    echo        Il tracker usera il fallback titolo finestra.
    echo        Per la COM API seguire README.md - sezione manifest.
) ELSE (
    echo        OK
)

REM 3. Installa avvio automatico
echo [3/3] Installazione task avvio automatico...
python "%~dp0installa_avvio_automatico.py"
IF ERRORLEVEL 1 (
    echo [ERRORE] Installazione task fallita. Eseguire come amministratore.
    pause & exit /b 1
)

echo.
echo  Setup completato!
echo.
echo  Avvio immediato del tracker:
echo    python "%~dp0cam_tracker.py"
echo.
echo  Oppure:
echo    schtasks /Run /TN DMGDesk_CAMTracker
echo.
pause
