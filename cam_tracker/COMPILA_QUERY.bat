@echo off
REM ================================================================
REM  COMPILA_QUERY.bat
REM  Compila cimatron_query.exe con manifest Cimatron embedded.
REM  Eseguire da terminale NORMALE (non admin).
REM ================================================================

cd /d "%~dp0"
set HERE=%~dp0
set MANIFEST=%HERE%cimatron_query.manifest

echo [1/2] Compilazione cimatron_query.exe...
pyinstaller cimatron_query.py ^
    --onefile ^
    --name cimatron_query ^
    --distpath "%HERE%" ^
    --workpath "%HERE%.build" ^
    --specpath "%HERE%.build" ^
    --manifest "%MANIFEST%" ^
    --noconfirm ^
    --log-level WARN

IF ERRORLEVEL 1 (
    echo [ERRORE] Compilazione fallita.
    pause
    exit /b 1
)

echo [2/2] Pulizia build temporanea...
rmdir /s /q "%HERE%.build" 2>nul

echo.
echo  OK — cimatron_query.exe creato in cam_tracker\
echo  Test: .\cimatron_query.exe
echo.
pause
