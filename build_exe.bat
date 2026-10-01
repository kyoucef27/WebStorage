@echo off
setlocal enabledelayedexpansion

echo =========================================================
echo    Tailscale File Uploader - Windows EXE Builder
echo =========================================================
echo.

:: 1. Check Python and venv
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
)

:: 2. Ensure dependencies and PyInstaller are installed
echo [*] Checking build dependencies...
.venv\Scripts\pip.exe install -r requirements.txt pyinstaller

:: 3. Generate icons if missing
if not exist "static\tray_icon.ico" (
    echo [*] Generating icon assets...
    .venv\Scripts\python.exe generate_icon.py
)

:: 4. Build Standalone Folder Package
echo.
echo [*] [1/2] Building Directory Package (dist\TailscaleUploader\TailscaleUploader.exe)...
echo.

.venv\Scripts\pyinstaller.exe ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name "TailscaleUploader" ^
    --icon "static\tray_icon.ico" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --hidden-import "pystray" ^
    --hidden-import "PIL" ^
    --hidden-import "werkzeug" ^
    --hidden-import "jinja2" ^
    tray_app.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Folder build failed!
    pause
    exit /b 1
)

:: 5. Copy config files to dist folder
echo [*] Copying configuration files to dist\TailscaleUploader ...
if exist ".env.example" (
    copy ".env.example" "dist\TailscaleUploader\.env.example" >nul
)
if exist ".env" (
    copy ".env" "dist\TailscaleUploader\.env" >nul
)

:: 6. Build Single-File Portable Executable
echo.
echo [*] [2/2] Building Single Portable EXE (dist\TailscaleUploader-Portable.exe)...
echo.

.venv\Scripts\pyinstaller.exe ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "TailscaleUploader-Portable" ^
    --icon "static\tray_icon.ico" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --hidden-import "pystray" ^
    --hidden-import "PIL" ^
    --hidden-import "werkzeug" ^
    --hidden-import "jinja2" ^
    tray_app.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Portable build failed!
    pause
    exit /b 1
)

echo.
echo =========================================================
echo [SUCCESS] Windows Executables Built Successfully!
echo.
echo 1. Portable Single-File EXE:
echo    dist\TailscaleUploader-Portable.exe
echo.
echo 2. Self-Contained Application Folder:
echo    dist\TailscaleUploader\TailscaleUploader.exe
echo =========================================================
echo.
pause
