@echo off
setlocal

echo =========================================================
echo    Enable Auto-Start on Windows Boot (Background Tray)
echo =========================================================
echo.

set SCRIPT_DIR=%~dp0
set TARGET_VBS=%SCRIPT_DIR%start_background.vbs
set SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TailscaleFileUploader.lnk

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%TARGET_VBS%\"'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Save()"

if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] Tailscale File Uploader will now start automatically in the background when you log in!
    echo Shortcut created in Windows Startup folder.
) else (
    echo [ERROR] Failed to create startup shortcut.
)

echo.
pause
