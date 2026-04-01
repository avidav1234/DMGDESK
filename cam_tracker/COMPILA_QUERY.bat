@echo off
REM ================================================================
REM  COMPILA_QUERY.bat
REM  Compila cimatron_query.exe con manifest Cimatron embedded.
REM  Eseguire da terminale NORMALE (non admin).
REM ================================================================

cd /d "%~dp0"

echo [1/2] Compilazione cimatron_query.exe...
pyinstaller --onefile --name cimatron_query --distpath . --workpath .build --specpath .build --manifest cimatron_query.manifest --noconfirm --log-level WARN cimatron_query.py

IF ERRORLEVEL 1 (
    echo [ERRORE] Compilazione fallita.
    pause
    exit /b 1
)

echo [2/2] Pulizia build temporanea...
rmdir /s /q .build 2>nul

echo.
echo  OK — cimatron_query.exe creato in cam_tracker\
echo  Test: .\cimatron_query.exe
echo.
pause
