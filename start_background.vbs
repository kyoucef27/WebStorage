' Tailscale File Uploader - Silent Background Launcher
' Starts the System Tray application without showing any command prompt window.

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

strScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
strPythonw = strScriptDir & "\.venv\Scripts\pythonw.exe"
strScript = strScriptDir & "\tray_app.py"

' If venv pythonw doesn't exist, fallback to global pythonw
If Not FSO.FileExists(strPythonw) Then
    strPythonw = "pythonw.exe"
End If

' Run in background (0 = hide window, False = don't wait for completion)
WshShell.CurrentDirectory = strScriptDir
WshShell.Run """" & strPythonw & """ """ & strScript & """", 0, False
