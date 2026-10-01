"""
Tailscale File Uploader - Configuration
=======================================
All server, networking, storage, and security settings are centralized here.
Values can be customized directly in this file or overridden via .env.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Base directory for user-writable files (.env, folders.json, uploads)
# Bundle directory for packaged assets (templates, static)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / ".env", override=True)

# Network Configuration
# 0.0.0.0 binds to all local network interfaces (including Tailscale IP)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5000))

# Upload limit in bytes (Default: 50 GB = 50 * 1024 * 1024 * 1024)
MAX_CONTENT_LENGTH = int(
    os.getenv("MAX_CONTENT_LENGTH", 50 * 1024 * 1024 * 1024)
)

# Authentication Settings
UPLOAD_PASSWORD = os.getenv("UPLOAD_PASSWORD", "tailscale-uploader-pass")

# Flask Session Security Key
SECRET_KEY = os.getenv("SECRET_KEY", "tailscale-file-uploader-default-secret-key-change-in-env")


def get_upload_password() -> str:
    """Return the configured password, reloading from .env if present and not in testing."""
    if os.getenv("TESTING") == "true":
        return UPLOAD_PASSWORD
    if (BASE_DIR / ".env").exists():
        load_dotenv(BASE_DIR / ".env", override=True)
    return os.getenv("UPLOAD_PASSWORD", UPLOAD_PASSWORD)



# Predefined Destination Folders
DEFAULT_UPLOADS_DIR = BASE_DIR / "uploads"
FOLDERS_FILE = BASE_DIR / "folders.json"

INITIAL_DEFAULT_FOLDERS = {
    "Default Uploads": str(DEFAULT_UPLOADS_DIR),
    "Downloads": str(Path.home() / "Downloads"),
    "Documents": str(Path.home() / "Documents"),
    "Desktop": str(Path.home() / "Desktop"),
}


def load_folders() -> dict[str, str]:
    """Load folders from folders.json or initialize from defaults."""
    import json
    if not FOLDERS_FILE.exists():
        save_folders(INITIAL_DEFAULT_FOLDERS)
        return INITIAL_DEFAULT_FOLDERS.copy()
    try:
        with open(FOLDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and data:
                return data
    except Exception:
        pass
    return INITIAL_DEFAULT_FOLDERS.copy()


def save_folders(folders_dict: dict[str, str]) -> None:
    """Save folders dictionary to folders.json."""
    import json
    with open(FOLDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(folders_dict, f, indent=2, ensure_ascii=False)


# Initialize FOLDERS in memory
FOLDERS = load_folders()


def get_configured_folders() -> dict[str, str]:
    """Return dictionary of configured folders."""
    return FOLDERS.copy()



def add_folder(name: str, path_str: str, create_if_missing: bool = False) -> tuple[bool, str]:
    """Add a new destination folder to configuration."""
    global FOLDERS
    name = name.strip()
    path_str = path_str.strip().strip('"').strip("'")

    if not name:
        return False, "Folder name cannot be empty."
    if not path_str:
        return False, "Folder path cannot be empty."

    current = load_folders()
    if name in current:
        return False, f"A folder named '{name}' already exists in your configuration."

    try:
        p = Path(path_str).resolve()
    except Exception as exc:
        return False, f"Invalid Windows path: {exc}"

    # Block sensitive system folders
    win_dir = Path(os.getenv("WINDIR", r"C:\Windows")).resolve()
    if p == win_dir or win_dir in p.parents:
        return False, "Setting system Windows directories as upload destinations is prohibited."

    if create_if_missing and not p.exists():
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"Failed to create directory on PC: {exc}"

    current[name] = str(p)
    save_folders(current)
    FOLDERS = current
    return True, f"Folder '{name}' added successfully."


def remove_folder(name: str) -> tuple[bool, str]:
    """Remove a folder from configuration."""
    global FOLDERS
    name = name.strip()
    if name == "Default Uploads":
        return False, "The 'Default Uploads' folder cannot be removed."

    current = load_folders()
    if name not in current:
        return False, f"Folder '{name}' was not found in configuration."

    del current[name]
    save_folders(current)
    FOLDERS = current
    return True, f"Folder '{name}' removed from configuration."


def resolve_folder(folder_name: str) -> tuple[Path | None, str | None]:
    """
    Validate that folder_name is a recognized configured alias and exists.
    Returns (Path, None) on success, or (None, error_message) on failure.
    """
    folders = get_configured_folders()
    if not folder_name or folder_name not in folders:
        return None, f"Destination folder alias '{folder_name}' is not configured."

    target_path = Path(folders[folder_name]).resolve()

    # If it is the default uploads directory inside the project, create it if missing
    if target_path == DEFAULT_UPLOADS_DIR.resolve():
        target_path.mkdir(parents=True, exist_ok=True)

    if not target_path.exists():
        return None, f"Configured path for '{folder_name}' ({target_path}) does not exist on this PC."

    if not target_path.is_dir():
        return None, f"Configured path for '{folder_name}' ({target_path}) is not a directory."

    return target_path, None

