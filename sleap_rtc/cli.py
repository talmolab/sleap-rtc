"""Unified CLI for sleap-RTC using rich-click."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import rich_click as click
import requests
from loguru import logger

# =============================================================================
# rich-click Configuration
# =============================================================================

# Use Rich markup in help text
click.rich_click.USE_RICH_MARKUP = True

# Style configuration
click.rich_click.STYLE_OPTION = "bold cyan"
click.rich_click.STYLE_ARGUMENT = "bold cyan"
click.rich_click.STYLE_COMMAND = "bold green"
click.rich_click.STYLE_SWITCH = "bold yellow"
click.rich_click.STYLE_METAVAR = "bold magenta"
click.rich_click.STYLE_USAGE = "bold"
click.rich_click.STYLE_HELPTEXT = ""

# Panel configuration
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.SHOW_METAVARS_COLUMN = True
click.rich_click.APPEND_METAVARS_HELP = True

# Command groups for organized help output
click.rich_click.COMMAND_GROUPS = {
    "sleap-rtc": [
        {
            "name": "Authentication",
            "commands": ["login", "logout", "whoami"],
        },
        {
            "name": "Rooms & Tokens",
            "commands": ["room", "token"],
        },
        {
            "name": "Worker & Client",
            "commands": ["worker", "train", "track"],
        },
        {
            "name": "Utilities",
            "commands": ["tui", "status", "doctor"],
        },
        {
            "name": "Experimental",
            "commands": ["test"],
        },
    ],
    "sleap-rtc test": [
        {
            "name": "File Browser Tools",
            "commands": ["browse", "resolve-paths"],
        },
    ],
}

from sleap_rtc.rtc_worker import run_RTCworker
from sleap_rtc.rtc_client import run_RTCclient
from sleap_rtc.rtc_client_track import run_RTCclient_track


# =============================================================================
# Authentication Helpers
# =============================================================================


def require_login() -> str:
    """Require user to be logged in and return valid JWT.

    Checks if user has a valid (non-expired) JWT token. If not, prints
    a helpful error message and exits.

    Returns:
        Valid JWT token string.

    Raises:
        SystemExit: If user is not logged in or JWT is expired.
    """
    from sleap_rtc.auth.credentials import get_jwt, get_user, is_logged_in

    if not is_logged_in():
        click.echo(click.style("Error: ", fg="red", bold=True) + "Not logged in.")
        click.echo("")
        click.echo("This command requires authentication. Please log in first:")
        click.echo(click.style("  sleap-rtc login", fg="cyan"))
        click.echo("")
        sys.exit(1)

    jwt_token = get_jwt()
    if not jwt_token:
        click.echo(click.style("Error: ", fg="red", bold=True) + "No JWT token found.")
        click.echo("")
        click.echo("Please log in again:")
        click.echo(click.style("  sleap-rtc login", fg="cyan"))
        click.echo("")
        sys.exit(1)

    # Check JWT expiration
    try:
        import jwt
        claims = jwt.decode(jwt_token, options={"verify_signature": False})
        exp = claims.get("exp")
        if exp:
            from datetime import datetime
            exp_dt = datetime.fromtimestamp(exp)
            if exp_dt < datetime.now():
                user = get_user()
                username = user.get("username", "unknown") if user else "unknown"
                click.echo(click.style("Error: ", fg="red", bold=True) + "JWT token has expired.")
                click.echo(f"  Last logged in as: {username}")
                click.echo("")
                click.echo("Please log in again:")
                click.echo(click.style("  sleap-rtc login", fg="cyan"))
                click.echo("")
                sys.exit(1)
    except Exception:
        # If we can't decode JWT, let the server handle validation
        pass

    return jwt_token


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
        click.echo(f"{'ROOM ID':<12} {'NAME':<16} {'ROLE':<8} {'EXPIRES':<20}")
        click.echo("-" * 60)

        for r in rooms:
            room_id = r.get("room_id", "?")[:12]
            name = (r.get("name") or room_id)[:16]
            role = r.get("role", "?")[:8]

            # Format expiration
            expires_at = r.get("expires_at")
            if expires_at:
                expires_dt = datetime.fromtimestamp(expires_at)
                now = datetime.now()
                if expires_dt < now:
                    expires_str = "EXPIRED"
                elif (expires_dt - now).days > 0:
                    expires_str = f"{(expires_dt - now).days}d left"
                else:
                    hours = (expires_dt - now).seconds // 3600
                    expires_str = f"{hours}h left"
            else:
                expires_str = "Never"

            click.echo(f"{room_id:<12} {name:<16} {role:<8} {expires_str:<20}")

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
@click.option(
    "--expires",
    "-e",
    type=click.Choice(["1d", "5d", "10d", "15d", "30d", "never"]),
    default="30d",
    help="Room expiration time (default: 30d). Use 'never' for no expiration.",
)
def room_create(name, expires):
    """Create a new room.

    Creates a room where you can add workers and invite collaborators.
    You will be the owner of the created room.

    Example:
        sleap-rtc room create --name "my-training-room"
        sleap-rtc room create --name "persistent-room" --expires never
    """
    from sleap_rtc.auth.credentials import get_jwt
    from sleap_rtc.config import get_config

    jwt_token = get_jwt()
    if not jwt_token:
        logger.error("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    config = get_config()
    endpoint = f"{config.get_http_url()}/api/auth/rooms"

    # Map expires to days (None = never expires)
    expires_map = {"1d": 1, "5d": 5, "10d": 10, "15d": 15, "30d": 30, "never": None}
    expires_in_days = expires_map[expires]

    payload = {"expires_in_days": expires_in_days}
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

        # Format expiration display
        if data.get("expires_at"):
            expires_dt = datetime.fromtimestamp(data["expires_at"])
            expires_str = expires_dt.strftime("%Y-%m-%d %H:%M")
        else:
            expires_str = "Never"

        click.echo("")
        click.echo("Room created successfully!")
        click.echo("")
        click.echo(f"  Room ID:    {data['room_id']}")
        click.echo(f"  Room Token: {data['room_token']}")
        click.echo(f"  Expires:    {expires_str}")
        click.echo("")
        click.echo("Next steps:")
        click.echo(f"  1. Create a worker token: sleap-rtc token create --room {data['room_id']} --name my-worker")
        click.echo(f"  2. Start a worker with the token")
        click.echo("")

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        sys.exit(1)


@room.command(name="info")
@click.argument("room_id")
def room_info(room_id):
    """Show details for a room.

    Displays room information including name, expiration, members, and role.

    Example:
        sleap-rtc room info abc123
    """
    from sleap_rtc.auth.credentials import get_jwt
    from sleap_rtc.config import get_config

    jwt_token = get_jwt()
    if not jwt_token:
        logger.error("Not logged in. Run: sleap-rtc login")
        sys.exit(1)

    config = get_config()
    endpoint = f"{config.get_http_url()}/api/auth/rooms/{room_id}"

    try:
        response = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30,
        )

        if response.status_code != 200:
            error = response.json().get("detail", response.json().get("error", response.text))
            logger.error(f"Failed to get room info: {error}")
            sys.exit(1)

        data = response.json()

        # Format expiration
        expires_at = data.get("expires_at")
        if expires_at:
            expires_dt = datetime.fromtimestamp(expires_at)
            now = datetime.now()
            time_left = expires_dt - now

            if time_left.total_seconds() < 0:
                expires_str = f"{expires_dt.strftime('%Y-%m-%d %H:%M')} (EXPIRED)"
            elif time_left.days > 0:
                expires_str = f"{expires_dt.strftime('%Y-%m-%d %H:%M')} ({time_left.days} days left)"
            elif time_left.seconds > 3600:
                hours_left = time_left.seconds // 3600
                expires_str = f"{expires_dt.strftime('%Y-%m-%d %H:%M')} ({hours_left} hours left)"
            else:
                minutes_left = time_left.seconds // 60
                expires_str = f"{expires_dt.strftime('%Y-%m-%d %H:%M')} ({minutes_left} minutes left)"
        else:
            expires_str = "Never"

        click.echo("")
        click.echo(f"Room: {data.get('name', room_id)}")
        click.echo("")
        click.echo(f"  Room ID:    {room_id}")
        click.echo(f"  Your Role:  {data.get('role', 'unknown')}")
        click.echo(f"  Expires:    {expires_str}")

        # Show token only for owners
        if data.get("token"):
            click.echo(f"  Room Token: {data['token']}")

        # Show members if available
        members = data.get("members", [])
        if members:
            click.echo("")
            click.echo("  Members:")
            for member in members:
                role_icon = "👑" if member.get("role") == "owner" else "👤"
                click.echo(f"    {role_icon} {member.get('username', member.get('user_id', 'unknown'))} ({member.get('role', 'member')})")

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


@room.command(name="create-secret")
@click.option(
    "--room",
    "--room-id",
    "-r",
    type=str,
    required=True,
    help="Room ID to create secret for.",
)
@click.option(
    "--save/--no-save",
    default=True,
    help="Save secret to credentials file (default: yes).",
)
def room_create_secret(room, save):
    """Generate a new room secret for P2P authentication.

    Creates a cryptographically secure 256-bit secret for authenticating
    P2P connections between workers and clients in the room.

    The secret must be shared with:
    - Workers: via --room-secret flag, SLEAP_ROOM_SECRET env var, or filesystem
    - Clients: via --room-secret flag, SLEAP_ROOM_SECRET env var, or credentials

    Configuration options (in priority order):
    1. CLI flag: --room-secret SECRET
    2. Environment variable: SLEAP_ROOM_SECRET=SECRET
    3. Filesystem: ~/.sleap-rtc/room-secrets/<room-id>
    4. Credentials file: ~/.sleap-rtc/credentials.json

    Examples:

        # Generate and save secret for a room
        sleap-rtc room create-secret --room my-room

        # Generate without saving (just display)
        sleap-rtc room create-secret --room my-room --no-save

        # Use the secret with worker
        sleap-rtc worker --api-key slp_xxx --room-secret SECRET

        # Use the secret with client (env var method)
        export SLEAP_ROOM_SECRET=SECRET
        sleap-rtc client-train --room my-room --token TOKEN -p package.zip
    """
    from sleap_rtc.auth.psk import generate_secret
    from sleap_rtc.auth.credentials import save_room_secret, get_room_secret

    # Check if secret already exists
    existing = get_room_secret(room)
    if existing:
        if not click.confirm(f"Room '{room}' already has a secret. Generate a new one?"):
            click.echo("Cancelled")
            return

    # Generate new secret
    secret = generate_secret()

    click.echo("")
    click.echo("Room secret generated!")
    click.echo("")
    click.echo(f"  Room ID: {room}")
    click.echo(f"  Secret:  {secret}")
    click.echo("")

    if save:
        save_room_secret(room, secret)
        click.echo("Secret saved to ~/.sleap-rtc/credentials.json")
        click.echo("")

    click.echo("To use this secret:")
    click.echo("")
    click.echo("  Worker:")
    click.echo(f"    sleap-rtc worker --api-key slp_xxx --room-secret {secret}")
    click.echo("    # Or set SLEAP_ROOM_SECRET environment variable")
    click.echo("")
    click.echo("  Client:")
    click.echo(f"    sleap-rtc client-train --room {room} --token TOKEN -p pkg.zip --room-secret {secret}")
    click.echo("    # Or set SLEAP_ROOM_SECRET environment variable")
    click.echo("")


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
    "--room",
    "--room-id",  # Alias for backward compatibility
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
    help="[Legacy] Room token for authentication (required if --room is provided).",
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
@click.option(
    "--room-secret",
    type=str,
    envvar="SLEAP_ROOM_SECRET",
    required=False,
    help="Room secret for P2P authentication. Can also use SLEAP_ROOM_SECRET env var.",
)
def worker(api_key, room, token, working_dir, name, room_secret):
    """Start the sleap-RTC worker node.

    Authentication modes (choose one):

    1. API Key (recommended):
       sleap-rtc worker --api-key slp_xxx...

       Get an API key from: sleap-rtc token create --room ROOM --name NAME

    2. Legacy room credentials:
       sleap-rtc worker --room ROOM --token TOKEN

       Or omit both to create a new anonymous room (deprecated).
    """
    # Check for credential file if no explicit auth provided
    if not api_key and not room:
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
    has_legacy = room is not None or token is not None

    if has_api_key and has_legacy:
        logger.error("Cannot use both --api-key and --room/--token")
        logger.error("Choose one authentication method")
        sys.exit(1)

    if has_legacy:
        # Legacy mode validation
        if (room and not token) or (token and not room):
            logger.error("Both --room and --token must be provided together")
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
        room_id=room,
        token=token,
        working_dir=working_dir,
        name=name,
        room_secret=room_secret,
    )


@cli.command(name="train")
@click.option(
    "--session-string",
    "--session_string",
    "-s",
    type=str,
    required=False,
    help="Session string for direct connection to a specific worker.",
)
@click.option(
    "--room",
    "--room-id",
    "-r",
    type=str,
    required=False,
    help="Room ID for room-based worker discovery. Requires login (sleap-rtc login).",
)
@click.option(
    "--token",
    "-t",
    type=str,
    required=False,
    help="Room token (optional with JWT auth, for backward compatibility).",
)
@click.option(
    "--worker-id",
    "-w",
    type=str,
    required=False,
    help="Specific worker peer-id to connect to (skips discovery).",
)
@click.option(
    "--auto-select",
    "-a",
    is_flag=True,
    default=False,
    help="Automatically select best worker by GPU memory (use with --room).",
)
@click.option(
    "--pkg-path",
    "--pkg_path",
    "-p",
    type=str,
    required=True,
    help="Path to SLEAP training package. Filename is resolved on worker filesystem via interactive selector.",
)
@click.option(
    "--controller-port",
    "--controller_port",
    type=int,
    required=False,
    default=9000,
    help="ZMQ port for controller communication with SLEAP.",
)
@click.option(
    "--publish-port",
    "--publish_port",
    type=int,
    required=False,
    default=9001,
    help="ZMQ port for publish communication with SLEAP.",
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
@click.option(
    "--room-secret",
    type=str,
    envvar="SLEAP_ROOM_SECRET",
    required=False,
    help="Room secret for P2P authentication. Can also use SLEAP_ROOM_SECRET env var.",
)
def train(**kwargs):
    """Run remote training on a worker.

    Connection modes (mutually exclusive):

    1. Session string (direct): --session-string SESSION
       Connect directly to a specific worker using its session string.

    2. Room-based discovery: --room ROOM
       Join a room and discover available workers. Requires login first
       (sleap-rtc login). Supports:
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
    room_id = kwargs.pop("room", None)
    token = kwargs.pop("token", None)
    worker_id = kwargs.pop("worker_id", None)
    auto_select = kwargs.pop("auto_select", False)
    min_gpu_memory = kwargs.pop("min_gpu_memory", None)

    # Extract path resolution options
    worker_path = kwargs.pop("worker_path", None)
    non_interactive = kwargs.pop("non_interactive", False)
    mount_label = kwargs.pop("mount", None)

    # Extract P2P authentication options
    room_secret = kwargs.pop("room_secret", None)

    # Validation: Must provide either session string OR room credentials
    has_session = session_string is not None
    has_room = room_id is not None

    if has_session and has_room:
        logger.error("Connection modes are mutually exclusive. Use only one of:")
        logger.error("  --session-string (direct connection)")
        logger.error("  --room (room-based discovery)")
        sys.exit(1)

    if not has_session and not has_room:
        logger.error("Must provide a connection method:")
        logger.error("  --session-string SESSION (direct connection)")
        logger.error("  --room ROOM (room-based discovery, requires login)")
        sys.exit(1)

    # Room-based connection requires JWT authentication
    jwt_token = None
    if has_room:
        jwt_token = require_login()

    # Validation: worker selection options require room-id
    if (worker_id or auto_select) and not room_id:
        logger.error("--worker-id and --auto-select require --room")
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
        kwargs["token"] = token or ""  # Token optional with JWT auth
        kwargs["jwt_token"] = jwt_token

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
        room_secret=room_secret,
        **kwargs,
    )


@cli.command(name="track")
@click.option(
    "--session-string",
    "--session_string",
    "-s",
    type=str,
    required=False,
    help="Session string for direct connection to a specific worker.",
)
@click.option(
    "--room",
    "--room-id",
    "-r",
    type=str,
    required=False,
    help="Room ID for room-based worker discovery. Requires login (sleap-rtc login).",
)
@click.option(
    "--token",
    "-t",
    type=str,
    required=False,
    help="Room token (optional with JWT auth, for backward compatibility).",
)
@click.option(
    "--worker-id",
    "-w",
    type=str,
    required=False,
    help="Specific worker peer-id to connect to (skips discovery).",
)
@click.option(
    "--auto-select",
    "-a",
    is_flag=True,
    default=False,
    help="Automatically select best worker by GPU memory (use with --room).",
)
@click.option(
    "--data-path",
    "--data_path",
    "-d",
    type=str,
    required=True,
    help="Local path to .slp file with data for inference. File is transferred to worker.",
)
@click.option(
    "--model-paths",
    "--model_paths",
    "-m",
    multiple=True,
    required=True,
    help="Local paths to trained model directories. Directories are transferred to worker.",
)
@click.option(
    "--output",
    "-o",
    type=str,
    default="predictions.slp",
    help="Output predictions filename.",
)
@click.option(
    "--only-suggested-frames",
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
@click.option(
    "--room-secret",
    type=str,
    envvar="SLEAP_ROOM_SECRET",
    required=False,
    help="Room secret for P2P authentication. Can also use SLEAP_ROOM_SECRET env var.",
)
def track(**kwargs):
    """Run remote inference on a worker with pre-trained models.

    Connection modes (mutually exclusive):

    1. Session string (direct): --session-string SESSION
       Connect directly to a specific worker using its session string.

    2. Room-based discovery: --room ROOM
       Join a room and discover available workers. Supports:
       - Interactive selection (default)
       - Auto-select: --auto-select
       - Direct worker: --worker-id PEER_ID
       - GPU filter: --min-gpu-memory MB

    Note: Room-based discovery requires authentication. Run 'sleap-rtc login' first.
    """
    # Extract connection options
    session_string = kwargs.pop("session_string", None)
    room_id = kwargs.pop("room", None)
    token = kwargs.pop("token", None)
    worker_id = kwargs.pop("worker_id", None)
    auto_select = kwargs.pop("auto_select", False)
    min_gpu_memory = kwargs.pop("min_gpu_memory", None)

    # Extract P2P authentication options
    room_secret = kwargs.pop("room_secret", None)

    # Validation: Must provide either session string OR room credentials
    has_session = session_string is not None
    has_room = room_id is not None

    if has_session and has_room:
        logger.error("Connection modes are mutually exclusive. Use only one of:")
        logger.error("  --session-string (direct connection)")
        logger.error("  --room (room-based discovery)")
        sys.exit(1)

    if not has_session and not has_room:
        logger.error("Must provide a connection method:")
        logger.error("  --session-string SESSION (direct connection)")
        logger.error("  --room ROOM (room-based discovery, requires login)")
        sys.exit(1)

    # Room-based connection requires JWT authentication
    jwt_token = None
    if has_room:
        jwt_token = require_login()

    # Validation: worker selection options require room-id
    if (worker_id or auto_select) and not room_id:
        logger.error("--worker-id and --auto-select require --room")
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
        kwargs["token"] = token or ""  # Token optional with JWT auth
        kwargs["jwt_token"] = jwt_token

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
        room_secret=room_secret,
        **kwargs,
    )


# =============================================================================
# Deprecated Command Aliases
# =============================================================================


@cli.command(name="client-train", hidden=True)
@click.option("--session-string", "--session_string", "-s", type=str, required=False)
@click.option("--room", "--room-id", "-r", type=str, required=False)
@click.option("--token", "-t", type=str, required=False)
@click.option("--worker-id", "-w", type=str, required=False)
@click.option("--auto-select", "-a", is_flag=True, default=False)
@click.option("--pkg-path", "--pkg_path", "-p", type=str, required=True, help="Path resolved on worker")
@click.option("--controller-port", "--controller_port", type=int, required=False, default=9000)
@click.option("--publish-port", "--publish_port", type=int, required=False, default=9001)
@click.option("--min-gpu-memory", type=int, required=False, default=None)
@click.option("--worker-path", type=str, required=False, default=None)
@click.option("--non-interactive", is_flag=True, default=False)
@click.option("--mount", type=str, required=False, default=None)
@click.option("--room-secret", type=str, envvar="SLEAP_ROOM_SECRET", required=False)
@click.pass_context
def client_train_deprecated(ctx, **kwargs):
    """[DEPRECATED] Use 'sleap-rtc train' instead."""
    click.echo(
        click.style("Warning: ", fg="yellow", bold=True)
        + "'sleap-rtc client-train' is deprecated. Use 'sleap-rtc train' instead."
    )
    ctx.invoke(train, **kwargs)


@cli.command(name="client", hidden=True)
@click.option("--session-string", "--session_string", "-s", type=str, required=False)
@click.option("--room", "--room-id", "-r", type=str, required=False)
@click.option("--token", "-t", type=str, required=False)
@click.option("--worker-id", "-w", type=str, required=False)
@click.option("--auto-select", "-a", is_flag=True, default=False)
@click.option("--pkg-path", "--pkg_path", "-p", type=str, required=True, help="Path resolved on worker")
@click.option("--controller-port", "--controller_port", type=int, required=False, default=9000)
@click.option("--publish-port", "--publish_port", type=int, required=False, default=9001)
@click.option("--min-gpu-memory", type=int, required=False, default=None)
@click.option("--worker-path", type=str, required=False, default=None)
@click.option("--non-interactive", is_flag=True, default=False)
@click.option("--mount", type=str, required=False, default=None)
@click.option("--room-secret", type=str, envvar="SLEAP_ROOM_SECRET", required=False)
@click.pass_context
def client_deprecated(ctx, **kwargs):
    """[DEPRECATED] Use 'sleap-rtc train' instead."""
    click.echo(
        click.style("Warning: ", fg="yellow", bold=True)
        + "'sleap-rtc client' is deprecated. Use 'sleap-rtc train' instead."
    )
    ctx.invoke(train, **kwargs)


@cli.command(name="client-track", hidden=True)
@click.option("--session-string", "--session_string", "-s", type=str, required=False)
@click.option("--room", "--room-id", "-r", type=str, required=False)
@click.option("--token", "-t", type=str, required=False)
@click.option("--worker-id", "-w", type=str, required=False)
@click.option("--auto-select", "-a", is_flag=True, default=False)
@click.option("--data-path", "--data_path", "-d", type=str, required=True, help="Local path, transferred to worker")
@click.option("--model-paths", "--model_paths", "-m", multiple=True, required=True, help="Local paths, transferred to worker")
@click.option("--output", "-o", type=str, default="predictions.slp")
@click.option("--only-suggested-frames", "--only_suggested_frames", is_flag=True, default=True)
@click.option("--min-gpu-memory", type=int, required=False, default=None)
@click.option("--room-secret", type=str, envvar="SLEAP_ROOM_SECRET", required=False)
@click.pass_context
def client_track_deprecated(ctx, **kwargs):
    """[DEPRECATED] Use 'sleap-rtc track' instead."""
    click.echo(
        click.style("Warning: ", fg="yellow", bold=True)
        + "'sleap-rtc client-track' is deprecated. Use 'sleap-rtc track' instead."
    )
    ctx.invoke(track, **kwargs)


# =============================================================================
# Test Command Group (Experimental Features)
# =============================================================================


@cli.group()
def test():
    """Experimental file browser tools.

    These commands provide web-based tools for browsing worker filesystems
    and resolving file paths. They are considered experimental and may change.

    Available commands:
        browse         - Browse a worker's filesystem via web UI
        resolve-paths  - Resolve missing video paths in SLP files
    """
    pass


@test.command(name="browse")
@click.option(
    "--room",
    "--room-id",  # Alias for backward compatibility
    "-r",
    type=str,
    required=True,
    help="Room ID to connect to (required).",
)
@click.option(
    "--token",
    "-t",
    type=str,
    required=False,
    help="Room token (optional with JWT auth, for backward compatibility).",
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
@click.option(
    "--room-secret",
    type=str,
    envvar="SLEAP_ROOM_SECRET",
    required=False,
    help="Room secret for P2P authentication. Can also use SLEAP_ROOM_SECRET env var.",
)
def test_browse(room, token, port, no_browser, room_secret):
    """Browse a Worker's filesystem via web UI.

    [bold yellow]EXPERIMENTAL[/bold yellow]: This feature is under development.

    This command connects to a Worker in the specified room and starts
    a local web server that provides a browser-based file explorer.

    The browser UI allows you to:
    - Browse mount points and directories on the Worker
    - View file information (name, size, type)
    - Copy file paths for use with --worker-path

    Requires authentication. Run 'sleap-rtc login' first.

    Examples:

        # Connect to a Worker and open browser
        sleap-rtc test browse --room my-room

        # Use a different port
        sleap-rtc test browse --room my-room --port 9000

        # Print URL without opening browser (for remote access)
        sleap-rtc test browse --room my-room --no-browser
    """
    import asyncio
    from sleap_rtc.rtc_browse import run_browse_client

    # Require JWT authentication (client will fetch JWT from credentials)
    require_login()

    logger.info(f"Starting filesystem browser for room: {room}")
    logger.info(f"Local server will run on port: {port}")

    try:
        asyncio.run(
            run_browse_client(
                room_id=room,
                token=token or "",
                port=port,
                open_browser=not no_browser,
                room_secret=room_secret,
            )
        )
    except KeyboardInterrupt:
        logger.info("Browse session ended by user")
    except Exception as e:
        logger.error(f"Browse error: {e}")
        sys.exit(1)


@test.command(name="resolve-paths")
@click.option(
    "--room",
    "--room-id",  # Alias for backward compatibility
    "-r",
    type=str,
    required=True,
    help="Room ID to connect to (required).",
)
@click.option(
    "--token",
    "-t",
    type=str,
    required=False,
    help="Room token (optional with JWT auth, for backward compatibility).",
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
@click.option(
    "--room-secret",
    type=str,
    envvar="SLEAP_ROOM_SECRET",
    required=False,
    help="Room secret for P2P authentication. Can also use SLEAP_ROOM_SECRET env var.",
)
@click.option(
    "--use-jwt/--no-jwt",
    default=True,
    help="Use JWT authentication (default: yes). Disable for testing.",
)
def test_resolve_paths(room, token, slp, port, no_browser, room_secret, use_jwt):
    """Resolve missing video paths in an SLP file on a Worker.

    [bold yellow]EXPERIMENTAL[/bold yellow]: This feature is under development.

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
        sleap-rtc test resolve-paths --room my-room --slp /mnt/data/project.slp

        # Use a different port
        sleap-rtc test resolve-paths -r my-room -s /mnt/data/project.slp -p 9000

        # Print URL without opening browser
        sleap-rtc test resolve-paths -r my-room -s /mnt/data/project.slp --no-browser
    """
    import asyncio
    from sleap_rtc.rtc_resolve import run_resolve_client

    # Require JWT authentication (unless --no-jwt for testing)
    # The client will fetch JWT from credentials internally
    if use_jwt:
        require_login()

    logger.info(f"Starting video path resolution for: {slp}")
    logger.info(f"Connecting to room: {room}")

    try:
        result = asyncio.run(
            run_resolve_client(
                room_id=room,
                token=token or "",
                slp_path=slp,
                port=port,
                open_browser=not no_browser,
                room_secret=room_secret,
                use_jwt=use_jwt,
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


# =============================================================================
# Utility Commands
# =============================================================================


@cli.command(name="tui")
@click.option(
    "--room",
    "--room-id",
    "-r",
    type=str,
    required=False,
    help="Room ID to connect to directly (bypasses room selection).",
)
@click.option(
    "--room-secret",
    type=str,
    envvar="SLEAP_ROOM_SECRET",
    required=False,
    help="Room secret for P2P authentication. Can also use SLEAP_ROOM_SECRET env var.",
)
def tui(room, room_secret):
    """Launch the interactive TUI file browser.

    The TUI (Text User Interface) provides an interactive way to:
    - Log in to SLEAP-RTC (if not already logged in)
    - Select from rooms you have access to
    - Browse worker filesystems with Miller columns navigation
    - Resolve video paths in SLP files

    If you provide --room, it will connect directly to that room,
    bypassing the room selection screen.

    Examples:

        # Launch TUI with room selection
        sleap-rtc tui

        # Connect directly to a specific room
        sleap-rtc tui --room my-room

        # Connect with a room secret for P2P auth
        sleap-rtc tui --room my-room --room-secret SECRET
    """
    from sleap_rtc.tui.app import TUIApp

    app = TUIApp(
        room_id=room,
        room_secret=room_secret,
    )
    app.run()


@cli.command(name="status")
def status():
    """Display current authentication and configuration status.

    Shows:
    - Current login status and user info
    - JWT token expiration
    - Saved room secrets
    - Credential file location
    - API tokens (if any)

    Example:
        sleap-rtc status
    """
    from sleap_rtc.auth.credentials import (
        get_credentials,
        get_jwt,
        get_user,
        is_logged_in,
        CREDENTIALS_PATH,
    )

    click.echo("")
    click.echo(click.style("SLEAP-RTC Status", bold=True))
    click.echo("=" * 40)

    # Login status
    click.echo("")
    click.echo(click.style("Authentication:", bold=True))
    if is_logged_in():
        user = get_user()
        click.echo(f"  Status:   {click.style('Logged in', fg='green')}")
        click.echo(f"  Username: {user.get('username', 'unknown')}")
        click.echo(f"  User ID:  {user.get('user_id', user.get('id', 'unknown'))}")

        # JWT expiry
        jwt_token = get_jwt()
        if jwt_token:
            try:
                import jwt
                claims = jwt.decode(jwt_token, options={"verify_signature": False})
                exp = claims.get("exp")
                if exp:
                    from datetime import datetime
                    exp_dt = datetime.fromtimestamp(exp)
                    now = datetime.now()
                    if exp_dt > now:
                        remaining = exp_dt - now
                        hours = remaining.total_seconds() / 3600
                        click.echo(f"  JWT expires: {exp_dt.strftime('%Y-%m-%d %H:%M')} ({hours:.1f}h remaining)")
                    else:
                        click.echo(f"  JWT expires: {click.style('EXPIRED', fg='red')}")
            except Exception:
                pass
    else:
        click.echo(f"  Status: {click.style('Not logged in', fg='yellow')}")
        click.echo("  Run 'sleap-rtc login' to authenticate")

    # Credential file
    click.echo("")
    click.echo(click.style("Credentials File:", bold=True))
    click.echo(f"  Location: {CREDENTIALS_PATH}")
    if CREDENTIALS_PATH.exists():
        click.echo(f"  Status:   {click.style('exists', fg='green')}")
    else:
        click.echo(f"  Status:   {click.style('not found', fg='yellow')}")

    # Room secrets
    creds = get_credentials()
    room_secrets = creds.get("room_secrets", {})
    click.echo("")
    click.echo(click.style("Room Secrets:", bold=True))
    if room_secrets:
        for room_id, secret in room_secrets.items():
            masked = secret[:4] + "..." + secret[-4:] if len(secret) > 8 else "****"
            click.echo(f"  {room_id}: {masked}")
    else:
        click.echo("  No room secrets saved")

    # API tokens
    tokens = creds.get("tokens", {})
    click.echo("")
    click.echo(click.style("API Tokens:", bold=True))
    if tokens:
        for room_id, token_info in tokens.items():
            name = token_info.get("worker_name", "unknown")
            api_key = token_info.get("api_key", "")
            masked_key = api_key[:8] + "..." if len(api_key) > 8 else api_key
            click.echo(f"  {room_id}: {name} ({masked_key})")
    else:
        click.echo("  No API tokens saved")

    click.echo("")


@cli.command(name="doctor")
def doctor():
    """Check system configuration and connectivity.

    Runs diagnostic checks to verify:
    - Python version and environment
    - Required dependencies
    - Network connectivity to signaling server
    - Credential file permissions
    - Configuration file status

    Use this command to troubleshoot connection issues.

    Example:
        sleap-rtc doctor
    """
    import platform

    click.echo("")
    click.echo(click.style("SLEAP-RTC Doctor", bold=True))
    click.echo("=" * 40)

    all_ok = True

    # Python version
    click.echo("")
    click.echo(click.style("Python Environment:", bold=True))
    py_version = platform.python_version()
    py_major, py_minor = map(int, py_version.split(".")[:2])
    if py_major >= 3 and py_minor >= 11:
        click.echo(f"  Python version: {py_version} {click.style('✓', fg='green')}")
    else:
        click.echo(f"  Python version: {py_version} {click.style('✗ (requires 3.11+)', fg='red')}")
        all_ok = False

    click.echo(f"  Platform: {platform.system()} {platform.release()}")

    # Check key dependencies
    click.echo("")
    click.echo(click.style("Dependencies:", bold=True))
    deps_to_check = ["aiortc", "websockets", "textual", "rich_click", "requests"]
    for dep in deps_to_check:
        try:
            __import__(dep.replace("-", "_"))
            click.echo(f"  {dep}: {click.style('✓', fg='green')}")
        except ImportError:
            click.echo(f"  {dep}: {click.style('✗ missing', fg='red')}")
            all_ok = False

    # Network connectivity
    click.echo("")
    click.echo(click.style("Network Connectivity:", bold=True))
    from sleap_rtc.config import get_config
    config = get_config()
    server_url = config.get_http_url()
    click.echo(f"  Signaling server: {server_url}")

    try:
        response = requests.get(f"{server_url}/health", timeout=10)
        if response.status_code == 200:
            click.echo(f"  Health check: {click.style('✓ reachable', fg='green')}")
        else:
            click.echo(f"  Health check: {click.style(f'✗ HTTP {response.status_code}', fg='yellow')}")
            all_ok = False
    except requests.exceptions.Timeout:
        click.echo(f"  Health check: {click.style('✗ timeout', fg='red')}")
        all_ok = False
    except requests.exceptions.ConnectionError:
        click.echo(f"  Health check: {click.style('✗ connection failed', fg='red')}")
        all_ok = False
    except Exception as e:
        click.echo(f"  Health check: {click.style(f'✗ {e}', fg='red')}")
        all_ok = False

    # Credential file
    click.echo("")
    click.echo(click.style("Credentials:", bold=True))
    from sleap_rtc.auth.credentials import CREDENTIALS_PATH, is_logged_in
    click.echo(f"  File: {CREDENTIALS_PATH}")

    if CREDENTIALS_PATH.exists():
        click.echo(f"  Exists: {click.style('✓', fg='green')}")
        # Check permissions
        import stat
        file_stat = CREDENTIALS_PATH.stat()
        mode = file_stat.st_mode
        if mode & stat.S_IRWXO:  # Others have any permissions
            click.echo(f"  Permissions: {click.style('✗ world-readable (insecure)', fg='yellow')}")
        else:
            click.echo(f"  Permissions: {click.style('✓ secure', fg='green')}")

        if is_logged_in():
            click.echo(f"  Logged in: {click.style('✓', fg='green')}")
        else:
            click.echo(f"  Logged in: {click.style('✗ no valid JWT', fg='yellow')}")
    else:
        click.echo(f"  Exists: {click.style('✗ not found', fg='yellow')}")
        click.echo("  Run 'sleap-rtc login' to create credentials")

    # Config file
    click.echo("")
    click.echo(click.style("Configuration:", bold=True))
    config_file = Path("sleap-rtc.toml")
    if config_file.exists():
        click.echo(f"  Config file: {config_file.absolute()} {click.style('✓', fg='green')}")
    else:
        click.echo(f"  Config file: {click.style('using defaults', fg='cyan')}")

    # Summary
    click.echo("")
    click.echo("=" * 40)
    if all_ok:
        click.echo(click.style("All checks passed! ✓", fg="green", bold=True))
    else:
        click.echo(click.style("Some checks failed. Review above.", fg="yellow", bold=True))
    click.echo("")


# =============================================================================
# Deprecated Top-Level Aliases for Test Commands
# =============================================================================


@cli.command(name="browse", hidden=True)
@click.option("--room", "--room-id", "-r", type=str, required=True)
@click.option("--token", "-t", type=str, required=False)
@click.option("--port", "-p", type=int, default=8765)
@click.option("--no-browser", is_flag=True, default=False)
@click.option("--room-secret", type=str, envvar="SLEAP_ROOM_SECRET", required=False)
@click.pass_context
def browse_deprecated(ctx, **kwargs):
    """[DEPRECATED] Use 'sleap-rtc test browse' instead."""
    click.echo(
        click.style("Warning: ", fg="yellow", bold=True)
        + "'sleap-rtc browse' is deprecated. Use 'sleap-rtc test browse' instead."
    )
    ctx.invoke(test_browse, **kwargs)


@cli.command(name="resolve-paths", hidden=True)
@click.option("--room", "--room-id", "-r", type=str, required=True)
@click.option("--token", "-t", type=str, required=False)
@click.option("--slp", "-s", type=str, required=True)
@click.option("--port", "-p", type=int, default=8765)
@click.option("--no-browser", is_flag=True, default=False)
@click.option("--room-secret", type=str, envvar="SLEAP_ROOM_SECRET", required=False)
@click.option("--use-jwt/--no-jwt", default=True)
@click.pass_context
def resolve_paths_deprecated(ctx, **kwargs):
    """[DEPRECATED] Use 'sleap-rtc test resolve-paths' instead."""
    click.echo(
        click.style("Warning: ", fg="yellow", bold=True)
        + "'sleap-rtc resolve-paths' is deprecated. Use 'sleap-rtc test resolve-paths' instead."
    )
    ctx.invoke(test_resolve_paths, **kwargs)


if __name__ == "__main__":
    cli()
