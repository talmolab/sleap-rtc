"""Authentication module for SLEAP-RTC.

This module provides:
- credentials: Load/save credentials from ~/.sleap-rtc/credentials.json
- github: Browser-based GitHub OAuth flow for CLI
- psk: Pre-shared key utilities for P2P authentication
"""

from sleap_rtc.auth.credentials import (
    get_credentials,
    save_credentials,
    clear_credentials,
    get_jwt,
    get_user,
    get_api_key,
    get_room_secret,
    save_room_secret,
    remove_room_secret,
    CREDENTIALS_PATH,
)
from sleap_rtc.auth.github import github_login, get_dashboard_url
from sleap_rtc.auth.psk import (
    generate_secret,
    generate_nonce,
    compute_hmac,
    verify_hmac,
)
from sleap_rtc.auth.secret_resolver import (
    resolve_secret,
    get_secret_base_path,
    get_secret_sources,
    ENV_ROOM_SECRET,
    ENV_SECRET_PATH,
)

__all__ = [
    # Credentials
    "get_credentials",
    "save_credentials",
    "clear_credentials",
    "get_jwt",
    "get_user",
    "get_api_key",
    "get_room_secret",
    "save_room_secret",
    "remove_room_secret",
    "CREDENTIALS_PATH",
    # GitHub OAuth
    "github_login",
    "get_dashboard_url",
    # PSK authentication
    "generate_secret",
    "generate_nonce",
    "compute_hmac",
    "verify_hmac",
    # Secret resolution
    "resolve_secret",
    "get_secret_base_path",
    "get_secret_sources",
    "ENV_ROOM_SECRET",
    "ENV_SECRET_PATH",
]
