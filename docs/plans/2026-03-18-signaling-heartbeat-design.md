# Signaling Server Heartbeat Design

## Problem

Cloudflare proxies the WebSocket connection between workers and the signaling server. When the signaling server restarts, Cloudflare keeps the worker-side WebSocket alive and answers TCP-level pings on the server's behalf. The worker thinks it's still connected, never reconnects, and disappears from the dashboard.

## Solution

Server-initiated application-level heartbeat. The signaling server sends `{"type": "ping"}` to every connected peer every 30s. The worker tracks when it last received a ping. If no ping arrives within 90s, the worker closes the WebSocket and triggers the reconnection loop. Cloudflare cannot fake application-level messages.

## Design Decisions

1. **Server-initiated, fire-and-forget**: Server sends pings, worker does not respond. Server detects dead connections when `websocket.send()` fails. Worker detects stale connections by tracking ping timestamps. Half the message volume of ping/pong.
2. **Per-connection ping task**: Each registered peer gets its own background task. No global coordination or locking. Matches the server's existing one-coroutine-per-connection pattern.
3. **90s timeout (3 missed pings)**: Conservative enough to tolerate network hiccups, responsive enough that workers reappear on the dashboard within ~2 minutes of a server restart.
4. **Watchdog is separate from the reader**: The admin handler loop (or handle_connection's message loop) updates a timestamp when a ping arrives. A separate watchdog task checks the timestamp every 30s and closes the websocket if stale. Clean separation of concerns.

## Server Side (webRTC-connect)

In `handle_client()`, after a peer registers, spawn a background task:

```python
async def _ping_loop(websocket, peer_id):
    """Send periodic pings to detect stale connections."""
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send(json.dumps({"type": "ping"}))
    except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
        pass
    except Exception as e:
        logging.warning(f"Ping loop error for {peer_id}: {e}")
```

Started after registration, cancelled in `handle_client`'s `finally` block.

## Worker Side (sleap-rtc)

### Tracking pings

Both message readers (admin handler in `mesh_coordinator.py` and `handle_connection` in `worker_class.py`) handle `{"type": "ping"}`:

```python
if msg_type == "ping":
    self._last_signaling_ping = time.monotonic()
```

### Watchdog task

```python
async def _signaling_heartbeat_watchdog(self):
    """Close websocket if server pings stop arriving."""
    try:
        while not self.shutting_down:
            await asyncio.sleep(30)
            elapsed = time.monotonic() - self._last_signaling_ping
            if elapsed > 90:
                logging.warning(
                    f"No signaling server ping for {int(elapsed)}s — "
                    f"connection presumed stale. Reconnecting..."
                )
                await self.websocket.close()
                return
    except asyncio.CancelledError:
        pass
```

Started in `run_worker` after each successful connection. Cancelled before starting a new one on reconnection.

### Timestamp initialization

`self._last_signaling_ping = time.monotonic()` is set when the websocket connects, giving the server 90s to send its first ping.

## Flow on Server Restart

1. Server dies → pings stop
2. Cloudflare keeps worker-side websocket alive (TCP pings still work)
3. 90s passes with no application-level pings → watchdog closes websocket
4. Admin handler raises `ConnectionClosed` → `handle_connection` returns
5. `run_worker` reconnection loop: backoff → reconnect → re-register
6. New server sends pings → watchdog resets → stable

## Files to Modify

**webRTC-connect (`server.py`):**
- Add `_ping_loop()` function
- Start ping task after registration in `handle_client()`
- Cancel ping task in `handle_client()`'s `finally` block

**sleap-rtc:**
- `worker_class.py` — Add `_signaling_heartbeat_watchdog()`, init attributes, start/cancel watchdog in reconnection loop, handle `"ping"` in `handle_connection`
- `mesh_coordinator.py` — Handle `"ping"` in `_admin_websocket_handler_loop`
- `tests/test_worker_reconnection.py` — Tests for watchdog behavior

## Timing

| Event | Interval |
|-------|----------|
| Server sends ping | Every 30s |
| Worker watchdog checks | Every 30s |
| Stale connection timeout | 90s (3 missed pings) |
| Worst-case detection time | ~120s (90s timeout + 30s watchdog check interval) |
