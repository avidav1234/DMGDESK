@echo off
cd /d "%~dp0"

echo Cartella: %CD%
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
echo [3/5] Pulizia...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo.
echo [4/5] Build (salva log in build_log.txt)...
pyinstaller --noconfirm DMGDesk.spec > build_log.txt 2>&1
echo Codice uscita: %ERRORLEVEL%

if not exist "dist\DMGDesk\DMGDesk.exe" (
    echo.
    echo ERRORE: build fallita. Apro il log...
    type build_log.txt
    pause & exit /b 1
)

echo.
echo BUILD OK!
echo EXE: dist\DMGDesk\DMGDesk.exe
explorer dist\DMGDesk
pause
