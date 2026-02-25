## Why

After removing OTP in Phase 1, the system relies entirely on the signaling server for authentication: JWT for client identity, API keys for worker identity, and room membership for authorization. If the signaling server is compromised, an attacker can impersonate any peer.

Pre-shared key (PSK) P2P authentication adds a zero-trust layer: workers challenge clients over the WebRTC data channel using a secret the signaling server never sees. This matches the blog-style pattern where the out-of-band secret distribution (shared filesystem, env var, config file) keeps the trust anchor outside the server.

## What Changes

### 1. Room secret generation
- Dashboard generates secrets client-side (browser crypto, never sent to server)
- CLI command `sleap-rtc room create-secret` generates secrets for headless workflows
- Secrets are 256-bit random values, displayed as base64

### 2. Secret distribution
- **Shared filesystem**: `/path/to/.sleap-rtc/room-secrets/<room_id>` — zero friction for HPC/NAS setups
- **Environment variable**: `SLEAP_ROOM_SECRET` — for RunAI, Docker, CI/CD
- **CLI flag**: `--room-secret` — manual one-time setup
- **Credentials file**: `~/.sleap-rtc/credentials.json` under `room_secrets` key — persistent per-room storage

### 3. P2P challenge-response protocol
- After WebRTC data channel opens, worker sends `AUTH_CHALLENGE::{nonce}` (32-byte random)
- Client computes `HMAC-SHA256(secret, nonce)` and responds with `AUTH_RESPONSE::{hmac}`
- Worker verifies HMAC; on success sends `AUTH_SUCCESS`, on failure sends `AUTH_FAILURE`
- Commands are rejected until auth succeeds

### 4. Secret persistence in credentials
- Secrets saved to credentials file after first successful use (or explicit save command)
- CLI reads secret from credentials if not provided via flag/env/filesystem
- Eliminates repeated secret entry

### 5. Worker-side secret configuration
- Worker loads secret from `--room-secret` flag, `SLEAP_ROOM_SECRET` env var, or config file
- Secret is required if present; workers without secrets accept unauthenticated clients (backward compat during migration)

## Impact

- Affected specs: `authentication`
- Affected code (sleap-rtc):
  - `sleap_rtc/protocol.py` — add `MSG_AUTH_CHALLENGE`, `MSG_AUTH_RESPONSE`, `MSG_AUTH_SUCCESS`, `MSG_AUTH_FAILURE`
  - `sleap_rtc/worker/worker_class.py` — challenge clients on data channel open
  - `sleap_rtc/client/client_class.py` — respond to challenges
  - `sleap_rtc/client/client_track_class.py` — same
  - `sleap_rtc/rtc_browse.py` — same
  - `sleap_rtc/auth/credentials.py` — add `room_secrets` storage
  - `sleap_rtc/auth/psk.py` — new module for HMAC operations
  - `sleap_rtc/cli.py` — add `room create-secret`, `--room-secret` flags
  - `sleap_rtc/tui/` — wire secret from credentials or prompt
- Affected code (dashboard):
  - `dashboard/app.js` — add client-side secret generation UI
  - `dashboard/index.html` — add "Room Secret" section
- No signaling server changes (secret never touches server)
- **Backward compatible**: Workers without secrets continue to work; adding secrets is opt-in per room
