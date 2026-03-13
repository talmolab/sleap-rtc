// SLEAP-RTC Dashboard Configuration
// Edit these values for your deployment

const CONFIG = {
    // GitHub OAuth App Client ID
    // Create one at: https://github.com/settings/applications/new
    GITHUB_CLIENT_ID: 'Ov23liThtdK2nvPctNXU',

    // Signaling server HTTP API URL
    // Production: https://signaling.sleap.ai (via Caddy reverse proxy)
    // Development: http://localhost:8001
    SIGNALING_SERVER: 'https://signaling.sleap.ai',

    // Relay server URL (SSE fanout for training logs and filesystem responses)
    // Production: https://signaling.sleap.ai/relay (via Caddy reverse proxy)
    // Development: http://localhost:8081
    RELAY_SERVER: 'https://signaling.sleap.ai/relay',

    // OAuth callback URL (this dashboard's URL + /callback.html)
    // For GitHub Pages: https://yourusername.github.io/sleap-RTC/dashboard/callback.html
    // For local dev: http://localhost:8000/callback.html
    OAUTH_CALLBACK_URL: window.location.origin + window.location.pathname.replace(/[^/]*$/, '') + 'callback.html',

    // localStorage keys
    STORAGE_KEYS: {
        JWT: 'sleap_rtc_jwt',
        USER: 'sleap_rtc_user',
    }
};

// Freeze config to prevent accidental modification
Object.freeze(CONFIG);
Object.freeze(CONFIG.STORAGE_KEYS);
