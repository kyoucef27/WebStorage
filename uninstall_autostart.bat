@echo off
setlocal

set SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TailscaleFileUploader.lnk

if exist "%SHORTCUT_PATH%" (
    del "%SHORTCUT_PATH%"
    echo [SUCCESS] Auto-start shortcut removed from Windows Startup folder.
) else (
    echo [*] Auto-start shortcut was not found in Windows Startup.
)

echo.
pause
