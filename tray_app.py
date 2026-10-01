"""
Tailscale File Uploader - Windows System Tray Application
=========================================================
Runs the file upload server in the background and displays an active tray icon
in the Windows Taskbar (notification area) with quick actions, status, and notifications.
"""

import os
import sys
import subprocess
import threading
import webbrowser
import socket
from pathlib import Path
from PIL import Image, ImageDraw

import pystray
from pystray import MenuItem as item, Menu
from werkzeug.serving import make_server

# Import app and configuration
import config
from app import app, logger

STATIC_DIR = config.BUNDLE_DIR / "static"
ICON_PATH = STATIC_DIR / "tray_icon.png"


def get_tailscale_ip() -> str:
    """Attempt to detect Tailscale IPv4 address via CLI, fallback to local host."""
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        ip = result.stdout.strip()
        if ip:
            return ip
    except Exception:
        pass

    # Fallback to local network IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def get_active_url() -> str:
    """Return the primary accessible URL for the web server."""
    ip = get_tailscale_ip()
    return f"http://{ip}:{config.PORT}"


def create_tray_image():
    """Load the tray icon image or generate a fallback icon dynamically."""
    if ICON_PATH.exists():
        try:
            return Image.open(ICON_PATH)
        except Exception:
            pass

    # Dynamic fallback icon: Teal shield with white upward upload arrow
    size = (64, 64)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark badge background with teal border
    draw.ellipse([4, 4, 60, 60], fill=(15, 23, 42, 255), outline=(13, 148, 136, 255), width=3)
    
    # White upward arrow
    draw.rectangle([29, 26, 35, 46], fill=(255, 255, 255, 255))
    draw.polygon([(32, 14), (18, 28), (46, 28)], fill=(255, 255, 255, 255))
    
    # Green active dot
    draw.ellipse([44, 44, 56, 56], fill=(34, 197, 94, 255), outline=(15, 23, 42, 255), width=2)
    return img


class ServerThread(threading.Thread):
    """Background thread running the WSGI server."""
    def __init__(self, flask_app, host, port):
        super().__init__(daemon=True)
        self.server = make_server(host, port, flask_app, threaded=True)
        self.ctx = flask_app.app_context()
        self.ctx.push()

    def run(self):
        logger.info("Serving Tailscale Uploader via Background Tray Service...")
        self.server.serve_forever()

    def shutdown(self):
        logger.info("Shutting down WSGI server...")
        self.server.shutdown()


class TrayApplication:
    """System tray icon manager for Tailscale File Uploader."""
    def __init__(self):
        self.server_thread = None
        self.icon = None
        self.app_url = get_active_url()

    def start_server(self):
        """Start the background Flask server thread."""
        self.server_thread = ServerThread(app, config.HOST, config.PORT)
        self.server_thread.start()

    def open_browser(self, icon=None, item=None):
        """Open web app in default browser."""
        webbrowser.open(self.app_url)

    def open_uploads_folder(self, icon=None, item=None):
        """Open default uploads folder in Windows File Explorer."""
        uploads_dir = Path(config.FOLDERS.get("Uploads", BASE_DIR / "uploads")).resolve()
        uploads_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(uploads_dir))
        else:
            subprocess.run(["xdg-open", str(uploads_dir)])

    def copy_url_to_clipboard(self, icon=None, item=None):
        """Copy active Tailscale URL to Windows clipboard."""
        try:
            cmd = f"Set-Clipboard -Value '{self.app_url}'"
            subprocess.run(["powershell", "-Command", cmd], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if self.icon:
                self.icon.notify(
                    f"Copied to clipboard:\n{self.app_url}",
                    title="Tailscale Uploader"
                )
        except Exception as e:
            logger.error("Failed to copy URL to clipboard: %s", e)

    def on_exit(self, icon, item):
        """Clean shutdown handler."""
        logger.info("Exiting application from System Tray...")
        if self.server_thread:
            self.server_thread.shutdown()
        icon.stop()
        sys.exit(0)

    def build_menu(self):
        """Construct the system tray context menu."""
        status_text = f"🟢 Running on port {config.PORT}"
        url_text = f"🌐 {self.app_url}"

        return Menu(
            item(url_text, self.open_browser, default=True),
            item("📋 Copy URL for Phone", self.copy_url_to_clipboard),
            item("📁 Open Uploads Folder", self.open_uploads_folder),
            Menu.SEPARATOR,
            item(status_text, None, enabled=False),
            Menu.SEPARATOR,
            item("❌ Exit Server", self.on_exit)
        )

    def run(self):
        """Start server and display tray icon."""
        self.start_server()
        image = create_tray_image()
        menu = self.build_menu()

        self.icon = pystray.Icon(
            name="TailscaleUploader",
            icon=image,
            title=f"Tailscale File Uploader ({self.app_url})",
            menu=menu
        )

        # Notify user that server is active
        threading.Timer(
            1.0,
            lambda: self.icon.notify(
                f"Active & ready on your private network:\n{self.app_url}",
                title="Tailscale File Uploader"
            )
        ).start()

        logger.info("System tray icon active. Running main event loop.")
        self.icon.run()


if __name__ == "__main__":
    app_instance = TrayApplication()
    app_instance.run()
