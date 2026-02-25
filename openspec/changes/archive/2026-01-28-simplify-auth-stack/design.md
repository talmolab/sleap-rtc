## Context

PRs #32–#34 introduced GitHub OAuth, JWT authentication, and a management dashboard. These additions made two older auth mechanisms — Cognito anonymous signin and P2P TOTP — redundant. Both remain as fallback/legacy code with deprecation warnings. This change removes them to simplify the auth stack before further feature work.

Detailed rationale is documented in `scratch/2026-01-27-otp-removal-case/README.md`.

## Goals / Non-Goals

**Goals:**
- Remove Cognito anonymous signin (dead code path)
- Remove P2P TOTP authentication (redundant with JWT + room membership)
- Clean up CLI flags made vestigial by these removals
- Simplify the credential file schema
- Reduce dashboard UI to reflect the simplified auth model

**Non-Goals:**
- Zero-trust signaling server architecture (Phase 2)
- Moving API key validation to P2P layer (Phase 2)
- Self-hostable signaling server (Phase 3)
- Adding new auth features (token scoping, session management)

## Decisions

### Decision 1: JWT is the only client auth path

Remove `--no-jwt` and `--use-jwt` flags entirely. All client commands require a valid JWT from `sleap-rtc login`. This eliminates the dual Cognito/JWT code paths.

**Alternative considered:** Keep `--no-jwt` for backward compatibility with a longer deprecation period. Rejected because the flag already prints a deprecation warning and no known users depend on Cognito-only auth after the login command was introduced.

### Decision 2: Remove OTP entirely rather than making it optional

Delete all TOTP code rather than adding an `--enable-otp` opt-in flag. The auto-resolve mechanism (storing OTP secrets in the same credentials file as JWTs) reduces OTP to single-factor auth. The signaling server generating and storing the secret means it provides no zero-trust benefit.

**Alternative considered:** Make OTP opt-in for high-security deployments. Rejected because the current OTP implementation doesn't achieve zero-trust (server holds the secret), so offering it as a "security" option would be misleading. A proper zero-trust P2P auth layer is a Phase 2 concern.

### Decision 3: Workers skip auth challenge on data channel open

After OTP removal, workers accept commands immediately when the data channel opens. The security boundary moves entirely to the signaling server layer: only clients with valid JWTs and room membership can reach workers. This matches the security model of comparable tools (Tailscale, ngrok, Fly.io).

### Decision 4: Credential file drops otp_secrets

The `~/.sleap-rtc/credentials.json` schema changes from:
```json
{
  "jwt": "...",
  "user": { "id": "...", "username": "..." },
  "tokens": {
    "room_id": { "api_key": "slp_xxx", "otp_secret": "BASE32..." }
  }
}
```
to:
```json
{
  "jwt": "...",
  "user": { "id": "...", "username": "..." },
  "tokens": {
    "room_id": { "api_key": "slp_xxx" }
  }
}
```
Existing credentials files with `otp_secret` fields are silently ignored (no migration needed — the field just becomes unused).

### Decision 5: DynamoDB schema — leave OTP fields as unused

Rather than running a schema migration to remove `otp_secret` from the `rooms` and `sleap_worker_tokens` tables, the server code simply stops reading/writing those fields. DynamoDB is schemaless, so unused fields cause no harm and existing records expire via TTL.

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Users on `--no-jwt` break | Clients that haven't run `sleap-rtc login` will fail | Clear error message directing to `sleap-rtc login`; release notes documenting the breaking change |
| OTP removal reduces defense-in-depth | Compromised signaling server grants room access | JWT + room membership still gate access; DTLS encrypts transport; Phase 2 addresses zero-trust |
| Flag removal is a breaking CLI change | Scripts using `--otp-secret` or `--no-jwt` break | Flags removed cleanly (Click will error on unknown flags); release notes document migration |

## Migration Plan

1. Remove Cognito code and flags — single PR
2. Remove OTP code and flags — same or immediately following PR
3. Clean up CLI flags — same PR if scope is manageable
4. Update dashboard — remove OTP tab and QR generation
5. Update signaling server — stop generating/storing OTP secrets
6. Release with clear migration notes: "Run `sleap-rtc login` if you haven't already"

Rollback: Revert the PR. No data migration is needed in either direction since DynamoDB fields are just ignored, not deleted.

## Open Questions

None for Phase 1. Phase 2 questions (zero-trust P2P auth, key distribution) are deferred and documented in the scratch investigation.
