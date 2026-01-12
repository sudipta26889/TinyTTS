// Theme toggle
const themeToggle = document.getElementById('theme-toggle');
const html = document.documentElement;

// Check for saved theme or system preference
if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    html.classList.add('dark');
} else {
    html.classList.remove('dark');
}

themeToggle.addEventListener('click', () => {
    html.classList.toggle('dark');
    localStorage.theme = html.classList.contains('dark') ? 'dark' : 'light';
});

// Tab switching
const tabPaste = document.getElementById('tab-paste');
const tabUpload = document.getElementById('tab-upload');
const inputPaste = document.getElementById('input-paste');
const inputUpload = document.getElementById('input-upload');

function setActiveTab(tab) {
    if (tab === 'paste') {
        tabPaste.classList.add('border-blue-600', 'text-blue-600', 'dark:text-blue-400');
        tabPaste.classList.remove('border-transparent', 'text-gray-500');
        tabUpload.classList.remove('border-blue-600', 'text-blue-600', 'dark:text-blue-400');
        tabUpload.classList.add('border-transparent', 'text-gray-500');
        inputPaste.classList.remove('hidden');
        inputUpload.classList.add('hidden');
    } else {
        tabUpload.classList.add('border-blue-600', 'text-blue-600', 'dark:text-blue-400');
        tabUpload.classList.remove('border-transparent', 'text-gray-500');
        tabPaste.classList.remove('border-blue-600', 'text-blue-600', 'dark:text-blue-400');
        tabPaste.classList.add('border-transparent', 'text-gray-500');
        inputUpload.classList.remove('hidden');
        inputPaste.classList.add('hidden');
    }
}

tabPaste.addEventListener('click', () => setActiveTab('paste'));
tabUpload.addEventListener('click', () => setActiveTab('upload'));

// File input display
const fileInput = document.getElementById('file-input');
const fileName = document.getElementById('file-name');

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        fileName.textContent = `Selected: ${fileInput.files[0].name}`;
        fileName.classList.remove('hidden');
    } else {
        fileName.classList.add('hidden');
    }
});

// Form submission
const form = document.getElementById('convert-form');
const convertBtn = document.getElementById('convert-btn');
const progressContainer = document.getElementById('progress-container');
const progressBar = document.getElementById('progress-bar');
const progressText = document.getElementById('progress-text');
const progressPercent = document.getElementById('progress-percent');
const resultContainer = document.getElementById('result-container');
const audioPlayer = document.getElementById('audio-player');
const downloadBtn = document.getElementById('download-btn');
const errorContainer = document.getElementById('error-container');
const errorText = document.getElementById('error-text');

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Reset UI
    resultContainer.classList.add('hidden');
    errorContainer.classList.add('hidden');
    progressContainer.classList.remove('hidden');
    progressBar.style.width = '0%';
    progressPercent.textContent = '0%';
    convertBtn.disabled = true;

    const formData = new FormData(form);

    try {
        // Start conversion
        const startRes = await fetch('/api/convert', {
            method: 'POST',
            body: formData
        });

        const startData = await startRes.json();

        if (!startRes.ok) {
            throw new Error(startData.error || 'Conversion failed');
        }

        const jobId = startData.job_id;

        // Poll for status
        while (true) {
            await new Promise(resolve => setTimeout(resolve, 500));

            const statusRes = await fetch(`/api/status/${jobId}`);
            const statusData = await statusRes.json();

            progressBar.style.width = `${statusData.progress}%`;
            progressPercent.textContent = `${statusData.progress}%`;

            if (statusData.total_chunks > 0) {
                progressText.textContent = `Processing chunk ${statusData.current_chunk} of ${statusData.total_chunks}...`;
            }

            if (statusData.status === 'completed') {
                // Show result
                const resultId = statusData.result_id;
                audioPlayer.src = `/api/audio/${resultId}`;
                downloadBtn.href = `/api/audio/${resultId}?download=1`;
                resultContainer.classList.remove('hidden');
                progressContainer.classList.add('hidden');
                loadHistory();
                break;
            } else if (statusData.status === 'failed') {
                throw new Error(statusData.error || 'Conversion failed');
            }
        }
    } catch (err) {
        errorText.textContent = err.message;
        errorContainer.classList.remove('hidden');
        progressContainer.classList.add('hidden');
    } finally {
        convertBtn.disabled = false;
    }
});

// History
const historyList = document.getElementById('history-list');
const searchInput = document.getElementById('search-input');
const fromDate = document.getElementById('from-date');
const toDate = document.getElementById('to-date');
const loadMoreBtn = document.getElementById('load-more-btn');

let currentPage = 1;
let isLoading = false;
let currentlyPlayingAudio = null;

// Helper function to escape HTML and prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadHistory(append = false) {
    if (isLoading) return;
    isLoading = true;

    const params = new URLSearchParams();
    if (searchInput.value) params.set('q', searchInput.value);
    if (fromDate.value) params.set('from', fromDate.value);
    if (toDate.value) params.set('to', toDate.value);
    params.set('page', append ? currentPage : 1);

    try {
        const res = await fetch(`/api/history?${params}`);
        const data = await res.json();

        if (!append) {
            currentPage = 1;
            historyList.innerHTML = '';
        }

        if (data.items.length === 0 && currentPage === 1) {
            historyList.innerHTML = '<p class="text-gray-500 dark:text-gray-400 text-center py-4">No history yet</p>';
            loadMoreBtn.classList.add('hidden');
        } else {
            data.items.forEach(item => {
                historyList.appendChild(createHistoryItem(item));
            });

            if (data.items.length === 20) {
                loadMoreBtn.classList.remove('hidden');
            } else {
                loadMoreBtn.classList.add('hidden');
            }
        }
    } catch (err) {
        console.error('Failed to load history:', err);
    } finally {
        isLoading = false;
    }
}

function createHistoryItem(item) {
    const div = document.createElement('div');
    div.className = 'border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden';
    div.innerHTML = `
        <button class="history-item-header w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
            <div class="flex items-center gap-3">
                <span class="text-gray-400">▶</span>
                <span class="text-sm text-gray-500 dark:text-gray-400">${new Date(item.created_at).toLocaleDateString()}</span>
                <span class="text-sm truncate max-w-xs">${escapeHtml(item.original_filename) || `"${escapeHtml(item.content_preview.substring(0, 30))}..."`}</span>
                <span class="text-xs text-gray-400">${formatDuration(item.audio_duration)}</span>
            </div>
        </button>
        <div class="history-item-content hidden px-4 py-4 bg-gray-50 dark:bg-gray-700/30 border-t border-gray-200 dark:border-gray-700">
            <p class="text-sm text-gray-600 dark:text-gray-300 mb-3 whitespace-pre-wrap">${escapeHtml(item.content_preview)}...</p>
            <div class="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Voice: ${escapeHtml(item.voice)} | Speed: ${item.speed}x
            </div>
            <div class="flex items-center gap-2">
                <button class="play-btn btn-secondary text-sm py-1 px-3">▶ Play</button>
                <a href="/api/audio/${item.id}?download=1" class="btn-secondary text-sm py-1 px-3">⬇ Download</a>
                <button class="delete-btn btn-secondary text-sm py-1 px-3 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30">🗑 Delete</button>
            </div>
            <audio class="history-audio w-full mt-3 hidden" controls></audio>
        </div>
    `;

    // Toggle expand
    const header = div.querySelector('.history-item-header');
    const content = div.querySelector('.history-item-content');
    const arrow = header.querySelector('span');

    header.addEventListener('click', () => {
        content.classList.toggle('hidden');
        arrow.textContent = content.classList.contains('hidden') ? '▶' : '▼';
    });

    // Play button
    const playBtn = div.querySelector('.play-btn');
    const audio = div.querySelector('.history-audio');

    playBtn.addEventListener('click', () => {
        if (currentlyPlayingAudio && currentlyPlayingAudio !== audio) {
            currentlyPlayingAudio.pause();
        }
        audio.src = `/api/audio/${item.id}`;
        audio.classList.remove('hidden');
        audio.play();
        currentlyPlayingAudio = audio;
    });

    // Delete button
    const deleteBtn = div.querySelector('.delete-btn');
    deleteBtn.addEventListener('click', async () => {
        if (!confirm('Delete this conversion?')) return;

        try {
            const res = await fetch(`/api/history/${item.id}`, { method: 'DELETE' });
            if (res.ok) {
                div.remove();
            } else {
                console.error('Failed to delete:', await res.text());
            }
        } catch (err) {
            console.error('Failed to delete:', err);
        }
    });

    return div;
}

function formatDuration(seconds) {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Search debounce
let searchTimeout;
searchInput.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(loadHistory, 300);
});

fromDate.addEventListener('change', loadHistory);
toDate.addEventListener('change', loadHistory);

loadMoreBtn.addEventListener('click', () => {
    currentPage++;
    loadHistory(true);
});

// Initial load
loadHistory();
