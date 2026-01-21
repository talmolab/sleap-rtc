// SLEAP-RTC Dashboard Application

class SleapRTCDashboard {
    constructor() {
        this.jwt = null;
        this.user = null;
        this.rooms = [];
        this.tokens = [];

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
        const userInfo = document.getElementById('user-info');

        if (this.isLoggedIn()) {
            loginSection.classList.add('hidden');
            dashboardSection.classList.remove('hidden');
            userInfo.classList.remove('hidden');

            // Update user info
            document.getElementById('user-avatar').src = this.user.avatar_url || '';
            document.getElementById('user-name').textContent = this.user.username || 'User';

            // Load data
            this.loadRooms();
            this.loadTokens();
        } else {
            loginSection.classList.remove('hidden');
            dashboardSection.classList.add('hidden');
            userInfo.classList.add('hidden');
        }
    }

    setupEventListeners() {
        // Login button
        document.getElementById('github-login-btn')?.addEventListener('click', () => this.handleLogin());

        // Logout button
        document.getElementById('logout-btn')?.addEventListener('click', () => this.handleLogout());

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });

        // Create room
        document.getElementById('create-room-btn')?.addEventListener('click', () => this.showModal('create-room-modal'));
        document.getElementById('create-room-form')?.addEventListener('submit', (e) => this.handleCreateRoom(e));

        // Join room
        document.getElementById('join-room-form')?.addEventListener('submit', (e) => this.handleJoinRoom(e));

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
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}-tab`);
            content.classList.toggle('hidden', content.id !== `${tabName}-tab`);
        });
    }

    showModal(modalId) {
        document.getElementById(modalId)?.classList.remove('hidden');
    }

    hideModal(modalId) {
        document.getElementById(modalId)?.classList.add('hidden');
    }

    showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.remove();
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
        const authUrl = new URL('https://github.com/login/oauth/authorize');
        authUrl.searchParams.set('client_id', CONFIG.GITHUB_CLIENT_ID);
        authUrl.searchParams.set('redirect_uri', CONFIG.OAUTH_CALLBACK_URL);
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
        this.updateUI();
        this.showToast('Logged out successfully');
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

        try {
            const data = await this.apiRequest('/api/auth/rooms');
            this.rooms = data.rooms || [];
            this.renderRooms();
        } catch (e) {
            console.error('Failed to load rooms:', e);
            container.innerHTML = `<p class="error">Failed to load rooms: ${e.message}</p>`;
        }
    }

    renderRooms() {
        const container = document.getElementById('rooms-list');

        if (this.rooms.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No rooms yet</h3>
                    <p>Create a room to get started with remote training.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.rooms.map(room => `
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title">${room.room_id}</div>
                        <div class="card-subtitle">${room.name || 'Unnamed Room'}</div>
                    </div>
                    <div class="card-actions">
                        ${room.role === 'owner' ? `
                            <button class="btn btn-secondary btn-small" onclick="app.handleInvite('${room.room_id}')">Invite</button>
                            <button class="btn btn-danger btn-small" onclick="app.handleDeleteRoom('${room.room_id}', '${room.name || room.room_id}')">Delete</button>
                        ` : ''}
                    </div>
                </div>
                <div class="card-meta">
                    <span><span class="badge ${room.role === 'owner' ? 'badge-success' : 'badge-warning'}">${room.role}</span></span>
                    <span>Joined: ${new Date(room.joined_at).toLocaleDateString()}</span>
                </div>
            </div>
        `).join('');
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

            // Generate QR code if OTP secret provided
            if (data.otp_secret) {
                document.getElementById('new-room-otp-secret').textContent = data.otp_secret;
                const qrContainer = document.getElementById('otp-qr-code');
                qrContainer.innerHTML = '';
                try {
                    if (typeof QRCode !== 'undefined') {
                        QRCode.toCanvas(qrContainer, data.otp_uri, {
                            width: 200,
                            margin: 2,
                            color: { dark: '#000000', light: '#ffffff' }
                        });
                    } else {
                        qrContainer.innerHTML = '<p style="color: var(--text-muted); font-size: 0.875rem;">QR code unavailable. Use the secret below.</p>';
                    }
                } catch (qrError) {
                    console.warn('QR code generation failed:', qrError);
                    qrContainer.innerHTML = '<p style="color: var(--text-muted); font-size: 0.875rem;">QR code unavailable. Use the secret below.</p>';
                }
            }

            this.hideModal('create-room-modal');
            this.showModal('room-created-modal');

            // Refresh rooms list
            nameInput.value = '';
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
        container.innerHTML = '<p class="loading">Loading tokens...</p>';

        try {
            const data = await this.apiRequest('/api/auth/tokens');
            this.tokens = data.tokens || [];
            this.renderTokens();
        } catch (e) {
            console.error('Failed to load tokens:', e);
            container.innerHTML = `<p class="error">Failed to load tokens: ${e.message}</p>`;
        }
    }

    renderTokens() {
        const container = document.getElementById('tokens-list');

        if (this.tokens.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No tokens yet</h3>
                    <p>Create a token to authenticate workers.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.tokens.map(token => `
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title">${token.worker_name}</div>
                        <div class="card-subtitle">Room: ${token.room_id}</div>
                    </div>
                    <div class="card-actions">
                        ${!token.revoked_at ? `
                            <button class="btn btn-danger btn-small" onclick="app.handleRevokeToken('${token.token_id}')">Revoke</button>
                        ` : ''}
                    </div>
                </div>
                <div class="card-meta">
                    <span>
                        <span class="badge ${token.revoked_at ? 'badge-danger' : 'badge-success'}">
                            ${token.revoked_at ? 'Revoked' : 'Active'}
                        </span>
                    </span>
                    <span>Created: ${new Date(token.created_at).toLocaleDateString()}</span>
                    ${token.expires_at ? `<span>Expires: ${new Date(token.expires_at).toLocaleDateString()}</span>` : ''}
                </div>
            </div>
        `).join('');
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
            document.getElementById('new-token-room').textContent = data.room_id;
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
}

// Initialize app
const app = new SleapRTCDashboard();
