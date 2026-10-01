# Tailscale File Uploader

A lightweight, secure, and self-hosted web application for uploading files from your mobile phone or remote computer directly to your Windows PC over your private [Tailscale](https://tailscale.com) network.

No third-party cloud services, no external dependencies like React or Node.js, and no database required. Files travel end-to-end encrypted directly across your private Tailscale mesh.

---

## Features

- **Private & Direct**: Runs directly on your Windows PC and is accessed securely through Tailscale (`http://100.x.y.z:5000`).
- **Multi-File Queue**: Select single or multiple files with drag-and-drop on desktop or native file picker on Android and iOS.
- **Real-Time Progress**: Dual progress bars displaying percentage, current file status, and overall queue bytes transferred via `XMLHttpRequest`.
- **Large File Streaming**: Streams incoming chunks directly to disk (4 MB buffer) without loading entire multi-gigabyte files into RAM. Configured for up to 50 GB uploads.
- **Safe Duplicate Handling**: Choose between **Auto-Rename** (e.g., `movie (1).mp4`), **Skip**, or **Overwrite**. Never destroys existing files unintentionally.
- **Folder Management Dashboard**: Add, view, and remove destination folders directly through the web UI with persistence in `folders.json`. Target any drive or folder on your Windows PC (e.g., `D:\Movies`, `E:\Projects`), with optional automatic directory creation.
- **Folder Whitelist**: Uploads are restricted strictly to configured folders. Arbitrary filesystem browsing and sensitive Windows system directories (`C:\Windows`) are blocked.
- **Hardened Security**:
  - Full path traversal protection against `../`, `..\`, absolute drive escapes, and control characters.
  - Windows reserved filename protection (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`).
  - Session-based password authentication with constant-time password comparison (`hmac.compare_digest`).
- **Destination File Browser**: View and safely delete files within configured destination folders directly from your browser.
- **One-Click Launch**: Includes `start.bat` for automatic virtual environment creation and server execution.

---

## Architecture & Security Model

```text
┌────────────────────────┐
│  Mobile Phone / Client │
│   (Tailscale Node)     │
└───────────┬────────────┘
            │  Encrypted WireGuard Tunnel (100.x.x.x)
            ▼
┌────────────────────────┐
│   Windows Firewall     │  <- Restricts TCP port 5000 to Tailscale network
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│  Python Flask Server   │  <- Password Authentication (Session cookie)
│  (0.0.0.0:5000)        │  <- Input validation & Canonical path verification
└───────────┬────────────┘
            │  Direct Chunked Stream (4 MB buffers)
            ▼
┌────────────────────────┐
│ Destination Directory  │
│ (e.g., D:\Downloads)   │
└────────────────────────┘
```

### Two-Layer Security

1. **Layer 1: Network Isolation (Tailscale)**:
   The server binds to port `5000`. By configuring Windows Firewall to only permit inbound traffic from Tailscale's IP range or network interface, your server is **completely invisible to the public internet and local LAN devices**. No router port-forwarding or public IP is ever required.
2. **Layer 2: Application Authentication**:
   Even within your Tailscale network, access to the upload endpoints requires the configured password stored in your `.env` file.

---

## Project Structure

```text
tailscale-file-uploader/
│
├── app.py                 # Flask server, streaming logic, security handlers, API endpoints
├── config.py              # Centralized configuration (Host, Port, Max size, Folders)
├── requirements.txt       # Python dependencies (Flask, python-dotenv, werkzeug, pytest)
├── start.bat              # One-click Windows startup script (auto venv & dependencies)
├── .env.example           # Environment template for password and secret key
├── .gitignore             # Git ignore file (excludes secrets and venv)
├── README.md              # Documentation and operational manual
│
├── templates/
│   └── index.html         # Responsive, clean utilitarian web interface
│
├── static/
│   ├── style.css          # Vanilla CSS design system (mobile & desktop optimized)
│   └── app.js             # Vanilla JS upload queue, progress tracker & browser
│
├── uploads/               # Built-in default upload destination directory
│   └── .gitkeep
│
└── tests/
    ├── __init__.py
    └── test_app.py        # Comprehensive test suite covering authentication, limits & security
```

---

## Quick Start (Windows)

### Option 1: Standalone Windows Executable (.exe)

You can run the compiled `.exe` without needing Python installed:

- **Portable Single-File**: Double-click [dist/TailscaleUploader-Portable.exe](file:///c:/Users/kefif/Desktop/studies/WEBSTORAGE/dist/TailscaleUploader-Portable.exe)
- **Folder Package**: Run [dist/TailscaleUploader/TailscaleUploader.exe](file:///c:/Users/kefif/Desktop/studies/WEBSTORAGE/dist/TailscaleUploader/TailscaleUploader.exe)
- **To Rebuild Executables**: Run [build_exe.bat](file:///c:/Users/kefif/Desktop/studies/WEBSTORAGE/build_exe.bat)

When launched, it automatically places the **Shield & Upload** active icon into your Windows System Tray (Taskbar notification area), serving files over Tailscale in the background.

### Option 2: Run in Background via Python (System Tray Icon)

To run the server with Python directly in the background:

- **Double-click `start_tray.bat`** (or `start_background.vbs`).
- **Features in System Tray Menu:**
  - 🌐 **Open Web App** (`http://<TAILSCALE-IP>:5000`)
  - 📋 **Copy URL for Phone** (copies link to clipboard)
  - 📁 **Open Uploads Folder** (opens Windows Explorer directly)
  - 🟢 **Live Status Indicator**
  - ❌ **Exit Server** cleanly

#### Auto-Start with Windows
- Double-click `install_autostart.bat` to have the uploader start automatically in the background every time Windows boots.
- Double-click `uninstall_autostart.bat` to remove it from startup.

### Option 3: Console Window Mode

1. Copy `.env.example` to `.env` and set your desired `UPLOAD_PASSWORD`:
   ```powershell
   copy .env.example .env
   ```
2. Double-click `start.bat` (or run it from PowerShell).
   - It will automatically set up `.venv`, install packages from `requirements.txt`, display your Tailscale IP, and launch the server.

### Option 2: Manual Setup

1. Open PowerShell in the project directory:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Create your `.env` configuration file:
   ```powershell
   copy .env.example .env
   ```
   Open `.env` in Notepad and change `UPLOAD_PASSWORD` and `SECRET_KEY`.

3. Start the application:
   ```powershell
   python app.py
   ```

---

## Finding Your Tailscale IP & Connecting

1. On your Windows PC, open PowerShell and run:
   ```powershell
   tailscale ip -4
   ```
   *(Alternatively, right-click the Tailscale icon in the Windows taskbar system tray and click "Copy IPv4 Address".)*
   
   Example Tailscale IP: `100.85.120.45`

2. On your phone (connected to the same Tailscale account/network), open your web browser:
   ```text
   http://100.85.120.45:5000
   ```

3. Enter your configured password to access the upload dashboard.

---

## Windows Firewall Configuration

By default, Windows Firewall blocks incoming connections on newly opened ports. You must add an inbound rule to permit traffic on port 5000.

### Recommended: Restrict Port 5000 Strictly to Tailscale

For maximum security, restrict the firewall rule to the Tailscale subnet (`100.64.0.0/10`):

Run PowerShell as **Administrator**:

```powershell
New-NetFirewallRule `
    -DisplayName "Tailscale File Uploader (Port 5000)" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 5000 `
    -RemoteAddress 100.64.0.0/10 `
    -Action Allow
```

> **Why `100.64.0.0/10`?**
> Tailscale allocates all Carrier-Grade NAT (CGNAT) addresses from this subnet. This ensures your home LAN devices or public networks cannot reach the upload server—only authorized Tailscale nodes can.

If you ever want to remove this rule:
```powershell
Remove-NetFirewallRule -DisplayName "Tailscale File Uploader (Port 5000)"
```

---

## Configuration (`config.py` & `.env`)

### `config.py` Settings

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `HOST` | `"0.0.0.0"` | Binds to all network adapters (including Tailscale). |
| `PORT` | `5000` | HTTP listening port. |
| `MAX_CONTENT_LENGTH` | `53687091200` (50 GB) | Rejects requests exceeding this size with HTTP 413. |
| `FOLDERS` | Dictionary | Whitelist mapping friendly names to absolute Windows paths. |

### Customizing Destination Folders

Edit `FOLDERS` in `config.py` to match the exact directories on your Windows machine:

```python
FOLDERS = {
    "Default Uploads": str(DEFAULT_UPLOADS_DIR),
    "Downloads": str(Path.home() / "Downloads"),
    "Movies": r"D:\Movies",
    "Projects": r"D:\Projects",
    "External Drive": r"E:\Backups",
}
```

- If a folder path does not exist on your computer, the server will **not crash**; it will flag it as unavailable in the dropdown and prevent uploads to that destination.
- The default `Default Uploads` directory is automatically created inside the project folder if it does not exist.

---

## Performance & Large Files

- **Streaming Directly to Disk**: When uploading large files (e.g., 4K videos or OS ISOs), the server streams data directly to the target file in **4 MB chunks** using `stream_to_disk()`. The file is never read entirely into memory (`file.read()` is never called).
- **Werkzeug Disk Spooling**: Requests larger than 2 MB are spooled to temporary files by Werkzeug rather than kept in RAM.
- **Transfer Speeds**: Real-world transfer speeds over Tailscale depend on:
  - **Direct connection vs. DERP Relay**: When both devices can reach each other directly (via UDP hole-punching), speeds match your local Wi-Fi or 5G connection speed. You can verify your connection state by running `tailscale status` or `tailscale ping <phone-ip>`.
  - **Disk write speed**: NVMe/SSD drives provide virtually bottleneck-free ingestion.

### Resumable Uploads Note (Version 1)

> **Important**: Version 1 implements standard HTTP multipart streaming uploads.
> If a 20 GB upload is interrupted midway (e.g., Wi-Fi drops), the upload must be restarted. The server automatically cleans up the partial file upon error to prevent corrupt orphaned files. Support for chunked resumable protocols (such as `tus.io`) can be added in a future version.

---

## Running the Automated Tests

The project includes automated tests using `pytest` that verify:
1. Valid password authentication succeeds.
2. Invalid password is rejected (HTTP 401).
3. Single file uploads succeed and verify data integrity on disk.
4. Multiple sequential uploads succeed.
5. Unconfigured destination names are rejected (HTTP 400).
6. Path traversal attempts (`../../`, `..\..\`, `C:\Windows`) are blocked and sanitized.
7. Windows reserved device names (`CON`, `PRN`, `NUL`, `AUX`) are neutralized.
8. Duplicate handling strategies: Auto-Rename (`file (1).ext`), Skip, and Overwrite.
9. Unauthorized uploads are rejected.
10. Requests exceeding `MAX_CONTENT_LENGTH` are rejected (HTTP 413).
11. Files cannot escape configured directories during upload or deletion.

To run the tests:

```powershell
.venv\Scripts\activate
pytest -v
```

---

## Troubleshooting Guide

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Browser says "Connection Refused"** | The server is not running, or listening on `127.0.0.1` instead of `0.0.0.0`. | Ensure `python app.py` is running and `HOST = "0.0.0.0"` in `config.py`. |
| **Browser times out on Phone** | Windows Firewall is blocking inbound connections on port 5000. | Run the `New-NetFirewallRule` PowerShell command shown in the Firewall section as Administrator. |
| **Phone cannot reach Tailscale IP** | Tailscale is disconnected on either the phone or Windows PC. | Verify that Tailscale is active and green on both devices. Check `tailscale status` in PowerShell. |
| **"Destination folder does not exist"** | The folder in `config.py` does not exist on your computer. | Check your drive letter (e.g. `D:\`) or create the folder on your PC. |
| **"Permission denied by Windows file system"** | The target directory requires Windows Administrator permissions. | Ensure the folder is within your user account directories (e.g. `Downloads`, `Documents`, or user-writable drives). |
| **Upload stops or fails with HTTP 413** | File size exceeds `MAX_CONTENT_LENGTH`. | Increase `MAX_CONTENT_LENGTH` in `config.py` or `.env`. |
| **Slow transfer speeds (< 2 MB/s)** | Tailscale is relaying through a DERP relay instead of establishing a direct P2P link. | Run `tailscale ping <phone-ip>` on your PC. If it says "via DERP", check that UPnP or NAT-PMP is enabled on your router or that UDP traffic is not blocked. |

---

## License

MIT License. Free for personal and commercial self-hosted use.
