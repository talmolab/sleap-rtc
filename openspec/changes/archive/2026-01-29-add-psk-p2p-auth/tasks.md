## 1. Protocol and Core Auth Module

- [ ] 1.1 Add protocol messages to `sleap_rtc/protocol.py`: `MSG_AUTH_CHALLENGE`, `MSG_AUTH_RESPONSE`, `MSG_AUTH_SUCCESS`, `MSG_AUTH_FAILURE`
- [ ] 1.2 Create `sleap_rtc/auth/psk.py` with:
  - `generate_secret()` → 32-byte random, base64-encoded
  - `generate_nonce()` → 32-byte random, base64-encoded
  - `compute_hmac(secret: str, nonce: str) → str` (base64-encoded HMAC-SHA256)
  - `verify_hmac(secret: str, nonce: str, hmac: str) → bool`
- [ ] 1.3 Add unit tests for `psk.py` in `tests/auth/test_psk.py`

## 2. Credentials Storage

- [ ] 2.1 Add `room_secrets` field to credential file schema in `sleap_rtc/auth/credentials.py`
- [ ] 2.2 Add `get_room_secret(room_id: str) → Optional[str]` function
- [ ] 2.3 Add `save_room_secret(room_id: str, secret: str)` function
- [ ] 2.4 Add `remove_room_secret(room_id: str)` function
- [ ] 2.5 Add unit tests for room secret storage in `tests/auth/test_credentials.py`

## 3. Secret Lookup Chain

- [ ] 3.1 Create `sleap_rtc/auth/secret_resolver.py` with `resolve_secret(room_id: str, cli_secret: Optional[str] = None) → Optional[str]` that checks:
  1. CLI flag value (if provided)
  2. `SLEAP_ROOM_SECRET` env var
  3. Filesystem path `~/.sleap-rtc/room-secrets/<room_id>`
  4. Credentials file `room_secrets.<room_id>`
- [ ] 3.2 Add configurable base path via `SLEAP_SECRET_PATH` env var
- [ ] 3.3 Add unit tests for secret resolution in `tests/auth/test_secret_resolver.py`

## 4. Worker-Side Authentication

- [ ] 4.1 Add `_room_secret` field to `WorkerClass` in `sleap_rtc/worker/worker_class.py`
- [ ] 4.2 Load secret from CLI flag, env var, or config on worker init
- [ ] 4.3 Add `_pending_auth` dict to track nonces for pending challenges per peer
- [ ] 4.4 On data channel open: if secret configured, generate nonce and send `AUTH_CHALLENGE`
- [ ] 4.5 Add `_handle_auth_response(peer_id, hmac)` method to verify HMAC
- [ ] 4.6 On success: mark peer as authenticated, send `AUTH_SUCCESS`
- [ ] 4.7 On failure: send `AUTH_FAILURE`, close channel
- [ ] 4.8 Block command processing until peer is authenticated (if secret configured)
- [ ] 4.9 Add timeout task (10s) for pending challenges
- [ ] 4.10 Log authentication events (challenge sent, success, failure) without exposing secrets

## 5. Client-Side Authentication

- [ ] 5.1 Add `_room_secret` field to client classes (`client_class.py`, `client_track_class.py`)
- [ ] 5.2 Use `resolve_secret()` to load secret on client init
- [ ] 5.3 Add `_handle_auth_challenge(nonce)` method to compute and send HMAC response
- [ ] 5.4 Add `_handle_auth_success()` method to mark connection as authenticated
- [ ] 5.5 Add `_handle_auth_failure(reason)` method to handle rejection
- [ ] 5.6 Wire handlers in `on_message()` dispatch

## 6. Browse Module Authentication

- [ ] 6.1 Add secret resolution to `sleap_rtc/rtc_browse.py`
- [ ] 6.2 Wire `AUTH_CHALLENGE`/`AUTH_SUCCESS`/`AUTH_FAILURE` handlers
- [ ] 6.3 Block browse operations until authenticated

## 7. CLI Commands

- [ ] 7.1 Add `sleap-rtc room create-secret [--room-id ROOM] [--save]` command to `sleap_rtc/cli.py`
- [ ] 7.2 Add `--room-secret` flag to `client-train`, `client-track`, `browse`, `resolve-paths` commands
- [ ] 7.3 Add `--room-secret` flag to `worker` command
- [ ] 7.4 Update help text with secret configuration examples

## 8. TUI Integration

- [ ] 8.1 Pass `room_secret` through TUI app → bridge → browser screen
- [ ] 8.2 Wire challenge/response handlers in `sleap_rtc/tui/bridge.py`
- [ ] 8.3 Show authentication status in TUI status bar
- [ ] 8.4 Display clear error on auth failure with instructions

## 9. Dashboard Integration

- [ ] 9.1 Add "Room Secret" section to room settings in `dashboard/index.html`
- [ ] 9.2 Implement client-side secret generation using Web Crypto API in `dashboard/app.js`
- [ ] 9.3 Store generated secret in browser localStorage (keyed by room_id)
- [ ] 9.4 Display secret with copy button; allow re-display from localStorage
- [ ] 9.5 Add help text explaining distribution options (env var, filesystem, credentials file)

## 10. Documentation and Verification

- [ ] 10.1 Update `README.md` with PSK authentication section
- [ ] 10.2 Add `docs/authentication.md` with detailed setup guide
- [ ] 10.3 Manual smoke test: worker with secret challenges client with secret → success
- [ ] 10.4 Manual smoke test: worker with secret challenges client without secret → failure
- [ ] 10.5 Manual smoke test: worker without secret accepts client immediately → success (legacy mode)
- [ ] 10.6 Manual smoke test: secret from env var, filesystem, credentials file each work
- [ ] 10.7 Verify dashboard secret generation works (browser console, copy-paste)
