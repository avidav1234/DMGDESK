@echo off
REM ================================================================
REM  COMPILA_QUERY.bat — Compila cimatron_query.exe e cimatron_daemon.exe
REM  Metodo da documentazione ufficiale Cimatron API
REM  Eseguire da terminale NORMALE (non admin).
REM ================================================================

cd /d "%~dp0"

echo Compilazione cimatron_query.exe (legacy)...
pyinstaller cimatron_query.py -F -m cimatron_query.manifest --distpath . --noconfirm --log-level WARN

IF ERRORLEVEL 1 (
    echo [ERRORE] Compilazione cimatron_query.exe fallita.
    pause
    exit /b 1
)

echo.
echo Compilazione cimatron_daemon.exe (daemon persistente)...
pyinstaller cimatron_daemon.py -F -m cimatron_query.manifest --distpath . --noconfirm --log-level WARN

IF ERRORLEVEL 1 (
    echo [ERRORE] Compilazione cimatron_daemon.exe fallita.
    pause
    exit /b 1
)

echo Pulizia...
if exist build rmdir /s /q build 2>nul
if exist cimatron_query.spec del cimatron_query.spec 2>nul
if exist cimatron_daemon.spec del cimatron_daemon.spec 2>nul

echo.
echo  OK — cimatron_query.exe e cimatron_daemon.exe pronti.
echo.
echo  Copia entrambi in:
echo    C:\Program Files\Cimatron\Cimatron\2025.0\Program\
echo.
echo  Il tracker usera' cimatron_daemon.exe automaticamente se presente.
echo.
pause
