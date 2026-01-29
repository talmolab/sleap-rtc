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
        this.searchQuery = ''; // Current search query

        this.init();
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    init() {
        // Load stored credentials
        this.loadStoredCredentials();

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
        document.getElementById('join-room-form')?.addEventListener('submit', (e) => this.handleJoinRoom(e));

        // Edit room name
        document.getElementById('edit-room-form')?.addEventListener('submit', (e) => this.handleSaveRoomName(e));

        // Create token
        document.getElementById('create-token-btn')?.addEventListener('click', () => this.showCreateTokenModal());
        document.getElementById('create-token-form')?.addEventListener('submit', (e) => this.handleCreateToken(e));

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

        // Search functionality
        document.getElementById('rooms-search')?.addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.renderRooms();
        });
        document.getElementById('tokens-search')?.addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.renderTokens();
            this.updateWorkerBadges();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // "/" to focus search (when not in an input)
            if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
                e.preventDefault();
                const activeTab = document.querySelector('.tab-content.active');
                if (activeTab?.id === 'rooms-tab') {
                    document.getElementById('rooms-search')?.focus();
                } else if (activeTab?.id === 'tokens-tab') {
                    document.getElementById('tokens-search')?.focus();
                }
            }
            // Escape to close modals
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal:not(.hidden)').forEach(modal => {
                    modal.classList.add('hidden');
                });
            }
        });

        // Join room button (will be added to sidebar)
        document.getElementById('join-room-btn')?.addEventListener('click', () => this.showModal('join-room-modal'));

        // Settings button
        document.getElementById('settings-btn')?.addEventListener('click', () => this.showModal('settings-modal'));

        // Mobile menu toggle
        document.getElementById('mobile-menu-btn')?.addEventListener('click', () => this.toggleMobileMenu());
        document.getElementById('sidebar-overlay')?.addEventListener('click', () => this.closeMobileMenu());

        // Close mobile menu when clicking nav items
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => this.closeMobileMenu());
        });
    }

    toggleMobileMenu() {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        sidebar?.classList.toggle('open');
        overlay?.classList.toggle('active');
    }

    closeMobileMenu() {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        sidebar?.classList.remove('open');
        overlay?.classList.remove('active');
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
            'tokens': 'Worker Tokens'
        };
        document.getElementById('page-title').textContent = titles[tabName] || tabName;
    }

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        // Populate settings modal with user info
        if (modalId === 'settings-modal' && this.user) {
            document.getElementById('settings-username').textContent = this.user.username || '-';
            document.getElementById('settings-user-id').textContent = this.user.id || '-';
        }

        modal.classList.remove('hidden');
        // Refresh Lucide icons in modal
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    hideModal(modalId) {
        document.getElementById(modalId)?.classList.add('hidden');
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

    renderSkeletonCards(count = 3) {
        return Array(count).fill(0).map(() => `
            <div class="skeleton-card">
                <div class="skeleton-header">
                    <div class="skeleton skeleton-icon"></div>
                    <div class="skeleton-content">
                        <div class="skeleton skeleton-title"></div>
                        <div class="skeleton skeleton-meta"></div>
                    </div>
                    <div class="skeleton-actions">
                        <div class="skeleton skeleton-btn"></div>
                        <div class="skeleton skeleton-btn"></div>
                    </div>
                </div>
            </div>
        `).join('');
    }

    async loadRooms() {
        const container = document.getElementById('rooms-list');
        container.innerHTML = this.renderSkeletonCards(3);

        try {
            const data = await this.apiRequest('/api/auth/rooms');
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

        // Filter rooms by search query
        const filteredRooms = this.searchQuery
            ? this.rooms.filter(room =>
                (room.name || '').toLowerCase().includes(this.searchQuery) ||
                room.room_id.toLowerCase().includes(this.searchQuery) ||
                room.role.toLowerCase().includes(this.searchQuery)
            )
            : this.rooms;

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

        if (filteredRooms.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <i data-lucide="search"></i>
                    </div>
                    <h3>No matching rooms</h3>
                    <p>No rooms match your search "${this.searchQuery}"</p>
                </div>
            `;
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
            return;
        }

        container.innerHTML = filteredRooms.map(room => `
            <div class="room-card">
                <div class="room-header">
                    <div class="room-main">
                        <div class="room-icon">
                            <i data-lucide="home"></i>
                        </div>
                        <div class="room-info">
                            <h3>
                                ${room.name || 'Unnamed Room'}
                                ${room.role === 'owner' ? `
                                    <button class="btn-edit-inline" onclick="app.handleEditRoomName('${room.room_id}', '${this.escapeHtml(room.name || '')}')">
                                        <i data-lucide="pencil"></i>
                                    </button>
                                ` : ''}
                            </h3>
                            <div class="room-meta">
                                <span class="room-meta-item">
                                    <i data-lucide="hash"></i>
                                    ${room.room_id}
                                </span>
                                <span class="room-meta-item" title="${formatExactDate(room.joined_at)}">
                                    <i data-lucide="calendar"></i>
                                    Joined ${formatRelativeTime(room.joined_at)}
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="room-actions">
                        <span class="role-badge ${room.role}">${room.role}</span>
                        <button class="btn btn-secondary btn-sm" onclick="app.handleViewRoom('${room.room_id}')">
                            <i data-lucide="eye"></i>
                            View
                        </button>
                        ${room.role === 'owner' ? `
                            <button class="btn btn-secondary btn-sm" onclick="app.handleRoomSecret('${room.room_id}')">
                                <i data-lucide="key"></i>
                                Secret
                            </button>
                            <button class="btn btn-secondary btn-sm" onclick="app.handleInvite('${room.room_id}')">
                                <i data-lucide="user-plus"></i>
                                Invite
                            </button>
                            <button class="btn btn-secondary btn-sm" onclick="app.handleViewMembers('${room.room_id}')">
                                <i data-lucide="users"></i>
                                Members
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="app.handleDeleteRoom('${room.room_id}', '${this.escapeHtml(room.name || room.room_id)}')">
                                <i data-lucide="trash-2"></i>
                                Delete
                            </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        `).join('');

        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML.replace(/'/g, "\\'");
    }

    async handleCreateRoom(e) {
        e.preventDefault();

        const nameInput = document.getElementById('room-name');
        const name = nameInput.value.trim();

        try {
            const data = await this.apiRequest('/api/auth/rooms', {
                method: 'POST',
                body: JSON.stringify({ name: name || undefined }),
            });

            // Show success modal
            document.getElementById('new-room-id').textContent = data.room_id;
            document.getElementById('new-room-token').textContent = data.room_token;

            this.hideModal('create-room-modal');
            document.getElementById('room-modal-title').textContent = 'Room Created!';
            this.showModal('room-created-modal');

            // Refresh rooms list
            nameInput.value = '';
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

    handleEditRoomName(roomId, currentName) {
        document.getElementById('edit-room-id').value = roomId;
        document.getElementById('edit-room-name').value = currentName;
        this.showModal('edit-room-modal');
    }

    async handleSaveRoomName(e) {
        e.preventDefault();

        const roomId = document.getElementById('edit-room-id').value;
        const newName = document.getElementById('edit-room-name').value.trim();

        try {
            await this.apiRequest(`/api/auth/rooms/${roomId}`, {
                method: 'PATCH',
                body: JSON.stringify({ name: newName || null }),
            });

            this.hideModal('edit-room-modal');
            this.showToast('Room name updated');
            this.loadRooms();

        } catch (e) {
            console.error('Failed to update room name:', e);
            this.showToast(e.message, 'error');
        }
    }

    async handleViewMembers(roomId) {
        const container = document.getElementById('members-list');
        container.innerHTML = '<p class="loading">Loading members...</p>';
        this.showModal('members-modal');

        try {
            const data = await this.apiRequest(`/api/auth/rooms/${roomId}/members`);
            const members = data.members || [];
            const currentRoom = this.rooms.find(r => r.room_id === roomId);
            const isOwner = currentRoom?.role === 'owner';

            if (members.length === 0) {
                container.innerHTML = '<p class="loading">No members in this room.</p>';
                return;
            }

            container.innerHTML = members.map(member => `
                <div class="member-row">
                    <div class="member-info">
                        <img class="member-avatar" src="${member.avatar_url || ''}" alt="">
                        <div class="member-details">
                            <span class="member-name">${member.username}</span>
                            <span class="member-joined">
                                <span class="role-badge ${member.role}">${member.role}</span>
                                · Joined ${formatRelativeTime(member.joined_at)}
                            </span>
                        </div>
                    </div>
                    <div class="member-actions">
                        ${isOwner && member.role !== 'owner' ? `
                            <button class="btn btn-danger btn-sm" onclick="app.handleRemoveMember('${roomId}', '${member.user_id}', '${this.escapeHtml(member.username)}')">
                                <i data-lucide="user-minus"></i>
                                Remove
                            </button>
                        ` : ''}
                    </div>
                </div>
            `).join('');

            // Refresh Lucide icons
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }

        } catch (e) {
            console.error('Failed to load members:', e);
            container.innerHTML = `<p class="loading" style="color: var(--status-error);">Failed to load members: ${e.message}</p>`;
        }
    }

    async handleRemoveMember(roomId, userId, username) {
        if (!confirm(`Are you sure you want to remove ${username} from this room?`)) {
            return;
        }

        try {
            await this.apiRequest(`/api/auth/rooms/${roomId}/members/${userId}`, {
                method: 'DELETE',
            });

            this.showToast(`${username} removed from room`);
            // Refresh the members list
            this.handleViewMembers(roomId);

        } catch (e) {
            console.error('Failed to remove member:', e);
            this.showToast(e.message, 'error');
        }
    }

    async handleDeleteRoom(roomId, roomName) {
        if (!confirm(`Are you sure you want to delete room "${roomName}"?\n\nThis will also delete all worker tokens and memberships for this room. This action cannot be undone.`)) {
            return;
        }

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
        container.innerHTML = this.renderSkeletonCards(3);

        try {
            const data = await this.apiRequest('/api/auth/tokens');
            this.tokens = data.tokens || [];
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

        // Filter tokens by search query
        const filteredTokens = this.searchQuery
            ? this.tokens.filter(token =>
                token.worker_name.toLowerCase().includes(this.searchQuery) ||
                token.room_id.toLowerCase().includes(this.searchQuery) ||
                (token.room_name || '').toLowerCase().includes(this.searchQuery) ||
                token.token_id.toLowerCase().includes(this.searchQuery)
            )
            : this.tokens;

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

        if (filteredTokens.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <i data-lucide="search"></i>
                    </div>
                    <h3>No matching tokens</h3>
                    <p>No tokens match your search "${this.searchQuery}"</p>
                </div>
            `;
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
            return;
        }

        container.innerHTML = filteredTokens.map(token => {
            const isRevoked = !!token.revoked_at;
            const expiresAt = token.expires_at ? new Date(token.expires_at) : null;
            const now = new Date();
            const msUntilExpiry = expiresAt ? expiresAt - now : Infinity;
            const isExpired = expiresAt && msUntilExpiry < 0;
            const isExpiringSoon = expiresAt && !isExpired && msUntilExpiry < 3 * 24 * 60 * 60 * 1000; // 3 days

            // Determine expiration badge
            let expirationBadge = '';
            if (!isRevoked && isExpired) {
                expirationBadge = `<span class="badge badge-expired"><i data-lucide="alert-circle"></i> Expired</span>`;
            } else if (!isRevoked && isExpiringSoon) {
                expirationBadge = `<span class="badge badge-expiring"><i data-lucide="alert-triangle"></i> Expiring Soon</span>`;
            }

            return `
            <div class="token-card">
                <div class="token-header">
                    <div class="token-main">
                        <div class="token-icon" ${isRevoked || isExpired ? 'style="opacity: 0.5;"' : ''}>
                            <i data-lucide="key-round"></i>
                        </div>
                        <div class="token-info">
                            <h3>${token.worker_name} ${expirationBadge}</h3>
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
                                    <span class="token-meta-item" ${isExpiringSoon || isExpired ? 'style="color: var(--status-warning);"' : ''} title="${formatExactDate(token.expires_at)}">
                                        <i data-lucide="${isExpiringSoon || isExpired ? 'alert-triangle' : 'clock'}"></i>
                                        ${isExpired ? 'Expired' : 'Expires'} ${formatRelativeTime(token.expires_at)}
                                    </span>
                                ` : ''}
                                ${isRevoked ? `
                                    <span class="token-meta-item" style="color: var(--status-error);">
                                        <i data-lucide="x-circle"></i>
                                        Revoked
                                    </span>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="token-actions">
                        ${!isRevoked ? `
                            <div id="worker-badge-${token.token_id}" class="worker-count-badge offline">
                                <i data-lucide="zap-off"></i>
                                Loading...
                            </div>
                            <button class="btn btn-danger btn-sm" onclick="app.handleRevokeToken('${token.token_id}')">
                                <i data-lucide="trash-2"></i>
                                Revoke
                            </button>
                        ` : ''}
                    </div>
                </div>
                ${!isRevoked ? `
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
        }).join('');

        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    async showCreateTokenModal() {
        // Populate room dropdown
        const select = document.getElementById('token-room');
        select.innerHTML = '<option value="">Select a room...</option>' +
            this.rooms.map(room => `
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

            // Show success modal
            document.getElementById('new-token-id').textContent = data.token_id;
            // Look up room name from our rooms list
            const room = this.rooms.find(r => r.room_id === roomId);
            const roomDisplay = room && room.name
                ? `${room.name} (${roomId.substring(0, 8)}...)`
                : roomId;
            document.getElementById('new-token-room').textContent = roomDisplay;
            document.getElementById('new-token-name').textContent = workerName;
            document.getElementById('worker-command').textContent = `sleap-rtc worker --api-key ${data.token_id}`;

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
        if (!confirm('Are you sure you want to revoke this token? Workers using it will no longer be able to connect.')) {
            return;
        }

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
                    <p class="security-note"><i data-lucide="shield-check"></i> This secret is stored only in your browser. The server never sees it.</p>
                    <div class="detail-row">
                        <label>Secret:</label>
                        <code id="room-secret-value" class="api-key">${existingSecret}</code>
                        <button class="btn btn-secondary btn-sm" onclick="app.copyToClipboard('${existingSecret}')">
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
