## Context

With OTP removed (Phase 1), authentication relies entirely on the signaling server. This is fine for labs that trust the server, but creates a single point of compromise for third-party users. The goal is a zero-trust P2P layer where the signaling server only routes connections — it cannot impersonate peers because it never sees the authentication secret.

**Stakeholders**: Lab administrators (set up secrets), researchers (use CLI/TUI), CI/CD pipelines (headless).

**Constraints**:
- Must work with shared filesystems (common in HPC setups)
- Must work headless (env vars, config files)
- Must not require re-entering secrets on every connection
- Must be backward compatible (existing workers without secrets continue to function)

## Goals / Non-Goals

**Goals**:
- Worker can verify client knows the room secret before accepting commands
- Secret never touches the signaling server
- Multiple distribution mechanisms (filesystem, env, CLI, credentials file)
- Secrets persist in credentials file for convenience

**Non-Goals**:
- Mutual authentication (client verifying worker) — can add later if needed
- Key rotation automation — manual process is acceptable for v1
- Revoking individual secrets — regenerate and redistribute instead
- Integration with external secret managers (Vault, etc.)

## Decisions

### Decision: HMAC-SHA256 challenge-response

**What**: Worker generates random nonce, client proves knowledge of secret by computing `HMAC-SHA256(secret, nonce)`.

**Why**: Simple, proven, no state beyond the shared secret. HMAC prevents replay attacks (nonce is fresh each time). SHA256 is universally available in Python stdlib (`hmac` module) and browser (`SubtleCrypto`).

**Alternatives considered**:
- **TOTP**: Already removed; same replay window issues, more complex (time sync).
- **SRP (Secure Remote Password)**: Stronger (zero-knowledge), but much more complex to implement correctly.
- **Public key signatures**: Requires key pair management per machine; overkill for shared-secret model.

### Decision: 256-bit secrets (32 bytes, base64-encoded)

**What**: Secrets are 32 bytes of cryptographically random data, displayed as 44-character base64 strings.

**Why**: 256 bits is standard for symmetric keys (AES-256 level). Base64 is copy-paste friendly and works in env vars, JSON, CLI flags.

**Alternatives considered**:
- **Shorter secrets** (e.g., 128-bit): Sufficient cryptographically but looks less serious to users.
- **Hex encoding**: Longer strings (64 chars vs 44), no benefit.
- **Passphrase-based**: Human-memorable but weaker; SLEAP is machine-to-machine.

### Decision: One-way authentication (worker challenges client)

**What**: Only the worker challenges the client. The client does not challenge the worker.

**Why**: Protects against unauthorized clients sending commands to workers. The main threat is someone with network access (but not the secret) trying to control a worker. Mutual auth would also protect against a fake worker, but that requires the signaling server to be compromised AND the attacker to intercept the WebRTC connection — a more sophisticated attack that's out of scope for v1.

**Trade-offs**:
- One-way is simpler and sufficient for the "untrusted client" threat.
- Mutual auth can be added later without breaking changes (worker just also responds to a client challenge).

### Decision: Secret lookup order

**What**: When connecting, client looks for secret in this order:
1. `--room-secret` CLI flag
2. `SLEAP_ROOM_SECRET` environment variable
3. Shared filesystem path (`~/.sleap-rtc/room-secrets/<room_id>` or configured path)
4. Credentials file (`~/.sleap-rtc/credentials.json` → `room_secrets.<room_id>`)

**Why**: CLI flag is highest priority (explicit override), env var is standard for containers, filesystem supports HPC shared mounts, credentials file is fallback for convenience.

### Decision: Backward compatibility via optional secrets

**What**: Workers without a configured secret accept all clients (current behavior). Workers with a secret require clients to authenticate.

**Why**: Allows gradual rollout. Labs can enable PSK per-room as they're ready. No forced migration.

**Migration path**:
1. Upgrade sleap-rtc (new code, secrets disabled)
2. Generate secret for a room via dashboard or CLI
3. Distribute secret to workers and clients
4. Workers with secret start requiring auth
5. Repeat per room

## Protocol Specification

```
Connection established (WebRTC data channel open):

    Worker                              Client
    ──────                              ──────
    [has secret configured?]
    │
    ├─ No secret → accept commands immediately (legacy mode)
    │
    └─ Has secret:
         generate nonce (32 bytes random)
         send AUTH_CHALLENGE::{base64(nonce)}  →
                                               [has secret?]
                                               │
                                               ├─ No secret → close connection
                                               │
                                               └─ Has secret:
                                                    hmac = HMAC-SHA256(secret, nonce)
                                            ←      send AUTH_RESPONSE::{base64(hmac)}
         verify HMAC
         │
         ├─ Valid:
         │    send AUTH_SUCCESS              →
         │    accept commands
         │
         └─ Invalid:
              send AUTH_FAILURE::invalid     →
              close connection (no retries for PSK)
```

### Message Formats

| Message | Format | Direction |
|---------|--------|-----------|
| `AUTH_CHALLENGE` | `AUTH_CHALLENGE::{base64_nonce}` | Worker → Client |
| `AUTH_RESPONSE` | `AUTH_RESPONSE::{base64_hmac}` | Client → Worker |
| `AUTH_SUCCESS` | `AUTH_SUCCESS` | Worker → Client |
| `AUTH_FAILURE` | `AUTH_FAILURE::{reason}` | Worker → Client |

Reasons: `invalid` (HMAC mismatch), `timeout` (no response within 10s), `missing` (client has no secret).

### No Retries

Unlike OTP (which allowed 3 retries for typos), PSK auth has no retries. The secret is either correct or not — there's no human entering digits. A mismatch indicates misconfiguration, not a typo.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Secret leaks via logs | Never log secrets; log only "secret configured: yes/no" |
| Secret in shell history | Recommend env vars or config files over CLI flags for production |
| Stale secrets after rotation | Document that clients must update credentials; no automatic invalidation |
| Credential file permissions | Set 600 on credentials.json (already done for JWT) |

## Resolved Questions

1. **Shared filesystem path convention**: Support configurable base path via `SLEAP_SECRET_PATH` env var (defaults to `~/.sleap-rtc/room-secrets/`). This allows HPC labs to point to a shared NAS mount like `/mnt/lab-nas/.sleap-rtc/secrets/` that both workers and clients can read.

2. **Dashboard secret display**: Allow re-display. Since the secret is generated client-side and stored in browser localStorage (never sent to the signaling server), a compromised server cannot access it. The threat model is server compromise, not browser compromise.

3. **TUI secret prompt**: Fail with clear error message and instructions pointing to `sleap-rtc room create-secret` or dashboard. No interactive prompt.
