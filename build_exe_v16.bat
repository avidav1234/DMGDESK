@echo off
cd /d "%~dp0"
echo Cartella: %CD%
echo.

echo IMPORTANTE: Assicurati che DMGDesk.exe non sia in esecuzione!
echo.

echo [1/5] Verifica Python...
python --version
if errorlevel 1 (
    echo ERRORE: Python non trovato nel PATH
    pause & exit /b 1
)

echo.
echo [2/5] Installazione dipendenze...
pip install pyinstaller customtkinter pandas openpyxl pillow
if errorlevel 1 (
    echo ERRORE: pip fallito
    pause & exit /b 1
)

echo.
echo [3/5] Chiude exe aperto e pulisce...
taskkill /f /im DMGDesk.exe 2>nul
timeout /t 2 /nobreak >nul
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo.
echo [4/5] Build (log in build_log.txt)...
pyinstaller --noconfirm --clean DMGDesk.spec > build_log.txt 2>&1
echo Codice uscita: %ERRORLEVEL%

if not exist "dist\DMGDesk.exe" (
    echo.
    echo ERRORE: build fallita. Log:
    type build_log.txt
    pause & exit /b 1
)

echo.
echo BUILD OK!
echo EXE: dist\DMGDesk.exe
explorer dist
pause
