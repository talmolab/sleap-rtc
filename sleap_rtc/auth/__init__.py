"""Authentication module for SLEAP-RTC.

This module provides:
- credentials: Load/save credentials from ~/.sleap-rtc/credentials.json
- github: Browser-based GitHub OAuth flow for CLI
- totp: TOTP validation for P2P authentication
"""

from sleap_rtc.auth.credentials import (
    get_credentials,
    save_credentials,
    clear_credentials,
    get_jwt,
    get_user,
    get_api_key,
    CREDENTIALS_PATH,
)
from sleap_rtc.auth.github import github_login, get_dashboard_url
from sleap_rtc.auth.totp import validate_otp, generate_otp

__all__ = [
    # Credentials
    "get_credentials",
    "save_credentials",
    "clear_credentials",
    "get_jwt",
    "get_user",
    "get_api_key",
    "CREDENTIALS_PATH",
    # GitHub OAuth
    "github_login",
    "get_dashboard_url",
    # TOTP
    "validate_otp",
    "generate_otp",
]
