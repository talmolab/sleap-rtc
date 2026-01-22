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
from sleap_rtc.protocol import (
    MSG_AUTH_REQUIRED,
    MSG_AUTH_RESPONSE,
    MSG_AUTH_SUCCESS,
    MSG_AUTH_FAILURE,
    format_message,
    parse_message,
)

# Setup logging
logging.basicConfig(level=logging.INFO)


class BrowseClient:
    """Client for browsing Worker filesystem.

    This client:
    - Connects to a Worker via WebRTC
    - Starts a local HTTP/WebSocket server for the browser UI
    - Relays filesystem messages between browser and Worker
    """

    def __init__(
        self,
        room_id: str,
        token: str,
        port: int = 8765,
        use_jwt: bool = False,
        no_jwt: bool = False,
        otp_secret: str = None,
    ):
        """Initialize the browse client.

        Args:
            room_id: Room ID to connect to.
            token: Room token for authentication.
            port: Local port for the file browser server.
            use_jwt: Require JWT authentication.
            no_jwt: Force Cognito auth (skip JWT).
            otp_secret: Base32-encoded OTP secret for auto-authentication.
        """
        self.room_id = room_id
        self.token = token
        self.port = port
        self.use_jwt = use_jwt
        self.no_jwt = no_jwt
        self.otp_secret = otp_secret

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

        # P2P Authentication state (TOTP)
        self._authenticated = False  # Whether we've passed TOTP auth
        self._auth_required = False  # Whether worker requires auth
        self._auth_event = None  # asyncio.Event to signal auth completion

    async def run(self, open_browser: bool = True):
        """Run the browse client.

        Args:
            open_browser: Whether to auto-open the browser.
        """
        try:
            # Determine authentication method
            jwt_token = None
            id_token = None

            if not self.no_jwt:
                # Try to get JWT from stored credentials
                from sleap_rtc.auth.credentials import get_valid_jwt, get_user
                jwt_token = get_valid_jwt()

                if jwt_token:
                    user = get_user()
                    self.peer_id = user.get("username", "unknown") if user else "unknown"
                    logging.info(f"Using JWT authentication as: {self.peer_id}")

            if not jwt_token:
                # Fall back to Cognito anonymous signin
                if self.use_jwt:
                    logging.error("JWT required but no valid JWT found. Run: sleap-rtc login")
                    return

                # Deprecation warning
                logging.warning(
                    "Using Cognito anonymous signin (deprecated). "
                    "Run 'sleap-rtc login' for GitHub OAuth authentication."
                )

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
                await self._register_with_room(jwt_token=jwt_token, id_token=id_token)

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

    async def _register_with_room(self, jwt_token: str = None, id_token: str = None):
        """Register with the signaling server room.

        Args:
            jwt_token: JWT token from GitHub OAuth (preferred).
            id_token: Cognito ID token (legacy fallback).
        """
        import platform
        import os

        register_data = {
            "type": "register",
            "peer_id": self.peer_id,
            "room_id": self.room_id,
            "token": self.token,
            "role": "client",
            "metadata": {
                "tags": ["sleap-rtc", "browse-client"],
                "properties": {
                    "platform": platform.system(),
                    "user_id": os.environ.get("USER", "unknown"),
                },
            },
        }

        # Use JWT if available, otherwise fall back to id_token
        if jwt_token:
            register_data["jwt"] = jwt_token
        elif id_token:
            register_data["id_token"] = id_token

        register_msg = json.dumps(register_data)

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
        """Send message to Worker via data channel.

        Note: FS_* commands are gated on authentication state.
        """
        if not self.data_channel or self.data_channel.readyState != "open":
            logging.warning("Data channel not open, cannot send message")
            return

        # Gate FS_* commands on authentication state
        if message.startswith("FS_") and self._auth_required and not self._authenticated:
            logging.warning("Cannot send FS command before authentication")
            return

        self.data_channel.send(message)

    async def _prompt_for_otp(self) -> str:
        """Prompt user to enter OTP code from their authenticator app.

        Returns:
            6-digit OTP code string.
        """
        print(f"\n{'='*60}")
        print("AUTHENTICATION REQUIRED")
        print(f"{'='*60}")
        print("Enter the 6-digit code from your authenticator app")
        print("(e.g., Google Authenticator, Authy)")
        print("")

        # Use asyncio to read input without blocking
        loop = asyncio.get_event_loop()

        # Read OTP code
        otp_code = await loop.run_in_executor(
            None, lambda: input("OTP Code: ").strip()
        )

        return otp_code

    def _get_otp_secret(self) -> str:
        """Get OTP secret from CLI option or stored credentials.

        Returns:
            Base32-encoded OTP secret string, or None if not available.
        """
        # CLI option takes precedence
        if self.otp_secret:
            return self.otp_secret

        # Try to get stored secret for this room
        from sleap_rtc.auth.credentials import get_stored_otp_secret
        return get_stored_otp_secret(self.room_id)

    async def _handle_auth_required(self, worker_id: str):
        """Handle AUTH_REQUIRED message from worker.

        Args:
            worker_id: ID of the worker requesting authentication.
        """
        self._auth_required = True
        logging.info(f"Worker {worker_id} requires TOTP authentication")

        # Check for OTP secret (CLI or stored)
        otp_secret = self._get_otp_secret()
        if otp_secret:
            # Auto-generate OTP from secret
            try:
                from sleap_rtc.auth.totp import generate_otp
                otp_code = generate_otp(otp_secret)
                logging.info("Auto-generated OTP from stored secret")
                print("\nAuto-authenticating with stored OTP secret...")
            except Exception as e:
                logging.warning(f"Failed to generate OTP: {e}")
                otp_code = await self._prompt_for_otp()
        else:
            # Prompt user for OTP
            otp_code = await self._prompt_for_otp()

        # Validate input
        if not otp_code or len(otp_code) != 6 or not otp_code.isdigit():
            print("Invalid code format. Please enter exactly 6 digits.")
            # Re-prompt (unlimited retries)
            asyncio.create_task(self._handle_auth_required(worker_id))
            return

        # Send AUTH_RESPONSE
        auth_response = format_message(MSG_AUTH_RESPONSE, otp_code)
        if self.data_channel and self.data_channel.readyState == "open":
            self.data_channel.send(auth_response)
            logging.info("Sent OTP code to worker")

    def _handle_auth_success(self):
        """Handle AUTH_SUCCESS message from worker."""
        self._authenticated = True
        print("\n" + "=" * 60)
        print("AUTHENTICATION SUCCESSFUL")
        print("=" * 60 + "\n")
        logging.info("Successfully authenticated with worker via TOTP")
        if self._auth_event:
            self._auth_event.set()

    def _handle_auth_failure(self, reason: str):
        """Handle AUTH_FAILURE message from worker.

        Args:
            reason: Failure reason from worker.
        """
        print(f"\nAuthentication failed: {reason}")
        print("Please try again.\n")
        logging.warning(f"Authentication failed: {reason}")
        # Re-prompt (unlimited retries)
        asyncio.create_task(self._handle_auth_required("worker"))

    async def _handle_worker_message(self, message):
        """Handle message from Worker."""
        if isinstance(message, str):
            # Handle authentication messages (AUTH_*)
            if message.startswith(MSG_AUTH_REQUIRED):
                msg_type, args = parse_message(message)
                worker_id = args[0] if args else "unknown"
                # Run auth prompt in background to not block message handler
                asyncio.create_task(self._handle_auth_required(worker_id))
                return

            if message == MSG_AUTH_SUCCESS:
                self._handle_auth_success()
                return

            if message.startswith(MSG_AUTH_FAILURE):
                msg_type, args = parse_message(message)
                reason = args[0] if args else "unknown"
                self._handle_auth_failure(reason)
                return

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
    use_jwt: bool = False,
    no_jwt: bool = False,
    otp_secret: str = None,
):
    """Run the browse client.

    Args:
        room_id: Room ID to connect to.
        token: Room token for authentication.
        port: Local port for the file browser server.
        open_browser: Whether to auto-open the browser.
        use_jwt: Require JWT authentication.
        no_jwt: Force Cognito auth (skip JWT).
        otp_secret: Base32-encoded OTP secret for auto-authentication.
    """
    client = BrowseClient(
        room_id=room_id,
        token=token,
        port=port,
        use_jwt=use_jwt,
        no_jwt=no_jwt,
        otp_secret=otp_secret,
    )
    await client.run(open_browser=open_browser)
