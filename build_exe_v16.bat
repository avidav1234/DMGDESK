@echo off
cd /d "%~dp0"

echo Cartella: %CD%
echo.

echo [1/6] Verifica Python...
python --version
if errorlevel 1 (
    echo ERRORE: Python non trovato nel PATH
    pause & exit /b 1
)

echo.
echo [2/6] Installazione dipendenze...
pip install pyinstaller customtkinter pandas openpyxl pillow
if errorlevel 1 (
    echo ERRORE: pip fallito
    pause & exit /b 1
)

echo.
echo [3/6] Pulizia COMPLETA (incluso __pycache__)...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo.
echo [4/6] Pulizia cache PyInstaller...
if exist "%APPDATA%\pyinstaller" rmdir /s /q "%APPDATA%\pyinstaller"

echo.
echo [5/6] Build in corso (salva log in build_log.txt)...
pyinstaller --noconfirm --clean DMGDesk.spec > build_log.txt 2>&1
echo Codice uscita: %ERRORLEVEL%

if not exist "dist\DMGDesk\DMGDesk.exe" (
    echo.
    echo ERRORE: build fallita. Log:
    type build_log.txt
    pause & exit /b 1
)

echo.
echo [6/6] Verifica...
echo BUILD OK!
echo EXE: dist\DMGDesk\DMGDesk.exe
explorer dist\DMGDesk
pause
