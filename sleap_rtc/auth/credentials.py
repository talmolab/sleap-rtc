"""Credential file management for SLEAP-RTC.

Stores credentials in ~/.sleap-rtc/credentials.json with the schema:
{
    "jwt": "eyJ...",
    "user": {
        "id": "12345678",
        "username": "researcher1",
        "avatar_url": "https://..."
    },
    "tokens": {
        "<room_id>": {
            "api_key": "slp_xxx...",
            "worker_name": "lab-gpu-1"
        }
    }
}
"""

import json
import os
import stat
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# Credentials file location
CREDENTIALS_DIR = Path.home() / ".sleap-rtc"
CREDENTIALS_PATH = CREDENTIALS_DIR / "credentials.json"


def _ensure_credentials_dir() -> None:
    """Ensure the credentials directory exists with proper permissions."""
    if not CREDENTIALS_DIR.exists():
        CREDENTIALS_DIR.mkdir(parents=True, mode=0o700)
        logger.debug(f"Created credentials directory: {CREDENTIALS_DIR}")


def get_credentials() -> dict[str, Any]:
    """Load credentials from file.

    Returns:
        Credentials dictionary, or empty dict if file doesn't exist.
    """
    if not CREDENTIALS_PATH.exists():
        return {}

    try:
        with open(CREDENTIALS_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load credentials: {e}")
        return {}


def save_credentials(credentials: dict[str, Any]) -> None:
    """Save credentials to file with restrictive permissions.

    Args:
        credentials: Credentials dictionary to save.
    """
    _ensure_credentials_dir()

    # Write to temp file first, then rename (atomic)
    temp_path = CREDENTIALS_PATH.with_suffix(".tmp")

    try:
        with open(temp_path, "w") as f:
            json.dump(credentials, f, indent=2)

        # Set restrictive permissions (owner read/write only)
        os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)

        # Atomic rename
        temp_path.rename(CREDENTIALS_PATH)
        logger.debug(f"Saved credentials to {CREDENTIALS_PATH}")

    except IOError as e:
        logger.error(f"Failed to save credentials: {e}")
        if temp_path.exists():
            temp_path.unlink()
        raise


def clear_credentials() -> None:
    """Remove the credentials file."""
    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()
        logger.info("Credentials cleared")
    else:
        logger.debug("No credentials to clear")


def get_jwt() -> Optional[str]:
    """Get the stored JWT token.

    Returns:
        JWT string if stored, None otherwise.
    """
    creds = get_credentials()
    return creds.get("jwt")


def get_user() -> Optional[dict[str, Any]]:
    """Get the stored user info.

    Returns:
        User dictionary with id, username, avatar_url if stored, None otherwise.
    """
    creds = get_credentials()
    return creds.get("user")


def get_api_key(room_id: str) -> Optional[str]:
    """Get the API key for a specific room.

    Args:
        room_id: The room ID to get the API key for.

    Returns:
        API key string if stored, None otherwise.
    """
    creds = get_credentials()
    tokens = creds.get("tokens", {})
    room_token = tokens.get(room_id, {})
    return room_token.get("api_key")


def save_jwt(jwt: str, user: dict[str, Any]) -> None:
    """Save JWT and user info to credentials.

    Args:
        jwt: JWT token string.
        user: User info dictionary.
    """
    creds = get_credentials()
    creds["jwt"] = jwt
    creds["user"] = user
    save_credentials(creds)


def save_token(room_id: str, api_key: str, worker_name: str) -> None:
    """Save a worker token for a room.

    Args:
        room_id: Room ID the token is for.
        api_key: API key (slp_xxx...).
        worker_name: Human-readable name for the worker.
    """
    creds = get_credentials()
    if "tokens" not in creds:
        creds["tokens"] = {}

    creds["tokens"][room_id] = {
        "api_key": api_key,
        "worker_name": worker_name,
    }
    save_credentials(creds)


def remove_token(room_id: str) -> bool:
    """Remove a stored token for a room.

    Args:
        room_id: Room ID to remove token for.

    Returns:
        True if token was removed, False if not found.
    """
    creds = get_credentials()
    tokens = creds.get("tokens", {})

    if room_id in tokens:
        del tokens[room_id]
        creds["tokens"] = tokens
        save_credentials(creds)
        return True
    return False


def is_logged_in() -> bool:
    """Check if user is currently logged in.

    Returns:
        True if JWT exists in credentials.
    """
    return get_jwt() is not None
