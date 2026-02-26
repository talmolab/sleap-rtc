# Add GitHub OAuth Authentication

## Why

The current anonymous Cognito authentication provides no user identity, access control, or token management. Users cannot create persistent rooms, manage worker access, or revoke compromised credentials. This limits SLEAP-RTC to trusted network deployments only.

## What Changes

### Signaling Server (webRTC-connect repo)
- **BREAKING**: Remove `/anonymous-signin` endpoint
- Add GitHub OAuth callback endpoint (`/api/auth/github/callback`)
- Add worker token CRUD endpoints (`/api/auth/token`, `/api/auth/tokens`)
- Add room management endpoints (`/api/auth/rooms`, `/api/auth/rooms/:id/invite`)
- Modify WebSocket `handle_register()` to accept API keys for workers
- Add three new DynamoDB tables: `sleap_users`, `sleap_worker_tokens`, `sleap_room_memberships`

### SLEAP-RTC Client Library
- Add CLI commands: `login`, `logout`, `whoami`
- Add CLI commands: `token create`, `token list`, `token revoke`
- Add CLI commands: `room list`, `room invite`, `room join`
- Add credential file management (`~/.sleap-rtc/credentials.json`)
- Modify worker to accept `--token slp_xxx` for API key auth

### Worker P2P Authentication
- Add TOTP validation module using `pyotp`
- Add `AUTH_REQUIRED`, `AUTH_RESPONSE`, `AUTH_SUCCESS`, `AUTH_FAILURE` DataChannel messages
- Worker challenges client with OTP before accepting commands

### GitHub Pages Dashboard
- Static site for GitHub OAuth login flow
- Token generation UI with QR codes for authenticator apps
- Token management (list, revoke)
- Room management UI

## Impact

- **Affected repos**: `sleap-RTC`, `webRTC-connect`
- **Affected code**:
  - `sleap_rtc/cli.py` - New auth commands
  - `sleap_rtc/worker/state_manager.py` - API key auth
  - `sleap_rtc/worker/worker_class.py` - TOTP validation in DataChannel
  - `sleap_rtc/client/client_class.py` - OTP entry flow
  - `sleap_rtc/protocol.py` - AUTH_* message types
  - `webRTC_external/server.py` - OAuth endpoints, API key validation
- **New dependencies**: `pyotp` (TOTP validation)
- **Breaking changes**: Anonymous authentication will be removed; existing workers must use new API key auth
