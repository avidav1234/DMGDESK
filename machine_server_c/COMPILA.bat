@echo off
REM ============================================================
REM MachineServer - Compilazione per Windows XP
REM Richiede MinGW (gcc) installato
REM ============================================================

echo.
echo ============================================================
echo   MachineServer C - Compilazione per Windows XP
echo ============================================================
echo.

REM Cerca gcc (MinGW)
where gcc >nul 2>&1
if errorlevel 1 (
    echo ERRORE: gcc non trovato.
    echo.
    echo Installare MinGW da: https://www.mingw-w64.org/
    echo oppure scaricare TDM-GCC da: https://jmeubank.github.io/tdm-gcc/
    echo.
    pause
    exit /b 1
)

echo [1/2] Compilazione in corso...
gcc -o MachineServer.exe server.c -lws2_32 -mwindows -O2 -static

if errorlevel 1 (
    echo.
    echo ERRORE durante la compilazione!
    pause
    exit /b 1
)

echo [2/2] Compilazione completata!
echo.
echo File creato: MachineServer.exe
echo.
echo Per avviare: doppio click su MachineServer.exe
echo Il log viene scritto in server_log.txt
echo.
pause
