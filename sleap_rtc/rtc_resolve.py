"""Resolve client for SLP video path resolution via WebRTC.

This module provides the resolve-paths command functionality, connecting to a Worker
via WebRTC to check video accessibility in an SLP file and launch a resolution UI
if any videos are missing.
"""

import asyncio
import logging
import json

import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription

from sleap_rtc.config import get_config
from sleap_rtc.client.fs_viewer_server import FSViewerServer
from sleap_rtc.protocol import (
    MSG_USE_WORKER_PATH,
    MSG_WORKER_PATH_OK,
    MSG_WORKER_PATH_ERROR,
    MSG_FS_CHECK_VIDEOS_RESPONSE,
    MSG_SEPARATOR,
)

# Setup logging
logging.basicConfig(level=logging.INFO)


class ResolveClient:
    """Client for resolving SLP video paths on Worker.

    This client:
    - Connects to a Worker via WebRTC
    - Sends an SLP path to the Worker for video accessibility check
    - If videos are missing, starts a local web server for the resolution UI
    - Relays messages between browser and Worker for path resolution
    """

    def __init__(self, room_id: str, token: str, slp_path: str, port: int = 8765):
        """Initialize the resolve client.

        Args:
            room_id: Room ID to connect to.
            token: Room token for authentication.
            slp_path: Path to SLP file on Worker filesystem.
            port: Local port for the resolution UI server.
        """
        self.room_id = room_id
        self.token = token
        self.slp_path = slp_path
        self.port = port

        # Load config
        config = get_config()
        self.dns = config.signaling_websocket

        # Connection state
        self.websocket = None
        self.pc = None
        self.data_channel = None
        self.peer_id = None

        # ICE servers from signaling
        self.ice_servers = []

        # Viewer server for resolution UI
        self.viewer_server = None

        # Video check result
        self.video_check_data = None

        # Shutdown flag
        self.shutting_down = False

        # Response queue for waiting on Worker responses
        self.response_queue = asyncio.Queue()

    async def run(self, open_browser: bool = True):
        """Run the resolve client.

        Args:
            open_browser: Whether to auto-open the browser.

        Returns:
            The resolved SLP path if videos were resolved, None otherwise.
        """
        try:
            # Sign in anonymously to get credentials
            sign_in_json = self._request_anonymous_signin()
            id_token = sign_in_json.get("id_token")
            self.peer_id = sign_in_json.get("username")

            if not id_token:
                logging.error("Failed to get anonymous ID token")
                return None

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
                    return None

                # Interactive worker selection
                from sleap_rtc.client.file_selector import WorkerSelector

                selector = WorkerSelector(workers)
                selected_worker = await selector.run()

                if selected_worker is None or selector.cancelled:
                    print("\nWorker selection cancelled.")
                    return None

                worker_id = selected_worker["peer_id"]
                logging.info(f"Connecting to worker: {worker_id}")

                # Establish WebRTC connection
                await self._connect_to_worker(worker_id)

                # Wait for data channel to open
                await self._wait_for_channel()

                # Send SLP path to Worker for video check
                print(f"\nChecking video accessibility for: {self.slp_path}")
                result = await self._send_worker_path(self.slp_path)

                if not result.get("success"):
                    print(f"\nError: {result.get('error')}")
                    return None

                # Wait for video check response
                video_data = await self._wait_for_video_check(timeout=30.0)

                if video_data is None:
                    print("\nVideo check timed out or failed.")
                    return None

                missing = video_data.get("missing", [])

                if not missing:
                    print(f"\nAll {video_data.get('total_videos', 0)} videos are accessible!")
                    print("No path resolution needed.")
                    return self.slp_path

                # Videos are missing - launch resolution UI
                print(f"\nFound {len(missing)} missing video(s):")
                for v in missing[:5]:
                    print(f"  - {v.get('filename')}")
                if len(missing) > 5:
                    print(f"  ... and {len(missing) - 5} more")

                print("\nLaunching video path resolution UI...")

                # Create and start viewer server for resolution
                self.viewer_server = FSViewerServer(
                    send_to_worker=self._send_to_worker,
                )
                self.viewer_server.set_video_check_data(video_data)

                # Start server at /resolve endpoint
                url = await self.viewer_server.start(
                    port=self.port,
                    open_browser=False,  # We'll open a specific URL
                )

                # Open browser to /resolve page
                resolve_url = url.replace("/?", "/resolve?")
                print(f"\nResolution UI started at: {resolve_url}")
                print("Press Ctrl+C to cancel.\n")

                if open_browser:
                    import webbrowser
                    webbrowser.open(resolve_url)

                # Run until resolution is complete or cancelled
                await self._run_message_loop()

                return self.slp_path

        except Exception as e:
            logging.error(f"Resolve client error: {e}")
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
                "tags": ["sleap-rtc", "resolve-client"],
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
        self.data_channel = self.pc.createDataChannel("resolve")

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
            "type": self.pc.localDescription.type,
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

    async def _send_worker_path(self, path: str, timeout: float = 15.0) -> dict:
        """Send USE_WORKER_PATH and wait for response.

        Args:
            path: Path on Worker filesystem.
            timeout: Timeout in seconds.

        Returns:
            dict with success status and path or error.
        """
        message = f"{MSG_USE_WORKER_PATH}{MSG_SEPARATOR}{path}"
        self._send_to_worker(message)

        try:
            response = await asyncio.wait_for(
                self.response_queue.get(),
                timeout=timeout,
            )

            if response.startswith(MSG_WORKER_PATH_OK):
                parts = response.split(MSG_SEPARATOR)
                return {"success": True, "path": parts[1] if len(parts) > 1 else path}

            elif response.startswith(MSG_WORKER_PATH_ERROR):
                parts = response.split(MSG_SEPARATOR)
                return {"success": False, "error": parts[1] if len(parts) > 1 else "Unknown error"}

            else:
                return {"success": False, "error": f"Unexpected response: {response[:50]}"}

        except asyncio.TimeoutError:
            return {"success": False, "error": "Worker path validation timed out"}

    async def _wait_for_video_check(self, timeout: float = 30.0) -> dict:
        """Wait for video check response.

        Args:
            timeout: Timeout in seconds.

        Returns:
            Video check data dict or None on timeout.
        """
        try:
            response = await asyncio.wait_for(
                self.response_queue.get(),
                timeout=timeout,
            )

            if response.startswith(f"{MSG_FS_CHECK_VIDEOS_RESPONSE}{MSG_SEPARATOR}"):
                json_str = response.split(MSG_SEPARATOR, 1)[1]
                return json.loads(json_str)

            # Not a video check response, might be something else
            logging.warning(f"Expected video check response, got: {response[:50]}")
            return None

        except asyncio.TimeoutError:
            logging.warning("Video check timed out")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse video check response: {e}")
            return None

    async def _handle_worker_message(self, message):
        """Handle message from Worker."""
        if isinstance(message, str):
            # Forward specific messages to response queue
            if (message.startswith(MSG_WORKER_PATH_OK) or
                message.startswith(MSG_WORKER_PATH_ERROR) or
                message.startswith(MSG_FS_CHECK_VIDEOS_RESPONSE)):
                await self.response_queue.put(message)

            # Forward FS_* messages to viewer server
            elif message.startswith("FS_"):
                if self.viewer_server:
                    await self.viewer_server.handle_worker_response(message)
            else:
                logging.debug(f"Ignoring message: {message[:50]}")

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
                    data = json.loads(message)
                    logging.debug(f"Signaling message: {data.get('type')}")

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

        logging.info("Resolve client cleaned up")


async def run_resolve_client(
    room_id: str,
    token: str,
    slp_path: str,
    port: int = 8765,
    open_browser: bool = True,
) -> str:
    """Run the resolve client.

    Args:
        room_id: Room ID to connect to.
        token: Room token for authentication.
        slp_path: Path to SLP file on Worker filesystem.
        port: Local port for the resolution UI server.
        open_browser: Whether to auto-open the browser.

    Returns:
        The resolved SLP path if successful, None otherwise.
    """
    client = ResolveClient(
        room_id=room_id,
        token=token,
        slp_path=slp_path,
        port=port,
    )
    return await client.run(open_browser=open_browser)
