@echo off
setlocal enabledelayedexpansion

echo =========================================================
echo       Tailscale File Uploader - Windows Launcher
echo =========================================================
echo.

:: 1. Check for Python installation
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found in your PATH.
    echo Please install Python 3.10+ from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

:: 2. Set up virtual environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [*] Virtual environment created successfully.
)

:: 3. Check for .env file; copy from .env.example if missing
if not exist ".env" (
    if exist ".env.example" (
        echo [*] No .env found. Copying .env.example to .env ...
        copy .env.example .env >nul
        echo [!] A new .env file was created. Please edit it to customize your password!
    )
)

:: 4. Install dependencies if not installed
:: Use a marker file inside .venv to avoid redundant reinstall on every boot
if not exist ".venv\installed.flag" (
    echo [*] Installing required dependencies from requirements.txt...
    .venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
    .venv\Scripts\pip.exe install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
    echo. > .venv\installed.flag
    echo [*] Dependencies installed successfully.
)

:: 5. Display Tailscale IP info if tailscale CLI is present
echo.
tailscale ip -4 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "tokens=*" %%i in ('tailscale ip -4') do (
        echo [*] Your PC's Tailscale IPv4: %%i
        echo [*] Open on your phone: http://%%i:5000
    )
) else (
    echo [*] Tailscale CLI not detected in PATH.
    echo [*] You can check your Tailscale IP from the Tailscale system tray icon.
    echo [*] Local machine access: http://localhost:5000
)
echo.

:: 6. Launch the server
echo [*] Launching Tailscale File Uploader server...
echo Press Ctrl+C in this window to stop the server.
echo =========================================================
echo.

.venv\Scripts\python.exe app.py

pause
