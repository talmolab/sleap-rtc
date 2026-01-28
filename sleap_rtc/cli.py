"""Unified CLI for sleap-RTC using Click."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import click
import requests
from loguru import logger

from sleap_rtc.rtc_worker import run_RTCworker
from sleap_rtc.rtc_client import run_RTCclient
from sleap_rtc.rtc_client_track import run_RTCclient_track


@click.group()
def cli():
    pass


# =============================================================================
# Auth Commands
# =============================================================================


@cli.command()
@click.option("--timeout", default=120, help="Login timeout in seconds.")
def login(timeout):
    """Log in to SLEAP-RTC via GitHub OAuth.

    Opens your browser to authenticate with GitHub via the SLEAP-RTC dashboard.
    After authorization, your credentials are saved locally for future CLI commands.

    Example:
        sleap-rtc login
    """
    from sleap_rtc.auth.credentials import save_jwt, is_logged_in, get_user
    from sleap_rtc.auth.github import github_login

    if is_logged_in():
        user = get_user()
        if user:
            click.echo(f"Already logged in as {user.get('username', 'unknown')}")
            if not click.confirm("Log in as a different user?"):
                return

    try:
        result = github_login(timeout=timeout)
        save_jwt(result["jwt"], result["user"])

        user = result["user"]
        click.echo(f"Logged in as {user.get('username', 'unknown')}")
        logger.info("Credentials saved to ~/.sleap-rtc/credentials.json")

    except Exception as e:
        logger.error(f"Login failed: {e}")
        sys.exit(1)


@cli.command()
def logout():
    """Log out and clear stored credentials.

    Removes the JWT and user info from ~/.sleap-rtc/credentials.json.
    Worker tokens (API keys) are also removed.
    """
    from sleap_rtc.auth.credentials import clear_credentials, is_logged_in

    if not is_logged_in():
        click.echo("Not currently logged in")
        return

    clear_credentials()
    click.echo("Logged out successfully")


@cli.command()
def whoami():
    """Display current logged-in user info.

    Shows your GitHub username and user ID from the stored JWT.
    """
    from sleap_rtc.auth.credentials import get_user, get_jwt, is_logged_in

    if not is_logged_in():
        click.echo("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    user = get_user()
    if not user:
        click.echo("No user info found. Try logging in again.")
        sys.exit(1)

    click.echo(f"Username: {user.get('username', 'unknown')}")
    click.echo(f"User ID:  {user.get('user_id', user.get('id', 'unknown'))}")

    # Show JWT expiry if we can decode it
    jwt_token = get_jwt()
    if jwt_token:
        try:
            import jwt
            # Decode without verification just to read claims
            claims = jwt.decode(jwt_token, options={"verify_signature": False})
            exp = claims.get("exp")
            if exp:
                exp_dt = datetime.fromtimestamp(exp)
                click.echo(f"JWT expires: {exp_dt.isoformat()}")
        except Exception:
            pass


# =============================================================================
# Token Commands (subgroup)
# =============================================================================


@cli.group()
def token():
    """Manage worker API tokens.

    Worker tokens are used to authenticate workers with the signaling server.
    Each token is associated with a specific room.
    """
    pass


@token.command(name="create")
@click.option(
    "--room",
    "-r",
    required=True,
    help="Room ID to create token for.",
)
@click.option(
    "--name",
    "-n",
    required=True,
    help="Human-readable name for this worker (e.g., 'lab-gpu-1').",
)
@click.option(
    "--expires",
    "-e",
    type=int,
    default=None,
    help="Token expiration in days (default: 7).",
)
@click.option(
    "--save/--no-save",
    default=True,
    help="Save token to credentials file (default: yes).",
)
def token_create(room, name, expires, save):
    """Create a new worker API token.

    Creates an API key for a worker to join a specific room.
    The room must already exist and you must be a member.

    Example:
        sleap-rtc token create --room abc123 --name lab-gpu-1
    """
    from sleap_rtc.auth.credentials import get_jwt, save_token
    from sleap_rtc.config import get_config

    jwt_token = get_jwt()
    if not jwt_token:
        logger.error("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    config = get_config()
    endpoint = f"{config.get_http_url()}/api/auth/token"

    payload = {
        "room_id": room,
        "worker_name": name,
    }
    if expires:
        payload["expires_days"] = expires

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30,
        )

        if response.status_code != 200:
            error = response.json().get("error", response.text)
            logger.error(f"Failed to create token: {error}")
            sys.exit(1)

        data = response.json()

        click.echo("")
        click.echo("Worker token created successfully!")
        click.echo("")
        click.echo(f"  API Key:     {data['token_id']}")
        click.echo(f"  Room:        {data['room_id']}")
        click.echo(f"  Worker Name: {name}")
        if data.get("expires_at"):
            click.echo(f"  Expires:     {data['expires_at']}")
        click.echo("")
        click.echo("To start a worker with this token:")
        click.echo(f"  sleap-rtc worker --api-key {data['token_id']}")
        click.echo("")

        if save:
            save_token(room, data["token_id"], name)
            logger.info("Token saved to ~/.sleap-rtc/credentials.json")

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        sys.exit(1)


@token.command(name="list")
def token_list():
    """List your API tokens.

    Shows all tokens you've created, their status, and expiration.
    """
    from sleap_rtc.auth.credentials import get_jwt
    from sleap_rtc.config import get_config

    jwt_token = get_jwt()
    if not jwt_token:
        logger.error("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    config = get_config()
    endpoint = f"{config.get_http_url()}/api/auth/tokens"

    try:
        response = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30,
        )

        if response.status_code != 200:
            error = response.json().get("error", response.text)
            logger.error(f"Failed to list tokens: {error}")
            sys.exit(1)

        data = response.json()
        tokens = data.get("tokens", [])

        if not tokens:
            click.echo("No tokens found")
            return

        click.echo("")
        click.echo(f"{'NAME':<20} {'ROOM':<12} {'STATUS':<10} {'EXPIRES':<20}")
        click.echo("-" * 62)

        for t in tokens:
            name = t.get("worker_name", "unknown")[:20]
            room = t.get("room_id", "?")[:12]
            status = "revoked" if t.get("revoked_at") else "active"
            expires = t.get("expires_at", "never")[:20]
            click.echo(f"{name:<20} {room:<12} {status:<10} {expires:<20}")

        click.echo("")

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        sys.exit(1)


@token.command(name="revoke")
@click.argument("token_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def token_revoke(token_id, yes):
    """Revoke an API token.

    Immediately invalidates the token. Workers using this token
    will no longer be able to connect.

    Example:
        sleap-rtc token revoke slp_abc123...
    """
    from sleap_rtc.auth.credentials import get_jwt
    from sleap_rtc.config import get_config

    jwt_token = get_jwt()
    if not jwt_token:
        logger.error("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    if not yes:
        if not click.confirm(f"Revoke token {token_id[:20]}...?"):
            click.echo("Cancelled")
            return

    config = get_config()
    endpoint = f"{config.get_http_url()}/api/auth/token/{token_id}"

    try:
        response = requests.delete(
            endpoint,
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30,
        )

        if response.status_code != 200:
            error = response.json().get("error", response.text)
            logger.error(f"Failed to revoke token: {error}")
            sys.exit(1)

        click.echo("Token revoked successfully")

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        sys.exit(1)


# =============================================================================
# Room Commands (subgroup)
# =============================================================================


@cli.group()
def room():
    """Manage rooms.

    Rooms are workspaces where workers and clients connect.
    Room owners can invite other users and create worker tokens.
    """
    pass


@room.command(name="list")
def room_list():
    """List rooms you have access to.

    Shows all rooms where you are an owner or member.
    """
    from sleap_rtc.auth.credentials import get_jwt
    from sleap_rtc.config import get_config

    jwt_token = get_jwt()
    if not jwt_token:
        logger.error("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    config = get_config()
    endpoint = f"{config.get_http_url()}/api/auth/rooms"

    try:
        response = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30,
        )

        if response.status_code != 200:
            error = response.json().get("error", response.text)
            logger.error(f"Failed to list rooms: {error}")
            sys.exit(1)

        data = response.json()
        rooms = data.get("rooms", [])

        if not rooms:
            click.echo("No rooms found")
            click.echo("Create one with: sleap-rtc room create")
            return

        click.echo("")
        click.echo(f"{'ROOM ID':<12} {'ROLE':<10} {'JOINED':<20}")
        click.echo("-" * 42)

        for r in rooms:
            room_id = r.get("room_id", "?")[:12]
            role = r.get("role", "?")[:10]
            joined = r.get("joined_at", "?")[:20]
            click.echo(f"{room_id:<12} {role:<10} {joined:<20}")

        click.echo("")

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        sys.exit(1)


@room.command(name="create")
@click.option(
    "--name",
    "-n",
    default=None,
    help="Optional name for the room.",
)
def room_create(name):
    """Create a new room.

    Creates a room where you can add workers and invite collaborators.
    You will be the owner of the created room.

    Example:
        sleap-rtc room create --name "my-training-room"
    """
    from sleap_rtc.auth.credentials import get_jwt
    from sleap_rtc.config import get_config

    jwt_token = get_jwt()
    if not jwt_token:
        logger.error("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    config = get_config()
    endpoint = f"{config.get_http_url()}/api/auth/rooms"

    payload = {}
    if name:
        payload["name"] = name

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30,
        )

        if response.status_code != 200:
            error = response.json().get("error", response.text)
            logger.error(f"Failed to create room: {error}")
            sys.exit(1)

        data = response.json()

        click.echo("")
        click.echo("Room created successfully!")
        click.echo("")
        click.echo(f"  Room ID:    {data['room_id']}")
        click.echo(f"  Room Token: {data['room_token']}")
        click.echo("")
        click.echo("Next steps:")
        click.echo(f"  1. Create a worker token: sleap-rtc token create --room {data['room_id']} --name my-worker")
        click.echo(f"  2. Start a worker with the token")
        click.echo("")

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        sys.exit(1)


@room.command(name="delete")
@click.argument("room_id")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt.",
)
def room_delete(room_id, force):
    """Delete a room.

    Permanently deletes a room and all associated data including tokens
    and memberships. Only room owners can delete rooms.

    Example:
        sleap-rtc room delete abc123
        sleap-rtc room delete abc123 --force
    """
    from sleap_rtc.auth.credentials import get_jwt
    from sleap_rtc.config import get_config

    jwt_token = get_jwt()
    if not jwt_token:
        logger.error("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    if not force:
        if not click.confirm(f"Are you sure you want to delete room '{room_id}'? This cannot be undone."):
            click.echo("Cancelled")
            return

    config = get_config()
    endpoint = f"{config.get_http_url()}/api/auth/rooms/{room_id}"

    try:
        response = requests.delete(
            endpoint,
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30,
        )

        if response.status_code != 200:
            error = response.json().get("detail", response.json().get("error", response.text))
            logger.error(f"Failed to delete room: {error}")
            sys.exit(1)

        click.echo(f"Room '{room_id}' deleted successfully")

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        sys.exit(1)


@room.command(name="invite")
@click.argument("room_id")
def room_invite(room_id):
    """Generate an invite code for a room.

    Creates a short-lived invite code that others can use to join the room.
    You must be the owner of the room to generate invites.

    Example:
        sleap-rtc room invite abc123
    """
    from sleap_rtc.auth.credentials import get_jwt
    from sleap_rtc.config import get_config

    jwt_token = get_jwt()
    if not jwt_token:
        logger.error("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    config = get_config()
    endpoint = f"{config.get_http_url()}/api/auth/rooms/{room_id}/invite"

    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30,
        )

        if response.status_code != 200:
            error = response.json().get("error", response.text)
            logger.error(f"Failed to create invite: {error}")
            sys.exit(1)

        data = response.json()

        click.echo("")
        click.echo("Invite code created!")
        click.echo("")
        click.echo(f"  Code:    {data['invite_code']}")
        click.echo(f"  Expires: {data.get('expires_at', 'in 24 hours')}")
        click.echo("")
        click.echo("Share this command with your collaborator:")
        click.echo(f"  sleap-rtc room join --code {data['invite_code']}")
        click.echo("")

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        sys.exit(1)


@room.command(name="join")
@click.option(
    "--code",
    "-c",
    required=True,
    help="Invite code from room owner.",
)
def room_join(code):
    """Join a room using an invite code.

    Use an invite code shared by the room owner to join their room.

    Example:
        sleap-rtc room join --code ABCD1234
    """
    from sleap_rtc.auth.credentials import get_jwt
    from sleap_rtc.config import get_config

    jwt_token = get_jwt()
    if not jwt_token:
        logger.error("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    config = get_config()
    endpoint = f"{config.get_http_url()}/api/auth/rooms/join"

    try:
        response = requests.post(
            endpoint,
            json={"invite_code": code},
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30,
        )

        if response.status_code != 200:
            error = response.json().get("error", response.text)
            logger.error(f"Failed to join room: {error}")
            sys.exit(1)

        data = response.json()

        click.echo("")
        click.echo("Successfully joined room!")
        click.echo("")
        click.echo(f"  Room ID: {data['room_id']}")
        click.echo(f"  Role:    {data.get('role', 'member')}")
        click.echo("")

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        sys.exit(1)


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
    "--api-key",
    "-k",
    type=str,
    envvar="SLEAP_RTC_API_KEY",
    required=False,
    help="API key for worker authentication (slp_xxx...). Can also use SLEAP_RTC_API_KEY env var.",
)
@click.option(
    "--room-id",
    "-r",
    type=str,
    required=False,
    help="[Legacy] Room ID to join (if not provided, a new room will be created).",
)
@click.option(
    "--token",
    "-t",
    type=str,
    required=False,
    help="[Legacy] Room token for authentication (required if --room-id is provided).",
)
@click.option(
    "--working-dir",
    "-w",
    type=str,
    required=False,
    help="Working directory for the worker. Overrides config file value.",
)
@click.option(
    "--name",
    "-n",
    type=str,
    required=False,
    help="Human-readable name for this worker (e.g. 'lab-gpu-1'). Shown in TUI and client discovery.",
)
def worker(api_key, room_id, token, working_dir, name):
    """Start the sleap-RTC worker node.

    Authentication modes (choose one):

    1. API Key (recommended):
       sleap-rtc worker --api-key slp_xxx...

       Get an API key from: sleap-rtc token create --room ROOM --name NAME

    2. Legacy room credentials:
       sleap-rtc worker --room-id ROOM --token TOKEN

       Or omit both to create a new anonymous room (deprecated).
    """
    # Check for credential file if no explicit auth provided
    if not api_key and not room_id:
        from sleap_rtc.auth.credentials import get_credentials
        creds = get_credentials()
        tokens = creds.get("tokens", {})
        if tokens:
            # Use first available token
            first_room = next(iter(tokens))
            api_key = tokens[first_room].get("api_key")
            if api_key:
                logger.info(f"Using API key from credentials for room: {first_room}")

    # Validate authentication options
    has_api_key = api_key is not None
    has_legacy = room_id is not None or token is not None

    if has_api_key and has_legacy:
        logger.error("Cannot use both --api-key and --room-id/--token")
        logger.error("Choose one authentication method")
        sys.exit(1)

    if has_legacy:
        # Legacy mode validation
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
        api_key=api_key,
        room_id=room_id,
        token=token,
        working_dir=working_dir,
        name=name,
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

    Requires JWT authentication. Run 'sleap-rtc login' first.

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

    Requires JWT authentication. Run 'sleap-rtc login' first.

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
