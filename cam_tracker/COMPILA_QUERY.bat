@echo off
REM ================================================================
REM  COMPILA_QUERY.bat
REM  Compila cimatron_query.exe con manifest Cimatron embedded.
REM  Eseguire da terminale NORMALE (non admin).
REM ================================================================

cd /d "%~dp0"

echo [1/2] Compilazione cimatron_query.exe...
pyinstaller .build_spec\cimatron_query.spec --distpath . --workpath .build_spec\work --noconfirm --log-level WARN

IF ERRORLEVEL 1 (
    echo [ERRORE] Compilazione fallita.
    pause
    exit /b 1
)

echo [2/2] Pulizia build temporanea...
rmdir /s /q .build_spec\work 2>nul

echo.
echo  OK — cimatron_query.exe creato in cam_tracker\
echo  Test: .\cimatron_query.exe
echo.
pause
