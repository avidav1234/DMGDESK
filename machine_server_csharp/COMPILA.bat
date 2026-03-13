@echo off
title Compilazione DMG Machine Server
echo.
echo ============================================
echo   DMG Machine Server - Compilazione
echo ============================================
echo.

REM --- Cerca csc.exe in tutte le versioni .NET installate ---

set CSC=
set NETVER=

REM Prova .NET 4.x (piu' comune su PC moderni)
if exist "%SystemRoot%\Microsoft.NET\Framework\v4.0.30319\csc.exe" (
    set CSC=%SystemRoot%\Microsoft.NET\Framework\v4.0.30319\csc.exe
    set NETVER=4.0
    goto :found
)

REM Prova .NET 3.5
if exist "%SystemRoot%\Microsoft.NET\Framework\v3.5\csc.exe" (
    set CSC=%SystemRoot%\Microsoft.NET\Framework\v3.5\csc.exe
    set NETVER=3.5
    goto :found
)

REM Prova .NET 2.0 (minimo per Windows XP)
if exist "%SystemRoot%\Microsoft.NET\Framework\v2.0.50727\csc.exe" (
    set CSC=%SystemRoot%\Microsoft.NET\Framework\v2.0.50727\csc.exe
    set NETVER=2.0
    goto :found
)

REM Nessuna versione trovata
echo [ERRORE] .NET Framework non trovato su questo PC.
echo.
echo Scarica .NET Framework 2.0 da:
echo https://www.microsoft.com/download/details.aspx?id=16614
echo.
pause
exit /b 1

:found
echo [OK] Trovato .NET Framework %NETVER%
echo      %CSC%
echo.

REM --- Cartella output ---
if not exist "%~dp0bin" mkdir "%~dp0bin"

REM --- Compilazione ---
echo Compilazione in corso...
echo.

"%CSC%" ^
    /target:winexe ^
    /platform:x86 ^
    /out:"%~dp0bin\MachineServer.exe" ^
    /reference:System.dll ^
    /reference:System.Drawing.dll ^
    /reference:System.Windows.Forms.dll ^
    "%~dp0Program.cs" ^
    "%~dp0ServerConfig.cs" ^
    "%~dp0SocketServer.cs" ^
    "%~dp0ServerForm.cs"

REM --- Risultato ---
if %ERRORLEVEL% == 0 (
    echo.
    echo ============================================
    echo   COMPILAZIONE COMPLETATA CON SUCCESSO!
    echo ============================================
    echo.
    echo   File creato:
    echo   %~dp0bin\MachineServer.exe
    echo.
    echo   Copia MachineServer.exe sulla macchina
    echo   e avvialo. Si minimizza nella taskbar.
    echo ============================================
    echo.

    REM Apri la cartella bin automaticamente
    explorer "%~dp0bin"
) else (
    echo.
    echo ============================================
    echo   ERRORE durante la compilazione.
    echo   Controlla i messaggi sopra.
    echo ============================================
    echo.
)

pause
