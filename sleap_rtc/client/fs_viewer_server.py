"""Filesystem viewer HTTP/WebSocket server for browse command.

This module provides a local web server that serves the filesystem browser UI
and relays messages between the browser and Worker via WebRTC.
"""

import asyncio
import json
import logging
import secrets
import webbrowser
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from aiohttp import web, WSMsgType

# Default port range to try
DEFAULT_PORT = 8765
MAX_PORT_TRIES = 10

# Path to the HTML viewer file
VIEWER_HTML_PATH = Path(__file__).parent / "static" / "fs_viewer.html"


class FSViewerServer:
    """HTTP/WebSocket server for filesystem browser UI.

    This server:
    - Serves the HTML viewer at /
    - Handles WebSocket connections at /ws with token authentication
    - Relays filesystem messages between browser and Worker
    """

    def __init__(
        self,
        send_to_worker: Callable[[str], None],
        on_worker_response: Optional[Callable[[str], None]] = None,
    ):
        """Initialize the server.

        Args:
            send_to_worker: Callback to send messages to Worker via WebRTC.
            on_worker_response: Optional callback when Worker responds.
        """
        self.send_to_worker = send_to_worker
        self.on_worker_response = on_worker_response

        # Generate secure token for this session
        self.token = secrets.token_urlsafe(16)

        # Server state
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.port: Optional[int] = None

        # Connected WebSocket clients
        self.ws_clients: set = set()

        # Response queue for Worker responses
        self.response_queue: asyncio.Queue = asyncio.Queue()

        # Debounce state
        self._debounce_task: Optional[asyncio.Task] = None
        self._pending_request: Optional[Dict[str, Any]] = None

        # Track request metadata for column view support
        self._request_metadata: Optional[Dict[str, Any]] = None

    async def start(self, port: int = DEFAULT_PORT, open_browser: bool = True) -> str:
        """Start the server.

        Args:
            port: Initial port to try (will try up to MAX_PORT_TRIES ports).
            open_browser: Whether to auto-open browser.

        Returns:
            URL of the viewer (with token).
        """
        # Create aiohttp application
        self.app = web.Application()
        self.app.router.add_get("/", self._handle_index)
        self.app.router.add_get("/ws", self._handle_websocket)

        # Try to bind to a port
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        for try_port in range(port, port + MAX_PORT_TRIES):
            try:
                self.site = web.TCPSite(self.runner, "localhost", try_port)
                await self.site.start()
                self.port = try_port
                break
            except OSError:
                continue
        else:
            raise RuntimeError(f"Could not bind to any port in range {port}-{port + MAX_PORT_TRIES - 1}")

        # Build URL with token
        url = f"http://localhost:{self.port}/?token={self.token}"

        logging.info(f"Filesystem viewer started at {url}")

        # Open browser if requested
        if open_browser:
            webbrowser.open(url)

        return url

    async def stop(self):
        """Stop the server and close all connections."""
        # Close all WebSocket clients
        for ws in list(self.ws_clients):
            await ws.close()
        self.ws_clients.clear()

        # Stop the server
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

        logging.info("Filesystem viewer stopped")

    async def _handle_index(self, request: web.Request) -> web.Response:
        """Handle GET / - serve the HTML viewer."""
        # Check if viewer HTML exists
        if not VIEWER_HTML_PATH.exists():
            return web.Response(
                text="Viewer HTML not found. Please reinstall sleap-rtc.",
                status=500,
            )

        # Read and return HTML
        html = VIEWER_HTML_PATH.read_text()
        return web.Response(text=html, content_type="text/html")

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections at /ws."""
        # Validate token from query parameter
        token = request.query.get("token")
        if token != self.token:
            logging.warning("WebSocket connection rejected: invalid token")
            return web.Response(status=403, text="Invalid token")

        # Create WebSocket response
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Add to clients
        self.ws_clients.add(ws)
        logging.info(f"WebSocket client connected (total: {len(self.ws_clients)})")

        try:
            # Request initial worker info
            await self._request_worker_info(ws)

            # Handle incoming messages
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_browser_message(ws, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logging.error(f"WebSocket error: {ws.exception()}")
        finally:
            # Remove from clients
            self.ws_clients.discard(ws)
            logging.info(f"WebSocket client disconnected (total: {len(self.ws_clients)})")

        return ws

    async def _request_worker_info(self, ws: web.WebSocketResponse):
        """Request worker info and mounts when client connects."""
        # Request FS_GET_INFO
        self.send_to_worker("FS_GET_INFO")

        # Request FS_GET_MOUNTS
        self.send_to_worker("FS_GET_MOUNTS")

    async def _handle_browser_message(self, ws: web.WebSocketResponse, data: str):
        """Handle message from browser client.

        Args:
            ws: The WebSocket connection.
            data: JSON message from browser.
        """
        try:
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "list_dir":
                # Debounce list_dir requests
                path = msg.get("path", "")
                offset = msg.get("offset", 0)
                column_index = msg.get("column_index")
                append = msg.get("append", False)
                await self._debounced_list_dir(path, offset, column_index, append)

            elif msg_type == "resolve":
                # Path resolution request
                pattern = msg.get("pattern", "")
                file_size = msg.get("file_size")
                self.send_to_worker(f"FS_RESOLVE::{pattern}::{file_size or ''}")

            else:
                logging.warning(f"Unknown browser message type: {msg_type}")

        except json.JSONDecodeError:
            logging.error(f"Invalid JSON from browser: {data[:100]}")

    async def _debounced_list_dir(
        self, path: str, offset: int, column_index: Optional[int], append: bool
    ):
        """Debounce list_dir requests (100ms)."""
        self._pending_request = {
            "path": path,
            "offset": offset,
            "column_index": column_index,
            "append": append,
        }

        # Cancel previous debounce task
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        # Create new debounce task
        self._debounce_task = asyncio.create_task(self._send_list_dir_after_delay())

    async def _send_list_dir_after_delay(self):
        """Send list_dir after debounce delay."""
        await asyncio.sleep(0.1)  # 100ms debounce

        if self._pending_request:
            path = self._pending_request["path"]
            offset = self._pending_request["offset"]
            # Store metadata to attach to response
            self._request_metadata = {
                "path": path,
                "column_index": self._pending_request.get("column_index"),
                "append": self._pending_request.get("append", False),
            }
            self.send_to_worker(f"FS_LIST_DIR::{path}::{offset}")
            self._pending_request = None

    async def handle_worker_response(self, message: str):
        """Handle response from Worker (called by browse command).

        Args:
            message: Message from Worker.
        """
        # Parse and forward to all connected clients
        try:
            if message.startswith("FS_INFO_RESPONSE::"):
                json_str = message.split("::", 1)[1]
                data = json.loads(json_str)
                await self._broadcast({
                    "type": "worker_info",
                    "data": data,
                })

            elif message.startswith("FS_MOUNTS_RESPONSE::"):
                json_str = message.split("::", 1)[1]
                data = json.loads(json_str)
                await self._broadcast({
                    "type": "mounts",
                    "data": data,
                })

            elif message.startswith("FS_LIST_RESPONSE::"):
                json_str = message.split("::", 1)[1]
                data = json.loads(json_str)
                # Attach request metadata for column view support
                if self._request_metadata:
                    data["path"] = self._request_metadata.get("path")
                    data["column_index"] = self._request_metadata.get("column_index")
                    data["append"] = self._request_metadata.get("append", False)
                    self._request_metadata = None
                await self._broadcast({
                    "type": "list_response",
                    "data": data,
                })

            elif message.startswith("FS_RESOLVE_RESPONSE::"):
                json_str = message.split("::", 1)[1]
                data = json.loads(json_str)
                await self._broadcast({
                    "type": "resolve_response",
                    "data": data,
                })

            elif message.startswith("FS_ERROR::"):
                parts = message.split("::")
                error_code = parts[1] if len(parts) > 1 else "UNKNOWN"
                error_msg = parts[2] if len(parts) > 2 else "Unknown error"
                await self._broadcast({
                    "type": "error",
                    "code": error_code,
                    "message": error_msg,
                })

            # Call optional callback
            if self.on_worker_response:
                self.on_worker_response(message)

        except Exception as e:
            logging.error(f"Error handling worker response: {e}")

    async def _broadcast(self, msg: dict):
        """Broadcast message to all connected WebSocket clients."""
        data = json.dumps(msg)
        for ws in list(self.ws_clients):
            if not ws.closed:
                try:
                    await ws.send_str(data)
                except Exception as e:
                    logging.error(f"Error sending to WebSocket: {e}")
                    self.ws_clients.discard(ws)

    async def notify_worker_disconnected(self):
        """Notify all clients that Worker has disconnected."""
        await self._broadcast({
            "type": "connection_lost",
            "message": "Worker disconnected",
        })


async def run_viewer_server(
    send_to_worker: Callable[[str], None],
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
) -> FSViewerServer:
    """Create and start a filesystem viewer server.

    Args:
        send_to_worker: Callback to send messages to Worker.
        port: Port to try (will try range if busy).
        open_browser: Whether to auto-open browser.

    Returns:
        The running FSViewerServer instance.
    """
    server = FSViewerServer(send_to_worker=send_to_worker)
    await server.start(port=port, open_browser=open_browser)
    return server
