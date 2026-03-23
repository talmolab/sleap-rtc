// SLEAP-RTC Dashboard Application

// =========================================================================
// Date Parsing and Formatting
// =========================================================================

/**
 * Parse a date value that could be an ISO string, Unix timestamp (seconds), or Date object
 * @param {string|number|Date} value - The date value to parse
 * @returns {Date|null} Parsed Date object or null if invalid
 */
function parseDate(value) {
    if (!value) return null;

    // Already a Date object
    if (value instanceof Date) return value;

    // Unix timestamp (number) - could be seconds or milliseconds
    if (typeof value === 'number') {
        // If the number is less than 10 billion, it's likely seconds (before year 2286)
        // If greater, it's likely milliseconds
        if (value < 10000000000) {
            return new Date(value * 1000); // Convert seconds to milliseconds
        }
        return new Date(value);
    }

    // String - could be ISO format or numeric string
    if (typeof value === 'string') {
        // Check if it's a numeric string (Unix timestamp)
        if (/^\d+$/.test(value)) {
            const num = parseInt(value, 10);
            if (num < 10000000000) {
                return new Date(num * 1000);
            }
            return new Date(num);
        }

        // ISO string - ensure UTC parsing
        let dateStr = value;
        if (!value.endsWith('Z') && !value.includes('+') && !value.includes('-', 10)) {
            dateStr = value + 'Z';
        }
        return new Date(dateStr);
    }

    return null;
}

/**
 * Format a date as relative time (e.g., "2 hours ago", "yesterday")
 * Uses Intl.RelativeTimeFormat for localized output
 * @param {string|number|Date} value - Date value (ISO string, Unix timestamp, or Date)
 * @returns {string} Relative time string
 */
function formatRelativeTime(value) {
    const date = parseDate(value);
    if (!date || isNaN(date.getTime())) return 'N/A';

    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

    // Handle future dates (for expiration)
    if (diffMs < 0) {
        const futureSec = Math.abs(diffSec);
        const futureMin = Math.floor(futureSec / 60);
        const futureHour = Math.floor(futureMin / 60);
        const futureDay = Math.floor(futureHour / 24);

        if (futureDay > 0) return rtf.format(futureDay, 'day');
        if (futureHour > 0) return rtf.format(futureHour, 'hour');
        if (futureMin > 0) return rtf.format(futureMin, 'minute');
        return 'in a moment';
    }

    // Handle past dates
    if (diffDay > 0) return rtf.format(-diffDay, 'day');
    if (diffHour > 0) return rtf.format(-diffHour, 'hour');
    if (diffMin > 0) return rtf.format(-diffMin, 'minute');
    return 'just now';
}

/**
 * Format a date as an exact datetime string for tooltip display
 * @param {string|number|Date} value - Date value (ISO string, Unix timestamp, or Date)
 * @returns {string} Formatted datetime string
 */
function formatExactDate(value) {
    const date = parseDate(value);
    if (!date || isNaN(date.getTime())) return '';

    return date.toLocaleString('en-US', {
        weekday: 'short',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short'
    });
}

/**
 * Extract hostname from worker peer_id
 * peer_id format: "worker-{worker_name}-{uuid}" e.g., "worker-labgpu1-8f3a"
 * @param {string} peerId - The peer ID string
 * @returns {string} Extracted hostname or the original peer_id
 */
function extractWorkerHostname(peerId) {
    if (!peerId) return 'Unknown';
    // Format: worker-{name}-{uuid4_hex_4chars}
    // Example: "worker-labgpu1-8f3a" -> "labgpu1"
    const match = peerId.match(/^worker-(.+)-[a-f0-9]{4}$/i);
    if (match) {
        return match[1];
    }
    // Fallback: return peer_id without "worker-" prefix if present
    return peerId.replace(/^worker-/i, '');
}

class SleapRTCDashboard {
    constructor() {
        this.jwt = null;
        this.user = null;
        this.rooms = [];
        this.roomWorkers = {}; // Cache of connected workers by room_id
        this.tokens = [];
        this.tokenWorkers = {}; // Cache of connected workers by token_id
        this.accountKeys = [];

        // Filter/sort state with localStorage persistence
        this.roomsFilter = localStorage.getItem('sleap_rooms_filter') || 'all';
        this.roomsSort = localStorage.getItem('sleap_rooms_sort') || 'joined_at';
        this.roomsSearch = '';
        this.tokensSort = localStorage.getItem('sleap_tokens_sort') || 'created_at';
        this.tokensActiveOnly = localStorage.getItem('sleap_tokens_active') === 'true';
        this.tokensSearch = '';
        this.searchDebounceTimer = null;

        // Active job tracking
        this.activeJobs = new Map(); // jobId → job state
        this._workerPollInterval = null;

        this.init();
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    init() {
        // DEBUG: intercept lucide.createIcons to trace unscoped calls that reset ALL icon SVGs
        if (typeof lucide !== 'undefined') {
            const _origCreateIcons = lucide.createIcons.bind(lucide);
            lucide.createIcons = function(opts) {
                if (!opts?.nodes) {
                    console.warn('[DEBUG-lucide] Unscoped createIcons() — resets all SVGs including modal spinner\n', new Error().stack);
                }
                return _origCreateIcons(opts);
            };
        }

        // Load stored credentials
        this.loadStoredCredentials();

        // Restore active jobs from sessionStorage
        this._loadActiveJobs();

        // Load theme preference
        this.loadTheme();

        // Setup event listeners
        this.setupEventListeners();

        // Check for CLI mode - auto-start OAuth
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('cli') === 'true' && urlParams.get('cli_state')) {
            // CLI mode: immediately start OAuth flow
            this.handleLogin();
            return;
        }

        // Check auth state and render
        this.updateUI();
    }

    loadTheme() {
        const savedTheme = localStorage.getItem('sleap_theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateThemeUI(savedTheme);
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('sleap_theme', newTheme);
        this.updateThemeUI(newTheme);
    }

    updateThemeUI(theme) {
        const label = document.getElementById('theme-label');
        if (label) {
            label.textContent = theme === 'dark' ? 'Dark' : 'Light';
        }
    }

    loadStoredCredentials() {
        const jwt = localStorage.getItem(CONFIG.STORAGE_KEYS.JWT);
        const userJson = localStorage.getItem(CONFIG.STORAGE_KEYS.USER);

        if (jwt && userJson) {
            this.jwt = jwt;
            try {
                this.user = JSON.parse(userJson);
            } catch (e) {
                console.error('Failed to parse user data:', e);
                this.clearCredentials();
            }
        }
    }

    saveCredentials(jwt, user) {
        this.jwt = jwt;
        this.user = user;
        localStorage.setItem(CONFIG.STORAGE_KEYS.JWT, jwt);
        localStorage.setItem(CONFIG.STORAGE_KEYS.USER, JSON.stringify(user));
    }

    clearCredentials() {
        this.jwt = null;
        this.user = null;
        localStorage.removeItem(CONFIG.STORAGE_KEYS.JWT);
        localStorage.removeItem(CONFIG.STORAGE_KEYS.USER);
    }

    isLoggedIn() {
        return this.jwt !== null && this.user !== null;
    }

    // =========================================================================
    // UI Management
    // =========================================================================

    updateUI() {
        const loginSection = document.getElementById('login-section');
        const dashboardSection = document.getElementById('dashboard-section');

        if (this.isLoggedIn()) {
            loginSection.classList.add('hidden');
            dashboardSection.classList.remove('hidden');

            // Update user info in top bar
            document.getElementById('user-avatar').src = this.user.avatar_url || '';
            document.getElementById('user-name').textContent = this.user.username || 'User';

            // Load data
            this.loadRooms();
            this.loadTokens();

            // Initialize Lucide icons
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        } else {
            loginSection.classList.remove('hidden');
            dashboardSection.classList.add('hidden');
        }
    }

    setupEventListeners() {
        // Login button
        document.getElementById('github-login-btn')?.addEventListener('click', () => this.handleLogin());

        // Logout button
        document.getElementById('logout-btn')?.addEventListener('click', () => this.handleLogout());

        // User dropdown toggle
        document.getElementById('user-trigger')?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleUserMenu();
        });

        // Close user menu when clicking outside
        document.addEventListener('click', (e) => {
            const dropdown = document.querySelector('.user-dropdown');
            if (dropdown && !dropdown.contains(e.target)) {
                document.getElementById('user-menu')?.classList.remove('open');
            }
        });

        // Sidebar navigation
        document.querySelectorAll('.nav-item[data-tab]').forEach(item => {
            item.addEventListener('click', (e) => this.switchTab(e.currentTarget.dataset.tab));
        });

        // Refresh buttons
        document.getElementById('refresh-rooms-btn')?.addEventListener('click', () => {
            this.loadRooms();
            this.showToast('Rooms refreshed');
        });
        document.getElementById('refresh-tokens-btn')?.addEventListener('click', () => {
            this.loadTokens();
            this.showToast('Tokens refreshed');
        });

        // Create room
        document.getElementById('create-room-btn')?.addEventListener('click', () => this.showModal('create-room-modal'));
        document.getElementById('create-room-form')?.addEventListener('submit', (e) => this.handleCreateRoom(e));

        // Join room
        document.getElementById('join-room-btn')?.addEventListener('click', () => this.showModal('join-room-modal'));
        document.getElementById('join-room-form')?.addEventListener('submit', (e) => this.handleJoinRoom(e));

        // Create token
        document.getElementById('create-token-btn')?.addEventListener('click', () => this.showCreateTokenModal());
        document.getElementById('create-token-form')?.addEventListener('submit', (e) => this.handleCreateToken(e));

        // Account keys
        document.getElementById('refresh-account-keys-btn')?.addEventListener('click', () => {
            this.loadAccountKeys();
            this.showToast('Account keys refreshed');
        });
        document.getElementById('create-account-key-form')?.addEventListener('submit', (e) => this.handleCreateAccountKey(e));

        // Settings button
        document.getElementById('settings-btn')?.addEventListener('click', () => this.showModal('settings-modal'));

        // Theme toggle
        document.getElementById('theme-toggle')?.addEventListener('click', () => this.toggleTheme());

        // Modal close buttons
        document.querySelectorAll('[data-close-modal]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const modal = e.target.closest('.modal');
                if (modal) modal.classList.add('hidden');
            });
        });

        // Copy buttons
        document.querySelectorAll('[data-copy]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetId = e.currentTarget.dataset.copy;
                const element = document.getElementById(targetId);
                if (element) {
                    this.copyToClipboard(element.textContent);
                }
            });
        });

        // Close modal on backdrop click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.add('hidden');
                }
            });
        });

        // Room filter/sort event listeners
        document.getElementById('rooms-filter')?.addEventListener('change', (e) => {
            this.roomsFilter = e.target.value;
            localStorage.setItem('sleap_rooms_filter', this.roomsFilter);
            this.loadRooms();
        });
        document.getElementById('rooms-sort')?.addEventListener('change', (e) => {
            this.roomsSort = e.target.value;
            localStorage.setItem('sleap_rooms_sort', this.roomsSort);
            this.loadRooms();
        });
        document.getElementById('rooms-search')?.addEventListener('input', (e) => {
            this.roomsSearch = e.target.value;
            this.debounceSearch(() => this.loadRooms());
        });

        // Token filter/sort event listeners
        document.getElementById('tokens-sort')?.addEventListener('change', (e) => {
            this.tokensSort = e.target.value;
            localStorage.setItem('sleap_tokens_sort', this.tokensSort);
            this.loadTokens();
        });
        document.getElementById('tokens-active-only')?.addEventListener('change', (e) => {
            this.tokensActiveOnly = e.target.checked;
            localStorage.setItem('sleap_tokens_active', this.tokensActiveOnly);
            this.loadTokens();
        });
        document.getElementById('tokens-search')?.addEventListener('input', (e) => {
            this.tokensSearch = e.target.value;
            this.debounceSearch(() => this.loadTokens());
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // `/` to focus search bar (only if not in an input/textarea)
            if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
                e.preventDefault();
                // Focus the search bar in the active tab
                const activeTab = document.querySelector('.tab-content.active');
                if (activeTab) {
                    const searchInput = activeTab.querySelector('input[type="text"][placeholder*="Search"]');
                    if (searchInput) {
                        searchInput.focus();
                    }
                }
            }
        });
    }

    debounceSearch(callback) {
        clearTimeout(this.searchDebounceTimer);
        this.searchDebounceTimer = setTimeout(callback, 300);
    }

    toggleUserMenu() {
        const menu = document.getElementById('user-menu');
        menu?.classList.toggle('open');
    }

    switchTab(tabName) {
        // Update sidebar nav items
        document.querySelectorAll('.nav-item[data-tab]').forEach(item => {
            item.classList.toggle('active', item.dataset.tab === tabName);
        });

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}-tab`);
        });

        // Update page title
        // Load account keys on first switch to the tab
        if (tabName === 'account-keys' && this.accountKeys.length === 0) {
            this.loadAccountKeys();
        }

        const titles = {
            'rooms': 'Rooms',
            'tokens': 'Worker Tokens',
            'account-keys': 'Account Keys',
            'quickstart': 'Quickstart Guide',
            'about': 'About SLEAP-CONNECT'
        };
        document.getElementById('page-title').textContent = titles[tabName] || tabName;

        // Re-initialize Lucide icons for the About and Quickstart tabs
        if ((tabName === 'about' || tabName === 'quickstart') && typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    showModal(modalId) {
        // Populate settings modal with user info
        if (modalId === 'settings-modal' && this.user) {
            document.getElementById('settings-username').textContent = this.user.username || '-';
            document.getElementById('settings-user-id').textContent = this.user.id || '-';
        }

        const modalEl = document.getElementById(modalId);
        modalEl?.classList.remove('hidden');
        // Refresh Lucide icons scoped to this modal only
        if (typeof lucide !== 'undefined' && modalEl) {
            lucide.createIcons({ nodes: Array.from(modalEl.querySelectorAll('[data-lucide]')) });
        }
    }

    hideModal(modalId) {
        document.getElementById(modalId)?.classList.add('hidden');
    }

    /**
     * Show a confirmation modal and return a Promise that resolves to true if confirmed
     * @param {string} title - The title of the confirmation dialog
     * @param {string} message - The message to display
     * @param {string} confirmText - The text for the confirm button (default: "Delete")
     * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
     */
    showConfirmModal(title, message, confirmText = 'Delete') {
        return new Promise((resolve) => {
            const modal = document.getElementById('confirm-modal');
            document.getElementById('confirm-title').textContent = title;
            document.getElementById('confirm-message').textContent = message;
            document.getElementById('confirm-ok').textContent = confirmText;

            const handleConfirm = () => {
                cleanup();
                resolve(true);
            };

            const handleCancel = () => {
                cleanup();
                resolve(false);
            };

            const cleanup = () => {
                modal.classList.add('hidden');
                document.getElementById('confirm-ok').removeEventListener('click', handleConfirm);
                document.getElementById('confirm-cancel').removeEventListener('click', handleCancel);
            };

            document.getElementById('confirm-ok').addEventListener('click', handleConfirm);
            document.getElementById('confirm-cancel').addEventListener('click', handleCancel);

            modal.classList.remove('hidden');
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        });
    }

    showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icon = type === 'success' ? 'check-circle' : 'x-circle';
        toast.innerHTML = `
            <i data-lucide="${icon}"></i>
            <span>${message}</span>
        `;
        container.appendChild(toast);

        // Initialize Lucide icon in toast
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }

        setTimeout(() => {
            toast.style.animation = 'slideIn 0.2s ease reverse';
            setTimeout(() => toast.remove(), 200);
        }, 3000);
    }

    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showToast('Copied to clipboard');
        } catch (e) {
            console.error('Copy failed:', e);
            this.showToast('Failed to copy', 'error');
        }
    }

    // =========================================================================
    // OAuth Flow
    // =========================================================================

    handleLogin() {
        // Check if we're in CLI mode
        const urlParams = new URLSearchParams(window.location.search);
        const cliState = urlParams.get('cli_state');

        const authUrl = new URL('https://github.com/login/oauth/authorize');
        authUrl.searchParams.set('client_id', CONFIG.GITHUB_CLIENT_ID);

        // Build redirect URI - include cli_state if present
        let redirectUri = CONFIG.OAUTH_CALLBACK_URL;
        if (cliState) {
            redirectUri += `?cli_state=${encodeURIComponent(cliState)}`;
        }
        authUrl.searchParams.set('redirect_uri', redirectUri);
        authUrl.searchParams.set('scope', 'read:user');
        authUrl.searchParams.set('state', this.generateState());

        window.location.href = authUrl.toString();
    }

    generateState() {
        const state = crypto.randomUUID();
        sessionStorage.setItem('oauth_state', state);
        return state;
    }

    handleLogout() {
        this.clearCredentials();
        this.stopWorkerPolling();
        document.getElementById('user-menu')?.classList.remove('open');
        this.updateUI();
        this.showToast('Signed out successfully');
    }

    // Called from callback.html
    async handleOAuthCallback(code, state) {
        // Verify state
        const savedState = sessionStorage.getItem('oauth_state');
        if (state !== savedState) {
            throw new Error('State mismatch - possible CSRF attack');
        }
        sessionStorage.removeItem('oauth_state');

        // Exchange code for JWT
        const response = await fetch(`${CONFIG.SIGNALING_SERVER}/api/auth/github/callback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code,
                redirect_uri: CONFIG.OAUTH_CALLBACK_URL,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'OAuth exchange failed');
        }

        const data = await response.json();
        this.saveCredentials(data.jwt, data.user);

        return data;
    }

    // =========================================================================
    // API Helpers
    // =========================================================================

    async apiRequest(endpoint, options = {}) {
        const url = `${CONFIG.SIGNALING_SERVER}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (this.jwt) {
            headers['Authorization'] = `Bearer ${this.jwt}`;
        }

        const response = await fetch(url, {
            ...options,
            headers,
        });

        if (response.status === 401) {
            // Token expired
            this.clearCredentials();
            this.updateUI();
            throw new Error('Session expired. Please log in again.');
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || error.error || `Request failed: ${response.status}`);
        }

        return response.json();
    }

    // =========================================================================
    // Relay SSE + Worker API Helpers
    // =========================================================================

    /**
     * Open an SSE connection to a relay channel.
     * @param {string} channel - Channel name (e.g., "worker:{peer_id}" or "job_{id}")
     * @returns {{on: function, close: function, raw: EventSource}}
     */
    sseConnect(channel) {
        const url = `${CONFIG.RELAY_SERVER}/stream/${encodeURIComponent(channel)}`;
        const es = new EventSource(url);
        const handlers = {};

        es.onmessage = (event) => {
            let data;
            try { data = JSON.parse(event.data); } catch { return; }
            const type = data.type;
            if (type && handlers[type]) handlers[type](data);
            if (handlers['*']) handlers['*'](data);
        };

        es.onerror = () => {
            console.warn(`[SSE] Error on channel ${channel}`);
        };

        return {
            on(type, cb) { handlers[type] = cb; return this; },
            close() { es.close(); },
            raw: es,
        };
    }

    /**
     * Forward an arbitrary message to a worker via the signaling server.
     */
    async apiWorkerMessage(roomId, peerId, message) {
        return this.apiRequest('/api/worker/message', {
            method: 'POST',
            body: JSON.stringify({ room_id: roomId, peer_id: peerId, message }),
        });
    }

    /**
     * Request a directory listing from a worker's filesystem.
     */
    async apiFsList(roomId, peerId, path, reqId, offset = 0) {
        return this.apiRequest('/api/fs/list', {
            method: 'POST',
            body: JSON.stringify({ room_id: roomId, peer_id: peerId, path, req_id: reqId, offset }),
        });
    }

    /**
     * Submit a training job to a worker.
     */
    async apiJobSubmit(roomId, peerId, config) {
        return this.apiRequest('/api/jobs/submit', {
            method: 'POST',
            body: JSON.stringify({ room_id: roomId, peer_id: peerId, config }),
        });
    }

    /**
     * Cancel a running training job.
     */
    async apiJobCancel(jobId, roomId, peerId) {
        return this.apiRequest(`/api/jobs/${jobId}/cancel`, {
            method: 'POST',
            body: JSON.stringify({ room_id: roomId, peer_id: peerId }),
        });
    }

    // =========================================================================
    // Rooms
    // =========================================================================

    async loadRooms() {
        const container = document.getElementById('rooms-list');
        container.innerHTML = '<p class="loading">Loading rooms...</p>';

        // Restore filter UI state
        const filterEl = document.getElementById('rooms-filter');
        const sortEl = document.getElementById('rooms-sort');
        const searchEl = document.getElementById('rooms-search');
        if (filterEl) filterEl.value = this.roomsFilter;
        if (sortEl) sortEl.value = this.roomsSort;
        if (searchEl && searchEl.value !== this.roomsSearch) searchEl.value = this.roomsSearch;

        // Build query params
        const params = new URLSearchParams();
        if (this.roomsFilter && this.roomsFilter !== 'all') {
            params.set('role', this.roomsFilter);
        }
        if (this.roomsSort) {
            params.set('sort_by', this.roomsSort);
        }
        if (this.roomsSearch) {
            params.set('search', this.roomsSearch);
        }
        const queryString = params.toString();
        const url = '/api/auth/rooms' + (queryString ? `?${queryString}` : '');

        try {
            const data = await this.apiRequest(url);
            this.rooms = data.rooms || [];
            this.renderRooms();
            this.startWorkerPolling();
            // Reconnect SSE for any active jobs restored from sessionStorage
            this._reconnectActiveJobs();
            this.updateCounts();
            // Load live workers for all rooms (non-blocking, same pattern as token workers)
            this.loadAllRoomWorkers().then(() => {
                this.updateRoomWorkerBadges();
            });
        } catch (e) {
            console.error('Failed to load rooms:', e);
            container.innerHTML = `<p class="loading" style="color: var(--status-error);">Failed to load rooms: ${e.message}</p>`;
        }
    }

    updateCounts() {
        // Update sidebar badges
        document.getElementById('rooms-count').textContent = this.rooms.length;
        document.getElementById('tokens-count').textContent = this.tokens.length;
        const activeAccountKeys = this.accountKeys.filter(k => !k.revoked_at);
        document.getElementById('account-keys-count').textContent = activeAccountKeys.length;

        // Update section titles
        document.getElementById('rooms-title-count').textContent = this.rooms.length;
        document.getElementById('tokens-title-count').textContent = this.tokens.length;
        document.getElementById('account-keys-title-count').textContent = this.accountKeys.length;
    }

    renderRooms() {
        const container = document.getElementById('rooms-list');

        if (this.rooms.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <i data-lucide="home"></i>
                    </div>
                    <h3>No rooms yet</h3>
                    <p>Create a room to get started with remote training.</p>
                    <button class="btn btn-primary" onclick="app.showModal('create-room-modal')">
                        <i data-lucide="plus"></i>
                        Create Room
                    </button>
                </div>
            `;
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
            return;
        }

        // Separate rooms into active and expired
        const now = new Date();
        const activeRooms = this.rooms.filter(room => {
            if (!room.expires_at) return true;
            const expiresAt = parseDate(room.expires_at);
            return expiresAt && expiresAt > now;
        });
        const expiredRooms = this.rooms.filter(room => {
            if (!room.expires_at) return false;
            const expiresAt = parseDate(room.expires_at);
            return expiresAt && expiresAt <= now;
        });

        // Check if expired section should be expanded (from localStorage)
        const expiredExpanded = localStorage.getItem('sleap_expired_rooms_expanded') === 'true';

        let html = '';

        // If no active rooms but there are expired ones, show empty state message
        if (activeRooms.length === 0 && expiredRooms.length > 0) {
            html += `
            <div class="empty-state" style="padding: 40px 20px;">
                <div class="empty-icon">
                    <i data-lucide="home"></i>
                </div>
                <h3>No active rooms</h3>
                <p>All your rooms have expired. Create a new room or delete the expired ones.</p>
                <button class="btn btn-primary" onclick="app.showModal('create-room-modal')">
                    <i data-lucide="plus"></i>
                    Create Room
                </button>
            </div>`;
        } else {
            // Active rooms section
            if (activeRooms.length > 0) {
                html += `<div class="rooms-section-header">
                    <h3>Active Rooms (${activeRooms.length})</h3>
                </div>`;
                html += activeRooms.map(room => this.renderRoomCard(room)).join('');
            }

            // Create Room button at the bottom of active section
            html += `
                <div class="create-item-row">
                    <button class="btn btn-primary btn-create-inline" onclick="app.showModal('create-room-modal')">
                        <i data-lucide="plus"></i>
                        Create Room
                    </button>
                </div>`;
        }

        // Expired rooms section (collapsible)
        if (expiredRooms.length > 0) {
            html += `
            <div class="rooms-section-header inactive-section ${expiredExpanded ? 'expanded' : ''}" onclick="app.toggleExpiredRoomsSection(this)">
                <div class="section-toggle">
                    <i data-lucide="${expiredExpanded ? 'chevron-down' : 'chevron-right'}"></i>
                    <h3>Expired Rooms (${expiredRooms.length})</h3>
                </div>
                <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); app.handleDeleteAllExpiredRooms()">
                    <i data-lucide="trash-2"></i>
                    Delete All
                </button>
            </div>
            <div class="expired-rooms-list" style="display: ${expiredExpanded ? 'block' : 'none'};">
                ${expiredRooms.map(room => this.renderRoomCard(room, true)).join('')}
            </div>`;
        }

        container.innerHTML = html;

        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }

        // Render active job badges on room cards
        for (const [, job] of this.activeJobs) {
            this._updateRoomBadges(job.roomId);
        }
    }

    renderRoomCard(room, isExpired = false) {
        // Check if room is expiring soon (< 3 days)
        const now = new Date();
        const expiresAt = room.expires_at ? parseDate(room.expires_at) : null;
        const isExpiringSoon = expiresAt &&
            expiresAt - now < 3 * 24 * 60 * 60 * 1000 &&
            expiresAt > now;
        if (!isExpired) {
            isExpired = expiresAt && expiresAt < now;
        }

        return `
        <div class="room-card ${isExpired ? 'expired inactive' : ''} ${isExpiringSoon ? 'expiring-soon' : ''}">
            <div class="room-header">
                <div class="room-main">
                    <div class="room-icon" ${isExpired ? 'style="opacity: 0.5;"' : ''}>
                        <i data-lucide="home"></i>
                    </div>
                    <div class="room-info">
                        <h3>${room.name || 'Unnamed Room'}</h3>
                        <div class="room-meta">
                            <span class="room-meta-item room-id-copy" title="Click to copy Room ID" onclick="event.stopPropagation(); app.copyToClipboard('${room.room_id}')">
                                <i data-lucide="hash"></i>
                                ${room.room_id}
                                <i data-lucide="copy" class="copy-hint-icon"></i>
                            </span>
                            <span class="room-meta-item" title="${formatExactDate(room.joined_at)}">
                                <i data-lucide="calendar"></i>
                                Joined ${formatRelativeTime(room.joined_at)}
                            </span>
                            ${room.expires_at ? `
                                <span class="room-meta-item ${isExpiringSoon ? 'warning' : ''} ${isExpired ? 'error' : ''}" title="${formatExactDate(room.expires_at)}">
                                    <i data-lucide="${isExpiringSoon || isExpired ? 'alert-triangle' : 'clock'}"></i>
                                    ${isExpired ? 'Expired' : `Expires ${formatRelativeTime(room.expires_at)}`}
                                </span>
                            ` : `
                                <span class="room-meta-item">
                                    <i data-lucide="infinity"></i>
                                    Never expires
                                </span>
                            `}
                        </div>
                    </div>
                </div>
                <div class="room-actions">
                    <span class="role-badge ${room.role}">${room.role}</span>
                    <span id="room-worker-badge-${room.room_id}" class="worker-count-badge offline">
                        <i data-lucide="zap-off"></i>
                        0 connected
                    </span>
                    ${room.role === 'owner' ? `
                        <button class="btn btn-secondary btn-sm" onclick="app.handleRoomSecret('${room.room_id}')">
                            <i data-lucide="key"></i>
                            Secret
                        </button>
                    ` : ''}
                    <button class="btn btn-danger btn-sm" onclick="app.handleDeleteRoom('${room.room_id}', '${this.escapeHtml(room.name || room.room_id)}')">
                        <i data-lucide="trash-2"></i>
                        Delete
                    </button>
                </div>
            </div>
            <div class="room-action-bar">
                ${!isExpired ? `
                    <button class="btn btn-submit-job btn-sm" data-room-id="${room.room_id}" onclick="app.openSubmitJobModal('${room.room_id}')">
                        <i data-lucide="play"></i>
                        Submit Job
                    </button>
                ` : ''}
                <button class="btn btn-ghost btn-sm" onclick="app.openWorkersModal('${room.room_id}')">
                    <i data-lucide="cpu"></i>
                    View Workers
                </button>
                <button class="btn btn-ghost btn-sm" onclick="app.openDeployWorkerModal('${room.room_id}')">
                    <i data-lucide="plus"></i>
                    Deploy Worker
                </button>
                ${!isExpired && room.role === 'owner' ? `
                    <button class="btn btn-ghost btn-sm" onclick="app.handleInvite('${room.room_id}')">
                        <i data-lucide="user-plus"></i>
                        Invite
                    </button>
                ` : ''}
                <div class="room-job-badges" id="room-job-badges-${room.room_id}"></div>
            </div>
        </div>
        `;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML.replace(/'/g, "\\'");
    }

    async handleCreateRoom(e) {
        e.preventDefault();

        const nameInput = document.getElementById('room-name');
        const expiresInput = document.getElementById('room-expires');
        const name = nameInput.value.trim();
        const expiresValue = expiresInput.value;

        // Build request body
        const body = {};
        if (name) body.name = name;
        if (expiresValue !== 'never') {
            body.expires_in_days = parseInt(expiresValue);
        } else {
            body.expires_in_days = null;  // Never expires
        }

        try {
            const data = await this.apiRequest('/api/auth/rooms', {
                method: 'POST',
                body: JSON.stringify(body),
            });

            // Show success modal
            document.getElementById('new-room-id').textContent = data.room_id;

            this.hideModal('create-room-modal');
            this.showModal('room-created-modal');

            // Refresh rooms list and reset form
            nameInput.value = '';
            expiresInput.value = '30';  // Reset to default
            this.loadRooms();

        } catch (e) {
            console.error('Failed to create room:', e);
            this.showToast(e.message, 'error');
        }
    }

    async handleInvite(roomId) {
        try {
            const data = await this.apiRequest(`/api/auth/rooms/${roomId}/invite`, {
                method: 'POST',
            });

            document.getElementById('invite-code').textContent = data.invite_code;
            document.getElementById('invite-code-cli').textContent = data.invite_code;
            this.showModal('invite-modal');

        } catch (e) {
            console.error('Failed to create invite:', e);
            this.showToast(e.message, 'error');
        }
    }

    async handleJoinRoom(e) {
        e.preventDefault();

        const codeInput = document.getElementById('join-code');
        const code = codeInput.value.trim();

        try {
            await this.apiRequest('/api/auth/rooms/join', {
                method: 'POST',
                body: JSON.stringify({ invite_code: code }),
            });

            this.hideModal('join-room-modal');
            this.showToast('Successfully joined room');
            codeInput.value = '';
            this.loadRooms();

        } catch (e) {
            console.error('Failed to join room:', e);
            this.showToast(e.message, 'error');
        }
    }

    async handleDeleteRoom(roomId, roomName) {
        const confirmed = await this.showConfirmModal(
            'Delete Room',
            `Are you sure you want to delete "${roomName}"? This will also delete all worker tokens and memberships. This action cannot be undone.`
        );

        if (!confirmed) return;

        try {
            await this.apiRequest(`/api/auth/rooms/${roomId}`, {
                method: 'DELETE',
            });

            this.showToast('Room deleted successfully');
            this.loadRooms();

        } catch (e) {
            console.error('Failed to delete room:', e);
            this.showToast(e.message, 'error');
        }
    }

    // =========================================================================
    // Tokens
    // =========================================================================

    async loadTokens() {
        const container = document.getElementById('tokens-list');
        container.innerHTML = '<p class="loading">Loading tokens...</p>';

        // Restore filter UI state
        const sortEl = document.getElementById('tokens-sort');
        const activeEl = document.getElementById('tokens-active-only');
        const searchEl = document.getElementById('tokens-search');
        if (sortEl) sortEl.value = this.tokensSort;
        if (activeEl) activeEl.checked = this.tokensActiveOnly;
        if (searchEl && searchEl.value !== this.tokensSearch) searchEl.value = this.tokensSearch;

        // Build query params
        const params = new URLSearchParams();
        if (this.tokensSort) {
            params.set('sort_by', this.tokensSort);
        }
        if (this.tokensActiveOnly) {
            params.set('active_only', 'true');
        }
        const queryString = params.toString();
        const url = '/api/auth/tokens' + (queryString ? `?${queryString}` : '');

        try {
            const data = await this.apiRequest(url);
            let tokens = data.tokens || [];

            // Client-side search filtering (API doesn't support search for tokens)
            if (this.tokensSearch) {
                const search = this.tokensSearch.toLowerCase();
                tokens = tokens.filter(t =>
                    t.worker_name.toLowerCase().includes(search) ||
                    (t.room_name && t.room_name.toLowerCase().includes(search)) ||
                    t.room_id.toLowerCase().includes(search)
                );
            }

            this.tokens = tokens;
            this.renderTokens();
            this.updateCounts();

            // Load worker counts for all tokens (non-blocking)
            this.loadAllTokenWorkers().then(() => {
                this.updateWorkerBadges();
            });
        } catch (e) {
            console.error('Failed to load tokens:', e);
            container.innerHTML = `<p class="loading" style="color: var(--status-error);">Failed to load tokens: ${e.message}</p>`;
        }
    }

    updateWorkerBadges() {
        // Update worker count badges after loading worker data
        for (const token of this.tokens) {
            if (token.revoked_at) continue;

            const workerData = this.tokenWorkers[token.token_id] || { workers: [], count: 0 };
            const badge = document.getElementById(`worker-badge-${token.token_id}`);
            const workersList = document.getElementById(`workers-list-${token.token_id}`);

            if (badge) {
                const count = workerData.count;
                const text = count === 0 ? '0 connected' :
                    count === 1 ? '1 connected' : `${count} connected`;
                badge.innerHTML = `
                    <i data-lucide="${count > 0 ? 'zap' : 'zap-off'}"></i>
                    ${text}
                `;
                badge.className = `worker-count-badge ${count === 0 ? 'offline' : ''}`;
            }

            if (workersList) {
                if (workerData.workers.length === 0) {
                    workersList.innerHTML = '<div class="nested-worker-row" style="justify-content: center; color: var(--text-muted);">No workers currently connected</div>';
                } else {
                    workersList.innerHTML = workerData.workers.map(worker => `
                        <div class="nested-worker-row">
                            <div class="worker-cell">
                                <div class="worker-avatar">
                                    <i data-lucide="monitor"></i>
                                </div>
                                <div>
                                    <div class="worker-name">${extractWorkerHostname(worker.peer_id)}</div>
                                    <div class="worker-id">${worker.peer_id}</div>
                                </div>
                            </div>
                            <span class="worker-connected" title="${formatExactDate(worker.connected_at)}">
                                Connected ${formatRelativeTime(worker.connected_at)}
                            </span>
                        </div>
                    `).join('');
                }
            }

            // Refresh Lucide icons
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    }

    renderTokens() {
        const container = document.getElementById('tokens-list');

        if (this.tokens.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <i data-lucide="key-round"></i>
                    </div>
                    <h3>No tokens yet</h3>
                    <p>Create a token to authenticate workers.</p>
                    <button class="btn btn-primary" onclick="app.showCreateTokenModal()">
                        <i data-lucide="plus"></i>
                        Create Token
                    </button>
                </div>
            `;
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
            return;
        }

        // Split tokens into active and inactive
        const activeTokens = this.tokens.filter(t => t.is_active);
        const inactiveTokens = this.tokens.filter(t => !t.is_active);

        // Check if inactive section should be expanded (from localStorage)
        const inactiveExpanded = localStorage.getItem('sleap_inactive_tokens_expanded') === 'true';

        let html = '';

        // If no active tokens but there are inactive ones, show empty state message
        if (activeTokens.length === 0 && inactiveTokens.length > 0) {
            html += `
            <div class="empty-state" style="padding: 40px 20px;">
                <div class="empty-icon">
                    <i data-lucide="key-round"></i>
                </div>
                <h3>No active tokens</h3>
                <p>All your tokens are expired or revoked. Create a new token or delete the inactive ones.</p>
                <button class="btn btn-primary" onclick="app.showCreateTokenModal()">
                    <i data-lucide="plus"></i>
                    Create Token
                </button>
            </div>`;
        } else {
            // Active tokens section
            if (activeTokens.length > 0) {
                html += `<div class="tokens-section-header">
                    <h3>Active Tokens (${activeTokens.length})</h3>
                </div>`;
                html += activeTokens.map(token => this.renderTokenCard(token, false)).join('');
            }

            // Create Token button at the bottom of active section
            html += `
                <div class="create-item-row">
                    <button class="btn btn-primary btn-create-inline" onclick="app.showCreateTokenModal()">
                        <i data-lucide="plus"></i>
                        Create Token
                    </button>
                </div>`;
        }

        // Inactive tokens section (collapsible)
        if (inactiveTokens.length > 0) {
            html += `
            <div class="tokens-section-header inactive-section ${inactiveExpanded ? 'expanded' : ''}" onclick="app.toggleInactiveSection(this)">
                <div class="section-toggle">
                    <i data-lucide="${inactiveExpanded ? 'chevron-down' : 'chevron-right'}"></i>
                    <h3>Inactive Tokens (${inactiveTokens.length})</h3>
                </div>
                <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); app.handleDeleteAllInactive()">
                    <i data-lucide="trash-2"></i>
                    Delete All
                </button>
            </div>
            <div class="inactive-tokens-list" style="display: ${inactiveExpanded ? 'block' : 'none'};">
                ${inactiveTokens.map(token => this.renderTokenCard(token, true)).join('')}
            </div>`;
        }

        container.innerHTML = html;

        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    renderTokenCard(token, isInactive) {
        const isRevoked = !!token.revoked_at;
        const isExpired = !token.is_active && !isRevoked;
        const now = new Date();
        const expiresAt = token.expires_at ? parseDate(token.expires_at) : null;
        const isExpiringSoon = expiresAt && !isInactive &&
            expiresAt - now < 3 * 24 * 60 * 60 * 1000 &&
            expiresAt > now;

        // Check if API key is available in session storage
        const storedKey = this.getStoredApiKey(token.token_id);
        const workerCommand = storedKey ? this.buildWorkerCommand(storedKey.api_key, storedKey.room_secret) : null;

        return `
        <div class="token-card ${isInactive ? 'inactive' : ''} ${storedKey ? 'has-key' : ''}">
            <div class="token-header">
                <div class="token-main">
                    <div class="token-icon" ${isInactive ? 'style="opacity: 0.5;"' : ''}>
                        <i data-lucide="key-round"></i>
                    </div>
                    <div class="token-info">
                        <h3>${token.worker_name}</h3>
                        <div class="token-meta">
                            <span class="token-meta-item">
                                <i data-lucide="home"></i>
                                ${token.room_name ? `${token.room_name} (${token.room_id.substring(0, 8)}...)` : token.room_id}
                            </span>
                            <span class="token-meta-item" title="${formatExactDate(token.created_at)}">
                                <i data-lucide="calendar"></i>
                                Created ${formatRelativeTime(token.created_at)}
                            </span>
                            ${token.expires_at ? `
                                <span class="token-meta-item ${isExpiringSoon ? 'warning' : ''} ${isExpired ? 'error' : ''}" title="${formatExactDate(token.expires_at)}">
                                    <i data-lucide="${isExpiringSoon || isExpired ? 'alert-triangle' : 'clock'}"></i>
                                    ${isExpired ? 'Expired' : `Expires ${formatRelativeTime(token.expires_at)}`}
                                </span>
                            ` : ''}
                            ${isRevoked ? `
                                <span class="token-meta-item error">
                                    <i data-lucide="x-circle"></i>
                                    Revoked ${token.revoked_at ? formatRelativeTime(token.revoked_at) : ''}
                                </span>
                            ` : ''}
                        </div>
                    </div>
                </div>
                <div class="token-actions">
                    ${!isInactive ? `
                        <div id="worker-badge-${token.token_id}" class="worker-count-badge offline">
                            <i data-lucide="zap-off"></i>
                            Loading...
                        </div>
                        <button class="btn btn-danger btn-sm" onclick="app.handleRevokeToken('${token.token_id}')">
                            <i data-lucide="trash-2"></i>
                            Revoke
                        </button>
                    ` : `
                        <button class="btn btn-danger btn-sm" onclick="app.handleDeleteToken('${token.token_id}', '${token.worker_name}')">
                            <i data-lucide="trash-2"></i>
                            Delete
                        </button>
                    `}
                </div>
            </div>
            ${storedKey && !isInactive ? `
                <div class="api-key-available">
                    <div class="api-key-header">
                        <i data-lucide="alert-circle"></i>
                        <span>API key available for this session only</span>
                    </div>
                    <div class="api-key-content">
                        <code class="worker-command">${workerCommand}</code>
                        <div class="api-key-actions">
                            <button class="btn btn-secondary btn-sm" onclick="app.copyToClipboard('${workerCommand}')">
                                <i data-lucide="copy"></i>
                                Copy Command
                            </button>
                            <button class="btn btn-ghost btn-sm" onclick="app.dismissApiKey('${token.token_id}')">
                                <i data-lucide="check"></i>
                                I've copied it
                            </button>
                        </div>
                    </div>
                </div>
            ` : ''}
            ${!isInactive ? `
                <div class="nested-workers">
                    <div class="nested-header" onclick="app.toggleWorkersList('${token.token_id}', this)">
                        <span>Connected Workers</span>
                        <i data-lucide="chevron-down"></i>
                    </div>
                    <div id="workers-list-${token.token_id}" class="nested-worker-list">
                        <div class="nested-worker-row" style="justify-content: center; color: var(--text-muted);">Loading workers...</div>
                    </div>
                </div>
            ` : ''}
        </div>
        `;
    }

    toggleInactiveSection(header) {
        const isExpanded = header.classList.toggle('expanded');
        const list = header.nextElementSibling;
        const icon = header.querySelector('[data-lucide]');

        list.style.display = isExpanded ? 'block' : 'none';
        localStorage.setItem('sleap_inactive_tokens_expanded', isExpanded);

        // Update chevron icon direction
        if (icon) {
            icon.setAttribute('data-lucide', isExpanded ? 'chevron-down' : 'chevron-right');
        }
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    toggleExpiredRoomsSection(header) {
        const isExpanded = header.classList.toggle('expanded');
        const list = header.nextElementSibling;
        const icon = header.querySelector('[data-lucide]');

        list.style.display = isExpanded ? 'block' : 'none';
        localStorage.setItem('sleap_expired_rooms_expanded', isExpanded);

        // Update chevron icon direction
        if (icon) {
            icon.setAttribute('data-lucide', isExpanded ? 'chevron-down' : 'chevron-right');
        }
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    async handleDeleteAllExpiredRooms() {
        const expiredRooms = this.rooms.filter(room => room.expires_at && new Date(room.expires_at) < new Date());

        const confirmed = await this.showConfirmModal(
            'Delete All Expired Rooms',
            `Delete all ${expiredRooms.length} expired rooms? This will also delete all associated tokens and memberships.`
        );

        if (!confirmed) return;

        try {
            // Delete each expired room
            for (const room of expiredRooms) {
                await this.apiRequest(`/api/auth/rooms/${room.room_id}`, {
                    method: 'DELETE',
                });
            }

            this.showToast(`Deleted ${expiredRooms.length} expired room(s)`);
            this.loadRooms();

        } catch (e) {
            console.error('Failed to delete expired rooms:', e);
            this.showToast(e.message, 'error');
        }
    }

    async handleDeleteToken(tokenId, workerName) {
        const confirmed = await this.showConfirmModal(
            'Delete Token',
            `Permanently delete token "${workerName}"? This cannot be undone.`
        );

        if (!confirmed) return;

        try {
            await this.apiRequest(`/api/auth/tokens/${tokenId}`, {
                method: 'DELETE',
            });

            this.showToast('Token deleted');
            this.loadTokens();

        } catch (e) {
            console.error('Failed to delete token:', e);
            this.showToast(e.message, 'error');
        }
    }

    async handleDeleteAllInactive() {
        const inactiveCount = this.tokens.filter(t => !t.is_active).length;

        const confirmed = await this.showConfirmModal(
            'Delete All Inactive Tokens',
            `Delete all ${inactiveCount} inactive tokens? This will permanently remove all revoked and expired tokens.`
        );

        if (!confirmed) return;

        try {
            const result = await this.apiRequest('/api/auth/tokens', {
                method: 'DELETE',
            });

            this.showToast(`Deleted ${result.deleted_count} token(s)`);
            this.loadTokens();

        } catch (e) {
            console.error('Failed to delete tokens:', e);
            this.showToast(e.message, 'error');
        }
    }

    async showCreateTokenModal() {
        // Populate room dropdown - filter out expired rooms
        const select = document.getElementById('token-room');
        const now = new Date();
        const activeRooms = this.rooms.filter(room => {
            if (!room.expires_at) return true;
            const expiresAt = parseDate(room.expires_at);
            return expiresAt && expiresAt > now;
        });
        select.innerHTML = '<option value="">Select a room...</option>' +
            activeRooms.map(room => `
                <option value="${room.room_id}">${room.room_id}${room.name ? ` - ${room.name}` : ''}</option>
            `).join('');

        this.showModal('create-token-modal');
    }

    async handleCreateToken(e) {
        e.preventDefault();

        const roomId = document.getElementById('token-room').value;
        const workerName = document.getElementById('token-name').value.trim();
        const expiresDays = parseInt(document.getElementById('token-expires').value) || 7;

        if (!roomId || !workerName) {
            this.showToast('Please fill in all required fields', 'error');
            return;
        }

        try {
            const data = await this.apiRequest('/api/auth/token', {
                method: 'POST',
                body: JSON.stringify({
                    room_id: roomId,
                    worker_name: workerName,
                    expires_days: expiresDays,
                }),
            });

            // Look up room info
            const room = this.rooms.find(r => r.room_id === roomId);
            const isOwner = room && room.role === 'owner';
            const storedSecret = this.getStoredRoomSecret(roomId);

            // Store API key in sessionStorage for this session
            this.storeApiKey(data.token_id, {
                api_key: data.token_id,
                room_secret: isOwner && storedSecret ? storedSecret : null,
                room_id: roomId,
                worker_name: workerName,
                created_at: Date.now(),
            });

            // Show success modal
            document.getElementById('new-token-id').textContent = data.token_id;
            const roomDisplay = room && room.name
                ? `${room.name} (${roomId.substring(0, 8)}...)`
                : roomId;
            document.getElementById('new-token-room').textContent = roomDisplay;
            document.getElementById('new-token-name').textContent = workerName;

            // Build worker command - include room secret if owner has one stored locally
            let workerCommand = `sleap-rtc worker --api-key ${data.token_id}`;
            if (isOwner && storedSecret) {
                workerCommand += ` --room-secret ${storedSecret}`;
            }
            document.getElementById('worker-command').textContent = workerCommand;

            this.hideModal('create-token-modal');
            this.showModal('token-created-modal');

            // Clear form
            document.getElementById('token-name').value = '';
            document.getElementById('token-expires').value = '7';

            // Refresh tokens list
            this.loadTokens();

        } catch (e) {
            console.error('Failed to create token:', e);
            this.showToast(e.message, 'error');
        }
    }

    async loadTokenWorkers(tokenId) {
        try {
            const data = await this.apiRequest(`/api/auth/tokens/${tokenId}/workers`);
            this.tokenWorkers[tokenId] = data;
            return data;
        } catch (e) {
            console.error(`Failed to load workers for token ${tokenId}:`, e);
            this.tokenWorkers[tokenId] = { workers: [], count: 0 };
            return this.tokenWorkers[tokenId];
        }
    }

    async loadAllTokenWorkers() {
        // Load worker counts for all active tokens in parallel
        const activeTokens = this.tokens.filter(t => !t.revoked_at);
        const promises = activeTokens.map(token => this.loadTokenWorkers(token.token_id));
        await Promise.all(promises);
    }

    async loadRoomWorkers(roomId) {
        try {
            const data = await this.apiRequest(`/api/rooms/${roomId}/workers`);
            this.roomWorkers[roomId] = data;
            return data;
        } catch (e) {
            console.error(`Failed to load workers for room ${roomId}:`, e);
            this.roomWorkers[roomId] = { workers: [], count: 0 };
            return this.roomWorkers[roomId];
        }
    }

    async loadAllRoomWorkers() {
        const promises = this.rooms.map(room => this.loadRoomWorkers(room.room_id));
        await Promise.all(promises);
    }
    updateRoomWorkerBadges() {
        for (const room of this.rooms) {
            const workerData = this.roomWorkers[room.room_id] || { workers: [], count: 0 };
            const badge = document.getElementById(`room-worker-badge-${room.room_id}`);

            if (badge) {
                const count = workerData.count;
                const text = count === 0 ? '0 connected' :
                    count === 1 ? '1 connected' : `${count} connected`;
                badge.innerHTML = `
                    <i data-lucide="${count > 0 ? 'zap' : 'zap-off'}"></i>
                    ${text}
                `;
                badge.className = `worker-count-badge ${count === 0 ? 'offline' : ''}`;
            }

            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    }

    // =========================================================================
    // Workers Modal
    // =========================================================================

    openWorkersModal(roomId) {
        this.currentWorkersRoomId = roomId;
        this.workersFilter = 'all';
        this.workersSearchQuery = '';

        // Set room name in modal header
        const room = this.rooms.find(r => r.room_id === roomId);
        const roomName = room ? (room.name || roomId) : roomId;
        const subtitle = document.getElementById('wm-room-name');
        if (subtitle) subtitle.textContent = roomName;

        // Reset search input
        const searchInput = document.getElementById('wm-search');
        if (searchInput) searchInput.value = '';

        // Reset filter chips
        document.querySelectorAll('#workers-modal .wm-filter-chip').forEach(c => c.classList.remove('active'));
        const allChip = document.querySelector('#workers-modal .wm-filter-chip[data-filter="all"]');
        if (allChip) allChip.classList.add('active');

        // Update empty-state command with room ID
        const cmdEl = document.getElementById('wm-empty-cmd');
        if (cmdEl) cmdEl.textContent = `sleap-rtc worker --account-key slp_acct_xxxx... --room ${roomId}`;

        this.renderWorkersModalList();
        this.showModal('workers-modal');
    }

    renderWorkersModalList() {
        const roomId = this.currentWorkersRoomId;
        const workerData = this.roomWorkers[roomId] || { workers: [], count: 0 };
        const workers = workerData.workers || [];
        const container = document.getElementById('wm-worker-list');
        const emptyState = document.getElementById('wm-empty-state');
        if (!container) return;

        const query = (this.workersSearchQuery || '').toLowerCase();
        const filter = this.workersFilter || 'all';

        // Count by status for filter chips
        const idleCount = workers.filter(w => {
            const status = (w.properties && w.properties.status) || 'available';
            return status === 'available';
        }).length;
        const busyCount = workers.filter(w => {
            const status = (w.properties && w.properties.status) || 'available';
            return status === 'busy';
        }).length;

        // Update chip counts
        const countAll = document.getElementById('wm-count-all');
        const countIdle = document.getElementById('wm-count-idle');
        const countBusy = document.getElementById('wm-count-busy');
        if (countAll) countAll.textContent = workers.length;
        if (countIdle) countIdle.textContent = idleCount;
        if (countBusy) countBusy.textContent = busyCount;

        // Apply filters
        let filtered = workers;
        if (filter === 'idle') {
            filtered = filtered.filter(w => {
                const status = (w.properties && w.properties.status) || 'available';
                return status === 'available';
            });
        } else if (filter === 'busy') {
            filtered = filtered.filter(w => {
                const status = (w.properties && w.properties.status) || 'available';
                return status === 'busy';
            });
        }

        // Apply search
        if (query) {
            filtered = filtered.filter(w => {
                const name = (w.worker_name || '').toLowerCase();
                const gpu = (w.properties && w.properties.gpu_model || '').toLowerCase();
                const peerId = (w.peer_id || '').toLowerCase();
                return name.includes(query) || gpu.includes(query) || peerId.includes(query);
            });
        }

        // Show empty state or worker list
        if (workers.length === 0) {
            container.innerHTML = '';
            if (emptyState) emptyState.classList.remove('hidden');
        } else if (filtered.length === 0) {
            container.innerHTML = '<div class="wm-no-results">No workers match your search.</div>';
            if (emptyState) emptyState.classList.add('hidden');
        } else {
            if (emptyState) emptyState.classList.add('hidden');
            container.innerHTML = filtered.map(worker => {
                const props = worker.properties || {};
                const gpuModel = props.gpu_model || 'Unknown GPU';
                const gpuMem = props.gpu_memory_mb ? `${Math.round(props.gpu_memory_mb / 1024)} GB` : '';
                const cuda = props.cuda_version ? `CUDA ${props.cuda_version}` : '';
                const sleapNn = props.sleap_nn_version ? `sleap-nn ${props.sleap_nn_version}` : '';
                const specs = [gpuModel, gpuMem, cuda, sleapNn].filter(Boolean).join(' \u00B7 ');

                const serverStatus = props.status || 'available';
                // Check local activeJobs first — server may report available even while training
                const activeJob = Array.from(this.activeJobs.values()).find(
                    j => j.workerId === worker.peer_id && j.roomId === roomId &&
                         j.status !== 'complete' && j.status !== 'failed' && j.status !== 'cancelled'
                );
                const status = activeJob ? 'busy' : serverStatus;
                console.log(`[DEBUG-workerStatus] WM worker=${worker.peer_id} server=${serverStatus} activeJob=${activeJob?.jobId?.slice(0,8) ?? 'none'} → effective=${status}`);
                const statusClass = status === 'busy' ? 'busy' : 'available';
                const statusText = status === 'busy' ? 'Busy' : 'Idle';

                const isBusy = status === 'busy' || status === 'reserved';
                const busyClickable = activeJob ? 'busy-clickable' : '';
                const clickHandler = activeJob
                    ? `onclick="app.hideModal('workers-modal');app.reopenJobModal('${activeJob.jobId}')"`
                    : '';

                const jobInfoHtml = activeJob
                    ? `<div class="wm-job-info">
                        <span class="wm-job-detail">
                            Training ${activeJob.modelType}${activeJob.lastEpoch > 0 ? ` — Epoch ${activeJob.lastEpoch}${activeJob.maxEpochs ? ' / ' + activeJob.maxEpochs : ''}` : ''}${activeJob.lastLoss != null ? ', loss ' + activeJob.lastLoss.toFixed(4) : ''}
                        </span>
                        <span class="wm-view-job-link">View Job <i data-lucide="arrow-right"></i></span>
                    </div>`
                    : '';

                const keyItem = worker.account_key_id
                    ? `<span class="worker-meta-item">
                            <i data-lucide="key"></i>
                            ${worker.account_key_id.slice(0, 20)}...
                            <span class="auth-badge account-key">ACCOUNT-KEY</span>
                        </span>`
                    : `<span class="worker-meta-item"><span class="auth-badge token">TOKEN</span></span>`;

                const metaOrJobInfo = activeJob
                    ? jobInfoHtml
                    : `<div class="wm-worker-meta">
                        <span class="wm-meta-item">
                            <i data-lucide="hash"></i>
                            ${worker.peer_id}
                            <span class="auth-badge peer-id">PEER ID</span>
                        </span>
                        ${keyItem}
                    </div>`;

                return `
                <div class="wm-worker-card ${busyClickable}" ${clickHandler}>
                    <div class="wm-worker-row">
                        <div class="wm-worker-icon"><i data-lucide="cpu"></i></div>
                        <div class="wm-worker-info">
                            <div class="wm-worker-name">${worker.worker_name || extractWorkerHostname(worker.peer_id)}</div>
                            <div class="wm-worker-specs">${specs}</div>
                        </div>
                        <div class="wm-worker-status">
                            <div class="wm-status-dot ${statusClass}"></div>
                            <span>${statusText}</span>
                            ${worker.connected_at ? `<span class="wm-connected-time" title="${formatExactDate(worker.connected_at)}">Connected ${formatRelativeTime(worker.connected_at)}</span>` : ''}
                        </div>
                    </div>
                    ${metaOrJobInfo}
                </div>`;
            }).join('');
        }

        if (typeof lucide !== 'undefined' && container) {
            lucide.createIcons({ nodes: Array.from(container.querySelectorAll('[data-lucide]')) });
        }
    }

    setWorkersFilter(filter) {
        this.workersFilter = filter;
        document.querySelectorAll('#workers-modal .wm-filter-chip').forEach(c => c.classList.remove('active'));
        const activeChip = document.querySelector(`#workers-modal .wm-filter-chip[data-filter="${filter}"]`);
        if (activeChip) activeChip.classList.add('active');
        this.renderWorkersModalList();
    }

    filterWorkersSearch() {
        const input = document.getElementById('wm-search');
        this.workersSearchQuery = input ? input.value : '';
        this.renderWorkersModalList();
    }

    toggleWorkersList(tokenId, headerElement) {
        const list = document.getElementById(`workers-list-${tokenId}`);
        if (list && headerElement) {
            const isExpanded = list.classList.toggle('expanded');
            headerElement.classList.toggle('expanded', isExpanded);
            // Refresh Lucide icons for the chevron
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    }
    async handleRevokeToken(tokenId) {
        const confirmed = await this.showConfirmModal(
            'Revoke Token',
            'Are you sure you want to revoke this token? Workers using it will no longer be able to connect.',
            'Revoke'
        );

        if (!confirmed) return;

        try {
            await this.apiRequest(`/api/auth/token/${tokenId}`, {
                method: 'DELETE',
            });

            this.showToast('Token revoked successfully');
            this.loadTokens();

        } catch (e) {
            console.error('Failed to revoke token:', e);
            this.showToast(e.message, 'error');
        }
    }

    // =========================================================================
    // Room Secrets (PSK P2P Authentication)
    // =========================================================================

    /**
     * Get the localStorage key for a room's secret
     * @param {string} roomId - The room ID
     * @returns {string} The localStorage key
     */
    getRoomSecretKey(roomId) {
        return `sleap_rtc_room_secret_${roomId}`;
    }

    /**
     * Get stored room secret from localStorage
     * @param {string} roomId - The room ID
     * @returns {string|null} The stored secret or null
     */
    getStoredRoomSecret(roomId) {
        return localStorage.getItem(this.getRoomSecretKey(roomId));
    }

    /**
     * Save room secret to localStorage
     * @param {string} roomId - The room ID
     * @param {string} secret - The secret to store
     */
    saveRoomSecret(roomId, secret) {
        localStorage.setItem(this.getRoomSecretKey(roomId), secret);
    }

    /**
     * Delete room secret from localStorage
     * @param {string} roomId - The room ID
     */
    deleteRoomSecret(roomId) {
        localStorage.removeItem(this.getRoomSecretKey(roomId));
    }

    // =========================================================================
    // =========================================================================
    // Account Keys
    // =========================================================================

    async loadAccountKeys() {
        const container = document.getElementById('account-keys-list');
        container.innerHTML = '<p class="loading">Loading account keys...</p>';

        try {
            const data = await this.apiRequest('/api/auth/account-keys');
            this.accountKeys = data.keys || [];
            this.renderAccountKeys();
            this.updateCounts();
        } catch (e) {
            console.error('Failed to load account keys:', e);
            container.innerHTML = `<p class="loading" style="color: var(--status-error);">Failed to load account keys: ${e.message}</p>`;
        }
    }

    renderAccountKeys() {
        const container = document.getElementById('account-keys-list');

        if (this.accountKeys.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <i data-lucide="shield"></i>
                    </div>
                    <h3>No account keys yet</h3>
                    <p>Account keys let you authenticate workers without logging in.<br>Give a key to any machine that needs to run as a worker.</p>
                    <button class="btn btn-primary" onclick="app.showCreateAccountKeyModal()">
                        <i data-lucide="plus"></i>
                        Create Account Key
                    </button>
                </div>
            `;
            if (typeof lucide !== 'undefined') lucide.createIcons();
            return;
        }

        const activeKeys = this.accountKeys.filter(k => !k.revoked_at);
        const revokedKeys = this.accountKeys.filter(k => !!k.revoked_at);
        const revokedExpanded = localStorage.getItem('sleap_revoked_keys_expanded') === 'true';

        let html = '';

        if (activeKeys.length === 0 && revokedKeys.length > 0) {
            html += `
            <div class="empty-state" style="padding: 40px 20px;">
                <div class="empty-icon">
                    <i data-lucide="shield"></i>
                </div>
                <h3>No active account keys</h3>
                <p>All your account keys have been revoked. Create a new key to authenticate workers.</p>
                <button class="btn btn-primary" onclick="app.showCreateAccountKeyModal()">
                    <i data-lucide="plus"></i>
                    Create Account Key
                </button>
            </div>`;
        } else {
            if (activeKeys.length > 0) {
                html += `<div class="acctkeys-section-header">
                    <h3>Active Keys (${activeKeys.length})</h3>
                </div>`;
                html += activeKeys.map(key => this.renderAccountKeyCard(key, false)).join('');
            }

            html += `
                <div class="create-item-row">
                    <button class="btn btn-primary btn-create-inline" onclick="app.showCreateAccountKeyModal()">
                        <i data-lucide="plus"></i>
                        Create Account Key
                    </button>
                </div>`;
        }

        if (revokedKeys.length > 0) {
            html += `
            <div class="acctkeys-section-header inactive-section ${revokedExpanded ? 'expanded' : ''}" onclick="app.toggleRevokedKeysSection(this)">
                <div class="section-toggle">
                    <i data-lucide="${revokedExpanded ? 'chevron-down' : 'chevron-right'}"></i>
                    <h3>Revoked Keys (${revokedKeys.length})</h3>
                </div>
                <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); app.handleDeleteAllRevokedKeys()">
                    <i data-lucide="trash-2"></i>
                    Delete All
                </button>
            </div>
            <div class="revoked-keys-list" style="display: ${revokedExpanded ? 'block' : 'none'};">
                ${revokedKeys.map(key => this.renderAccountKeyCard(key, true)).join('')}
            </div>`;
        }

        container.innerHTML = html;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    renderAccountKeyCard(key, isRevoked) {
        const storedSecret = this.getStoredAccountKeySecret(key.key_id);

        return `
        <div class="acctkey-card ${isRevoked ? 'inactive' : ''} ${storedSecret ? 'has-key' : ''}">
            <div class="acctkey-header">
                <div class="acctkey-main">
                    <div class="acctkey-icon" ${isRevoked ? 'style="opacity: 0.5;"' : ''}>
                        <i data-lucide="shield"></i>
                    </div>
                    <div class="acctkey-info">
                        <h3>${key.name || 'unnamed'}</h3>
                        <div class="acctkey-meta">
                            <span class="acctkey-meta-item acctkey-key-id">
                                <i data-lucide="fingerprint"></i>
                                ${key.key_id.substring(0, 20)}...
                            </span>
                            <span class="acctkey-meta-item" title="${formatExactDate(key.created_at)}">
                                <i data-lucide="calendar"></i>
                                Created ${formatRelativeTime(key.created_at)}
                            </span>
                            ${isRevoked ? `
                                <span class="acctkey-meta-item error">
                                    <i data-lucide="x-circle"></i>
                                    Revoked ${key.revoked_at ? formatRelativeTime(key.revoked_at) : ''}
                                </span>
                            ` : ''}
                        </div>
                    </div>
                </div>
                <div class="acctkey-actions">
                    ${!isRevoked ? `
                        <button class="btn btn-danger btn-sm" onclick="app.handleRevokeAccountKey('${key.key_id}', '${(key.name || 'unnamed').replace(/'/g, "\\'")}')">
                            <i data-lucide="trash-2"></i>
                            Revoke
                        </button>
                    ` : `
                        <button class="btn btn-danger btn-sm" onclick="app.handleDeleteAccountKey('${key.key_id}', '${(key.name || 'unnamed').replace(/'/g, "\\'")}')">
                            <i data-lucide="trash-2"></i>
                            Delete
                        </button>
                    `}
                </div>
            </div>
            ${storedSecret && !isRevoked ? `
                <div class="api-key-available">
                    <div class="api-key-header">
                        <i data-lucide="alert-circle"></i>
                        <span>Account key available for this session only</span>
                    </div>
                    <div class="api-key-content">
                        <code class="worker-command">export SLEAP_RTC_ACCOUNT_KEY=${storedSecret}</code>
                        <div class="api-key-actions">
                            <button class="btn btn-secondary btn-sm" onclick="app.copyToClipboard('export SLEAP_RTC_ACCOUNT_KEY=${storedSecret}')">
                                <i data-lucide="copy"></i>
                                Copy Command
                            </button>
                            <button class="btn btn-ghost btn-sm" onclick="app.dismissAccountKeySecret('${key.key_id}')">
                                <i data-lucide="check"></i>
                                I've copied it
                            </button>
                        </div>
                    </div>
                </div>
            ` : ''}
        </div>
        `;
    }

    showCreateAccountKeyModal() {
        document.getElementById('account-key-name').value = '';
        this.showModal('create-account-key-modal');
    }

    async handleCreateAccountKey(e) {
        e.preventDefault();
        const name = document.getElementById('account-key-name').value.trim();
        if (!name) return;

        try {
            const data = await this.apiRequest('/api/auth/account-keys', {
                method: 'POST',
                body: JSON.stringify({ name }),
            });

            // Store the full key in sessionStorage (shown only once)
            this.storeAccountKeySecret(data.key_id, data.key_id);

            // Close modal and reload
            document.getElementById('create-account-key-modal').classList.add('hidden');
            this.showToast('Account key created');
            await this.loadAccountKeys();
        } catch (e) {
            console.error('Failed to create account key:', e);
            this.showToast(`Failed to create key: ${e.message}`);
        }
    }

    async handleRevokeAccountKey(keyId, keyName) {
        const confirmed = await this.showConfirmModal(
            'Revoke Account Key',
            `Are you sure you want to revoke "${keyName}"? Any workers using this key will lose access immediately.`,
            'Revoke'
        );
        if (!confirmed) return;

        try {
            await this.apiRequest(`/api/auth/account-keys/${keyId}`, {
                method: 'DELETE',
            });
            this.showToast('Account key revoked');
            await this.loadAccountKeys();
        } catch (e) {
            console.error('Failed to revoke account key:', e);
            this.showToast(`Failed to revoke key: ${e.message}`);
        }
    }

    async handleDeleteAccountKey(keyId, keyName) {
        const confirmed = await this.showConfirmModal(
            'Delete Account Key',
            `Are you sure you want to permanently delete "${keyName}"? This cannot be undone.`,
            'Delete'
        );
        if (!confirmed) return;

        try {
            await this.apiRequest(`/api/auth/account-keys/${keyId}`, {
                method: 'DELETE',
            });
            this.showToast('Account key deleted');
            await this.loadAccountKeys();
        } catch (e) {
            console.error('Failed to delete account key:', e);
            this.showToast(`Failed to delete key: ${e.message}`);
        }
    }

    async handleDeleteAllRevokedKeys() {
        const revokedCount = this.accountKeys.filter(k => !!k.revoked_at).length;
        const confirmed = await this.showConfirmModal(
            'Delete All Revoked Keys',
            `Delete all ${revokedCount} revoked keys? This will permanently remove them.`,
            'Delete All'
        );
        if (!confirmed) return;

        try {
            const revokedKeys = this.accountKeys.filter(k => !!k.revoked_at);
            await Promise.all(
                revokedKeys.map(k =>
                    this.apiRequest(`/api/auth/account-keys/${k.key_id}`, { method: 'DELETE' })
                )
            );
            this.showToast(`Deleted ${revokedKeys.length} revoked keys`);
            await this.loadAccountKeys();
        } catch (e) {
            console.error('Failed to delete revoked keys:', e);
            this.showToast(`Failed to delete keys: ${e.message}`);
        }
    }

    toggleRevokedKeysSection(header) {
        const isExpanded = header.classList.toggle('expanded');
        const list = header.nextElementSibling;
        const icon = header.querySelector('[data-lucide]');

        list.style.display = isExpanded ? 'block' : 'none';
        localStorage.setItem('sleap_revoked_keys_expanded', isExpanded);

        if (icon) {
            icon.setAttribute('data-lucide', isExpanded ? 'chevron-down' : 'chevron-right');
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    }

    // Account Key Secret Session Storage
    storeAccountKeySecret(keyId, fullKey) {
        const pending = JSON.parse(sessionStorage.getItem('pendingAccountKeys') || '{}');
        pending[keyId] = fullKey;
        sessionStorage.setItem('pendingAccountKeys', JSON.stringify(pending));
    }

    getStoredAccountKeySecret(keyId) {
        const pending = JSON.parse(sessionStorage.getItem('pendingAccountKeys') || '{}');
        return pending[keyId] || null;
    }

    dismissAccountKeySecret(keyId) {
        const pending = JSON.parse(sessionStorage.getItem('pendingAccountKeys') || '{}');
        delete pending[keyId];
        sessionStorage.setItem('pendingAccountKeys', JSON.stringify(pending));
        this.renderAccountKeys();
    }

    // =========================================================================
    // API Key Session Storage (for newly created tokens)
    // =========================================================================

    /**
     * Store API key in sessionStorage (cleared when tab closes)
     * @param {string} tokenId - The token ID
     * @param {object} keyData - { api_key, room_secret, room_id, worker_name, created_at }
     */
    storeApiKey(tokenId, keyData) {
        const pendingKeys = JSON.parse(sessionStorage.getItem('pendingApiKeys') || '{}');
        pendingKeys[tokenId] = keyData;
        sessionStorage.setItem('pendingApiKeys', JSON.stringify(pendingKeys));
    }

    /**
     * Get stored API key from sessionStorage
     * @param {string} tokenId - The token ID
     * @returns {object|null} The key data or null if not found
     */
    getStoredApiKey(tokenId) {
        const pendingKeys = JSON.parse(sessionStorage.getItem('pendingApiKeys') || '{}');
        return pendingKeys[tokenId] || null;
    }

    /**
     * Remove API key from sessionStorage (user confirmed they copied it)
     * @param {string} tokenId - The token ID
     */
    dismissApiKey(tokenId) {
        const pendingKeys = JSON.parse(sessionStorage.getItem('pendingApiKeys') || '{}');
        delete pendingKeys[tokenId];
        sessionStorage.setItem('pendingApiKeys', JSON.stringify(pendingKeys));
        // Re-render tokens to update UI
        this.renderTokens();
        // Re-initialize worker badges
        this.updateWorkerBadges();
    }

    /**
     * Build the worker command string for a token
     * @param {string} apiKey - The API key
     * @param {string|null} roomSecret - Optional room secret
     * @returns {string} The worker command
     */
    buildWorkerCommand(apiKey, roomSecret) {
        let cmd = `sleap-rtc worker --api-key ${apiKey}`;
        if (roomSecret) {
            cmd += ` --room-secret ${roomSecret}`;
        }
        return cmd;
    }

    /**
     * Generate a cryptographically secure room secret using Web Crypto API
     * @returns {Promise<string>} A 64-character hex string (32 bytes)
     */
    async generateRoomSecret() {
        const bytes = new Uint8Array(32);
        crypto.getRandomValues(bytes);
        return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
    }

    /**
     * Handle room secret button click - show modal with generate/view options
     * @param {string} roomId - The room ID
     */
    async handleRoomSecret(roomId) {
        const existingSecret = this.getStoredRoomSecret(roomId);
        const content = document.getElementById('room-secret-content');

        if (existingSecret) {
            // Show existing secret with options to copy or regenerate
            content.innerHTML = `
                <div class="success-details">
                    <p>This room has a P2P authentication secret configured.</p>
                    <p class="security-note" style="margin-bottom: 16px;"><i data-lucide="shield-check"></i> This secret is stored only in your browser. The server never sees it.</p>
                    <div class="detail-row">
                        <label>Secret:</label>
                        <code id="room-secret-value" class="api-key">${existingSecret}</code>
                        <button class="btn btn-secondary btn-sm" onclick="app.copyToClipboard('${existingSecret}')">
                            <i data-lucide="copy"></i>
                        </button>
                    </div>
                    <div class="detail-row">
                        <label>Room ID:</label>
                        <code id="room-id-value">${roomId}</code>
                        <button class="btn btn-secondary btn-sm" onclick="app.copyToClipboard('${roomId}')">
                            <i data-lucide="copy"></i>
                        </button>
                    </div>
                </div>
                <div class="help-text">
                    <p><strong>How to distribute this secret:</strong></p>
                    <p>Both workers and clients need this secret to communicate. Share it securely with your team.</p>
                    <ul>
                        <li><strong>CLI flag:</strong> <code>--room-secret ${existingSecret}</code></li>
                        <li><strong>Environment variable:</strong> <code>SLEAP_RTC_ROOM_SECRET_${roomId.replace(/-/g, '_').toUpperCase()}=${existingSecret}</code></li>
                        <li><strong>Filesystem:</strong> Save to <code>~/.sleap-rtc/secrets/${roomId}</code></li>
                    </ul>
                </div>
                <div class="form-actions" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border-color);">
                    <button type="button" class="btn btn-danger btn-sm" onclick="app.regenerateRoomSecret('${roomId}')">
                        <i data-lucide="refresh-cw"></i>
                        Regenerate Secret
                    </button>
                </div>
            `;
        } else {
            // No secret yet - offer to generate one
            content.innerHTML = `
                <div class="info-banner">
                    <p>P2P authentication adds an extra layer of security for direct worker-client communication.</p>
                    <p>When enabled, both the worker and client must have the same secret to authorize connections.</p>
                    <p><strong><i data-lucide="shield-check"></i> Privacy:</strong> This secret is generated in your browser and stored locally. The server never sees it.</p>
                </div>
                <div class="success-details" style="margin-top: 16px;">
                    <div class="detail-row">
                        <label>Room ID:</label>
                        <code id="room-id-value">${roomId}</code>
                        <button class="btn btn-secondary btn-sm" onclick="app.copyToClipboard('${roomId}')">
                            <i data-lucide="copy"></i>
                        </button>
                    </div>
                </div>
                <div class="form-actions" style="margin-top: 1rem;">
                    <button type="button" class="btn btn-primary" onclick="app.generateAndSaveRoomSecret('${roomId}')">
                        <i data-lucide="key"></i>
                        Generate Secret
                    </button>
                </div>
            `;
        }

        this.showModal('room-secret-modal');

        // Initialize Lucide icons in modal
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    /**
     * Generate a new secret and save it
     * @param {string} roomId - The room ID
     */
    async generateAndSaveRoomSecret(roomId) {
        try {
            const secret = await this.generateRoomSecret();
            this.saveRoomSecret(roomId, secret);
            this.showToast('Room secret generated and saved');

            // Refresh the modal content to show the new secret
            await this.handleRoomSecret(roomId);
        } catch (e) {
            console.error('Failed to generate room secret:', e);
            this.showToast('Failed to generate secret', 'error');
        }
    }

    /**
     * Regenerate room secret (with confirmation)
     * @param {string} roomId - The room ID
     */
    async regenerateRoomSecret(roomId) {
        if (!confirm('Are you sure you want to regenerate the room secret?\n\nAll workers and clients using the old secret will need to be updated.')) {
            return;
        }

        await this.generateAndSaveRoomSecret(roomId);
    }

    // ── Job submission ────────────────────────────────────────────────────────

    openSubmitJobModal(roomId) {
        // Guard: warn and bail if no workers are connected
        const workerCount = this.roomWorkers[roomId]?.workers?.length ?? 0;
        if (workerCount === 0) {
            this.showToast(
                'No workers connected to this room. Start a worker with sleap-rtc worker before submitting a job.',
                'error'
            );
            return;
        }

        this._sjRoomId = roomId;
        this._sjWorkerId = null;
        this._sjConfigContent = null;
        this._sjLabelsPath = null;

        // Reset all views to initial state
        document.getElementById('sj-hyperparams').classList.add('hidden');
        document.getElementById('sj-config-error').classList.add('hidden');
        document.getElementById('sj-selected-path').classList.add('hidden');
        document.getElementById('sj-browser-error').classList.add('hidden');
        document.getElementById('sj-wandb-link').classList.add('hidden');
        document.getElementById('sj-next-1').disabled = true;
        document.getElementById('sj-next-2').disabled = true;
        document.getElementById('sj-submit-btn').disabled = true;

        // Find room name for subtitle
        const room = this.rooms?.find(r => r.room_id === roomId);
        document.getElementById('sj-subtitle').textContent = room?.name || roomId;

        this._sjRenderWorkerList();
        this._sjInitDropzone();
        this.sjGoToStep(1);
        this.showModal('submit-job-modal');
    }

    _sjRenderWorkerList() {
        const container = document.getElementById('sj-worker-list');
        if (!container) return;

        // DEBUG: log activeJobs state so we can verify worker status derivation
        console.log('[DEBUG-workerStatus] _sjRenderWorkerList roomId=%s activeJobs:', this._sjRoomId,
            Array.from(this.activeJobs.entries()).map(([id, j]) =>
                `${id.slice(0,8)} worker=${j.workerId} room=${j.roomId} status=${j.status}`));

        const workers = this.roomWorkers[this._sjRoomId]?.workers ?? [];
        if (workers.length === 0) {
            container.innerHTML = '<p class="text-muted">No workers connected to this room.</p>';
            return;
        }

        container.innerHTML = workers.map(worker => {
            const props = worker.properties ?? {};
            const serverStatus = props.status ?? 'available';
            const gpuModel = props.gpu_model || 'Unknown GPU';
            const gpuMem = props.gpu_memory_mb ? `${Math.round(props.gpu_memory_mb / 1024)} GB` : '';
            const cuda = props.cuda_version ? `CUDA ${props.cuda_version}` : '';
            const sleapNnVersion = props.sleap_nn_version ? `sleap-nn ${props.sleap_nn_version}` : '';
            const specs = [gpuModel, gpuMem, cuda, sleapNnVersion].filter(Boolean).join(' · ');

            // Check local activeJobs first — server may report available even while training
            const activeJob = Array.from(this.activeJobs.values()).find(
                j => j.workerId === worker.peer_id && j.roomId === this._sjRoomId &&
                     j.status !== 'complete' && j.status !== 'failed' && j.status !== 'cancelled'
            );
            // status is one of: available, busy, reserved, maintenance
            const status = activeJob ? 'busy' : serverStatus;
            console.log(`[DEBUG-workerStatus] SJ worker=${worker.peer_id} server=${serverStatus} activeJob=${activeJob?.jobId?.slice(0,8) ?? 'none'} → effective=${status}`);
            const isAvailable = status === 'available';
            const disabledClass = isAvailable ? '' : ' disabled';
            const clickHandler = isAvailable
                ? `onclick="app.sjSelectWorker('${worker.peer_id}')"`
                : '';
            const busyLabel = activeJob
                ? `<span class="sj-busy-label">Training ${activeJob.modelType}${activeJob.lastEpoch > 0 ? ' (Epoch ' + activeJob.lastEpoch + ')' : ''}</span>`
                : '';

            const selectedClass = worker.peer_id === this._sjWorkerId ? ' selected' : '';
            return `<div class="sj-worker-row${disabledClass}${selectedClass}" data-peer-id="${worker.peer_id}" ${clickHandler}>
                <div class="sj-worker-info">
                    <span class="sj-worker-name">${worker.worker_name ?? worker.peer_id}</span>
                    <span class="sj-worker-specs">${specs}</span>
                </div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px;">
                    <span class="sj-status-dot ${status}" title="${status}"></span>
                    ${busyLabel}
                </div>
            </div>`;
        }).join('');
    }

    sjSelectWorker(peerId) {
        this._sjWorkerId = peerId;

        // Update selected state on all rows
        document.querySelectorAll('.sj-worker-row').forEach(row => {
            row.classList.toggle('selected', row.dataset.peerId === peerId);
        });

        document.getElementById('sj-next-1').disabled = false;
    }

    closeSubmitJobModal() {
        this.hideModal('submit-job-modal');

        // If a job is actively running, disconnect SSE but keep tracking
        const jobId = this._currentJobId;
        const job = jobId ? this.activeJobs.get(jobId) : null;

        if (job && job.status !== 'complete' && job.status !== 'failed' && job.status !== 'cancelled') {
            // Close modal SSE, re-open as background SSE so stale check stays guarded
            this._sjJobSSE?.close();
            this._sjJobSSE = null;
            const bgSse = this.sseConnect(jobId);
            bgSse.on('status', (data) => this._backgroundJobStatus(jobId, data))
                 .on('job_status', (data) => this._backgroundJobStatus(jobId, data))
                 .on('job_progress', (data) => this._backgroundJobProgress(jobId, data))
                 .on('epoch', (data) => this._backgroundJobEpoch(jobId, data));
            job.sseConnection = bgSse;
            // Update badge on room card
            this._updateRoomBadges(job.roomId);
        } else {
            this._sjCleanupSSE();
            // If terminal, keep badge briefly for user to review
            if (job) this._updateRoomBadges(job.roomId);
        }

        this._sjWorkerSSE?.close();
        this._sjWorkerSSE = null;
    }

    reopenJobModal(jobId) {
        const job = this.activeJobs.get(jobId);
        if (!job) return;

        this._sjRoomId = job.roomId;
        this._sjWorkerId = job.workerId;
        this._sjModelType = job.modelType;
        this._sjMaxEpochs = job.maxEpochs;
        this._currentJobId = jobId;

        // Set subtitle
        const room = this.rooms?.find(r => r.room_id === job.roomId);
        document.getElementById('sj-subtitle').textContent = room?.name || job.roomId;

        // Go to status view
        this.sjGoToStep('status');
        this._sjResetProgressPanel();

        // Restore last-known state from activeJobs
        this._restoreJobState(job);

        // Reconnect SSE for live updates
        if (job.status !== 'complete' && job.status !== 'failed' && job.status !== 'cancelled') {
            // Close background SSE first to prevent duplicate event handlers
            if (job.sseConnection) {
                job.sseConnection.close();
                job.sseConnection = null;
            }
            this._sjJobSSE = this.sseConnect(jobId);
            this._sjJobSSE
                .on('status', (data) => this._sjHandleJobStatus(data))
                .on('job_status', (data) => this._sjHandleJobStatus(data))
                .on('job_progress', (data) => this._sjHandleJobProgress(data))
                .on('epoch', (data) => this._sjHandleJobEpoch(data));
            job.sseConnection = this._sjJobSSE;

            // Append reconnect marker to log
            this._sjAppendLog('— Reconnected —', 'log-reconnect');
        }

        this.showModal('submit-job-modal');
    }

    _restoreJobState(job) {
        // Status label
        const label = document.getElementById('sj-status-label');
        if (label) {
            if (job.status === 'complete') {
                label.textContent = 'Complete';
                this._sjUpdateStatusIcon('complete');
                this._sjShowCloseButton();
            } else if (job.status === 'failed') {
                label.textContent = `Failed: ${job.failMessage || 'Job failed'}`;
                this._sjUpdateStatusIcon('failed');
                this._sjShowCloseButton();
            } else if (job.lastEpoch > 0) {
                label.textContent = `Training ${job.modelType} — Epoch ${job.lastEpoch}${job.lastLoss != null ? `, loss ${job.lastLoss.toFixed(4)}` : ''}`;
            } else {
                label.textContent = 'Running…';
            }
        }

        // Epoch counter
        if (job.lastEpoch > 0) {
            const cur = document.getElementById('sj-epoch-current');
            if (cur) cur.textContent = job.lastEpoch;
            const total = document.getElementById('sj-epoch-total');
            if (total) total.textContent = job.maxEpochs ? ` / ${job.maxEpochs}` : '';
            document.getElementById('sj-epoch-section')?.classList.remove('hidden');
        }

        // WandB link
        if (job.wandbUrl) {
            const link = document.getElementById('sj-wandb-link');
            if (link) {
                link.href = job.wandbUrl;
                link.classList.remove('hidden');
            }
        }

        // Job queue
        const queue = document.getElementById('sj-job-queue');
        if (queue) {
            queue.textContent = 'Job 1 / 1';
            queue.classList.remove('hidden');
        }

        // Replay stored log lines
        if (job.logs && job.logs.length > 0) {
            for (const entry of job.logs) {
                this._sjAppendLog(entry.text, entry.cls || '');
            }
        }
    }

    /**
     * Close all active SSE connections for the submit job modal.
     */
    _sjCleanupSSE() {
        this._sjWorkerSSE?.close();
        this._sjJobSSE?.close();
        this._sjWorkerSSE = null;
        this._sjJobSSE = null;
    }

    // ── Active job tracking ──────────────────────────────────────────────────

    _persistActiveJobs() {
        const jobs = Array.from(this.activeJobs.values()).map(j => ({
            jobId: j.jobId, roomId: j.roomId, workerId: j.workerId,
            workerName: j.workerName, status: j.status, modelType: j.modelType,
            lastEpoch: j.lastEpoch, maxEpochs: j.maxEpochs, startedAt: j.startedAt,
            lastLoss: j.lastLoss, wandbUrl: j.wandbUrl, failMessage: j.failMessage,
            logs: (j.logs || []).slice(-500),
        }));
        sessionStorage.setItem('sleap-rtc-active-jobs', JSON.stringify(jobs));
    }

    _loadActiveJobs() {
        try {
            const raw = sessionStorage.getItem('sleap-rtc-active-jobs');
            if (!raw) return;
            const jobs = JSON.parse(raw);
            for (const j of jobs) {
                this.activeJobs.set(j.jobId, { ...j, logs: j.logs || [], sseConnection: null });
            }
            const now = Date.now();
            for (const [jobId, job] of this.activeJobs) {
                // Remove jobs older than 24 hours
                if (job.startedAt && now - job.startedAt > 24 * 60 * 60 * 1000) {
                    this.activeJobs.delete(jobId);
                }
            }
        } catch (e) {
            console.warn('[ActiveJobs] Failed to load from sessionStorage:', e);
        }
    }

    _removeActiveJob(jobId) {
        const job = this.activeJobs.get(jobId);
        if (job?.sseConnection) job.sseConnection.close();
        this.activeJobs.delete(jobId);
        this._persistActiveJobs();
    }

    _updateRoomBadges(roomId) {
        const badgeContainer = document.getElementById(`room-job-badges-${roomId}`);
        if (!badgeContainer) return;

        const jobs = Array.from(this.activeJobs.values()).filter(j => j.roomId === roomId);

        if (jobs.length === 0) {
            badgeContainer.innerHTML = '';
            return;
        }

        // Only show badges for terminal jobs (complete/failed)
        const terminalJobs = jobs.filter(j => j.status === 'complete' || j.status === 'failed' || j.status === 'cancelled');
        if (terminalJobs.length === 0) {
            badgeContainer.innerHTML = '';
            return;
        }

        badgeContainer.innerHTML = terminalJobs.map(job => {
            const name = job.workerName || job.workerId;
            const cls = job.status === 'complete' ? 'btn-training-complete' : 'btn-training-failed';
            const label = job.status === 'complete'
                ? `<strong>${name}</strong> Job Completed!`
                : `<strong>${name}</strong> Job Failed`;
            return `<button class="btn ${cls} btn-sm" onclick="event.stopPropagation();app.openJobSummary('${job.jobId}')">
                ${label}
                <span class="btn-badge-dismiss-inline" title="Dismiss" onclick="event.stopPropagation();app.dismissJobBadge('${job.jobId}')">&times;</span>
            </button>`;
        }).join('');

        if (typeof lucide !== 'undefined') {
            lucide.createIcons({ nodes: Array.from(badgeContainer.querySelectorAll('[data-lucide]')) });
        }
    }

    dismissJobBadge(jobId) {
        const job = this.activeJobs.get(jobId);
        const roomId = job?.roomId;
        this._removeActiveJob(jobId);
        if (roomId) this._updateRoomBadges(roomId);
    }

    openJobSummary(jobId) {
        const job = this.activeJobs.get(jobId);
        if (!job) return;

        const room = this.rooms?.find(r => r.room_id === job.roomId);
        document.getElementById('jsum-subtitle').textContent = room?.name || job.roomId;

        // Summary line
        const isComplete = job.status === 'complete';
        const statusLabel = isComplete ? 'Complete' : (job.failMessage || 'Failed');
        const statusCls = isComplete ? 'complete' : 'failed';
        const parts = [
            `<span class="jsum-item jsum-status ${statusCls}">${isComplete ? '&#10003;' : '&#10007;'} ${statusLabel}</span>`,
            `<span class="jsum-item">Worker: <strong>${job.workerName || job.workerId}</strong></span>`,
            `<span class="jsum-item">Model: ${job.modelType}</span>`,
            `<span class="jsum-item">Epochs: ${job.lastEpoch}${job.maxEpochs ? ' / ' + job.maxEpochs : ''}</span>`,
        ];
        if (job.lastLoss != null) parts.push(`<span class="jsum-item">Final Loss: ${job.lastLoss.toFixed(4)}</span>`);
        if (job.wandbUrl) parts.push(`<span class="jsum-item"><a href="${job.wandbUrl}" target="_blank" rel="noopener">Track in WandB &rarr;</a></span>`);
        document.getElementById('jsum-summary').innerHTML = parts.join('');

        // Logs
        const logContainer = document.getElementById('jsum-logs');
        logContainer.innerHTML = '';
        if (job.logs && job.logs.length > 0) {
            for (const entry of job.logs) {
                const line = document.createElement('div');
                line.className = `log-line${entry.cls ? ' ' + entry.cls : ''}`;
                line.textContent = entry.text;
                logContainer.appendChild(line);
            }
        } else {
            logContainer.innerHTML = '<div class="log-line" style="color:var(--text-muted)">No logs available.</div>';
        }

        this.showModal('job-summary-modal');
    }

    // ── Worker status polling ────────────────────────────────────────────────

    startWorkerPolling() {
        this.stopWorkerPolling();
        if (this.rooms.length === 0) return;

        this._workerPollInterval = setInterval(() => {
            for (const room of this.rooms) {
                this.loadRoomWorkers(room.room_id).then(() => {
                    this._updateWorkerBadge(room.room_id);
                    // If Workers modal is open for this room, re-render
                    if (this.currentWorkersRoomId === room.room_id &&
                        !document.getElementById('workers-modal')?.classList.contains('hidden')) {
                        this.renderWorkersModalList();
                    }
                    // If Submit Job modal is open for this room, re-render worker list
                    if (this._sjRoomId === room.room_id &&
                        !document.getElementById('submit-job-modal')?.classList.contains('hidden')) {
                        this._sjRenderWorkerList();
                    }
                    // Detect stale jobs: worker went available but job still "running"
                    this._checkStaleJobs(room.room_id);
                }).catch(() => {}); // Silently ignore poll failures
            }
        }, 15000);
    }

    stopWorkerPolling() {
        if (this._workerPollInterval) {
            clearInterval(this._workerPollInterval);
            this._workerPollInterval = null;
        }
    }

    _updateWorkerBadge(roomId) {
        const data = this.roomWorkers[roomId];
        if (!data) return;
        const badge = document.getElementById(`room-worker-badge-${roomId}`);
        if (!badge) return;
        const count = data.workers?.length ?? 0;
        const text = count === 0 ? '0 connected' : `${count} connected`;
        badge.innerHTML = `<i data-lucide="${count === 0 ? 'zap-off' : 'zap'}"></i> ${text}`;
        badge.className = `worker-count-badge ${count === 0 ? 'offline' : ''}`;
        if (typeof lucide !== 'undefined') {
            lucide.createIcons({ nodes: Array.from(badge.querySelectorAll('[data-lucide]')) });
        }
    }

    _checkStaleJobs(roomId) {
        const workers = this.roomWorkers[roomId]?.workers ?? [];
        for (const [jobId, job] of this.activeJobs) {
            if (job.roomId !== roomId) continue;
            if (job.status === 'complete' || job.status === 'failed' || job.status === 'cancelled') continue;
            // If SSE is active, trust it to report completion — don't override with stale heuristic
            if (job.sseConnection) continue;

            const worker = workers.find(w => w.peer_id === job.workerId);
            const workerStatus = worker?.properties?.status || 'unknown';

            // If worker is available but job is still running, the job likely ended while disconnected
            if (workerStatus === 'available' && job.lastEpoch > 0) {
                job.status = 'complete';
                this._persistActiveJobs();
                this._updateRoomBadges(roomId);
            }
        }
    }

    _reconnectActiveJobs() {
        for (const [jobId, job] of this.activeJobs) {
            if (job.status === 'complete' || job.status === 'failed' || job.status === 'cancelled') continue;

            // Connect SSE in background (no modal open)
            const sse = this.sseConnect(jobId);
            sse.on('status', (data) => this._backgroundJobStatus(jobId, data))
               .on('job_status', (data) => this._backgroundJobStatus(jobId, data))
               .on('job_progress', (data) => this._backgroundJobProgress(jobId, data))
               .on('epoch', (data) => this._backgroundJobEpoch(jobId, data));
            job.sseConnection = sse;
        }
    }

    _backgroundJobStatus(jobId, data) {
        const job = this.activeJobs.get(jobId);
        if (!job) return;
        job.status = data.status;
        this._persistActiveJobs();
        this._updateRoomBadges(job.roomId);
    }

    _backgroundJobEpoch(jobId, data) {
        const job = this.activeJobs.get(jobId);
        if (!job) return;
        if (data.epoch != null) job.lastEpoch = data.epoch;
        if (data.loss != null) job.lastLoss = Number(data.loss);
        if (data.wandb_url) job.wandbUrl = data.wandb_url;
        this._persistActiveJobs();
        this._updateRoomBadges(job.roomId);
    }

    _backgroundJobProgress(jobId, data) {
        const job = this.activeJobs.get(jobId);
        if (!job) return;
        if (data.event === 'epoch_end' && data.epoch != null) {
            job.lastEpoch = data.epoch;
            const logs = data.logs || {};
            if (logs['train/loss'] != null) job.lastLoss = Number(logs['train/loss']);
        }
        if (data.wandb_url && !job.wandbUrl) job.wandbUrl = data.wandb_url;
        this._persistActiveJobs();
        this._updateRoomBadges(job.roomId);
    }

    // ── Task 5: YAML config upload ────────────────────────────────────────────

    parseTrainingConfig(yamlText) {
        const doc = jsyaml.load(yamlText);
        // sleap-nn uses trainer_config as the top-level key; fall back to trainer or root
        const trainer = doc?.trainer_config ?? doc?.trainer ?? doc ?? {};
        const wandb = trainer.wandb ?? doc?.wandb ?? {};
        // batch_size lives under train_data_loader in sleap-nn configs
        const batch_size = trainer?.train_data_loader?.batch_size
            ?? trainer.batch_size ?? doc?.batch_size ?? 'unknown';
        // learning rate lives under optimizer.lr in sleap-nn configs
        const learning_rate = trainer?.optimizer?.lr
            ?? trainer.learning_rate ?? doc?.learning_rate ?? 'unknown';
        // Detect model type from head_configs (the non-null key)
        const headConfigs = doc?.model_config?.head_configs ?? trainer?.head_configs ?? {};
        const model_type = Object.entries(headConfigs)
            .find(([, v]) => v != null)?.[0] ?? 'unknown';
        return {
            batch_size,
            learning_rate,
            max_epochs: trainer.max_epochs ?? doc?.max_epochs ?? 'unknown',
            model_type,
            run_name: trainer.run_name ?? wandb.name ?? wandb.run_name ?? doc?.run_name ?? 'unknown',
            wandb_project: wandb.project ?? 'unknown',
            wandb_entity: wandb.entity ?? 'unknown',
        };
    }

    _sjRenderHyperparams(fields) {
        const container = document.getElementById('sj-hyperparams');
        if (!container) return;
        const rows = [
            ['Batch size', fields.batch_size],
            ['Learning rate', fields.learning_rate],
            ['Max epochs', fields.max_epochs],
            ['Run name', fields.run_name],
            ['WandB project', fields.wandb_project],
            ['WandB entity', fields.wandb_entity],
        ];
        container.innerHTML = rows.map(([label, val]) =>
            `<div class="sj-hyperparam-item"><span class="sj-hyperparam-label">${label}</span><span class="sj-hyperparam-value">${val}</span></div>`
        ).join('');
        container.classList.remove('hidden');
    }

    _sjHandleConfigFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const text = e.target.result;
            const errorEl = document.getElementById('sj-config-error');
            const next2 = document.getElementById('sj-next-2');
            const dropzone = document.getElementById('sj-config-dropzone');
            try {
                const fields = this.parseTrainingConfig(text);
                this._sjConfigContent = text;
                this._sjMaxEpochs = fields.max_epochs !== 'unknown' ? Number(fields.max_epochs) : null;
                this._sjModelType = fields.model_type !== 'unknown' ? fields.model_type : null;
                this._sjRenderHyperparams(fields);
                errorEl.classList.add('hidden');
                next2.disabled = false;
                // Show filename and allow re-upload
                if (dropzone) {
                    dropzone.innerHTML = `
                        <i data-lucide="file-check"></i>
                        <p><strong>${file.name}</strong></p>
                        <p style="font-size:0.8em;opacity:0.7">Drop a different file or <label for="sj-config-input" class="sj-browse-link">browse</label> to replace</p>
                        <input type="file" id="sj-config-input" accept=".yaml,.yml" class="hidden">
                    `;
                    lucide.createIcons();
                    // Re-wire the new file input
                    const newInput = document.getElementById('sj-config-input');
                    if (newInput) {
                        newInput.addEventListener('change', () => {
                            const f = newInput.files[0];
                            if (f) this._sjHandleConfigFile(f);
                        });
                    }
                }
            } catch (err) {
                this._sjConfigContent = null;
                document.getElementById('sj-hyperparams').classList.add('hidden');
                errorEl.textContent = `Invalid YAML: ${err.message}`;
                errorEl.classList.remove('hidden');
                next2.disabled = true;
            }
        };
        reader.readAsText(file);
    }

    _sjInitDropzone() {
        const dropzone = document.getElementById('sj-config-dropzone');
        const fileInput = document.getElementById('sj-config-input');
        if (!dropzone || !fileInput) return;

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('drag-over');
        });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('drag-over');
            const file = e.dataTransfer.files[0];
            if (file) this._sjHandleConfigFile(file);
        });
        fileInput.addEventListener('change', () => {
            const file = fileInput.files[0];
            if (file) this._sjHandleConfigFile(file);
        });
    }

    // ── File browser + validation + job submission (via relay) ──────────────

    async sjEnterStep3() {
        this.sjGoToStep(3);

        // Reset state
        this._sjLabelsPath = null;
        this._sjPathMappings = {};
        this._sjMissingVideos = [];
        this._sjBrowseMode = 'slp'; // 'slp' or 'video'
        this._sjResolvingVideoIndex = null;

        // Show spinner, hide columns and panels
        document.getElementById('sj-browser-spinner')?.classList.remove('hidden');
        document.getElementById('sj-file-columns')?.classList.add('hidden');
        document.getElementById('sj-browser-error')?.classList.add('hidden');
        document.getElementById('sj-validation-status')?.classList.add('hidden');
        document.getElementById('sj-missing-videos')?.classList.add('hidden');
        document.getElementById('sj-selected-path')?.classList.add('hidden');
        document.getElementById('sj-submit-btn').disabled = true;

        try {
            // Open SSE connection to worker channel
            this._sjWorkerSSE = this.sseConnect(`worker:${this._sjWorkerId}`);

            // Route SSE events for file browsing
            this._sjWorkerSSE
                .on('fs_list_res', (data) => this._sjHandleFsListRes(data))
                .on('worker_path_ok', (data) => this._sjHandlePathOk(data))
                .on('worker_path_error', (data) => this._sjHandlePathError(data))
                .on('fs_check_videos_response', (data) => this._sjHandleVideoCheck(data));

            // Get mount points from cached worker metadata
            const workers = this.roomWorkers[this._sjRoomId]?.workers ?? [];
            const worker = workers.find(w => w.peer_id === this._sjWorkerId);
            const mounts = worker?.properties?.mounts ?? [];

            document.getElementById('sj-browser-spinner')?.classList.add('hidden');
            document.getElementById('sj-file-columns')?.classList.remove('hidden');

            if (mounts.length > 0) {
                // Render mount points as initial column
                const entries = mounts.map(m => ({
                    name: m.label || m.path,
                    path: m.path,
                    is_dir: true,
                }));
                this._sjRenderColumn(entries, 0);
            } else {
                // No mounts in metadata — request root listing
                const reqId = crypto.randomUUID();
                this._sjPendingRequests = this._sjPendingRequests || {};
                this._sjPendingRequests[reqId] = { colIndex: 0 };
                await this.apiFsList(this._sjRoomId, this._sjWorkerId, '/', reqId);
            }
        } catch (err) {
            document.getElementById('sj-browser-spinner')?.classList.add('hidden');
            const errEl = document.getElementById('sj-browser-error');
            if (errEl) {
                errEl.textContent = `Failed to connect: ${err.message}`;
                errEl.classList.remove('hidden');
            }
        }
    }

    // ── SSE event handlers ───────────────────────────────────────────────────

    _sjHandleFsListRes(data) {
        const reqId = data.req_id;
        const pending = this._sjPendingRequests?.[reqId];
        if (!pending) {
            // No matching request — stale or duplicate response, ignore
            console.warn('[SSE] Ignoring fs_list_res with unknown req_id:', reqId);
            return;
        }
        const colIndex = pending.colIndex;
        delete this._sjPendingRequests[reqId];

        // Normalize entries
        const parentPath = data.path?.replace(/\/$/, '') ?? '';
        const entries = (data.entries || []).map(e => ({
            name: e.name,
            path: e.path ?? `${parentPath}/${e.name}`,
            is_dir: e.is_dir ?? (e.type === 'directory'),
        }));

        this._sjRenderColumn(entries, colIndex);
    }

    _sjHandlePathOk(data) {
        const statusEl = document.getElementById('sj-validation-status');
        if (statusEl) {
            statusEl.innerHTML = '<i data-lucide="loader-2" class="spin"></i> Checking videos…';
            statusEl.className = 'sj-validation-status validating';
            statusEl.classList.remove('hidden');
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    }

    _sjHandlePathError(data) {
        const statusEl = document.getElementById('sj-validation-status');
        const msg = data.error || data.message || 'Path rejected by worker';
        if (statusEl) {
            statusEl.innerHTML = `<i data-lucide="x-circle"></i> ${this._escapeHtml(msg)}`;
            statusEl.className = 'sj-validation-status error';
            statusEl.classList.remove('hidden');
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
        // Re-enable file browser for user to pick a different file
        document.getElementById('sj-submit-btn').disabled = true;
    }

    _sjHandleVideoCheck(data) {
        const statusEl = document.getElementById('sj-validation-status');
        const missing = data.missing || [];
        const total = data.total_videos || 0;
        const accessible = data.accessible || 0;

        if (missing.length === 0) {
            // All videos found — ready to submit
            if (statusEl) {
                statusEl.innerHTML = `<i data-lucide="check-circle"></i> All ${total} videos found`;
                statusEl.className = 'sj-validation-status success';
                statusEl.classList.remove('hidden');
                if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: Array.from(statusEl.querySelectorAll('[data-lucide]')) });
            }
            document.getElementById('sj-submit-btn').disabled = false;
        } else {
            // Missing videos — show resolution UI
            this._sjMissingVideos = missing;
            if (statusEl) {
                statusEl.innerHTML = `<i data-lucide="alert-triangle"></i> ${missing.length} of ${total} videos not found`;
                statusEl.className = 'sj-validation-status warning';
                statusEl.classList.remove('hidden');
                if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: Array.from(statusEl.querySelectorAll('[data-lucide]')) });
            }
            this._sjRenderMissingVideos();
        }
    }

    // ── Path validation ──────────────────────────────────────────────────────

    async _sjValidatePath(path) {
        const statusEl = document.getElementById('sj-validation-status');
        if (statusEl) {
            statusEl.innerHTML = '<i data-lucide="loader-2" class="spin"></i> Validating path…';
            statusEl.className = 'sj-validation-status validating';
            statusEl.classList.remove('hidden');
            if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: Array.from(statusEl.querySelectorAll('[data-lucide]')) });
        }
        document.getElementById('sj-submit-btn').disabled = true;

        try {
            await this.apiWorkerMessage(this._sjRoomId, this._sjWorkerId, {
                type: 'use_worker_path',
                path,
            });
        } catch (err) {
            if (statusEl) {
                statusEl.innerHTML = `<i data-lucide="x-circle"></i> ${this._escapeHtml(err.message)}`;
                statusEl.className = 'sj-validation-status error';
                statusEl.classList.remove('hidden');
                if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: Array.from(statusEl.querySelectorAll('[data-lucide]')) });
            }
        }
    }

    // ── Missing videos resolution ────────────────────────────────────────────

    _sjRenderMissingVideos() {
        const container = document.getElementById('sj-missing-videos');
        if (!container) return;

        const resolved = Object.keys(this._sjPathMappings).length;
        const total = this._sjMissingVideos.length;

        let html = `<div class="sj-missing-header">
            <strong>Missing Videos (${total - resolved} unresolved)</strong>
            <span class="sj-resolve-count">Resolved: ${resolved}/${total}</span>
        </div>`;

        html += this._sjMissingVideos.map((video, i) => {
            const originalPath = video.original_path || video.filename;
            const resolvedPath = this._sjPathMappings[originalPath];
            const isResolved = !!resolvedPath;

            return `<div class="sj-video-item ${isResolved ? 'resolved' : ''}">
                <div class="sj-video-info">
                    <span class="sj-video-icon">${isResolved ? '<i data-lucide="check-circle"></i>' : '<i data-lucide="circle"></i>'}</span>
                    <div>
                        <div class="sj-video-filename">${this._escapeHtml(video.filename)}</div>
                        <div class="sj-video-original">${this._escapeHtml(originalPath)}</div>
                        ${isResolved ? `<div class="sj-video-mapped">&rarr; ${this._escapeHtml(resolvedPath)}</div>` : ''}
                    </div>
                </div>
                <button class="btn btn-secondary btn-sm" onclick="app._sjBrowseForVideo(${i})">
                    ${isResolved ? 'Change' : 'Browse'}
                </button>
            </div>`;
        }).join('');

        container.innerHTML = html;
        container.classList.remove('hidden');
        if (typeof lucide !== 'undefined') {
            lucide.createIcons({ nodes: Array.from(container.querySelectorAll('[data-lucide]')) });
        }

        // Enable submit if all resolved
        if (resolved === total) {
            document.getElementById('sj-submit-btn').disabled = false;
        }
    }

    _sjBrowseForVideo(index) {
        this._sjBrowseMode = 'video';
        this._sjResolvingVideoIndex = index;

        // Show file browser again for video selection
        document.getElementById('sj-file-columns')?.classList.remove('hidden');
        document.getElementById('sj-file-columns').innerHTML = '';

        // Render mounts as initial column
        const workers = this.roomWorkers[this._sjRoomId]?.workers ?? [];
        const worker = workers.find(w => w.peer_id === this._sjWorkerId);
        const mounts = worker?.properties?.mounts ?? [];

        if (mounts.length > 0) {
            const entries = mounts.map(m => ({
                name: m.label || m.path,
                path: m.path,
                is_dir: true,
            }));
            this._sjRenderColumn(entries, 0);
        }
    }

    _sjResolveVideo(path) {
        const video = this._sjMissingVideos[this._sjResolvingVideoIndex];
        if (!video) return;

        const originalPath = video.original_path || video.filename;
        this._sjPathMappings[originalPath] = path;

        // Switch back to slp mode and hide browser
        this._sjBrowseMode = 'slp';
        this._sjResolvingVideoIndex = null;
        document.getElementById('sj-file-columns')?.classList.add('hidden');

        // Re-render missing videos list
        this._sjRenderMissingVideos();
    }

    // ── File browser (column view via relay) ─────────────────────────────────

    _sjFileIcon(isDir, isVideo, name) {
        if (isDir) {
            return `<svg class="sj-entry-icon" style="color: #fbbf24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
            </svg>`;
        }
        const ext = (name || '').split('.').pop().toLowerCase();
        if (ext === 'slp') {
            return `<svg class="sj-entry-icon" style="color: #a78bfa" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <circle cx="12" cy="14" r="3"/>
            </svg>`;
        }
        if (isVideo || ['mp4', 'avi', 'mov'].includes(ext)) {
            return `<svg class="sj-entry-icon" style="color: #38bdf8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <rect x="2" y="4" width="20" height="16" rx="2"/>
                <polygon points="10 9 16 12 10 15"/>
            </svg>`;
        }
        return `<svg class="sj-entry-icon" style="color: #9090a8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
        </svg>`;
    }

    _sjRenderColumn(entries, colIndex) {
        const container = document.getElementById('sj-file-columns');
        if (!container) return;

        // Truncate columns to the right of colIndex
        const existing = container.querySelectorAll('.sj-file-column');
        existing.forEach((col, i) => { if (i >= colIndex) col.remove(); });

        // Determine file filter based on browse mode
        const isVideoMode = this._sjBrowseMode === 'video';
        const videoExtensions = ['.mp4', '.avi', '.mov', '.mkv', '.h5', '.hdf5'];

        // Filter: show directories + relevant files
        const visible = entries.filter(e => {
            if (e.is_dir) return true;
            const name = (e.name ?? e.path ?? '').toLowerCase();
            if (isVideoMode) {
                return videoExtensions.some(ext => name.endsWith(ext));
            }
            return name.endsWith('.slp');
        });

        const col = document.createElement('div');
        col.className = 'sj-file-column';
        col.dataset.colIndex = colIndex;

        visible.forEach(entry => {
            const name = entry.name ?? entry.path.split('/').pop();
            const row = document.createElement('div');
            row.className = 'sj-file-entry' + (entry.is_dir ? ' is-dir' : (isVideoMode ? ' is-video' : ' is-slp'));
            row.innerHTML = this._sjFileIcon(entry.is_dir, isVideoMode, name) + `<span>${this.escapeHtml(name)}</span>`;

            if (entry.is_dir) {
                row.onclick = () => {
                    const reqId = crypto.randomUUID();
                    this._sjPendingRequests = this._sjPendingRequests || {};
                    this._sjPendingRequests[reqId] = { colIndex: colIndex + 1 };
                    this.apiFsList(this._sjRoomId, this._sjWorkerId, entry.path, reqId);
                    // Highlight selected dir
                    col.querySelectorAll('.sj-file-entry').forEach(r => r.classList.remove('selected'));
                    row.classList.add('selected');
                };
            } else if (isVideoMode) {
                // Video file selection (for resolving missing videos)
                row.onclick = () => {
                    container.querySelectorAll('.sj-file-entry').forEach(r => r.classList.remove('selected'));
                    row.classList.add('selected');
                    this._sjResolveVideo(entry.path);
                };
            } else {
                // .slp file selection
                row.onclick = () => {
                    this._sjLabelsPath = entry.path;
                    const pathEl = document.getElementById('sj-selected-path');
                    if (pathEl) {
                        pathEl.textContent = `Selected: ${entry.path}`;
                        pathEl.classList.remove('hidden');
                    }
                    // Highlight
                    container.querySelectorAll('.sj-file-entry').forEach(r => r.classList.remove('selected'));
                    row.classList.add('selected');
                    // Trigger path validation
                    this._sjValidatePath(entry.path);
                };
            }
            col.appendChild(row);
        });

        container.appendChild(col);
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    // ── Job submission + status (via relay) ───────────────────────────────────

    async submitJob() {
        const submitBtn = document.getElementById('sj-submit-btn');
        if (submitBtn) submitBtn.disabled = true;

        try {
            const config = {
                type: 'train',
                config_content: this._sjConfigContent,
                labels_path: this._sjLabelsPath,
                path_mappings: this._sjPathMappings,
                model_types: [],
            };

            const result = await this.apiJobSubmit(
                this._sjRoomId, this._sjWorkerId, config
            );
            const jobId = result.job_id;

            // Track this job in activeJobs
            const workerData = this.roomWorkers[this._sjRoomId]?.workers ?? [];
            const worker = workerData.find(w => w.peer_id === this._sjWorkerId);
            const jobEntry = {
                jobId,
                roomId: this._sjRoomId,
                workerId: this._sjWorkerId,
                workerName: worker?.worker_name || this._sjWorkerId,
                status: 'submitted',
                modelType: this._sjModelType || 'model',
                lastEpoch: 0,
                maxEpochs: this._sjMaxEpochs || null,
                lastLoss: null,
                logs: [],
                wandbUrl: null,
                startedAt: Date.now(),
                sseConnection: null,
            };
            this.activeJobs.set(jobId, jobEntry);
            this._currentJobId = jobId;
            this._persistActiveJobs();

            // Close worker SSE (no longer needed)
            this._sjWorkerSSE?.close();
            this._sjWorkerSSE = null;

            // Open job SSE for status updates
            this._sjJobSSE = this.sseConnect(jobId);
            jobEntry.sseConnection = this._sjJobSSE;
            this._sjJobSSE
                .on('status', (data) => this._sjHandleJobStatus(data))
                .on('job_status', (data) => this._sjHandleJobStatus(data))
                .on('job_progress', (data) => this._sjHandleJobProgress(data))
                .on('epoch', (data) => this._sjHandleJobEpoch(data));

            // Optimistically mark worker as busy in local cache
            if (worker?.properties) {
                worker.properties.status = 'busy';
            }

            // Switch to status view and reset progress panel
            this.sjGoToStep('status');
            this._sjResetProgressPanel();
            const label = document.getElementById('sj-status-label');
            if (label) label.textContent = 'Submitted…';

        } catch (err) {
            const errEl = document.getElementById('sj-browser-error');
            if (errEl) {
                errEl.textContent = `Submit failed: ${err.message}`;
                errEl.classList.remove('hidden');
            }
            if (submitBtn) submitBtn.disabled = false;
        }
    }

    _sjHandleJobStatus(data) {
        const label = document.getElementById('sj-status-label');
        const status = data.status;
        const stage = data.stage;
        const modelLabel = this._sjModelType || 'model';

        // Update activeJobs entry
        const job = this._currentJobId ? this.activeJobs.get(this._currentJobId) : null;
        if (job) {
            job.status = status;
            if (status === 'failed') {
                job.failMessage = data.message || data.error || 'Job failed';
            }
            this._persistActiveJobs();
            this._updateRoomBadges(job.roomId);
        }

        if (status === 'running' || status === 'submitted') {
            if (label) {
                if (stage === 'inference') label.textContent = 'Running inference…';
                else if (status === 'running') label.textContent = `Training ${modelLabel}…`;
                else label.textContent = 'Submitted…';
            }
        } else if (status === 'accepted') {
            if (label) label.textContent = 'Worker accepted! Starting training job…';
        } else if (status === 'complete') {
            if (label) label.textContent = 'Complete';
            this._sjUpdateStatusIcon('complete');
            this._sjShowCloseButton();
        } else if (status === 'failed') {
            const msg = data.message || data.error || 'Job failed';
            if (label) label.textContent = `Failed: ${msg}`;
            this._sjUpdateStatusIcon('failed');
            this._sjShowCloseButton();
        } else if (status === 'cancelled') {
            if (label) label.textContent = 'Cancelled';
            this._sjUpdateStatusIcon('cancelled');
            this._sjShowCloseButton();
        }
    }

    _sjHandleJobEpoch(data) {
        const label = document.getElementById('sj-status-label');
        const epoch = data.epoch;
        const loss = data.loss != null ? Number(data.loss).toFixed(4) : null;
        const modelLabel = this._sjModelType || 'model';
        if (label && epoch != null) {
            label.textContent = `Training ${modelLabel} — Epoch ${epoch}${loss ? `, loss ${loss}` : ''}`;
        }
        if (epoch != null) {
            this._sjUpdateEpoch(epoch);
        }
        if (data.wandb_url) {
            const link = document.getElementById('sj-wandb-link');
            if (link) {
                link.href = data.wandb_url;
                link.classList.remove('hidden');
            }
        }

        // Update activeJobs entry
        const job = this._currentJobId ? this.activeJobs.get(this._currentJobId) : null;
        if (job) {
            if (epoch != null) job.lastEpoch = epoch;
            if (loss != null) job.lastLoss = Number(loss);
            if (data.wandb_url) job.wandbUrl = data.wandb_url;
            this._persistActiveJobs();
            this._updateRoomBadges(job.roomId);
        }
    }

    _sjHandleJobProgress(data) {
        const event = data.event;
        const what = data.what ? `[${data.what}] ` : '';

        if (event === 'train_begin') {
            this._sjAppendLog(`${what}Training started`);
            if (data.wandb_url) {
                const link = document.getElementById('sj-wandb-link');
                if (link) {
                    link.href = data.wandb_url;
                    link.classList.remove('hidden');
                }
            }
        } else if (event === 'epoch_end') {
            const epoch = data.epoch;
            const logs = data.logs || {};
            const parts = Object.entries(logs)
                .map(([k, v]) => `${k}: ${Number(v).toFixed(4)}`)
                .join('  ');
            this._sjAppendLog(`${what}Epoch ${epoch}  ${parts}`);

            // Update left panel: status label, epoch counter, metrics
            const label = document.getElementById('sj-status-label');
            const modelLabel = this._sjModelType || 'model';
            const trainLoss = logs['train/loss'] != null ? Number(logs['train/loss']).toFixed(4) : null;
            if (label && epoch != null) {
                label.textContent = `Training ${modelLabel} — Epoch ${epoch}${trainLoss ? `, loss ${trainLoss}` : ''}`;
            }
            this._sjUpdateEpoch(epoch);
            this._sjUpdateMetrics(logs);
        } else if (event === 'train_end') {
            this._sjAppendLog(`${what}Training complete`, 'log-info');
        }

        // Update activeJobs entry with log line
        const job = this._currentJobId ? this.activeJobs.get(this._currentJobId) : null;
        if (job) {
            if (event === 'epoch_end' && data.epoch != null) {
                const logs = data.logs || {};
                const trainLoss = logs['train/loss'] != null ? Number(logs['train/loss']) : null;
                job.lastEpoch = data.epoch;
                if (trainLoss != null) job.lastLoss = trainLoss;
            }
            if (data.wandb_url && !job.wandbUrl) job.wandbUrl = data.wandb_url;
            // Store log line for replay on reopen
            if (event === 'train_begin') job.logs.push({ text: `${what}Training started` });
            else if (event === 'epoch_end') {
                const logs = data.logs || {};
                const parts = Object.entries(logs).map(([k, v]) => `${k}: ${Number(v).toFixed(4)}`).join('  ');
                job.logs.push({ text: `${what}Epoch ${data.epoch}  ${parts}` });
            } else if (event === 'train_end') job.logs.push({ text: `${what}Training complete`, cls: 'log-info' });
            this._persistActiveJobs();
            this._updateRoomBadges(job.roomId);
        }
    }

    _sjResetProgressPanel() {
        // Reset spinner to loading state
        const spinner = document.getElementById('sj-status-spinner');
        if (spinner) {
            spinner.className = 'sj-status-spinner';
            spinner.innerHTML = '<i data-lucide="loader-2"></i>';
        }
        // Reset label
        const label = document.getElementById('sj-status-label');
        if (label) {
            label.className = 'sj-status-label';
        }
        // Show job queue tracker
        const queue = document.getElementById('sj-job-queue');
        if (queue) {
            queue.textContent = 'Job 1 / 1';
            queue.classList.remove('hidden');
        }
        // Hide epoch section and metrics until training starts
        document.getElementById('sj-epoch-section')?.classList.add('hidden');
        document.getElementById('sj-metrics')?.classList.add('hidden');
        // Reset metric values
        ['sj-metric-train-loss', 'sj-metric-val-loss', 'sj-metric-train-time', 'sj-metric-lr'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '—';
        });
        // Reset epoch
        const cur = document.getElementById('sj-epoch-current');
        if (cur) cur.textContent = '0';
        const total = document.getElementById('sj-epoch-total');
        if (total) total.textContent = this._sjMaxEpochs ? ` / ${this._sjMaxEpochs}` : '';
        // Clear log
        const log = document.getElementById('sj-training-log');
        if (log) log.innerHTML = '';
        // Re-init lucide icons scoped to status view
        const statusView = document.getElementById('sj-status');
        if (window.lucide && statusView) {
            lucide.createIcons({ nodes: Array.from(statusView.querySelectorAll('[data-lucide]')) });
        }
    }

    _sjUpdateStatusIcon(state) {
        const spinner = document.getElementById('sj-status-spinner');
        const label = document.getElementById('sj-status-label');
        if (!spinner) return;

        if (state === 'complete') {
            spinner.className = 'sj-status-spinner complete';
            spinner.innerHTML = '<i data-lucide="check-circle"></i>';
            if (label) label.className = 'sj-status-label complete';
        } else if (state === 'failed' || state === 'cancelled') {
            spinner.className = 'sj-status-spinner failed';
            spinner.innerHTML = '<i data-lucide="x-circle"></i>';
            if (label) label.className = 'sj-status-label failed';
        }
        if (window.lucide) lucide.createIcons();
    }

    _sjUpdateMetrics(logs) {
        // Show metrics section
        document.getElementById('sj-metrics')?.classList.remove('hidden');

        const updates = {
            'sj-metric-train-loss': logs['train/loss'] != null ? Number(logs['train/loss']).toFixed(4) : null,
            'sj-metric-val-loss': logs['val/loss'] != null ? Number(logs['val/loss']).toFixed(4) : null,
            'sj-metric-train-time': logs['train/time'] != null ? `${Number(logs['train/time']).toFixed(1)}s` : null,
            'sj-metric-lr': logs['train/lr'] != null ? Number(logs['train/lr']).toFixed(6) : null,
        };
        for (const [id, val] of Object.entries(updates)) {
            if (val != null) {
                const el = document.getElementById(id);
                if (el) el.textContent = val;
            }
        }
    }

    _sjUpdateEpoch(epoch) {
        document.getElementById('sj-epoch-section')?.classList.remove('hidden');
        const cur = document.getElementById('sj-epoch-current');
        if (cur) cur.textContent = epoch;
    }

    _sjAppendLog(text, extraClass = '') {
        const log = document.getElementById('sj-training-log');
        if (!log) return;
        const line = document.createElement('div');
        line.className = `log-line${extraClass ? ' ' + extraClass : ''}`;
        line.textContent = text;
        log.appendChild(line);
        log.scrollTop = log.scrollHeight;
    }

    _sjShowCloseButton() {
        const actions = document.querySelector('#sj-status .form-actions');
        if (actions) {
            actions.innerHTML = `<button class="btn btn-secondary" onclick="app.closeSubmitJobModal()">Close</button>`;
        }
    }

    sjGoToStep(step) {
        // Hide all views
        ['sj-step1', 'sj-step2', 'sj-step3', 'sj-status'].forEach(id => {
            document.getElementById(id)?.classList.add('hidden');
        });

        // Show target view (status view doesn't have a step number)
        const viewId = step === 'status' ? 'sj-status' : `sj-step${step}`;
        document.getElementById(viewId)?.classList.remove('hidden');

        // Hide stepper and update title for status view; show for wizard steps
        const stepper = document.querySelector('.sj-step-indicator');
        const title = document.getElementById('sj-title');
        if (step === 'status') {
            if (stepper) stepper.classList.add('hidden');
            if (title) title.textContent = 'Training Job';
        } else {
            if (stepper) stepper.classList.remove('hidden');
            if (title) title.textContent = 'Submit Training Job';
            // Update step indicator dots (steps 1-3 only)
            for (let i = 1; i <= 3; i++) {
                const dot = document.getElementById(`sj-step-dot-${i}`);
                if (!dot) continue;
                dot.classList.remove('active', 'done');
                if (i < step) dot.classList.add('done');
                else if (i === step) dot.classList.add('active');
            }
        }
    }
    // =========================================================================
    // Deploy Worker Modal
    // =========================================================================

    openDeployWorkerModal(roomId) {
        this.deployWorkerRoomId = roomId;
        this.deployMountCount = 0;
        this.deployDirectMountCount = 0;

        // Populate account key dropdowns from cached keys
        const activeKeys = this.accountKeys.filter(k => !k.revoked_at);
        const keyOptions = activeKeys.map(k =>
            `<option value="${k.key_id}">${this.escapeHtml(k.name || k.key_id)}</option>`
        ).join('');
        const noKeysOption = '<option value="">No account keys — create one first</option>';
        const options = activeKeys.length > 0 ? keyOptions : noKeysOption;

        document.getElementById('dw-account-key').innerHTML = options;
        document.getElementById('dw-runai-key').innerHTML = options;
        document.getElementById('dw-direct-key').innerHTML = options;

        // Reset form fields
        document.getElementById('dw-name').value = '';
        document.getElementById('dw-workdir').value = '/mnt/data';
        document.getElementById('dw-reconnect').value = 'forever';
        document.getElementById('dw-gpu').checked = true;
        document.getElementById('dw-restart').checked = true;
        document.getElementById('dw-mounts').innerHTML = '';
        document.getElementById('dw-direct-name').value = '';
        document.getElementById('dw-direct-mounts').innerHTML = '';

        // Reset to Docker tab
        this.switchDeployTab('docker');

        // Load account keys if not yet loaded
        if (this.accountKeys.length === 0) {
            this.loadAccountKeys().then(() => {
                const freshKeys = this.accountKeys.filter(k => !k.revoked_at);
                const freshOptions = freshKeys.map(k =>
                    `<option value="${k.key_id}">${this.escapeHtml(k.name || k.key_id)}</option>`
                ).join('');
                const opts = freshKeys.length > 0 ? freshOptions : noKeysOption;
                document.getElementById('dw-account-key').innerHTML = opts;
                document.getElementById('dw-runai-key').innerHTML = opts;
                document.getElementById('dw-direct-key').innerHTML = opts;
                this.updateDockerCommand();
                this.updateDirectCommands();
            });
        }

        this.updateDockerCommand();
        this.updateRunAIKey();
        this.updateDirectCommands();
        this.showModal('deploy-worker-modal');
    }

    switchDeployTab(tabName) {
        document.querySelectorAll('#deploy-worker-modal .dw-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('#deploy-worker-modal .dw-tab-content').forEach(t => t.classList.remove('active'));
        document.getElementById(`dw-tab-${tabName}`)?.classList.add('active');
        document.querySelector(`#deploy-worker-modal .dw-tab[data-tab="${tabName}"]`)?.classList.add('active');
    }

    updateDockerCommand() {
        const keyEl = document.getElementById('dw-account-key');
        const key = keyEl ? keyEl.value : '';
        const name = (document.getElementById('dw-name')?.value || '').trim();
        const workdir = (document.getElementById('dw-workdir')?.value || '').trim();
        const reconnect = document.getElementById('dw-reconnect')?.value || 'forever';
        const gpu = document.getElementById('dw-gpu')?.checked;
        const restart = document.getElementById('dw-restart')?.checked;
        const mounts = this.getDeployMounts('dw-mounts');

        const parts = ['docker run -d'];
        if (gpu) parts.push('--gpus all');
        if (restart) parts.push('--restart unless-stopped');
        if (key) parts.push(`-e SLEAP_RTC_ACCOUNT_KEY=${key}`);
        for (const mount of mounts) {
            parts.push(`-v ${mount}:${mount}`);
        }
        parts.push('ghcr.io/talmolab/sleap-rtc-worker:latest');
        parts.push('worker');
        if (name) parts.push(`--name ${name}`);
        if (workdir) parts.push(`--working-dir ${workdir}`);
        if (reconnect !== 'forever') parts.push(`--max-reconnect-time ${reconnect}`);

        const el = document.getElementById('dw-command');
        if (el) el.textContent = parts.join(' \\\n  ');
    }

    updateRunAIKey() {
        const key = document.getElementById('dw-runai-key')?.value || '';
        const display = document.getElementById('dw-runai-key-display');
        if (display) display.textContent = key;
    }

    updateDirectCommands() {
        const key = document.getElementById('dw-direct-key')?.value || '';
        const name = (document.getElementById('dw-direct-name')?.value || '').trim();
        const mounts = this.getDeployMounts('dw-direct-mounts');

        // Step 2: mount commands
        const step2 = document.getElementById('dw-direct-step2-text');
        if (step2) {
            if (mounts.length > 0) {
                step2.textContent = mounts.map(m => {
                    const label = m.split('/').filter(Boolean).pop() || 'data';
                    return `sleap-rtc config add-mount ${m} "${label}" --global`;
                }).join('\n');
            } else {
                step2.textContent = 'sleap-rtc config add-mount /path/to/your/data "My Data" --global';
            }
        }

        // Step 3: worker command
        let workerCmd = `sleap-rtc worker --account-key ${key || 'slp_acct_xxx...'}`;
        if (name) workerCmd += ` --name ${name}`;
        const step3 = document.getElementById('dw-direct-step3-text');
        if (step3) step3.textContent = workerCmd;

        // Combined copy block
        const installCmd = 'uv tool install --python 3.11 sleap-rtc --with "sleap-nn[torch]" --with-executables-from sleap-nn --torch-backend auto';
        const allLines = [`# Step 1: Install sleap-rtc`, installCmd, ''];
        allLines.push('# Step 2: Register data mounts');
        if (mounts.length > 0) {
            for (const m of mounts) {
                const label = m.split('/').filter(Boolean).pop() || 'data';
                allLines.push(`sleap-rtc config add-mount ${m} "${label}" --global`);
            }
        } else {
            allLines.push('sleap-rtc config add-mount /path/to/your/data "My Data" --global');
        }
        allLines.push('', '# Step 3: Start the worker', workerCmd);

        const allEl = document.getElementById('dw-direct-all-commands');
        if (allEl) allEl.textContent = allLines.join('\n');
    }

    getDeployMounts(containerId) {
        const inputs = document.querySelectorAll(`#${containerId} .dw-mount-row input`);
        return Array.from(inputs).map(i => i.value.trim()).filter(v => v);
    }

    addDeployMount(containerId, value = '') {
        const isDocker = containerId === 'dw-mounts';
        const count = isDocker ? ++this.deployMountCount : ++this.deployDirectMountCount;
        const rowId = `${containerId}-row-${count}`;
        const container = document.getElementById(containerId);
        if (!container) return;

        const row = document.createElement('div');
        row.className = 'dw-mount-row';
        row.id = rowId;
        row.innerHTML = `
            <input type="text" class="form-input" placeholder="/path/on/host" value="${value}"
                oninput="app.${isDocker ? 'updateDockerCommand' : 'updateDirectCommands'}()">
            <button class="dw-btn-mount-remove" onclick="app.removeDeployMount('${rowId}', '${containerId}')" title="Remove">
                <i data-lucide="x"></i>
            </button>
        `;
        container.appendChild(row);
        lucide.createIcons({ nodes: [row] });
        if (isDocker) this.updateDockerCommand();
        else this.updateDirectCommands();
    }

    removeDeployMount(rowId, containerId) {
        document.getElementById(rowId)?.remove();
        if (containerId === 'dw-mounts') this.updateDockerCommand();
        else this.updateDirectCommands();
    }

    copyDeployText(preId, btnId) {
        const text = document.getElementById(preId)?.textContent;
        if (!text) return;
        navigator.clipboard.writeText(text).then(() => {
            const btn = document.getElementById(btnId);
            if (!btn) return;
            btn.classList.add('copied');
            const orig = btn.innerHTML;
            btn.innerHTML = '<i data-lucide="check"></i> Copied!';
            lucide.createIcons({ nodes: [btn] });
            setTimeout(() => {
                btn.classList.remove('copied');
                btn.innerHTML = orig;
                lucide.createIcons({ nodes: [btn] });
            }, 2000);
        });
    }

    copyDeployInline(btn, textElId) {
        const textEl = document.getElementById(textElId);
        const text = textEl ? textEl.textContent : '';
        if (!text) return;
        navigator.clipboard.writeText(text.trim()).then(() => {
            btn.classList.add('copied');
            const orig = btn.innerHTML;
            btn.innerHTML = '<i data-lucide="check"></i>';
            lucide.createIcons({ nodes: [btn] });
            setTimeout(() => {
                btn.classList.remove('copied');
                btn.innerHTML = orig;
                lucide.createIcons({ nodes: [btn] });
            }, 2000);
        });
    }
}

// Initialize app
const app = new SleapRTCDashboard();
