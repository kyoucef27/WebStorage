"""
Comprehensive test suite for Tailscale File Uploader.
Validates authentication, file upload integrity, path traversal protection,
large file rejection, duplicate handling, and safe deletion.
"""

import io
import os
import shutil
import tempfile
from pathlib import Path
import pytest

import config
from app import app, sanitize_filename, resolve_safe_target_path


@pytest.fixture
def test_dirs():
    """Create temporary directories to simulate configured host folders."""
    temp_root = tempfile.mkdtemp(prefix="tailscale_test_")
    downloads_dir = Path(temp_root) / "Downloads"
    movies_dir = Path(temp_root) / "Movies"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    movies_dir.mkdir(parents=True, exist_ok=True)

    # Patch config FOLDERS for tests
    orig_folders = config.FOLDERS.copy()
    config.FOLDERS = {
        "Downloads": str(downloads_dir),
        "Movies": str(movies_dir),
    }

    yield {
        "root": Path(temp_root),
        "downloads": downloads_dir,
        "movies": movies_dir,
    }

    # Teardown
    config.FOLDERS = orig_folders
    shutil.rmtree(temp_root, ignore_errors=True)


@pytest.fixture
def client():
    """Configure Flask test client with test password and secret key."""
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key-12345"
    os.environ["TESTING"] = "true"
    config.UPLOAD_PASSWORD = "test-secure-password"

    with app.test_client() as client:
        yield client
    os.environ.pop("TESTING", None)


@pytest.fixture
def auth_client(client):
    """A client with an active authenticated session."""
    with client.session_transaction() as sess:
        sess["authenticated"] = True
    return client


# -----------------------------------------------------------------------------
# 1. Authentication Tests
# -----------------------------------------------------------------------------
def test_login_success(client):
    """Test login with the correct password."""
    response = client.post("/login", json={"password": "test-secure-password"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Verify session cookie was set
    with client.session_transaction() as sess:
        assert sess.get("authenticated") is True


def test_login_wrong_password(client):
    """Test login with an incorrect password is rejected."""
    response = client.post("/login", json={"password": "wrong-password"})
    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False
    assert "Invalid password" in data["error"]


def test_logout(auth_client):
    """Test logout clears authenticated session."""
    response = auth_client.post("/logout")
    assert response.status_code == 200
    with auth_client.session_transaction() as sess:
        assert sess.get("authenticated") is None


def test_unauthorized_upload_rejected(client):
    """Test unauthenticated client cannot upload files."""
    data = {
        "destination": "Downloads",
        "file": (io.BytesIO(b"secret file"), "secret.txt"),
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert response.status_code == 401
    assert response.get_json()["success"] is False


# -----------------------------------------------------------------------------
# 2. Upload Tests
# -----------------------------------------------------------------------------
def test_upload_success(auth_client, test_dirs):
    """Test standard single file upload succeeds."""
    file_content = b"Hello, this is a test document over Tailscale!"
    data = {
        "destination": "Downloads",
        "file": (io.BytesIO(file_content), "hello.txt"),
    }
    response = auth_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert response.status_code == 201
    res_data = response.get_json()
    assert res_data["success"] is True
    assert res_data["filename"] == "hello.txt"

    target_file = test_dirs["downloads"] / "hello.txt"
    assert target_file.exists()
    assert target_file.read_bytes() == file_content


def test_multiple_sequential_uploads(auth_client, test_dirs):
    """Test multiple files uploaded sequentially to destination."""
    files = [
        ("file1.zip", b"zip data 1"),
        ("file2.iso", b"iso data 2"),
        ("file3.mp4", b"mp4 data 3"),
    ]
    for filename, content in files:
        data = {
            "destination": "Movies",
            "file": (io.BytesIO(content), filename),
        }
        res = auth_client.post("/api/upload", data=data, content_type="multipart/form-data")
        assert res.status_code == 201
        assert (test_dirs["movies"] / filename).read_bytes() == content


# -----------------------------------------------------------------------------
# 3. Duplicate Handling Tests
# -----------------------------------------------------------------------------
def test_duplicate_handling_auto_rename(auth_client, test_dirs):
    """Test duplicate filename is safely renamed with counter."""
    dest = test_dirs["downloads"]
    (dest / "photo.jpg").write_bytes(b"original content")

    data = {
        "destination": "Downloads",
        "conflict_strategy": "rename",
        "file": (io.BytesIO(b"second content"), "photo.jpg"),
    }
    res = auth_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    assert res.get_json()["filename"] == "photo (1).jpg"

    # Original untouched
    assert (dest / "photo.jpg").read_bytes() == b"original content"
    assert (dest / "photo (1).jpg").read_bytes() == b"second content"


def test_duplicate_handling_skip(auth_client, test_dirs):
    """Test duplicate file is skipped if requested."""
    dest = test_dirs["downloads"]
    (dest / "data.csv").write_bytes(b"original data")

    data = {
        "destination": "Downloads",
        "conflict_strategy": "skip",
        "file": (io.BytesIO(b"new data"), "data.csv"),
    }
    res = auth_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    res_json = res.get_json()
    assert res_json["status"] == "skipped"
    # Content must remain original
    assert (dest / "data.csv").read_bytes() == b"original data"


def test_duplicate_handling_overwrite(auth_client, test_dirs):
    """Test duplicate file can be overwritten if explicitly requested."""
    dest = test_dirs["downloads"]
    (dest / "replace_me.txt").write_bytes(b"initial")

    data = {
        "destination": "Downloads",
        "conflict_strategy": "overwrite",
        "file": (io.BytesIO(b"updated"), "replace_me.txt"),
    }
    res = auth_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    assert (dest / "replace_me.txt").read_bytes() == b"updated"


# -----------------------------------------------------------------------------
# 4. Security & Path Traversal Tests
# -----------------------------------------------------------------------------
def test_invalid_destination_rejected(auth_client):
    """Test unconfigured or arbitrary destination name is rejected."""
    data = {
        "destination": "C:\\Windows\\System32",
        "file": (io.BytesIO(b"payload"), "test.txt"),
    }
    response = auth_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert response.status_code == 400
    assert response.get_json()["success"] is False


@pytest.mark.parametrize("malicious_filename", [
    "../../etc/passwd",
    "..\\..\\Windows\\win.ini",
    "....//....//escape.txt",
    "/root/danger.sh",
    "C:\\Windows\\exploit.exe",
])
def test_path_traversal_sanitized(malicious_filename, test_dirs):
    """Test path traversal characters are sanitized and never escape directory."""
    dest = test_dirs["downloads"]
    clean_name = sanitize_filename(malicious_filename)
    assert "/" not in clean_name
    assert "\\" not in clean_name
    assert ".." not in clean_name

    target_path = resolve_safe_target_path(dest, malicious_filename)
    assert target_path.resolve().is_relative_to(dest.resolve())


def test_windows_reserved_names_sanitized(test_dirs):
    """Test Windows reserved names (CON, NUL, AUX) are prefixed safely."""
    dest = test_dirs["downloads"]
    clean_con = sanitize_filename("CON.txt")
    assert clean_con.startswith("safe_")
    clean_nul = sanitize_filename("NUL")
    assert clean_nul.startswith("safe_")


# -----------------------------------------------------------------------------
# 5. File Listing and Deletion Tests
# -----------------------------------------------------------------------------
def test_list_files(auth_client, test_dirs):
    """Test listing files within configured destination."""
    dest = test_dirs["downloads"]
    (dest / "file_a.txt").write_bytes(b"content a")
    (dest / "file_b.txt").write_bytes(b"content b")

    res = auth_client.get("/api/files?destination=Downloads")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    file_names = [f["name"] for f in data["files"]]
    assert "file_a.txt" in file_names
    assert "file_b.txt" in file_names


def test_delete_file_success(auth_client, test_dirs):
    """Test deleting a file within the configured folder."""
    dest = test_dirs["downloads"]
    target = dest / "delete_me.txt"
    target.write_bytes(b"goodbye")

    res = auth_client.delete("/api/files", json={
        "destination": "Downloads",
        "filename": "delete_me.txt"
    })
    assert res.status_code == 200
    assert not target.exists()


def test_delete_file_traversal_blocked(auth_client, test_dirs):
    """Test attempting to delete outside configured destination is blocked."""
    outside_file = test_dirs["root"] / "outside.txt"
    outside_file.write_bytes(b"important outside data")

    res = auth_client.delete("/api/files", json={
        "destination": "Downloads",
        "filename": "../../outside.txt"
    })
    # Since sanitize_filename strips path traversal, the server will look for
    # 'outside.txt' inside Downloads, not find it, and return 404
    assert res.status_code == 404
    assert outside_file.exists()


# -----------------------------------------------------------------------------
# 6. Large File Size Enforcement
# -----------------------------------------------------------------------------
def test_oversized_file_rejected(auth_client):
    """Test request exceeding MAX_CONTENT_LENGTH returns 413."""
    orig_limit = app.config["MAX_CONTENT_LENGTH"]
    try:
        # Temporarily set limit to 100 bytes for test
        app.config["MAX_CONTENT_LENGTH"] = 100
        oversized_data = {
            "destination": "Downloads",
            "file": (io.BytesIO(b"A" * 500), "big.bin"),
        }
        res = auth_client.post("/api/upload", data=oversized_data, content_type="multipart/form-data")
        assert res.status_code == 413
        assert res.get_json()["success"] is False
    finally:
        app.config["MAX_CONTENT_LENGTH"] = orig_limit


# -----------------------------------------------------------------------------
# 7. Folder Management Dashboard Tests
# -----------------------------------------------------------------------------
def test_add_and_delete_folder(auth_client, test_dirs):
    """Test adding a custom folder and deleting it via API."""
    custom_folder = test_dirs["root"] / "MyCustomDir"

    # Add folder with auto-creation
    add_res = auth_client.post("/api/folders", json={
        "name": "Custom Uploads",
        "path": str(custom_folder),
        "create_if_missing": True
    })
    assert add_res.status_code == 200
    assert add_res.get_json()["success"] is True
    assert custom_folder.exists()

    # Verify it appears in folder list
    list_res = auth_client.get("/api/folders")
    assert list_res.status_code == 200
    names = [f["name"] for f in list_res.get_json()["folders"]]
    assert "Custom Uploads" in names

    # Delete the folder from configuration
    del_res = auth_client.delete("/api/folders", json={"name": "Custom Uploads"})
    assert del_res.status_code == 200
    assert del_res.get_json()["success"] is True

    # Default uploads cannot be deleted
    del_default = auth_client.delete("/api/folders", json={"name": "Default Uploads"})
    assert del_default.status_code == 400


def test_add_folder_system_directory_blocked(auth_client):
    """Test setting Windows system directory as upload folder is rejected."""
    res = auth_client.post("/api/folders", json={
        "name": "System Windows",
        "path": r"C:\Windows\System32"
    })
    assert res.status_code == 400
    assert res.get_json()["success"] is False

