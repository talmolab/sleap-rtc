## Why

The auth stack currently has three overlapping mechanisms: GitHub OAuth (JWT), Cognito anonymous signin (legacy), and P2P TOTP (OTP). Cognito is fully redundant since PR #32 introduced GitHub OAuth — it exists only as a fallback with deprecation warnings. OTP is security theater: the signaling server generates and stores the secret, auto-resolve stores it alongside the JWT, so compromising one compromises both. These layers add complexity (dual code paths, extra CLI flags, confusing documentation) without meaningful security benefit.

Removing both simplifies the auth model to two clean layers: **identity** (JWT via GitHub OAuth) and **authorization** (room membership for clients, API keys for workers), plus WebRTC's built-in DTLS encryption.

## What Changes

### 1. Remove Cognito anonymous signin
- **BREAKING**: Remove `--no-jwt` flag from `client-train`, `client-track`, `browse`, `resolve-paths`
- Remove `--use-jwt` flag (JWT becomes the only path, flag is meaningless)
- Delete `request_anonymous_signin()` in `worker/state_manager.py`
- Delete Cognito fallback code in all client commands
- Make JWT authentication required for all client commands
- Remove deprecation warning logic (nothing to deprecate anymore)

### 2. Remove P2P TOTP (OTP)
- **BREAKING**: Remove `--otp-secret` flag from `client-train`, `client-track`, `browse`
- Delete `AUTH_REQUIRED`, `AUTH_RESPONSE`, `AUTH_SUCCESS`, `AUTH_FAILURE` protocol messages
- Delete worker-side OTP validation (`_validate_otp()`, auth challenge on data channel open)
- Delete client-side OTP handling (auto-resolve, manual prompt, stored secrets)
- Delete TUI OTP input screen (`tui/screens/otp_input.py`)
- Delete `sleap_rtc/auth/totp.py` if solely OTP-related
- Remove OTP secret from credential file schema
- Remove OTP secret from token creation API response
- Remove OTP QR code generation from dashboard
- Remove "Verify OTP" tab from dashboard

### 3. Clean up signaling server
- Stop generating OTP secrets on room creation
- Stop storing OTP secrets in rooms table
- Stop sending OTP secrets in `registered_auth` to workers
- Remove `/verify-otp` endpoint
- Remove OTP-related fields from token creation

### 4. Clean up CLI flag naming
- Standardize `--room` vs `--room-id` (pick one, alias the other)
- Remove vestigial `--token` flag where replaced by JWT + room membership

## Impact

- Affected specs: `authentication`, `cli`
- Affected code (sleap-rtc):
  - `sleap_rtc/cli.py` — remove 6+ flags (`--no-jwt`, `--use-jwt`, `--otp-secret` x3)
  - `sleap_rtc/worker/worker_class.py` — remove OTP validation, auth challenge
  - `sleap_rtc/client/client_class.py` — remove Cognito fallback, OTP handling
  - `sleap_rtc/client/client_track_class.py` — same
  - `sleap_rtc/rtc_browse.py` — remove Cognito fallback, OTP handling
  - `sleap_rtc/rtc_resolve.py` — remove Cognito fallback
  - `sleap_rtc/rtc_client.py` — remove `otp_secret` parameter
  - `sleap_rtc/rtc_client_track.py` — remove `otp_secret` parameter
  - `sleap_rtc/auth/credentials.py` — remove OTP storage functions
  - `sleap_rtc/auth/totp.py` — delete if OTP-only
  - `sleap_rtc/protocol.py` — remove auth protocol messages
  - `sleap_rtc/tui/` — remove OTP screen, OTP wiring in app/bridge/browser
  - `sleap_rtc/worker/state_manager.py` — remove anonymous signin
- Affected code (signaling server):
  - `webRTC-connect/webRTC_external/server.py` — remove OTP generation, storage, endpoint
- Affected code (dashboard):
  - `dashboard/app.js` — remove OTP tab, QR generation
  - `dashboard/index.html` — remove OTP UI section
- **Breaking changes**: Users relying on `--no-jwt` (Cognito) or `--otp-secret` flags must switch to JWT auth via `sleap-rtc login`. Workers no longer challenge clients with OTP.
