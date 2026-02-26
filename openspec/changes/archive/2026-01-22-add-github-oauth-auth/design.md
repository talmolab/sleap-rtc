# Design: GitHub OAuth Authentication

## Context

SLEAP-RTC currently uses anonymous AWS Cognito authentication which provides no user identity or access control. The signaling server at `webRTC-connect/webRTC_external/server.py` already has infrastructure for JWT validation (RS256) and DynamoDB access, making it straightforward to add proper authentication.

**Stakeholders:**
- Researchers using SLEAP-RTC for remote training
- Lab administrators managing GPU workers
- Security-conscious deployments requiring access control

**Constraints:**
- Must work with Docker workers (no browser access)
- GitHub Pages hosting for dashboard (no server-side code)
- Existing signaling server infrastructure should be reused

## Goals / Non-Goals

### Goals
- User authentication via GitHub OAuth
- Worker authorization via API keys
- Peer-to-peer verification via TOTP
- Token revocation capability
- Room-based access control

### Non-Goals
- Multi-factor authentication for web login (GitHub handles this)
- Fine-grained permissions within rooms
- Audit logging (can be added later)
- Rate limiting (can be added later)

## Decisions

### Decision 1: Two-Layer Authentication Model

**Choice:** API keys for signaling server access + TOTP for P2P verification

**Rationale:** Even if the signaling server is compromised, attackers cannot control workers without valid OTP codes. This defense-in-depth approach protects against:
- Stolen API keys (need authenticator app)
- Signaling server breach (P2P auth is independent)
- Man-in-the-middle on WebRTC setup (OTP required after connection)

**Alternatives considered:**
- API key only: Simpler but single point of failure
- mTLS: Complex certificate management, doesn't fit Docker UX
- SSH-style keys: Requires key exchange infrastructure

### Decision 2: RS256 for JWT Signing

**Choice:** RS256 (asymmetric) instead of HS256 (symmetric)

**Rationale:**
- Signaling server already uses RS256 for Cognito tokens (`server.py:80`)
- GitHub Pages dashboard can verify JWTs without storing secrets
- Multiple services can verify tokens independently
- Public key can be distributed safely

**Alternatives considered:**
- HS256: Faster but requires secret sharing; dashboard couldn't verify tokens

### Decision 3: GitHub OAuth (not custom credentials)

**Choice:** GitHub as sole identity provider

**Rationale:**
- Target users already have GitHub accounts (researchers, developers)
- No password management burden
- GitHub handles MFA, security, recovery
- Simple integration with GitHub Pages hosting

**Alternatives considered:**
- Custom username/password: Security burden, password storage risks
- Multiple OAuth providers: Complexity without clear benefit
- ORCID OAuth: Narrower user base

### Decision 4: Token Format

**API Key Format:** `slp_` + 32 characters URL-safe base64
- Example: `slp_dGhpcyBpcyBhIHRlc3QgdG9rZW4gZm9y`
- Prefix enables easy identification in logs/configs
- URL-safe for use in query params if needed

**OTP Secret Format:** Base32-encoded 160-bit (32 characters)
- Example: `JBSWY3DPEHPK3PXP4WTNKFQW5ZJMHQ2T`
- Compatible with Google Authenticator, 1Password, Authy

### Decision 5: DynamoDB Table Design

**Choice:** Three new tables with GSIs for common query patterns

```
sleap_users (PK: user_id)
├── GSI: username-index

sleap_worker_tokens (PK: token_id)
├── GSI: user_id-index
├── GSI: room_id-index

sleap_room_memberships (PK: user_id, SK: room_id)
├── GSI: room_id-index
```

**Rationale:**
- Single-table design rejected: Query patterns are distinct enough
- Existing `rooms` table kept separate: Maintains backward compatibility during migration

## Risks / Trade-offs

### Risk: GitHub OAuth dependency
- **Impact:** If GitHub is down, no new logins
- **Mitigation:** JWTs remain valid for 7 days; existing sessions continue working

### Risk: OTP secret compromise
- **Impact:** Attacker with API key + OTP secret can control worker
- **Mitigation:** OTP secret only shown once at creation; stored encrypted in DynamoDB

### Risk: Migration disruption
- **Impact:** Existing workers stop working when Cognito removed
- **Mitigation:** Phase migration - both auth systems work in parallel initially

### Trade-off: UX complexity vs security
- **Choice:** Require OTP for P2P auth
- **Trade-off:** Users must set up authenticator app, enter codes
- **Justification:** Security of GPU resources justifies friction

## Migration Plan

### Phase 1: Add GitHub OAuth (parallel to Cognito)
1. Add new environment variables to signaling server
2. Create DynamoDB tables
3. Add `/api/auth/*` endpoints
4. Deploy - both auth systems work

### Phase 2: Add API Key Auth for Workers
1. Add token generation endpoints
2. Modify `handle_register()` to accept API keys
3. Add CLI commands for token management
4. Workers can use either auth method

### Phase 3: Add TOTP P2P Auth
1. Add `pyotp` dependency
2. Implement DataChannel auth protocol
3. Update worker to challenge clients
4. Update client to send OTP

### Phase 4: Remove Cognito
1. Remove `/anonymous-signin` endpoint
2. Remove Cognito environment variables
3. Update documentation
4. All auth through new system

### Rollback
- Each phase can be rolled back independently
- Phase 4 rollback: Re-add Cognito endpoint, set env vars
- Database changes are additive (no destructive migrations)

## Open Questions

1. **Token rotation:** Should long-running workers auto-rotate tokens?
   - Current answer: No, keep simple. Manual revoke + new token if needed.

2. **Room creation limits:** Should users have a max number of rooms?
   - Current answer: No limits initially. Add if abuse occurs.

## References

- Investigation docs: `scratch/2026-01-15-authflow-investigation/`
- Signaling server: `webRTC-connect/webRTC_external/server.py`
- Existing auth: `sleap_rtc/worker/state_manager.py:60-110`
