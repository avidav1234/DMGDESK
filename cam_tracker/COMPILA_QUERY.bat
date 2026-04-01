@echo off
REM ================================================================
REM  COMPILA_QUERY.bat — Compila cimatron_query.exe
REM  Metodo da documentazione ufficiale Cimatron API
REM  Eseguire da terminale NORMALE (non admin).
REM ================================================================

cd /d "%~dp0"

echo Compilazione cimatron_query.exe...
pyinstaller cimatron_query.py -F -m cimatron_query.manifest --distpath . --noconfirm --log-level WARN

IF ERRORLEVEL 1 (
    echo [ERRORE] Compilazione fallita.
    pause
    exit /b 1
)

echo Pulizia...
if exist build rmdir /s /q build 2>nul
if exist cimatron_query.spec del cimatron_query.spec 2>nul

echo.
echo  OK — cimatron_query.exe pronto.
echo  Test: .\cimatron_query.exe
echo.
pause
