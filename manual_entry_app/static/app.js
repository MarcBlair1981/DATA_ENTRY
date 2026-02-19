// DOM Elements
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('file-info');
const filenameDisplay = document.getElementById('filename-display');
const btnImport = document.getElementById('btn-import');
const btnVerify = document.getElementById('btn-verify');
const consoleWindow = document.getElementById('console-window');
const statusText = document.getElementById('status-text');
const statusSub = document.getElementById('status-sub');
const statusIcon = document.getElementById('status-icon');
const progressBar = document.getElementById('progress-bar');
const progressText = document.getElementById('progress-text');
const progressCount = document.getElementById('progress-count');

let selectedFile = null;
let pollingInterval = null;

// --- Drag & Drop ---
dropzone.addEventListener('click', () => fileInput.click());

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('border-brand-500', 'bg-dark-800');
});

dropzone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropzone.classList.remove('border-brand-500', 'bg-dark-800');
});

dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('border-brand-500', 'bg-dark-800');
    if (e.dataTransfer.files.length) {
        handleFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFile(e.target.files[0]);
    }
});

function handleFile(file) {
    if (!file.name.endsWith('.csv')) {
        alert("Please select a valid CSV file.");
        return;
    }
    selectedFile = file;
    filenameDisplay.textContent = file.name;
    fileInfo.classList.remove('hidden');
    dropzone.querySelector('div').classList.add('opacity-0'); // Hide icon
    dropzone.querySelector('h3').classList.add('opacity-0');
    dropzone.querySelector('p').classList.add('opacity-0');

    // Enable Buttons
    btnImport.disabled = false;
    btnVerify.disabled = false;

    log(`File selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`);
}

function resetFile() {
    selectedFile = null;
    fileInput.value = '';
    fileInfo.classList.add('hidden');
    dropzone.querySelector('div').classList.remove('opacity-0');
    dropzone.querySelector('h3').classList.remove('opacity-0');
    dropzone.querySelector('p').classList.remove('opacity-0');

    btnImport.disabled = true;
    btnVerify.disabled = true;
}

// --- API Calls ---

async function startTask(mode) {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('mode', mode);
    formData.append('backfill_en', document.getElementById('backfill-en').checked);

    // Get Selected Mode
    const selectedMode = document.querySelector('input[name="workflow_mode"]:checked').value;
    formData.append('workflow_mode', selectedMode);

    try {
        log(`Starting ${mode.toUpperCase()} task...`);
        btnImport.disabled = true;
        btnVerify.disabled = true;

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            startPolling();
        } else {
            const data = await response.json();
            log(`Error: ${data.message}`, 'ERROR');
            btnImport.disabled = false;
            btnVerify.disabled = false;
        }
    } catch (e) {
        log(`Network Error: ${e.message}`, 'ERROR');
        btnImport.disabled = false;
        btnVerify.disabled = false;
    }
}

function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(async () => {
        try {
            const res = await fetch('/status');
            const data = await res.json();
            updateUI(data);

            if (data.status.state === 'COMPLETED' || data.status.state === 'ERROR') {
                clearInterval(pollingInterval);
                btnImport.disabled = false;
                btnVerify.disabled = false;
            }
        } catch (e) {
            console.error("Polling error", e);
        }
    }, 1000);
}

// --- UI Updates ---

function updateUI(data) {
    const status = data.status;

    // Status Text
    statusText.textContent = status.state;
    statusSub.textContent = status.message;

    // Icon State
    statusIcon.className = `w-16 h-16 rounded-full flex items-center justify-center mb-3 transition-all duration-500`;
    if (status.state === 'RUNNING') {
        statusIcon.classList.add('bg-brand-900', 'animate-pulse');
        statusIcon.innerHTML = '<i data-lucide="loader-2" class="w-8 h-8 text-brand-500 animate-spin"></i>';
    } else if (status.state === 'COMPLETED') {
        statusIcon.classList.add('bg-green-900');
        statusIcon.innerHTML = '<i data-lucide="check" class="w-8 h-8 text-green-500"></i>';
    } else if (status.state === 'ERROR') {
        statusIcon.classList.add('bg-red-900');
        statusIcon.innerHTML = '<i data-lucide="alert-triangle" class="w-8 h-8 text-red-500"></i>';
    } else if (status.state === 'PAUSED') {
        statusIcon.classList.add('bg-yellow-900', 'animate-pulse');
        statusIcon.innerHTML = '<i data-lucide="pause-circle" class="w-8 h-8 text-yellow-500"></i>';
    } else {
        statusIcon.classList.add('bg-gray-800');
        statusIcon.innerHTML = '<i data-lucide="power" class="w-8 h-8 text-gray-600"></i>';
    }
    lucide.createIcons();

    // Button States
    const btnPause = document.getElementById('btn-pause');
    if (status.state === 'RUNNING') {
        btnPause.innerHTML = '<i data-lucide="pause" class="w-4 h-4"></i> Pause';
        btnPause.classList.replace('bg-green-600', 'bg-yellow-600');
        btnPause.classList.replace('hover:bg-green-500', 'hover:bg-yellow-500');
        btnPause.disabled = false;
    } else if (status.state === 'PAUSED') {
        btnPause.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i> Resume';
        btnPause.classList.replace('bg-yellow-600', 'bg-green-600');
        btnPause.classList.replace('hover:bg-yellow-500', 'hover:bg-green-500');
        btnPause.disabled = false;
    } else {
        btnPause.disabled = true;
    }

    // Progress
    let pct = 0;
    if (status.total > 0) {
        pct = (status.progress / status.total) * 100;
        progressCount.textContent = `${status.progress}/${status.total}`;
    }
    progressBar.style.width = `${pct}%`;
    progressText.textContent = `${Math.round(pct)}%`;

    // Logs
    if (data.logs && data.logs.length > 0) {
        // Only append new logs? stick to simple repaint for now or complex Set diff
        // Clearing is easiest but flickers. 
        // Better: Just check last message?
        // For prototype simplicity:
        consoleWindow.innerHTML = '';
        data.logs.forEach(entry => {
            const div = document.createElement('div');
            div.className = `mb-1 ${getColorForLevel(entry.level)}`;
            div.textContent = `> ${entry.message}`;
            consoleWindow.appendChild(div);
        });
        consoleWindow.scrollTop = consoleWindow.scrollHeight;
    }
}

function getColorForLevel(level) {
    switch (level) {
        case 'ERROR': return 'text-red-500';
        case 'WARNING': return 'text-yellow-500';
        case 'SUCCESS': return 'text-green-500';
        default: return 'text-gray-300';
    }
}

function log(msg, level = 'INFO') {
    const div = document.createElement('div');
    div.className = `mb-1 ${getColorForLevel(level)}`;
    div.textContent = `> ${msg}`;
    consoleWindow.appendChild(div);
    consoleWindow.scrollTop = consoleWindow.scrollHeight;
}

// --- Info Modal ---
function toggleInfo() {
    const modal = document.getElementById('info-modal');
    modal.classList.toggle('hidden');
    // Simple fade animation toggling classes
    if (!modal.classList.contains('hidden')) {
        setTimeout(() => modal.classList.remove('opacity-0'), 10);
    } else {
        modal.classList.add('opacity-0');
    }
}

function downloadLogs() {
    window.location.href = '/download_logs';
}

async function togglePause() {
    const btnPause = document.getElementById('btn-pause');
    const isPaused = btnPause.textContent.trim().includes('Resume');
    const endpoint = isPaused ? '/resume' : '/pause';

    try {
        const res = await fetch(endpoint, { method: 'POST' });
        const data = await res.json();
        log(data.message, 'WARNING');
    } catch (e) {
        log(`Error toggling pause: ${e.message}`, 'ERROR');
    }
}
