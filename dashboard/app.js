// SLEAP-RTC Dashboard Application

// =========================================================================
// Relative Time Formatting
// =========================================================================

/**
 * Format a date as relative time (e.g., "2 hours ago", "yesterday")
 * Uses Intl.RelativeTimeFormat for localized output
 * @param {string} isoString - ISO 8601 date string
 * @returns {string} Relative time string
 */
function formatRelativeTime(isoString) {
    if (!isoString) return 'N/A';
    if (typeof isoString !== 'string') isoString = String(isoString);

    // Ensure UTC parsing: if no timezone indicator, assume UTC
    let dateStr = isoString;
    if (!isoString.endsWith('Z') && !isoString.includes('+') && !isoString.includes('-', 10)) {
        dateStr = isoString + 'Z';
    }
    const date = new Date(dateStr);
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
 * @param {string} isoString - ISO 8601 date string
 * @returns {string} Formatted datetime string
 */
function formatExactDate(isoString) {
    if (!isoString) return '';
    if (typeof isoString !== 'string') isoString = String(isoString);
    // Ensure UTC parsing: if no timezone indicator, assume UTC
    let dateStr = isoString;
    if (!isoString.endsWith('Z') && !isoString.includes('+') && !isoString.includes('-', 10)) {
        dateStr = isoString + 'Z';
    }
    const date = new Date(dateStr);
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
        this.tokens = [];
        this.tokenWorkers = {}; // Cache of connected workers by token_id

        // Filter/sort state with localStorage persistence
        this.roomsFilter = localStorage.getItem('sleap_rooms_filter') || 'all';
        this.roomsSort = localStorage.getItem('sleap_rooms_sort') || 'joined_at';
        this.roomsSearch = '';
        this.tokensSort = localStorage.getItem('sleap_tokens_sort') || 'created_at';
        this.tokensActiveOnly = localStorage.getItem('sleap_tokens_active') === 'true';
        this.tokensSearch = '';
        this.searchDebounceTimer = null;

        this.init();
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    init() {
        // Load stored credentials
        this.loadStoredCredentials();

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
        const titles = {
            'rooms': 'Rooms',
            'tokens': 'Worker Tokens',
            'about': 'About SLEAP-RTC'
        };
        document.getElementById('page-title').textContent = titles[tabName] || tabName;

        // Re-initialize Lucide icons for the About tab
        if (tabName === 'about' && typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    showModal(modalId) {
        // Populate settings modal with user info
        if (modalId === 'settings-modal' && this.user) {
            document.getElementById('settings-username').textContent = this.user.username || '-';
            document.getElementById('settings-user-id').textContent = this.user.id || '-';
        }

        document.getElementById(modalId)?.classList.remove('hidden');
        // Refresh Lucide icons in modal
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
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
            this.updateCounts();
        } catch (e) {
            console.error('Failed to load rooms:', e);
            container.innerHTML = `<p class="loading" style="color: var(--status-error);">Failed to load rooms: ${e.message}</p>`;
        }
    }

    updateCounts() {
        // Update sidebar badges
        document.getElementById('rooms-count').textContent = this.rooms.length;
        document.getElementById('tokens-count').textContent = this.tokens.length;

        // Update section titles
        document.getElementById('rooms-title-count').textContent = this.rooms.length;
        document.getElementById('tokens-title-count').textContent = this.tokens.length;
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
        const activeRooms = this.rooms.filter(room => !room.expires_at || new Date(room.expires_at) > now);
        const expiredRooms = this.rooms.filter(room => room.expires_at && new Date(room.expires_at) <= now);

        // Check if expired section should be expanded (from localStorage)
        const expiredExpanded = localStorage.getItem('sleap_expired_rooms_expanded') === 'true';

        let html = '';

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

        // If no active rooms but there are expired ones, show a message
        if (activeRooms.length === 0 && expiredRooms.length > 0) {
            html = `
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
            </div>` + html;
        }

        container.innerHTML = html;

        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    renderRoomCard(room, isExpired = false) {
        // Check if room is expiring soon (< 3 days)
        const isExpiringSoon = room.expires_at &&
            new Date(room.expires_at) - new Date() < 3 * 24 * 60 * 60 * 1000 &&
            new Date(room.expires_at) > new Date();
        if (!isExpired) {
            isExpired = room.expires_at && new Date(room.expires_at) < new Date();
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
                            <span class="room-meta-item">
                                <i data-lucide="hash"></i>
                                ${room.room_id}
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
                    ${!isExpired ? `
                        ${room.role === 'owner' ? `
                            <button class="btn btn-secondary btn-sm" onclick="app.handleRoomSecret('${room.room_id}')">
                                <i data-lucide="key"></i>
                                Secret
                            </button>
                            <button class="btn btn-secondary btn-sm" onclick="app.handleInvite('${room.room_id}')">
                                <i data-lucide="user-plus"></i>
                                Invite
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="app.handleDeleteRoom('${room.room_id}', '${this.escapeHtml(room.name || room.room_id)}')">
                                <i data-lucide="trash-2"></i>
                                Delete
                            </button>
                        ` : ''}
                    ` : `
                        <button class="btn btn-danger btn-sm" onclick="app.handleDeleteRoom('${room.room_id}', '${this.escapeHtml(room.name || room.room_id)}')">
                            <i data-lucide="trash-2"></i>
                            Delete
                        </button>
                    `}
                </div>
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
            document.getElementById('new-room-token').textContent = data.room_token;

            this.hideModal('create-room-modal');
            document.getElementById('room-modal-title').textContent = 'Room Created!';
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

    async handleViewRoom(roomId) {
        try {
            const data = await this.apiRequest(`/api/auth/rooms/${roomId}`);

            // Populate the room details modal (reuse the room-created-modal)
            document.getElementById('new-room-id').textContent = data.room_id;
            document.getElementById('new-room-token').textContent = data.room_token || 'N/A';

            document.getElementById('room-modal-title').textContent = 'Room Details';
            this.showModal('room-created-modal');

        } catch (e) {
            console.error('Failed to get room details:', e);
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

        // If no active tokens but there are inactive ones, show a message
        if (activeTokens.length === 0 && inactiveTokens.length > 0) {
            html = `
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
            </div>` + html;
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
        const isExpiringSoon = token.expires_at && !isInactive &&
            new Date(token.expires_at) - new Date() < 3 * 24 * 60 * 60 * 1000 &&
            new Date(token.expires_at) > new Date();

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
        const activeRooms = this.rooms.filter(room => !room.expires_at || new Date(room.expires_at) > now);
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
}

// Initialize app
const app = new SleapRTCDashboard();
