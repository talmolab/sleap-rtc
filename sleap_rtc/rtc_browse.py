"""Browse client for filesystem viewing via WebRTC.

This module provides the browse command functionality, connecting to a Worker
via WebRTC and serving a local web UI for filesystem browsing.
"""

import asyncio
import logging
import json

import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription

from sleap_rtc.config import get_config
from sleap_rtc.client.fs_viewer_server import FSViewerServer

# Setup logging
logging.basicConfig(level=logging.INFO)


class BrowseClient:
    """Client for browsing Worker filesystem.

    This client:
    - Connects to a Worker via WebRTC
    - Starts a local HTTP/WebSocket server for the browser UI
    - Relays filesystem messages between browser and Worker
    """

    def __init__(self, room_id: str, token: str, port: int = 8765):
        """Initialize the browse client.

        Args:
            room_id: Room ID to connect to.
            token: Room token for authentication.
            port: Local port for the file browser server.
        """
        self.room_id = room_id
        self.token = token
        self.port = port

        # Load config
        config = get_config()
        self.dns = config.signaling_websocket

        # Connection state
        self.websocket = None
        self.pc = None
        self.data_channel = None
        self.peer_id = None

        # Viewer server
        self.viewer_server = None

        # Shutdown flag
        self.shutting_down = False

    async def run(self, open_browser: bool = True):
        """Run the browse client.

        Args:
            open_browser: Whether to auto-open the browser.
        """
        try:
            # Sign in anonymously to get credentials
            sign_in_json = self._request_anonymous_signin()
            id_token = sign_in_json.get("id_token")
            self.peer_id = sign_in_json.get("username")

            if not id_token:
                logging.error("Failed to get anonymous ID token")
                return

            logging.info(f"Signed in as: {self.peer_id}")

            # Connect to signaling server
            async with websockets.connect(self.dns) as websocket:
                self.websocket = websocket

                # Register with room
                await self._register_with_room(id_token)

                # Discover workers
                workers = await self._discover_workers()

                if not workers:
                    logging.error("No workers found in room")
                    print("\nNo workers found in the room. Make sure a Worker is running.")
                    return

                # Interactive worker selection
                from sleap_rtc.client.file_selector import WorkerSelector

                selector = WorkerSelector(workers)
                selected_worker = await selector.run()

                if selected_worker is None or selector.cancelled:
                    print("\nWorker selection cancelled.")
                    return

                worker_id = selected_worker["peer_id"]
                logging.info(f"Connecting to worker: {worker_id}")

                # Establish WebRTC connection
                await self._connect_to_worker(worker_id)

                # Wait for data channel to open
                await self._wait_for_channel()

                # Create and start viewer server
                self.viewer_server = FSViewerServer(
                    send_to_worker=self._send_to_worker,
                )

                url = await self.viewer_server.start(
                    port=self.port,
                    open_browser=open_browser,
                )

                print(f"\nFilesystem browser started at: {url}")
                print("Press Ctrl+C to stop.\n")

                # Run until shutdown
                await self._run_message_loop()

        except Exception as e:
            logging.error(f"Browse client error: {e}")
            raise
        finally:
            await self._cleanup()

    def _request_anonymous_signin(self) -> dict:
        """Request anonymous sign-in from Cognito."""
        import requests
        from sleap_rtc.config import get_config

        config = get_config()
        url = config.get_http_endpoint("/anonymous-signin")

        response = requests.post(url)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Anonymous sign-in failed: {response.status_code}")
            return {}

    async def _register_with_room(self, id_token: str):
        """Register with the signaling server room."""
        import platform
        import os

        register_msg = json.dumps({
            "type": "register",
            "peer_id": self.peer_id,
            "room_id": self.room_id,
            "token": self.token,
            "id_token": id_token,
            "role": "client",
            "metadata": {
                "tags": ["sleap-rtc", "browse-client"],
                "properties": {
                    "platform": platform.system(),
                    "user_id": os.environ.get("USER", "unknown"),
                },
            },
        })

        await self.websocket.send(register_msg)

        # Wait for registration confirmation
        response = await self.websocket.recv()
        data = json.loads(response)

        if data.get("type") == "registered_auth":
            logging.info("Registered with room")
            # Store ICE servers if provided
            self.ice_servers = data.get("ice_servers", [])
        else:
            raise RuntimeError(f"Registration failed: {data}")

    async def _discover_workers(self) -> list:
        """Discover available workers in the room."""
        filters = {
            "role": "worker",
            "room_id": self.room_id,
            "tags": ["sleap-rtc"],
            "properties": {"status": "available"},
        }

        discover_msg = json.dumps({
            "type": "discover_peers",
            "from_peer_id": self.peer_id,
            "filters": filters,
        })

        await self.websocket.send(discover_msg)

        # Wait for discovery response
        try:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            data = json.loads(response)

            if data.get("type") == "peer_list":
                workers = data.get("peers", [])
                logging.info(f"Discovered {len(workers)} workers")
                return workers
            else:
                logging.warning(f"Unexpected discovery response: {data}")
                return []
        except asyncio.TimeoutError:
            logging.error("Worker discovery timed out")
            return []

    async def _connect_to_worker(self, worker_id: str):
        """Establish WebRTC connection to worker."""
        # Create peer connection
        self.pc = RTCPeerConnection()

        # Create data channel
        self.data_channel = self.pc.createDataChannel("browse")

        @self.data_channel.on("open")
        def on_open():
            logging.info("Data channel opened")

        @self.data_channel.on("message")
        async def on_message(message):
            await self._handle_worker_message(message)

        # Create and send offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        offer_msg = json.dumps({
            "type": self.pc.localDescription.type,  # "offer"
            "sender": self.peer_id,
            "target": worker_id,
            "sdp": self.pc.localDescription.sdp,
        })

        await self.websocket.send(offer_msg)
        logging.info(f"Sent offer to worker {worker_id}")

        # Wait for answer
        while True:
            response = await self.websocket.recv()
            data = json.loads(response)
            msg_type = data.get("type")

            if msg_type == "answer":
                logging.info("Received answer from worker")
                answer = RTCSessionDescription(
                    sdp=data.get("sdp"),
                    type="answer",
                )
                await self.pc.setRemoteDescription(answer)
                break

            elif msg_type == "candidate":
                # Handle ICE candidate
                candidate = data.get("candidate")
                if candidate:
                    await self.pc.addIceCandidate(candidate)

            else:
                logging.debug(f"Ignoring message type: {msg_type}")

    async def _wait_for_channel(self):
        """Wait for data channel to be open."""
        while self.data_channel.readyState != "open":
            await asyncio.sleep(0.1)
        logging.info("Data channel ready")

    def _send_to_worker(self, message: str):
        """Send message to Worker via data channel."""
        if self.data_channel and self.data_channel.readyState == "open":
            self.data_channel.send(message)
        else:
            logging.warning("Data channel not open, cannot send message")

    async def _handle_worker_message(self, message):
        """Handle message from Worker."""
        if isinstance(message, str):
            # Forward FS_* messages to viewer server
            if message.startswith("FS_"):
                if self.viewer_server:
                    await self.viewer_server.handle_worker_response(message)
            else:
                logging.debug(f"Ignoring non-FS message: {message[:50]}")

    async def _run_message_loop(self):
        """Run the main message loop until shutdown."""
        try:
            while not self.shutting_down:
                # Check WebSocket for signaling messages
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=1.0,
                    )
                    # Handle signaling messages if needed
                    data = json.loads(message)
                    logging.debug(f"Signaling message: {data.get('action')}")

                except asyncio.TimeoutError:
                    pass

                # Check if connection is still alive
                if self.pc and self.pc.connectionState in ("failed", "closed"):
                    logging.warning("WebRTC connection lost")
                    if self.viewer_server:
                        await self.viewer_server.notify_worker_disconnected()
                    break

        except websockets.exceptions.ConnectionClosed:
            logging.warning("Signaling connection closed")
            if self.viewer_server:
                await self.viewer_server.notify_worker_disconnected()

    async def _cleanup(self):
        """Clean up resources."""
        self.shutting_down = True

        # Stop viewer server
        if self.viewer_server:
            await self.viewer_server.stop()

        # Close data channel
        if self.data_channel:
            self.data_channel.close()

        # Close peer connection
        if self.pc:
            await self.pc.close()

        logging.info("Browse client cleaned up")


async def run_browse_client(
    room_id: str,
    token: str,
    port: int = 8765,
    open_browser: bool = True,
):
    """Run the browse client.

    Args:
        room_id: Room ID to connect to.
        token: Room token for authentication.
        port: Local port for the file browser server.
        open_browser: Whether to auto-open the browser.
    """
    client = BrowseClient(room_id=room_id, token=token, port=port)
    await client.run(open_browser=open_browser)
