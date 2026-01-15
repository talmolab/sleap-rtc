"""Unified CLI for sleap-RTC using Click."""

import click
from loguru import logger
from pathlib import Path
from sleap_rtc.rtc_worker import run_RTCworker
from sleap_rtc.rtc_client import run_RTCclient
from sleap_rtc.rtc_client_track import run_RTCclient_track
import sys


@click.group()
def cli():
    pass


def show_worker_help():
    """Display"""
    help_text = """
    sleap-rtc worker - Set this machine as a sleap-RTC worker node.

    Usage:
      sleap-rtc worker

    Tips:
      - This machine should have a GPU available for optimal model inference.
      - Ensure that the sleap-RTC Client is running and accessible.
      - Make sure to copy the session-string after connecting to the signaling
        server.
    """
    click.echo(help_text)


@cli.command()
@click.option(
    "--room-id",
    "-r",
    type=str,
    required=False,
    help="Room ID to join (if not provided, a new room will be created).",
)
@click.option(
    "--token",
    "-t",
    type=str,
    required=False,
    help="Room token for authentication (required if --room-id is provided).",
)
@click.option(
    "--working-dir",
    "-w",
    type=str,
    required=False,
    help="Working directory for the worker. Overrides config file value.",
)
def worker(room_id, token, working_dir):
    """Start the sleap-RTC worker node."""
    # Validate that both room_id and token are provided together
    if (room_id and not token) or (token and not room_id):
        logger.error("Both --room-id and --token must be provided together")
        sys.exit(1)

    # Validate working directory if provided
    if working_dir:
        working_dir_path = Path(working_dir)
        if not working_dir_path.exists():
            logger.error(f"Working directory does not exist: {working_dir}")
            sys.exit(1)
        if not working_dir_path.is_dir():
            logger.error(f"Working directory is not a directory: {working_dir}")
            sys.exit(1)
        logger.info(f"Using working directory: {working_dir}")

    run_RTCworker(
        room_id=room_id,
        token=token,
        working_dir=working_dir,
    )


@cli.command(name="client-train")
@click.option(
    "--session-string",
    "--session_string",
    "-s",
    type=str,
    required=False,
    help="Session string for direct connection to a specific worker.",
)
@click.option(
    "--room-id",
    type=str,
    required=False,
    help="Room ID for room-based worker discovery.",
)
@click.option(
    "--token",
    type=str,
    required=False,
    help="Room token for authentication (required with --room-id).",
)
@click.option(
    "--worker-id",
    type=str,
    required=False,
    help="Specific worker peer-id to connect to (skips discovery).",
)
@click.option(
    "--auto-select",
    is_flag=True,
    default=False,
    help="Automatically select best worker by GPU memory (use with --room-id).",
)
@click.option(
    "--pkg_path",
    "-p",
    type=str,
    required=True,
    help="Path to the SLEAP training package.",
)
@click.option(
    "--controller_port",
    type=int,
    required=False,
    default=9000,
    help="ZMQ ports for controller communication with SLEAP.",
)
@click.option(
    "--publish_port",
    type=int,
    required=False,
    default=9001,
    help="ZMQ ports for publish communication with SLEAP.",
)
@click.option(
    "--min-gpu-memory",
    type=int,
    required=False,
    default=None,
    help="Minimum GPU memory in MB required for training.",
)
@click.option(
    "--worker-path",
    type=str,
    required=False,
    default=None,
    help="Path on worker filesystem to use directly (skips path resolution).",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Non-interactive mode: auto-select best match without prompting (for CI/scripts).",
)
@click.option(
    "--mount",
    type=str,
    required=False,
    default=None,
    help="Mount label to search (skips mount selection prompt). Use 'all' to search all mounts.",
)
def client_train(**kwargs):
    """Run remote training on a worker.

    Connection modes (mutually exclusive):

    1. Session string (direct): --session-string SESSION
       Connect directly to a specific worker using its session string.

    2. Room-based discovery: --room-id ROOM --token TOKEN
       Join a room and discover available workers. Supports:
       - Interactive selection (default)
       - Auto-select: --auto-select
       - Direct worker: --worker-id PEER_ID
       - GPU filter: --min-gpu-memory MB

    Path resolution options:

    - --worker-path PATH: Use this path directly on the worker (skips resolution)
    - --non-interactive: Auto-select best match without prompting (for CI/scripts)
    - --mount LABEL: Search only this mount (skips mount selection)
    """
    # Extract connection options
    session_string = kwargs.pop("session_string", None)
    room_id = kwargs.pop("room_id", None)
    token = kwargs.pop("token", None)
    worker_id = kwargs.pop("worker_id", None)
    auto_select = kwargs.pop("auto_select", False)
    min_gpu_memory = kwargs.pop("min_gpu_memory", None)

    # Extract path resolution options
    worker_path = kwargs.pop("worker_path", None)
    non_interactive = kwargs.pop("non_interactive", False)
    mount_label = kwargs.pop("mount", None)

    # Validation: Must provide either session string OR room credentials
    has_session = session_string is not None
    has_room = room_id is not None

    if has_session and has_room:
        logger.error("Connection modes are mutually exclusive. Use only one of:")
        logger.error("  --session-string (direct connection)")
        logger.error("  --room-id and --token (room-based discovery)")
        sys.exit(1)

    if not has_session and not has_room:
        logger.error("Must provide a connection method:")
        logger.error("  --session-string SESSION (direct connection)")
        logger.error("  --room-id ROOM --token TOKEN (room-based discovery)")
        sys.exit(1)

    # Validation: room-id and token must be together
    if (room_id and not token) or (token and not room_id):
        logger.error("Both --room-id and --token must be provided together")
        sys.exit(1)

    # Validation: worker selection options require room-id
    if (worker_id or auto_select) and not room_id:
        logger.error("--worker-id and --auto-select require --room-id and --token")
        sys.exit(1)

    # Validation: worker-id and auto-select are mutually exclusive
    if worker_id and auto_select:
        logger.error("Cannot use both --worker-id and --auto-select")
        sys.exit(1)

    # Setup ZMQ ports
    logger.info(f"Using controller port: {kwargs['controller_port']}")
    logger.info(f"Using publish port: {kwargs['publish_port']}")
    kwargs["zmq_ports"] = dict()
    kwargs["zmq_ports"]["controller"] = kwargs.pop("controller_port")
    kwargs["zmq_ports"]["publish"] = kwargs.pop("publish_port")

    # Handle room-based connection
    if room_id:
        logger.info(f"Room-based connection: room_id={room_id}")
        kwargs["room_id"] = room_id
        kwargs["token"] = token

        if worker_id:
            logger.info(f"Direct worker connection: worker_id={worker_id}")
            kwargs["worker_id"] = worker_id
        elif auto_select:
            logger.info("Auto-select mode enabled")
            kwargs["auto_select"] = True
        else:
            logger.info("Interactive worker selection mode")

        if min_gpu_memory:
            logger.info(f"Minimum GPU memory filter: {min_gpu_memory}MB")
            kwargs["min_gpu_memory"] = min_gpu_memory

    # Log path resolution options
    if worker_path:
        logger.info(f"Using explicit worker path: {worker_path}")
    if non_interactive:
        logger.info("Non-interactive mode: will auto-select best match")
    if mount_label:
        logger.info(f"Using mount filter: {mount_label}")

    return run_RTCclient(
        session_string=session_string,
        pkg_path=kwargs.pop("pkg_path"),
        zmq_ports=kwargs.pop("zmq_ports"),
        worker_path=worker_path,
        non_interactive=non_interactive,
        mount_label=mount_label,
        **kwargs,
    )


@cli.command(name="client-track")
@click.option(
    "--session-string",
    "--session_string",
    "-s",
    type=str,
    required=False,
    help="Session string for direct connection to a specific worker.",
)
@click.option(
    "--room-id",
    type=str,
    required=False,
    help="Room ID for room-based worker discovery.",
)
@click.option(
    "--token",
    type=str,
    required=False,
    help="Room token for authentication (required with --room-id).",
)
@click.option(
    "--worker-id",
    type=str,
    required=False,
    help="Specific worker peer-id to connect to (skips discovery).",
)
@click.option(
    "--auto-select",
    is_flag=True,
    default=False,
    help="Automatically select best worker by GPU memory (use with --room-id).",
)
@click.option(
    "--data_path",
    "-d",
    type=str,
    required=True,
    help="Path to .slp file with data for inference.",
)
@click.option(
    "--model_paths",
    "-m",
    multiple=True,
    required=True,
    help="Paths to trained model directories (can specify multiple times).",
)
@click.option(
    "--output",
    "-o",
    type=str,
    default="predictions.slp",
    help="Output predictions filename.",
)
@click.option(
    "--only_suggested_frames",
    is_flag=True,
    default=True,
    help="Track only suggested frames.",
)
@click.option(
    "--min-gpu-memory",
    type=int,
    required=False,
    default=None,
    help="Minimum GPU memory in MB required for inference.",
)
def client_track(**kwargs):
    """Run remote inference on a worker with pre-trained models.

    Connection modes (mutually exclusive):

    1. Session string (direct): --session-string SESSION
       Connect directly to a specific worker using its session string.

    2. Room-based discovery: --room-id ROOM --token TOKEN
       Join a room and discover available workers. Supports:
       - Interactive selection (default)
       - Auto-select: --auto-select
       - Direct worker: --worker-id PEER_ID
       - GPU filter: --min-gpu-memory MB
    """
    # Extract connection options
    session_string = kwargs.pop("session_string", None)
    room_id = kwargs.pop("room_id", None)
    token = kwargs.pop("token", None)
    worker_id = kwargs.pop("worker_id", None)
    auto_select = kwargs.pop("auto_select", False)
    min_gpu_memory = kwargs.pop("min_gpu_memory", None)

    # Validation: Must provide either session string OR room credentials
    has_session = session_string is not None
    has_room = room_id is not None

    if has_session and has_room:
        logger.error("Connection modes are mutually exclusive. Use only one of:")
        logger.error("  --session-string (direct connection)")
        logger.error("  --room-id and --token (room-based discovery)")
        sys.exit(1)

    if not has_session and not has_room:
        logger.error("Must provide a connection method:")
        logger.error("  --session-string SESSION (direct connection)")
        logger.error("  --room-id ROOM --token TOKEN (room-based discovery)")
        sys.exit(1)

    # Validation: room-id and token must be together
    if (room_id and not token) or (token and not room_id):
        logger.error("Both --room-id and --token must be provided together")
        sys.exit(1)

    # Validation: worker selection options require room-id
    if (worker_id or auto_select) and not room_id:
        logger.error("--worker-id and --auto-select require --room-id and --token")
        sys.exit(1)

    # Validation: worker-id and auto-select are mutually exclusive
    if worker_id and auto_select:
        logger.error("Cannot use both --worker-id and --auto-select")
        sys.exit(1)

    logger.info(f"Running inference with models: {kwargs['model_paths']}")

    # Handle room-based connection
    if room_id:
        logger.info(f"Room-based connection: room_id={room_id}")
        kwargs["room_id"] = room_id
        kwargs["token"] = token

        if worker_id:
            logger.info(f"Direct worker connection: worker_id={worker_id}")
            kwargs["worker_id"] = worker_id
        elif auto_select:
            logger.info("Auto-select mode enabled")
            kwargs["auto_select"] = True
        else:
            logger.info("Interactive worker selection mode")

        if min_gpu_memory:
            logger.info(f"Minimum GPU memory filter: {min_gpu_memory}MB")
            kwargs["min_gpu_memory"] = min_gpu_memory

    return run_RTCclient_track(
        session_string=session_string,
        data_path=kwargs.pop("data_path"),
        model_paths=list(kwargs.pop("model_paths")),
        output=kwargs.pop("output"),
        only_suggested_frames=kwargs.pop("only_suggested_frames"),
        **kwargs,
    )


# Deprecated alias for backward compatibility
@cli.command(name="client", hidden=True)
@click.pass_context
def client_deprecated(ctx, **kwargs):
    """[DEPRECATED] Use 'client-train' instead."""
    logger.warning(
        "Warning: 'sleap-rtc client' is deprecated. Use 'sleap-rtc client-train' instead."
    )
    ctx.invoke(client_train, **kwargs)


@cli.command(name="browse")
@click.option(
    "--room",
    "-r",
    type=str,
    required=True,
    help="Room ID to connect to (required).",
)
@click.option(
    "--token",
    "-t",
    type=str,
    required=True,
    help="Room token for authentication (required).",
)
@click.option(
    "--port",
    "-p",
    type=int,
    default=8765,
    help="Local port for the file browser server (default: 8765).",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Don't auto-open browser (just print URL).",
)
def browse(room, token, port, no_browser):
    """Browse a Worker's filesystem via web UI.

    This command connects to a Worker in the specified room and starts
    a local web server that provides a browser-based file explorer.

    The browser UI allows you to:
    - Browse mount points and directories on the Worker
    - View file information (name, size, type)
    - Copy file paths for use with --worker-path

    Examples:

        # Connect to a Worker and open browser
        sleap-rtc browse --room my-room --token secret123

        # Use a different port
        sleap-rtc browse --room my-room --token secret123 --port 9000

        # Print URL without opening browser (for remote access)
        sleap-rtc browse --room my-room --token secret123 --no-browser
    """
    import asyncio
    from sleap_rtc.rtc_browse import run_browse_client

    logger.info(f"Starting filesystem browser for room: {room}")
    logger.info(f"Local server will run on port: {port}")

    try:
        asyncio.run(
            run_browse_client(
                room_id=room,
                token=token,
                port=port,
                open_browser=not no_browser,
            )
        )
    except KeyboardInterrupt:
        logger.info("Browse session ended by user")
    except Exception as e:
        logger.error(f"Browse error: {e}")
        sys.exit(1)


@cli.command(name="resolve-paths")
@click.option(
    "--room",
    "-r",
    type=str,
    required=True,
    help="Room ID to connect to (required).",
)
@click.option(
    "--token",
    "-t",
    type=str,
    required=True,
    help="Room token for authentication (required).",
)
@click.option(
    "--slp",
    "-s",
    type=str,
    required=True,
    help="Path to SLP file on Worker filesystem (required).",
)
@click.option(
    "--port",
    "-p",
    type=int,
    default=8765,
    help="Local port for the resolution UI server (default: 8765).",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Don't auto-open browser (just print URL).",
)
def resolve_paths(room, token, slp, port, no_browser):
    """Resolve missing video paths in an SLP file on a Worker.

    This command connects to a Worker and checks if the video paths in an SLP
    file are accessible. If any videos are missing, it launches a web UI that
    allows you to browse the Worker's filesystem and resolve the paths.

    The resolution process:
    1. Worker checks if videos in the SLP are accessible
    2. If all accessible, prints success message
    3. If videos are missing, launches resolution UI
    4. In UI, you can browse and locate the correct video files
    5. Auto-detection finds other videos in the same directory
    6. Save creates a new SLP with corrected paths

    Examples:

        # Check video paths in an SLP file
        sleap-rtc resolve-paths --room my-room --token secret123 --slp /mnt/data/project.slp

        # Use a different port
        sleap-rtc resolve-paths -r my-room -t secret123 -s /mnt/data/project.slp -p 9000

        # Print URL without opening browser
        sleap-rtc resolve-paths -r my-room -t secret123 -s /mnt/data/project.slp --no-browser
    """
    import asyncio
    from sleap_rtc.rtc_resolve import run_resolve_client

    logger.info(f"Starting video path resolution for: {slp}")
    logger.info(f"Connecting to room: {room}")

    try:
        result = asyncio.run(
            run_resolve_client(
                room_id=room,
                token=token,
                slp_path=slp,
                port=port,
                open_browser=not no_browser,
            )
        )
        if result:
            logger.info(f"Resolution complete: {result}")
        else:
            logger.warning("Resolution cancelled or failed")
    except KeyboardInterrupt:
        logger.info("Resolution cancelled by user")
    except Exception as e:
        logger.error(f"Resolution error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
