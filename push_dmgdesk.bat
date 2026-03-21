@echo off
setlocal enabledelayedexpansion

:: ═══════════════════════════════════════════════════════
:: push_dmgdesk.bat — DMG Desk auto-deploy
:: Metti questo file nella root del progetto
:: Crea .env nella stessa cartella con: GITHUB_TOKEN=ghp_...
:: ═══════════════════════════════════════════════════════

set SCRIPT_DIR=%~dp0
set ENV_FILE=%SCRIPT_DIR%.env
set BRANCH=dmgdesk
set REPO_URL=https://github.com/avidav1234/tool-manager.git
set DOWNLOADS=%USERPROFILE%\Downloads

:: Carica token da .env
if not exist "%ENV_FILE%" (
    echo.
    echo  [ERRORE] File .env non trovato in %SCRIPT_DIR%
    echo  Crea il file .env con questa riga:
    echo  GITHUB_TOKEN=ghp_il_tuo_token
    echo.
    pause
    exit /b 1
)

for /f "tokens=1,2 delims==" %%a in (%ENV_FILE%) do (
    if "%%a"=="GITHUB_TOKEN" set GITHUB_TOKEN=%%b
)

if "%GITHUB_TOKEN%"=="" (
    echo  [ERRORE] GITHUB_TOKEN non trovato nel file .env
    pause
    exit /b 1
)

:: Vai nella root del progetto
cd /d "%SCRIPT_DIR%"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       DMG Desk — Auto Deploy         ║
echo  ╚══════════════════════════════════════╝
echo.

:: Controlla se esiste uno zip in Downloads da applicare
set LATEST_ZIP=
for /f "delims=" %%f in ('dir /b /o-d "%DOWNLOADS%\dmgdesk_*.zip" 2^>nul') do (
    if "!LATEST_ZIP!"=="" set LATEST_ZIP=%%f
)

if not "%LATEST_ZIP%"=="" (
    echo  [1/4] Trovato zip: %LATEST_ZIP%
    echo        Estrazione in corso...
    powershell -Command "Expand-Archive -Path '%DOWNLOADS%\%LATEST_ZIP%' -DestinationPath '%SCRIPT_DIR%' -Force"
    echo        Estratto OK
    echo.
) else (
    echo  [1/4] Nessun zip trovato in Downloads — uso file esistenti
    echo.
)

:: Configura git con token
git remote set-url origin https://%GITHUB_TOKEN%@github.com/avidav1234/tool-manager.git

:: Checkout branch
echo  [2/4] Branch: %BRANCH%
git checkout %BRANCH% 2>nul || git checkout -b %BRANCH%
echo.

:: Stage e commit
echo  [3/4] Commit...
git add -A

:: Messaggio commit automatico con timestamp
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set TODAY=%%c-%%b-%%a
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set NOW=%%a:%%b
git commit -m "DMG Desk update — %TODAY% %NOW%"

if %errorlevel% equ 0 (
    echo  Commit OK
) else (
    echo  Nessuna modifica da committare
)
echo.

:: Push
echo  [4/4] Push su origin/%BRANCH%...
git push origin %BRANCH%

if %errorlevel% equ 0 (
    echo.
    echo  ╔══════════════════════════════════════╗
    echo  ║   Push completato con successo!      ║
    echo  ╚══════════════════════════════════════╝
    echo.
    echo  Branch: https://github.com/avidav1234/tool-manager/tree/%BRANCH%
) else (
    echo.
    echo  [ERRORE] Push fallito — controlla la connessione e il token
)

echo.
pause
