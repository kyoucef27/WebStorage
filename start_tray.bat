@echo off
setlocal enabledelayedexpansion

echo =========================================================
echo    Tailscale File Uploader - Background Tray Launcher
echo =========================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found in PATH.
    pause
    exit /b 1
)

:: 2. Ensure virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
)

:: 3. Check for .env file
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [!] A default .env was created.
    )
)

:: 4. Ensure dependencies are installed
if not exist ".venv\installed.flag" (
    echo [*] Installing dependencies...
    .venv\Scripts\pip.exe install -r requirements.txt
    echo. > .venv\installed.flag
)

:: 5. Launch silently in the background
echo [*] Launching Tailscale File Uploader in background...
echo [*] Look for the Shield icon in your Windows Taskbar tray (bottom right)!
wscript.exe start_background.vbs

echo [*] Server is now running in the background.
timeout /t 3 >nul
exit
