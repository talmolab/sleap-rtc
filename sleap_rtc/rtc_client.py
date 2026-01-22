import asyncio
import logging

from sleap_rtc.client.client_class import RTCClient


def run_RTCclient(
    session_string: str = None,
    pkg_path: str = None,
    zmq_ports: dict = None,
    room_id: str = None,
    token: str = None,
    worker_id: str = None,
    auto_select: bool = False,
    min_gpu_memory: int = None,
    worker_path: str = None,
    non_interactive: bool = False,
    mount_label: str = None,
    use_jwt: bool = False,
    no_jwt: bool = False,
    otp_secret: str = None,
    **kwargs,
):
    """Standalone function to run the RTC client with CLI arguments.

    Args:
        session_string: Session string for direct connection to specific worker
        pkg_path: Path to the SLEAP training/inference package
        zmq_ports: Dict with 'controller' and 'publish' port numbers
        room_id: Room ID for room-based worker discovery
        token: Room token for authentication
        worker_id: Specific worker peer-id to connect to (skips discovery)
        auto_select: Automatically select best worker by GPU memory
        min_gpu_memory: Minimum GPU memory in MB for worker filtering
        worker_path: Explicit path on worker filesystem (skips resolution)
        non_interactive: Auto-select best match without prompting (for CI/scripts)
        mount_label: Specific mount label to search (skips mount selection)
        use_jwt: Require JWT authentication (fail if not logged in)
        no_jwt: Force Cognito auth (skip JWT even if logged in)
        otp_secret: Base32-encoded OTP secret for auto-authentication
        **kwargs: Additional arguments passed to run_client
    """
    # Create client instance (DNS will be loaded from config)
    client = RTCClient(
        DNS=None,  # Use config
        port_number="8080",
        gui=False,  # Indicate that this is running in CLI mode
    )

    # Map CLI arguments to method parameters
    method_kwargs = {
        "file_path": pkg_path,
        "output_dir": ".",
        "zmq_ports": [
            zmq_ports.get("controller", 9000),
            zmq_ports.get("publish", 9001),
        ],  # Convert dict to list
        "config_info_list": None,  # None since CLI (used for updating LossViewer)
        "session_string": session_string,
        # Room-based connection parameters
        "room_id": room_id,
        "token": token,
        "worker_id": worker_id,
        "auto_select": auto_select,
        "min_gpu_memory": min_gpu_memory,
        # Path resolution parameters
        "worker_path": worker_path,
        "non_interactive": non_interactive,
        "mount_label": mount_label,
        # JWT authentication parameters
        "use_jwt": use_jwt,
        "no_jwt": no_jwt,
        # OTP auto-authentication
        "otp_secret": otp_secret,
    }

    # Add any additional kwargs
    method_kwargs.update(kwargs)

    # Run the async method
    try:
        asyncio.run(client.run_client(**method_kwargs))
    except KeyboardInterrupt:
        logging.info("Client interrupted by user. Shutting down...")
    except Exception as e:
        logging.error(f"Client error: {e}")
        raise
