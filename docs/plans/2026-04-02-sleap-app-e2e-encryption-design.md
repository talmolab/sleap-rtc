# sleap-app E2E Encryption for Relay Transport — Design

## Goal

Add end-to-end encryption to sleap-app's `RelayTransport` so all relay messages between sleap-app (desktop and web) and workers are encrypted, matching the dashboard's encryption from PR #77. The signaling server cannot read message payloads.

## Background

- PR #77 added E2E encryption for the dashboard's relay path (ECDH P-256 + AES-256-GCM)
- Worker-side encryption (`_handle_key_exchange`, `_decrypt_if_encrypted`, `RelayChannel` encryption) is already deployed
- Signaling server already forwards `key_exchange_response` and `encrypted_relay` message types
- sleap-app has a fully working `RelayTransport` class in `src/lib/transport.ts` with REST + SSE
- sleap-app supports both desktop (Tauri) and web (app.sleap.ai) — both use the same TypeScript code

## Architecture

**Approach:** Independent TypeScript implementation of the same crypto operations used by the dashboard. Encryption integrated directly into the existing `RelayTransport` class — transparent to the rest of the app.

**New file:** `src/lib/e2e.ts` (~100 lines) — ECDH P-256 keypair gen, HKDF-SHA256 key derivation, AES-256-GCM encrypt/decrypt. Pure typed functions, no side effects.

**Modified file:** `src/lib/transport.ts` — `RelayTransport` class gets key exchange in `open()`, encrypt in `send()`, decrypt in SSE handler.

**No changes to:** `connectStore.ts`, `inferenceStore.ts`, `trainingStore.ts`, or any UI components. Encryption is invisible to the rest of the app.

**Works on both platforms:** Web Crypto API is native in all browsers and Tauri's WebView (WebKit/Chromium).

**No new dependencies.** Zero npm packages added.

**Crypto parameters (must match Python worker exactly):**
- Curve: P-256 (secp256r1)
- KDF: HKDF-SHA256, no salt, info = `"sleap-rtc-relay-e2e-v1"`
- Cipher: AES-256-GCM, 12-byte nonce
- Public key format: uncompressed point (65 bytes), URL-safe base64 no padding

## Key Exchange Flow

Triggered automatically when `RelayTransport.open()` is called (after WebRTC 10-second timeout fallback).

```
1. RelayTransport.open() called
2. Opens SSE connection to worker:{peerId} channel
3. Generates ephemeral P-256 keypair + sessionId (UUID)
4. Sends key_exchange via POST /api/worker/message:
   { type: "key_exchange", session_id, public_key }
5. Waits for key_exchange_response on SSE (5s timeout, 1 retry)
6. Derives shared AES-256 key via ECDH + HKDF
7. Sets _e2eReady = true
8. All subsequent send/receive is encrypted
```

**Failure handling:** 5-second timeout, retry once, then throw. `connectStore.ts` catches the error and shows "Could not establish secure connection with worker."

**Encryption state:** Private fields on the `RelayTransport` instance (`_sessionId`, `_sharedKey`, `_e2eReady`). Garbage collected when transport is destroyed. No persistence.

**WebRTC path unaffected:** When WebRTC succeeds, `RelayTransport` is never created, key exchange never fires. DTLS handles encryption automatically on the P2P path.

## Code Changes

### New: `src/lib/e2e.ts`

```typescript
generateKeypair(): Promise<{ privateKey: CryptoKey; publicKeyRaw: ArrayBuffer }>
deriveSharedKey(privateKey: CryptoKey, peerPublicKey: ArrayBuffer): Promise<CryptoKey>
encrypt(key: CryptoKey, payload: object): Promise<{ nonce: string; ciphertext: string }>
decrypt(key: CryptoKey, nonce: string, ciphertext: string): Promise<object | null>
publicKeyToB64(raw: ArrayBuffer): string
publicKeyFromB64(b64: string): ArrayBuffer
```

### Modified: `src/lib/transport.ts` — `RelayTransport`

**Private fields added:**
- `_sessionId: string | null`
- `_sharedKey: CryptoKey | null`
- `_e2eReady: boolean`

**`open()` updated:** After opening SSE, calls `_initKeyExchange()`. Transport is not marked ready until key exchange completes.

**`send()` updated:** When `_e2eReady`, all outbound messages are encrypted and routed through `POST /api/worker/message` instead of dedicated endpoints:
- `FS_LIST_DIR` → encrypted `{type: "fs_list_req", path, req_id, offset}`
- `JOB_SUBMIT` → encrypted `{type: "job_assigned", job_id, config}` with client-generated `job_id`
- `JOB_CANCEL` → encrypted `{type: "job_cancel", job_id, mode: "cancel"}`
- `JOB_STOP` → encrypted `{type: "job_cancel", job_id, mode: "stop"}`
- `FS_GET_MOUNTS` → encrypted `{type: "fs_get_mounts"}`
- `CONTROL_COMMAND` → encrypted `{type: "job_cancel", job_id, mode: "stop"}`

**`_handleSSEEvent()` updated:** When receiving `encrypted_relay` events, checks `session_id`, decrypts, then processes the inner message through the existing switch statement.

**`_postJobSubmit()` updated:** When E2E is active, generates `job_id` client-side (`job_${crypto.randomUUID().slice(0,8)}`), sends encrypted via `_sendWorkerMessage`, and opens job SSE channel immediately.

### No changes to other files

`connectStore.ts`, `inferenceStore.ts`, `trainingStore.ts`, and all UI components are untouched. They call `transport.send()` with protocol messages and receive protocol messages back — encryption is invisible.

## Message Flow Comparison

**What the worker's RelayChannel sends (already filtered by PR #77):**

| Message type | Sent during training? | Sent during inference? |
|---|---|---|
| `job_status` (accepted/rejected/complete/failed) | Yes | Yes |
| `job_progress` (train_begin, epoch_end, train_end) | Yes | No |
| `MODEL_TYPE::` switch | Yes | No |
| `TRAIN_JOB_START` / `TRAINING_JOBS_DONE` | Yes | No |
| `INFERENCE_BEGIN/COMPLETE/FAILED` | Yes | Yes |
| `[stderr]` lines | No | Yes |
| `CR::` tqdm progress | No | Yes |
| Catch-all text lines | No | Yes |

All of these will be encrypted as `encrypted_relay` envelopes with the `job_id` in plaintext for SSE channel routing.

## Rollout

**No phased rollout needed.** Worker and signaling server already support encryption (PR #77 + webRTC-connect `amick/relay-server-encryption`). Only the sleap-app frontend changes:
- **Web:** GitHub Pages redeploy → immediate effect
- **Desktop:** next Tauri app release includes encryption automatically

**Backward compatibility:** Workers without PR #77 will cause key exchange timeout → error message shown to user.

## Testing

**Unit tests (`src/lib/e2e.test.ts`):**
- Keypair generation, base64 round-trip, ECDH key derivation, encrypt/decrypt round-trip, wrong key failure

**Integration tests:**
- Mock fetch/SSE, verify key exchange flow, verify `send()` produces encrypted envelopes, verify SSE handler decrypts

**Cross-language test vector:**
- Hardcoded Python-encrypted message → TypeScript decrypts (verifies parameter alignment)

**E2E manual testing:**
- Connect via relay, browse filesystem, submit training/inference, verify worker logs show `[E2E]`, verify signaling server shows `encrypted_relay`
