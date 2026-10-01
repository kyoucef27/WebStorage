/**
 * Tailscale File Uploader - Frontend Application
 * Vanilla JavaScript implementation for file queueing, multi-file streaming uploads,
 * real-time progress tracking, and remote file management.
 */

(() => {
  'use strict';

  // --- State ---
  let authenticated = false;
  let configuredFolders = [];
  let uploadQueue = []; // Array of { id, file, status, bytesUploaded, error }
  let isUploading = false;
  let fileToDelete = null;

  // --- DOM Elements ---
  const authSection = document.getElementById('authSection');
  const dashboardSection = document.getElementById('dashboardSection');
  const navActions = document.getElementById('navActions');
  const alertContainer = document.getElementById('alertContainer');
  const loginForm = document.getElementById('loginForm');
  const passwordInput = document.getElementById('passwordInput');
  const togglePasswordBtn = document.getElementById('togglePasswordBtn');
  const logoutBtn = document.getElementById('logoutBtn');

  const destinationSelect = document.getElementById('destinationSelect');
  const destinationStatus = document.getElementById('destinationStatus');
  const conflictSelect = document.getElementById('conflictSelect');

  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const browseBtn = document.getElementById('browseBtn');

  const queueContainer = document.getElementById('queueContainer');
  const queueList = document.getElementById('queueList');
  const queueSummary = document.getElementById('queueSummary');
  const clearQueueBtn = document.getElementById('clearQueueBtn');
  const startUploadBtn = document.getElementById('startUploadBtn');

  const progressContainer = document.getElementById('progressContainer');
  const overallStatusText = document.getElementById('overallStatusText');
  const overallPercentage = document.getElementById('overallPercentage');
  const overallProgressBar = document.getElementById('overallProgressBar');
  const overallBytesText = document.getElementById('overallBytesText');
  const overallFileCount = document.getElementById('overallFileCount');
  const currentFileName = document.getElementById('currentFileName');
  const currentFilePercent = document.getElementById('currentFilePercent');
  const currentProgressBar = document.getElementById('currentProgressBar');

  const browserFolderLabel = document.getElementById('browserFolderLabel');
  const refreshFilesBtn = document.getElementById('refreshFilesBtn');
  const fileTable = document.getElementById('fileTable');
  const fileTableBody = document.getElementById('fileTableBody');
  const fileListEmpty = document.getElementById('fileListEmpty');

  const deleteModal = document.getElementById('deleteModal');
  const deleteFileName = document.getElementById('deleteFileName');
  const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
  const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');

  // --- Folder Management Elements ---
  const foldersSection = document.getElementById('foldersSection');
  const navTabUpload = document.getElementById('navTabUpload');
  const navTabFolders = document.getElementById('navTabFolders');
  const addFolderForm = document.getElementById('addFolderForm');
  const newFolderName = document.getElementById('newFolderName');
  const newFolderPath = document.getElementById('newFolderPath');
  const createIfMissingCheck = document.getElementById('createIfMissingCheck');
  const addFolderSubmitBtn = document.getElementById('addFolderSubmitBtn');
  const foldersTableBody = document.getElementById('foldersTableBody');
  const refreshFoldersTableBtn = document.getElementById('refreshFoldersTableBtn');

  // --- Utility Functions ---
  function formatBytes(bytes, decimals = 1) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  function formatDate(timestamp) {
    if (!timestamp) return '-';
    const date = new Date(timestamp * 1000);
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function showAlert(message, type = 'info', timeout = 6000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerHTML = `
      <span>${escapeHtml(message)}</span>
      <button class="alert-close" aria-label="Close alert">&times;</button>
    `;

    const closeBtn = alertDiv.querySelector('.alert-close');
    closeBtn.addEventListener('click', () => alertDiv.remove());

    alertContainer.appendChild(alertDiv);

    if (timeout > 0) {
      setTimeout(() => {
        if (alertDiv.parentNode) alertDiv.remove();
      }, timeout);
    }
  }

  function clearAlerts() {
    alertContainer.innerHTML = '';
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // --- Authentication Management ---
  async function checkAuthStatus() {
    try {
      const res = await fetch('/api/auth-status');
      const data = await res.json();
      setAuthState(data.authenticated);
    } catch (err) {
      console.error('Failed to check auth status:', err);
      setAuthState(false);
    }
  }

  function setAuthState(isAuth) {
    authenticated = isAuth;
    if (authenticated) {
      authSection.style.display = 'none';
      dashboardSection.style.display = 'block';
      foldersSection.style.display = 'none';
      navActions.style.display = 'flex';
      switchTab('upload');
      loadFolders();
    } else {
      authSection.style.display = 'block';
      dashboardSection.style.display = 'none';
      foldersSection.style.display = 'none';
      navActions.style.display = 'none';
      passwordInput.value = '';
    }
  }

  // --- View Switching (Uploads vs Folders) ---
  function switchTab(target) {
    if (target === 'upload') {
      dashboardSection.style.display = 'block';
      foldersSection.style.display = 'none';
      if (navTabUpload) navTabUpload.className = 'btn btn-primary btn-sm nav-tab active';
      if (navTabFolders) navTabFolders.className = 'btn btn-secondary btn-sm nav-tab';
    } else {
      dashboardSection.style.display = 'none';
      foldersSection.style.display = 'block';
      if (navTabUpload) navTabUpload.className = 'btn btn-secondary btn-sm nav-tab';
      if (navTabFolders) navTabFolders.className = 'btn btn-primary btn-sm nav-tab active';
      renderFoldersTable();
    }
  }

  if (navTabUpload) navTabUpload.addEventListener('click', () => switchTab('upload'));
  if (navTabFolders) navTabFolders.addEventListener('click', () => switchTab('folders'));

  async function handleLogin() {
    const password = passwordInput.value;
    if (!password) {
      showAlert('Please enter the server password.', 'warning');
      return;
    }

    try {
      const res = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      });
      const data = await res.json();

      if (data.success) {
        clearAlerts();
        showAlert('Authentication successful.', 'success', 3000);
        setAuthState(true);
      } else {
        showAlert(data.error || 'Authentication failed.', 'danger');
      }
    } catch (err) {
      showAlert('Unable to connect to the server.', 'danger');
    }
  }

  async function handleLogout() {
    try {
      await fetch('/logout', { method: 'POST' });
    } catch (err) {
      console.error('Logout error:', err);
    }
    uploadQueue = [];
    renderQueue();
    setAuthState(false);
    showAlert('You have been logged out.', 'info', 3000);
  }

  // Toggle password visibility
  togglePasswordBtn.addEventListener('click', () => {
    const isPass = passwordInput.getAttribute('type') === 'password';
    passwordInput.setAttribute('type', isPass ? 'text' : 'password');
  });

  loginForm.addEventListener('submit', handleLogin);
  logoutBtn.addEventListener('click', handleLogout);

  // --- Destination Folders Management ---
  async function loadFolders() {
    try {
      const res = await fetch('/api/folders');
      if (res.status === 401) {
        setAuthState(false);
        return;
      }
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      configuredFolders = data.folders || [];
      renderFolderOptions();
      renderFoldersTable();
    } catch (err) {
      showAlert('Failed to load destination folders: ' + err.message, 'danger');
    }
  }

  function renderFoldersTable() {
    if (!foldersTableBody) return;
    foldersTableBody.innerHTML = '';

    if (!configuredFolders || configuredFolders.length === 0) {
      foldersTableBody.innerHTML = '<tr><td colspan="4" class="text-muted">No folders configured.</td></tr>';
      return;
    }

    configuredFolders.forEach(folder => {
      const tr = document.createElement('tr');
      const isDefault = folder.name === 'Default Uploads';
      const statusBadge = folder.available
        ? '<span class="badge badge-online"><span class="badge-dot"></span> Ready</span>'
        : '<span class="badge" style="background: rgba(245,158,11,0.15); color:#f59e0b;">Missing on PC</span>';

      tr.innerHTML = `
        <td><strong>${escapeHtml(folder.name)}</strong></td>
        <td class="time-cell" style="word-break: break-all;">${escapeHtml(folder.path)}</td>
        <td>${statusBadge}</td>
        <td class="text-right">
          ${!isDefault ? `
            <button class="btn btn-ghost btn-sm btn-delete-folder" data-name="${escapeHtml(folder.name)}" title="Remove folder from configuration">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          ` : '<span class="badge badge-neutral">Built-in</span>'}
        </td>
      `;

      if (!isDefault) {
        const delBtn = tr.querySelector('.btn-delete-folder');
        delBtn.addEventListener('click', () => handleDeleteFolder(folder.name));
      }

      foldersTableBody.appendChild(tr);
    });
  }

  async function handleAddFolder(e) {
    if (e) e.preventDefault();
    const name = newFolderName.value.trim();
    const path = newFolderPath.value.trim();
    const createIfMissing = createIfMissingCheck.checked;

    if (!name || !path) {
      showAlert('Please enter both folder name and path.', 'warning');
      return;
    }

    if (addFolderSubmitBtn) addFolderSubmitBtn.disabled = true;
    try {
      const res = await fetch('/api/folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, path, create_if_missing: createIfMissing })
      });
      const data = await res.json();
      if (data.success) {
        showAlert(data.message || `Folder "${name}" added successfully.`, 'success');
        newFolderName.value = '';
        newFolderPath.value = '';
        await loadFolders();
      } else {
        showAlert(data.error || 'Failed to add folder.', 'danger');
      }
    } catch (err) {
      showAlert('Network error adding folder: ' + err.message, 'danger');
    } finally {
      if (addFolderSubmitBtn) addFolderSubmitBtn.disabled = false;
    }
  }

  async function handleDeleteFolder(name) {
    if (!confirm(`Remove destination folder "${name}" from configuration?\n(Note: Files on your computer will NOT be deleted).`)) {
      return;
    }

    try {
      const res = await fetch('/api/folders', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      const data = await res.json();
      if (data.success) {
        showAlert(data.message || `Folder "${name}" removed.`, 'info');
        await loadFolders();
      } else {
        showAlert(data.error || 'Failed to remove folder.', 'danger');
      }
    } catch (err) {
      showAlert('Network error removing folder: ' + err.message, 'danger');
    }
  }

  if (addFolderForm) addFolderForm.addEventListener('submit', handleAddFolder);
  if (refreshFoldersTableBtn) refreshFoldersTableBtn.addEventListener('click', loadFolders);


  function renderFolderOptions() {
    destinationSelect.innerHTML = '';
    if (configuredFolders.length === 0) {
      destinationSelect.innerHTML = '<option value="">No folders configured</option>';
      destinationStatus.textContent = 'Please configure FOLDERS in config.py.';
      return;
    }

    let defaultOption = null;

    configuredFolders.forEach(folder => {
      const opt = document.createElement('option');
      opt.value = folder.name;
      opt.textContent = folder.name + (!folder.available ? ' (Unavailable on PC)' : '');
      opt.disabled = !folder.available;
      if (folder.available && !defaultOption) {
        defaultOption = folder.name;
      }
      destinationSelect.appendChild(opt);
    });

    if (defaultOption) {
      destinationSelect.value = defaultOption;
    }

    updateFolderStatus();
    loadFilesList();
  }

  function updateFolderStatus() {
    const selectedName = destinationSelect.value;
    const folder = configuredFolders.find(f => f.name === selectedName);
    if (!folder) {
      destinationStatus.textContent = '';
      return;
    }

    browserFolderLabel.textContent = folder.name;

    if (folder.available) {
      destinationStatus.innerHTML = `<span style="color: var(--accent-success)">✓ Available on PC:</span> ${escapeHtml(folder.path)}`;
    } else {
      destinationStatus.innerHTML = `<span style="color: var(--accent-danger)">✗ Not found:</span> ${escapeHtml(folder.path)} (${escapeHtml(folder.error || 'Folder missing')})`;
    }
  }

  destinationSelect.addEventListener('change', () => {
    updateFolderStatus();
    loadFilesList();
  });

  // --- Destination File Browser ---
  async function loadFilesList() {
    const destination = destinationSelect.value;
    if (!destination) return;

    try {
      const res = await fetch(`/api/files?destination=${encodeURIComponent(destination)}`);
      if (res.status === 401) {
        setAuthState(false);
        return;
      }
      const data = await res.json();
      if (!data.success) {
        fileTable.style.display = 'none';
        fileListEmpty.style.display = 'block';
        fileListEmpty.querySelector('p').textContent = data.error || 'Folder not accessible.';
        return;
      }

      renderFileList(data.files || []);
    } catch (err) {
      console.error('Error fetching file list:', err);
    }
  }

  function renderFileList(files) {
    fileTableBody.innerHTML = '';
    if (!files || files.length === 0) {
      fileTable.style.display = 'none';
      fileListEmpty.style.display = 'block';
      fileListEmpty.querySelector('p').textContent = 'No files found in this destination.';
      return;
    }

    fileListEmpty.style.display = 'none';
    fileTable.style.display = 'table';

    files.forEach(file => {
      const tr = document.createElement('tr');

      const isDir = file.is_dir;
      const iconSvg = isDir
        ? `<svg class="file-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`
        : `<svg class="file-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;

      tr.innerHTML = `
        <td>
          <div class="file-name-cell">
            ${iconSvg}
            <span>${escapeHtml(file.name)}</span>
          </div>
        </td>
        <td class="size-cell">${isDir ? 'Folder' : formatBytes(file.size)}</td>
        <td class="time-cell">${formatDate(file.modified)}</td>
        <td class="text-right">
          ${!isDir ? `
            <button class="btn btn-ghost btn-sm btn-delete-file" data-filename="${escapeHtml(file.name)}" title="Delete file">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          ` : '-'}
        </td>
      `;

      if (!isDir) {
        const deleteBtn = tr.querySelector('.btn-delete-file');
        deleteBtn.addEventListener('click', () => promptDeleteFile(file.name));
      }

      fileTableBody.appendChild(tr);
    });
  }

  refreshFilesBtn.addEventListener('click', loadFilesList);

  // --- Deletion Flow ---
  function promptDeleteFile(filename) {
    fileToDelete = filename;
    deleteFileName.textContent = filename;
    deleteModal.style.display = 'flex';
  }

  cancelDeleteBtn.addEventListener('click', () => {
    deleteModal.style.display = 'none';
    fileToDelete = null;
  });

  confirmDeleteBtn.addEventListener('click', async () => {
    if (!fileToDelete) return;
    const dest = destinationSelect.value;
    const target = fileToDelete;
    deleteModal.style.display = 'none';
    fileToDelete = null;

    try {
      const res = await fetch('/api/files', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ destination: dest, filename: target })
      });
      const data = await res.json();
      if (data.success) {
        showAlert(`Deleted "${target}" successfully.`, 'info', 4000);
        loadFilesList();
      } else {
        showAlert(data.error || 'Failed to delete file.', 'danger');
      }
    } catch (err) {
      showAlert('Network error deleting file: ' + err.message, 'danger');
    }
  });

  // --- File Selection & Queue Handling ---
  dropZone.addEventListener('click', (e) => {
    if (e.target !== browseBtn && browseBtn.contains(e.target)) return;
    fileInput.click();
  });

  browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  // Drag and Drop handlers
  ['dragenter', 'dragover'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('dragover');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    if (e.dataTransfer && e.dataTransfer.files) {
      addFilesToQueue(e.dataTransfer.files);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files) {
      addFilesToQueue(fileInput.files);
      fileInput.value = ''; // Reset input to allow selecting same file again if desired
    }
  });

  function addFilesToQueue(fileList) {
    if (isUploading) {
      showAlert('Please wait for active upload to finish before adding more files.', 'warning');
      return;
    }

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      uploadQueue.push({
        id: 'file-' + Date.now() + '-' + Math.random().toString(36).substring(2, 8),
        file: file,
        status: 'pending',
        bytesUploaded: 0,
        error: null
      });
    }

    renderQueue();
  }

  function renderQueue() {
    if (uploadQueue.length === 0) {
      queueContainer.style.display = 'none';
      queueList.innerHTML = '';
      return;
    }

    queueContainer.style.display = 'block';
    queueList.innerHTML = '';

    let totalBytes = 0;
    uploadQueue.forEach(item => {
      totalBytes += item.file.size;

      const itemDiv = document.createElement('div');
      itemDiv.className = 'queue-item';
      itemDiv.id = item.id;

      let statusTagClass = 'status-pending';
      let statusText = 'Ready';

      if (item.status === 'uploading') {
        statusTagClass = 'status-uploading';
        statusText = 'Uploading';
      } else if (item.status === 'done') {
        statusTagClass = 'status-done';
        statusText = 'Uploaded ✓';
      } else if (item.status === 'skipped') {
        statusTagClass = 'status-skipped';
        statusText = 'Skipped';
      } else if (item.status === 'error') {
        statusTagClass = 'status-error';
        statusText = 'Failed ✗';
      }

      itemDiv.innerHTML = `
        <div class="queue-item-info">
          <span class="queue-item-name" title="${escapeHtml(item.file.name)}">${escapeHtml(item.file.name)}</span>
          <span class="queue-item-size">${formatBytes(item.file.size)}</span>
        </div>
        <div class="queue-item-meta">
          <span class="queue-status-tag ${statusTagClass}">${statusText}</span>
          ${!isUploading && item.status !== 'uploading' ? `
            <button class="btn-remove-file" title="Remove from queue" data-id="${item.id}">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          ` : ''}
        </div>
      `;

      const removeBtn = itemDiv.querySelector('.btn-remove-file');
      if (removeBtn) {
        removeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          removeQueueItem(item.id);
        });
      }

      queueList.appendChild(itemDiv);
    });

    queueSummary.textContent = `${uploadQueue.length} files (${formatBytes(totalBytes)})`;
  }

  function removeQueueItem(id) {
    if (isUploading) return;
    uploadQueue = uploadQueue.filter(item => item.id !== id);
    renderQueue();
  }

  clearQueueBtn.addEventListener('click', () => {
    if (isUploading) return;
    uploadQueue = [];
    renderQueue();
    progressContainer.style.display = 'none';
  });

  // --- Real-time Streaming Upload Execution ---
  startUploadBtn.addEventListener('click', async () => {
    if (isUploading) return;

    const pendingItems = uploadQueue.filter(i => i.status === 'pending' || i.status === 'error');
    if (pendingItems.length === 0) {
      showAlert('No pending files to upload.', 'warning');
      return;
    }

    const destination = destinationSelect.value;
    if (!destination) {
      showAlert('Please select a valid destination folder.', 'danger');
      return;
    }

    const conflictStrategy = conflictSelect.value;

    // Lock UI during upload
    isUploading = true;
    startUploadBtn.disabled = true;
    clearQueueBtn.disabled = true;
    destinationSelect.disabled = true;
    conflictSelect.disabled = true;
    progressContainer.style.display = 'block';

    let totalQueueBytes = 0;
    uploadQueue.forEach(item => totalQueueBytes += item.file.size);

    let completedPriorBytes = 0;
    let successCount = 0;
    let failCount = 0;

    for (let index = 0; index < uploadQueue.length; index++) {
      const item = uploadQueue[index];
      if (item.status === 'done' || item.status === 'skipped') {
        completedPriorBytes += item.file.size;
        continue;
      }

      item.status = 'uploading';
      renderQueue();

      // Update Overall Status UI
      overallFileCount.textContent = `File ${index + 1} of ${uploadQueue.length}`;
      currentFileName.textContent = item.file.name;
      currentFilePercent.textContent = '0%';
      currentProgressBar.style.width = '0%';

      try {
        await uploadSingleFile(item, destination, conflictStrategy, (bytesLoaded) => {
          // Current file progress
          const filePercent = Math.min(100, Math.round((bytesLoaded / item.file.size) * 100));
          currentFilePercent.textContent = `${filePercent}%`;
          currentProgressBar.style.width = `${filePercent}%`;

          // Overall progress
          const currentTotalBytes = completedPriorBytes + bytesLoaded;
          const overallPercent = totalQueueBytes > 0 
            ? Math.min(100, Math.round((currentTotalBytes / totalQueueBytes) * 100))
            : 100;

          overallProgressBar.style.width = `${overallPercent}%`;
          overallPercentage.textContent = `${overallPercent}%`;
          overallBytesText.textContent = `${formatBytes(currentTotalBytes)} / ${formatBytes(totalQueueBytes)}`;
        });

        completedPriorBytes += item.file.size;
        if (item.status === 'skipped') {
          // skipped
        } else {
          item.status = 'done';
          successCount++;
        }
      } catch (err) {
        item.status = 'error';
        item.error = err.message;
        failCount++;
        showAlert(`Failed to upload ${item.file.name}: ${err.message}`, 'danger', 8000);
      }

      renderQueue();
    }

    // Reset upload state
    isUploading = false;
    startUploadBtn.disabled = false;
    clearQueueBtn.disabled = false;
    destinationSelect.disabled = false;
    conflictSelect.disabled = false;

    // Overall final update
    overallStatusText.textContent = 'Upload sequence completed';
    overallProgressBar.style.width = '100%';
    overallPercentage.textContent = '100%';

    // Refresh file list in destination
    loadFilesList();

    if (failCount === 0) {
      showAlert(`All ${successCount} files uploaded successfully!`, 'success', 5000);
    } else {
      showAlert(`Upload finished with ${successCount} succeeded and ${failCount} failed.`, 'warning', 8000);
    }
  });

  function uploadSingleFile(item, destination, conflictStrategy, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();

      formData.append('file', item.file);
      formData.append('destination', destination);
      formData.append('conflict_strategy', conflictStrategy);

      xhr.open('POST', '/api/upload', true);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(e.loaded);
        }
      };

      xhr.onload = () => {
        if (xhr.status === 401) {
          setAuthState(false);
          reject(new Error('Session expired. Please log in again.'));
          return;
        }

        let resp;
        try {
          resp = JSON.parse(xhr.responseText);
        } catch (e) {
          resp = { success: false, error: 'Server returned non-JSON response.' };
        }

        if (xhr.status >= 200 && xhr.status < 300 && resp.success) {
          if (resp.status === 'skipped') {
            item.status = 'skipped';
          } else {
            item.status = 'done';
          }
          resolve(resp);
        } else {
          reject(new Error(resp.error || `HTTP error ${xhr.status}`));
        }
      };

      xhr.onerror = () => {
        reject(new Error('Network error or connection lost. Check Tailscale connection.'));
      };

      xhr.ontimeout = () => {
        reject(new Error('Upload timed out.'));
      };

      xhr.send(formData);
    });
  }

  // --- Initialize on Page Load ---
  checkAuthStatus();

})();
