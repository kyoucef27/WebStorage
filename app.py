"""
Tailscale File Uploader - Main Application
==========================================
A secure, streaming, self-hosted file upload server designed for Windows
accessed over a private Tailscale network.
"""

import hmac
import logging
import os
import re
import sys
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    session,
)
from werkzeug.exceptions import RequestEntityTooLarge

import config

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("tailscale-uploader")

# -----------------------------------------------------------------------------
# Flask Application Setup
# -----------------------------------------------------------------------------
app = Flask(
    __name__,
    template_folder=str(config.BUNDLE_DIR / "templates"),
    static_folder=str(config.BUNDLE_DIR / "static"),
)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

# Session Cookie hardening
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False  # Set to True if using HTTPS/TLS certs

# -----------------------------------------------------------------------------
# Security & Filename Utilities
# -----------------------------------------------------------------------------
# Windows reserved device filenames (case-insensitive)
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

# Invalid Windows characters: < > : " / \ | ? * and control chars 0-31
INVALID_CHARS_REGEX = re.compile(r'[\<\>\:\"\/\\\|\?\*\x00-\x1f]')


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a user-provided filename to ensure it is completely safe for
    Windows filesystems while preserving international characters (UTF-8).
    
    Guarantees:
    - Strips all path separators (forward and back slashes)
    - Strips directory traversal sequences ('..')
    - Removes invalid Windows filesystem characters (< > : " / \\ | ? *)
    - Strips leading/trailing dots and spaces
    - Prevents Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    - Falls back to a safe timestamped name if string is empty
    """
    if not filename:
        return f"upload_{int(datetime.now().timestamp())}.bin"

    # Strip any path separators and grab base name
    clean_name = os.path.basename(filename.replace("\\", "/"))

    # Remove invalid characters
    clean_name = INVALID_CHARS_REGEX.sub("_", clean_name)

    # Strip leading/trailing dots and whitespace
    clean_name = clean_name.strip(" .")

    # If empty or only underscores/dots after cleaning
    if not clean_name or set(clean_name) <= {"_", "."}:
        clean_name = f"upload_{int(datetime.now().timestamp())}.bin"

    # Check for Windows reserved names (e.g., 'NUL' or 'CON.txt')
    stem = Path(clean_name).stem.upper()
    if stem in WINDOWS_RESERVED_NAMES:
        clean_name = f"safe_{clean_name}"

    # Limit filename length to 240 chars to respect Windows MAX_PATH limitations
    if len(clean_name) > 240:
        ext = Path(clean_name).suffix
        stem_trimmed = clean_name[: 240 - len(ext)]
        clean_name = stem_trimmed + ext

    return clean_name


def resolve_safe_target_path(destination_dir: Path, filename: str) -> Path:
    """
    Build and verify the target path strictly inside destination_dir.
    Raises ValueError if path traversal is detected.
    """
    safe_name = sanitize_filename(filename)
    dest_resolved = destination_dir.resolve()
    target_path = (dest_resolved / safe_name).resolve()

    try:
        # target_path must be strictly inside destination_dir
        target_path.relative_to(dest_resolved)
    except ValueError as exc:
        logger.warning(
            "Security alert: Path traversal attempt blocked! destination=%s, input=%s, resolved=%s",
            destination_dir, filename, target_path
        )
        raise ValueError("Invalid target path. Traversal detected.") from exc

    return target_path


def get_unique_filename(destination_dir: Path, filename: str) -> Path:
    """
    Generate an auto-incremented filename if destination already exists:
    'photo.jpg' -> 'photo (1).jpg' -> 'photo (2).jpg'
    """
    target = resolve_safe_target_path(destination_dir, filename)
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    counter = 1

    while True:
        candidate_name = f"{stem} ({counter}){suffix}"
        candidate_path = destination_dir / candidate_name
        if not candidate_path.exists():
            return candidate_path
        counter += 1


def stream_to_disk(stream, target_path: Path, chunk_size: int = 4 * 1024 * 1024) -> int:
    """
    Stream incoming file bytes directly to disk in 4MB chunks without loading
    the full file into RAM. Cleans up partial file on failure.
    """
    bytes_written = 0
    try:
        with open(target_path, "wb") as f_out:
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                f_out.write(chunk)
                bytes_written += len(chunk)
        return bytes_written
    except Exception as exc:
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass
        logger.error("Error streaming to disk (%s): %s", target_path, exc)
        raise


# -----------------------------------------------------------------------------
# Authentication Helpers & Decorators
# -----------------------------------------------------------------------------
def is_authenticated() -> bool:
    """Check if the current request session is authenticated."""
    return session.get("authenticated") is True


def login_required(f):
    """Decorator to protect API endpoints and views requiring authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Authentication required."}), 401
            # If user visits root directly while unauthenticated, the index template handles showing login UI
        return f(*args, **kwargs)
    return decorated_function


# -----------------------------------------------------------------------------
# Error Handlers
# -----------------------------------------------------------------------------
@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(error):
    max_gb = config.MAX_CONTENT_LENGTH / (1024 * 1024 * 1024)
    logger.warning("Upload failed: File exceeds MAX_CONTENT_LENGTH (%s GB)", max_gb)
    return jsonify({
        "success": False,
        "error": f"File exceeds the configured server maximum limit of {max_gb:.1f} GB."
    }), 413


@app.errorhandler(500)
def handle_internal_error(error):
    logger.error("Internal Server Error: %s", error)
    return jsonify({
        "success": False,
        "error": "An internal server error occurred while processing the request."
    }), 500


# -----------------------------------------------------------------------------
# Application Routes
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    """Serve the single-page application interface."""
    return render_template(
        "index.html",
        max_size_gb=round(config.MAX_CONTENT_LENGTH / (1024 * 1024 * 1024), 1)
    )


@app.route("/login", methods=["POST"])
def login():
    """Handle password authentication."""
    data = request.get_json(silent=True) or request.form
    password = data.get("password", "")

    client_ip = request.remote_addr
    # Use hmac.compare_digest for constant-time comparison to prevent timing attacks
    expected_password = config.get_upload_password()

    if hmac.compare_digest(password.encode("utf-8"), expected_password.encode("utf-8")):
        session["authenticated"] = True
        logger.info("Successful authentication from client IP: %s", client_ip)
        return jsonify({"success": True, "message": "Authentication successful."})

    logger.warning("Failed login attempt from client IP: %s", client_ip)
    return jsonify({"success": False, "error": "Invalid password."}), 401


@app.route("/logout", methods=["POST"])
def logout():
    """Clear session authentication."""
    session.clear()
    logger.info("User logged out from IP: %s", request.remote_addr)
    return jsonify({"success": True, "message": "Logged out successfully."})


@app.route("/api/auth-status", methods=["GET"])
def auth_status():
    """Return current session authentication status."""
    return jsonify({"authenticated": is_authenticated()})


@app.route("/api/folders", methods=["GET", "POST", "DELETE"])
@login_required
def manage_folders():
    """
    Handle folder listing, creation, and deletion under a unified endpoint.
    """
    if request.method == "GET":
        folder_list = []
        for alias, raw_path in config.get_configured_folders().items():
            resolved_path, error = config.resolve_folder(alias)
            folder_list.append({
                "name": alias,
                "path": str(raw_path),
                "available": resolved_path is not None,
                "error": error
            })
        return jsonify({"success": True, "folders": folder_list})

    elif request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        path_str = data.get("path", "").strip()
        create_if_missing = bool(data.get("create_if_missing", False))

        if not name or not path_str:
            return jsonify({"success": False, "error": "Both folder name and path are required."}), 400

        success, message = config.add_folder(name, path_str, create_if_missing=create_if_missing)
        if not success:
            return jsonify({"success": False, "error": message}), 400

        logger.info("Folder added to configuration: '%s' -> '%s' by client %s", name, path_str, request.remote_addr)
        return jsonify({"success": True, "message": message})

    elif request.method == "DELETE":
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()

        if not name:
            return jsonify({"success": False, "error": "Folder name is required."}), 400

        success, message = config.remove_folder(name)
        if not success:
            return jsonify({"success": False, "error": message}), 400

        logger.info("Folder removed from configuration: '%s' by client %s", name, request.remote_addr)
        return jsonify({"success": True, "message": message})




@app.route("/api/upload", methods=["POST"])
@login_required
def upload_file():
    """
    Upload a file directly to the selected destination folder using streaming.
    Supports conflict resolution: 'rename' (default), 'overwrite', or 'skip'.
    """
    destination_alias = request.form.get("destination", "").strip()
    conflict_strategy = request.form.get("conflict_strategy", "rename").lower()

    if not destination_alias:
        return jsonify({"success": False, "error": "No destination folder specified."}), 400

    dest_path, err = config.resolve_folder(destination_alias)
    if err:
        logger.error("Upload rejected: destination resolution failed: %s", err)
        return jsonify({"success": False, "error": err}), 400

    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file payload received in request."}), 400

    uploaded_file = request.files["file"]
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "error": "No file selected."}), 400

    original_filename = uploaded_file.filename
    client_ip = request.remote_addr

    try:
        sanitized_name = sanitize_filename(original_filename)
        candidate_path = resolve_safe_target_path(dest_path, sanitized_name)
    except ValueError as ve:
        logger.warning("Upload rejected for safety from %s: %s", client_ip, ve)
        return jsonify({"success": False, "error": "Unsafe filename or path traversal detected."}), 400

    # Handle duplicates according to requested strategy
    final_path = candidate_path
    if candidate_path.exists():
        if conflict_strategy == "skip":
            logger.info(
                "Upload skipped (file exists): '%s' in '%s' from %s",
                sanitized_name, destination_alias, client_ip
            )
            return jsonify({
                "success": True,
                "status": "skipped",
                "filename": sanitized_name,
                "destination": destination_alias,
                "message": f"File '{sanitized_name}' already exists. Skipped."
            })
        elif conflict_strategy == "overwrite":
            final_path = candidate_path
        else:  # default 'rename'
            final_path = get_unique_filename(dest_path, sanitized_name)

    logger.info(
        "Upload starting: '%s' -> '%s' (destination: %s) from %s",
        original_filename, final_path.name, destination_alias, client_ip
    )

    try:
        # Stream file directly to target path without memory buffering
        bytes_written = stream_to_disk(uploaded_file.stream, final_path)
    except Exception as exc:
        logger.error("Upload failed for '%s': %s", original_filename, exc)
        return jsonify({
            "success": False,
            "error": "Failed to write file to disk. Check PC storage permissions and free space."
        }), 500

    logger.info(
        "Upload completed successfully: '%s' saved as '%s' (%d bytes) in '%s'",
        original_filename, final_path.name, bytes_written, destination_alias
    )

    return jsonify({
        "success": True,
        "status": "uploaded",
        "original_filename": original_filename,
        "filename": final_path.name,
        "destination": destination_alias,
        "size": bytes_written
    }), 201


@app.route("/api/files", methods=["GET"])
@login_required
def list_files():
    """
    List files in the selected configured destination folder.
    Only allows viewing configured destinations; path traversal is strictly prohibited.
    """
    destination_alias = request.args.get("destination", "").strip()
    if not destination_alias:
        return jsonify({"success": False, "error": "Destination parameter is required."}), 400

    dest_path, err = config.resolve_folder(destination_alias)
    if err:
        return jsonify({"success": False, "error": err}), 400

    try:
        entries = []
        for item in dest_path.iterdir():
            # Only list regular files or subdirectories
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": stat.st_size if not item.is_dir() else 0,
                    "modified": stat.st_mtime
                })
            except (OSError, PermissionError):
                continue

        # Sort files by last modified time (newest first)
        entries.sort(key=lambda x: x["modified"], reverse=True)

        return jsonify({
            "success": True,
            "destination": destination_alias,
            "files": entries
        })
    except Exception as exc:
        logger.error("Error reading directory contents (%s): %s", dest_path, exc)
        return jsonify({"success": False, "error": "Unable to read destination folder contents."}), 500


@app.route("/api/files", methods=["DELETE"])
@login_required
def delete_file():
    """
    Safely delete a file inside the selected configured destination folder.
    Guarantees no traversal or deletion outside the target folder.
    """
    data = request.get_json(silent=True) or {}
    destination_alias = data.get("destination", "").strip()
    filename = data.get("filename", "").strip()

    if not destination_alias or not filename:
        return jsonify({"success": False, "error": "Both destination and filename are required."}), 400

    dest_path, err = config.resolve_folder(destination_alias)
    if err:
        return jsonify({"success": False, "error": err}), 400

    try:
        target_path = resolve_safe_target_path(dest_path, filename)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid file path specified."}), 400

    if not target_path.exists():
        return jsonify({"success": False, "error": f"File '{filename}' does not exist."}), 404

    if target_path.is_dir():
        return jsonify({"success": False, "error": "Deleting directories is not permitted."}), 400

    try:
        target_path.unlink()
        logger.info(
            "File deleted: '%s' from destination '%s' by client %s",
            filename, destination_alias, request.remote_addr
        )
        return jsonify({
            "success": True,
            "message": f"File '{filename}' was successfully deleted."
        })
    except PermissionError:
        logger.error("Permission denied when attempting to delete: %s", target_path)
        return jsonify({"success": False, "error": "Permission denied by Windows file system."}), 403
    except OSError as exc:
        logger.error("OS error deleting file %s: %s", target_path, exc)
        return jsonify({"success": False, "error": "Failed to delete file from disk."}), 500


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting Tailscale File Uploader Server")
    logger.info("Listening on: http://%s:%s", config.HOST, config.PORT)
    logger.info("Max upload limit: %.2f GB", config.MAX_CONTENT_LENGTH / (1024**3))
    logger.info("Configured folders:")
    for name, path in config.FOLDERS.items():
        exists_mark = "READY" if Path(path).exists() else "MISSING"
        logger.info("  - %-18s -> %s [%s]", name, path, exists_mark)
    logger.info("=" * 60)

    # Note: threaded=True ensures concurrent connections are supported.
    app.run(
        host=config.HOST,
        port=config.PORT,
        threaded=True,
        debug=False
    )
