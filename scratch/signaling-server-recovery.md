# Signaling Server Recovery Guide

Last updated: 2026-03-19

## Infrastructure

- **EC2 region:** us-west-1
- **Elastic IP:** 52.9.213.137
- **Domain:** signaling.sleap.ai (behind Cloudflare, which proxies to the Elastic IP)
- **Instance type:** t3.small (per Terraform config)
- **Security group inbound rules:**
  - 22, TCP, SSH admin access
  - 80, TCP, Caddy ACME challenge
  - 443, TCP, Caddy HTTPS
  - 3478, TCP, TURN/STUN TCP
  - 3478, UDP, TURN/STUN UDP
  - 8001, TCP, HTTP API
  - 8080, TCP, WebSocket Signaling
  - 8081, TCP, Relay server SSE
  - 49152-65535, UDP, TURN relay ports

## What can kill the instance

Merging a PR to `main` in `webRTC-connect` that includes changes to `terraform/**` files will trigger the `terraform-deploy-dev.yml` workflow, which runs `terraform apply` and may recreate the EC2 instance. **Check PR file changes before merging.** PRs that only touch `webRTC_external/` are safe.

This happened on 2026-03-18 when PR #29 was merged — it included `terraform/modules/signaling-server/main.tf` changes which triggered instance replacement.

## Full recovery steps (start to finish)

### 1. Launch a new EC2 instance

If Terraform created one automatically, use that. Otherwise launch a `t3.small` in `us-west-1` with Ubuntu and the same security group.

### 2. Reassociate the Elastic IP

1. AWS Console → EC2 → Elastic IPs
2. Find `52.9.213.137`
3. If associated with a terminated instance: Actions → Monitor and troubleshoot → Disassociate Elastic IP address
4. Select it → Actions → Associate Elastic IP address → choose new instance → **allow reassociation**
5. Verify: `curl -s http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8001/health` (won't work yet until Docker is running)

### 3. Install Docker (if not already installed)

```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu
```

### 4. Start the signaling server container

```bash
sudo docker pull ghcr.io/talmolab/webrtc-server:linux-amd64-test

sudo docker run -d --name sleap-rtc-signaling \
  --restart unless-stopped \
  -p 8080:8080 -p 8081:8081 -p 8001:8001 \
  -e GITHUB_CLIENT_ID='Ov23liThtdK2nvPctNXU' \
  -e GITHUB_CLIENT_SECRET='<secret>' \
  -e SLEAP_JWT_PRIVATE_KEY='<private_key>' \
  -e SLEAP_JWT_PUBLIC_KEY='<public_key>' \
  ghcr.io/talmolab/webrtc-server:linux-amd64-test
```

**Note:** The JWT keys use `|` as newline separators in the env var values. Get the actual values from the previous `docker run` command in shell history or from a secure secrets store.

Verify:
```bash
curl -s http://localhost:8001/health
# Expected: {"status":"healthy","timestamp":"...","version":"2.0.0"}
```

### 5. Install and configure Caddy

Caddy is required because Cloudflare connects to the origin via HTTPS (port 443). Caddy terminates TLS and proxies to the Docker container's ports.

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

Replace `/etc/caddy/Caddyfile` with:

```
signaling.sleap.ai {
    tls internal
    reverse_proxy /health localhost:8001
    reverse_proxy /metrics localhost:8001
    reverse_proxy /api/* localhost:8001
    reverse_proxy /delete-peer localhost:8001
    reverse_proxy /delete-peers-and-room localhost:8001
    reverse_proxy /create-room localhost:8001
    reverse_proxy /anonymous-signin localhost:8001

    handle_path /relay/* {
        reverse_proxy localhost:8081
    }

    reverse_proxy localhost:8080
}
```

Key details:
- `tls internal` uses Caddy's internal CA (self-signed cert). This works because Cloudflare's SSL mode is "Full" (not "Full Strict").
- Let's Encrypt won't work because Cloudflare intercepts the ACME HTTP-01 challenge.
- `handle_path /relay/*` strips the `/relay` prefix before proxying — the relay server's routes are `/stream/{channel}` and `/publish/{channel}`, not `/relay/stream/...`.
- All API paths (`/api/*`, `/delete-peer`, `/health`, etc.) go to port 8001 (FastAPI HTTP server).
- Default route (`/`) goes to port 8080 (WebSocket signaling server).

Start Caddy:
```bash
sudo systemctl restart caddy
sudo journalctl -u caddy --no-pager -n 10  # check for errors
```

### 6. Verify everything works

```bash
# Local health check
curl -s http://localhost:8001/health

# External health check (through Cloudflare + Caddy)
curl -s https://signaling.sleap.ai/health

# WebSocket reachable
curl -s http://localhost:8080/
# Expected: "Failed to open a WebSocket connection: missing Connection header."

# Relay reachable
curl -s http://localhost:8081/health

# Check pings are being sent (wait 35s after a worker connects)
sudo docker logs sleap-rtc-signaling 2>&1 | grep -i ping
```

## Traffic path

```
Client/Worker → Cloudflare (signaling.sleap.ai:443) → EC2 Elastic IP:443 → Caddy (TLS termination) → Docker (8080/8001/8081)
```

## Route mapping

| External path | Caddy proxies to | Service |
|---------------|------------------|---------|
| `/` (WebSocket) | localhost:8080 | Signaling WebSocket server |
| `/health` | localhost:8001 | HTTP API health check |
| `/metrics` | localhost:8001 | HTTP API metrics |
| `/api/*` | localhost:8001 | HTTP API (auth, rooms, jobs, etc.) |
| `/delete-peer` | localhost:8001 | Peer cleanup API |
| `/delete-peers-and-room` | localhost:8001 | Room cleanup API |
| `/create-room` | localhost:8001 | Room creation API |
| `/anonymous-signin` | localhost:8001 | Anonymous auth API |
| `/relay/*` | localhost:8081 (prefix stripped) | Relay SSE server |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `curl https://signaling.sleap.ai` times out | Caddy not running or port 443 not open | Check `sudo systemctl status caddy` and security group |
| Health check returns 502 | Docker container not running | `sudo docker ps` then restart if needed |
| CORS errors on dashboard | Caddy adding duplicate CORS headers | Don't add CORS in Caddyfile — the API server and relay handle their own CORS |
| Let's Encrypt cert fails | Cloudflare intercepts ACME challenge | Use `tls internal` instead |
| Dashboard file browser empty | `/relay/*` not using `handle_path` | Must use `handle_path /relay/*` to strip prefix |
| Worker connects but dashboard shows 0 | Elastic IP not associated with current instance | Reassociate in AWS console |
