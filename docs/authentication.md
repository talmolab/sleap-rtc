# SLEAP-RTC Authentication Guide

This document covers authentication mechanisms in SLEAP-RTC, including server-based JWT authentication and optional peer-to-peer PSK authentication.

## Overview

SLEAP-RTC uses a layered authentication approach:

1. **Server Authentication**: JWT tokens authenticate users with the signaling server
2. **Room Access**: Room tokens and memberships control who can join rooms
3. **P2P Authentication (Optional)**: PSK authentication secures direct worker-client communication

## P2P Authentication with Pre-Shared Keys (PSK)

PSK authentication adds an additional security layer for peer-to-peer communication. When enabled, workers challenge connecting clients to prove they possess a shared secret before accepting any commands.

### When to Use PSK Authentication

**Recommended for:**
- Production deployments with sensitive data
- Multi-tenant environments
- Compliance requirements (data isolation)
- Networks where you want defense-in-depth

**Optional for:**
- Development and testing
- Single-user deployments
- Trusted internal networks

### Generating a Room Secret

#### Option 1: CLI Command (Recommended)

```bash
# Generate and save to credentials file
sleap-rtc room create-secret --room <room_id>

# Generate and save to credentials file (explicit)
sleap-rtc room create-secret --room <room_id> --save

# Generate without saving (display only)
sleap-rtc room create-secret --room <room_id> --no-save
```

#### Option 2: Dashboard

1. Log in to the SLEAP-RTC dashboard
2. Navigate to the Rooms tab
3. Click the "Secret" button on your room
4. Click "Generate Secret"
5. Copy the displayed secret

#### Option 3: Manual Generation

Generate a 32-byte random secret using any secure method:

```bash
# Using OpenSSL
openssl rand -hex 32

# Using Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Distributing the Secret

The secret must be available to both the worker and all clients that will connect. Choose a distribution method based on your environment:

#### Method 1: CLI Flag

Pass the secret directly on the command line:

```bash
# Worker
sleap-rtc worker --room-id <room_id> --token <token> --room-secret <secret>

# Client
sleap-rtc train --room <room_id> --room-secret <secret> --pkg-path package.zip
```

**Pros:** Simple, explicit
**Cons:** Secret visible in process list, shell history

#### Method 2: Environment Variable

Set the secret as an environment variable:

```bash
# Room-specific variable (recommended)
export SLEAP_RTC_ROOM_SECRET_<ROOM_ID>=<secret>

# Example for room "abc-123-def"
export SLEAP_RTC_ROOM_SECRET_ABC_123_DEF=<secret>

# Then run without --room-secret flag
sleap-rtc worker --room-id abc-123-def --token <token>
```

**Pros:** Not visible in process list, works with containers
**Cons:** Must set before starting process

#### Method 3: Filesystem

Store the secret in a file:

```bash
# Create the secrets directory
mkdir -p ~/.sleap-rtc/secrets

# Store the secret (one file per room)
echo "<secret>" > ~/.sleap-rtc/secrets/<room_id>

# Set permissions (important!)
chmod 600 ~/.sleap-rtc/secrets/<room_id>
```

**Pros:** Persistent, easy to manage multiple rooms
**Cons:** Must secure filesystem access

#### Method 4: Credentials File

Use the CLI to save to the credentials file:

```bash
sleap-rtc room create-secret --room <room_id> --save
```

This stores the secret in `~/.sleap-rtc/credentials.json` under the `room_secrets` key.

**Pros:** Centralized with other credentials
**Cons:** Single file contains all secrets

### Secret Resolution Priority

When a worker or client starts, it looks for the room secret in this order:

1. **CLI flag** (`--room-secret <value>`)
2. **Environment variable** (`SLEAP_RTC_ROOM_SECRET_<ROOM_ID>`)
3. **Filesystem** (`~/.sleap-rtc/secrets/<room_id>`)
4. **Credentials file** (`~/.sleap-rtc/credentials.json` → `room_secrets.<room_id>`)

The first non-empty value found is used. If no secret is found, PSK authentication is disabled (legacy mode).

### Authentication Flow

```
Client                           Worker
   |                                |
   |-- WebRTC Connection Open ----->|
   |                                |
   |<----- AUTH_CHALLENGE(nonce) ---|  (Worker generates random nonce)
   |                                |
   |  (Client computes HMAC)        |
   |                                |
   |-- AUTH_RESPONSE(hmac) -------->|
   |                                |
   |  (Worker verifies HMAC)        |
   |                                |
   |<----- AUTH_SUCCESS ------------|  (or AUTH_FAILURE)
   |                                |
   |== Commands now accepted ======>|
```

### Security Details

- **Algorithm**: HMAC-SHA256
- **Nonce**: 32 bytes, cryptographically random, unique per challenge
- **Secret**: 32 bytes (64 hex characters), cryptographically random
- **Timeout**: 10 seconds to respond to challenge
- **Verification**: Constant-time comparison to prevent timing attacks

### Error Handling

#### Authentication Failed

If the client provides an incorrect secret:

```
ERROR: P2P authentication failed: Invalid credentials
Ensure the room secret matches between worker and client.
```

**Solutions:**
1. Verify the secret is identical on both sides
2. Check for trailing whitespace or newlines
3. Regenerate the secret if compromised

#### Authentication Timeout

If the client doesn't respond within 10 seconds:

```
ERROR: P2P authentication failed: Timeout
```

**Solutions:**
1. Check network connectivity
2. Verify client has the secret configured
3. Check for firewall blocking WebRTC

#### No Secret Configured (Client)

If the worker requires authentication but the client has no secret:

```
ERROR: P2P authentication failed: No secret configured
Configure the room secret using --room-secret, environment variable, or credentials file.
```

### Legacy Mode (No PSK)

If the worker has no secret configured:

1. No `AUTH_CHALLENGE` is sent
2. Client connects immediately
3. Commands are accepted without authentication

This maintains backward compatibility with existing deployments.

### TUI Integration

When using the TUI browser:

1. Configure the secret via CLI: `sleap-rtc tui --room <room_id> --room-secret <secret>`
2. Or set the environment variable before launching
3. Authentication status is shown during connection
4. Clear error messages guide troubleshooting

### Best Practices

1. **Generate unique secrets per room**: Don't reuse secrets across rooms
2. **Rotate secrets periodically**: Especially after team changes
3. **Use filesystem or env vars in production**: Avoid CLI flags in scripts
4. **Set restrictive permissions**: `chmod 600` on secret files
5. **Never commit secrets to version control**: Add to `.gitignore`
6. **Use the same distribution method**: Consistency reduces errors
7. **Document your secret management process**: Team members need to know how to configure

### Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| "Invalid credentials" | Secret mismatch | Verify secret on both sides |
| "Timeout" | Network or missing secret | Check connectivity and config |
| "No secret configured" | Missing client secret | Add secret via CLI/env/file |
| Connection works without secret | Worker has no secret | Configure secret on worker |
| Works locally, fails remotely | Different secret sources | Ensure same secret everywhere |

### Example: Production Setup

```bash
# 1. On the management machine, generate secret
sleap-rtc room create-secret --room production-room --no-save
# Output: Generated secret: a1b2c3d4...

# 2. Store secret securely on worker machine
ssh worker-host "mkdir -p ~/.sleap-rtc/secrets && echo 'a1b2c3d4...' > ~/.sleap-rtc/secrets/production-room && chmod 600 ~/.sleap-rtc/secrets/production-room"

# 3. Store secret on client machines (or use env var in CI/CD)
export SLEAP_RTC_ROOM_SECRET_PRODUCTION_ROOM=a1b2c3d4...

# 4. Start worker (secret auto-loaded from filesystem)
ssh worker-host "sleap-rtc worker --room-id production-room --token <token>"

# 5. Connect client (secret from env var)
sleap-rtc train --room production-room --pkg-path job.zip
```
