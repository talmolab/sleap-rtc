"""TOTP (Time-based One-Time Password) utilities for SLEAP-RTC.

Used for P2P authentication between clients and workers.
"""

from typing import Optional

try:
    import pyotp
except ImportError:
    pyotp = None


def validate_otp(secret: str, otp: str, window: int = 1) -> bool:
    """Validate a TOTP code against a secret.

    Args:
        secret: Base32-encoded TOTP secret.
        otp: 6-digit OTP code to validate.
        window: Number of time periods to check before/after current (default: 1).
                A window of 1 means we accept codes from 30 seconds before
                to 30 seconds after the current time.

    Returns:
        True if OTP is valid, False otherwise.

    Raises:
        ImportError: If pyotp is not installed.
    """
    if pyotp is None:
        raise ImportError(
            "pyotp is required for OTP validation. "
            "Install it with: pip install pyotp"
        )

    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(otp, valid_window=window)
    except Exception:
        return False


def generate_otp(secret: str) -> str:
    """Generate the current TOTP code for a secret.

    Args:
        secret: Base32-encoded TOTP secret.

    Returns:
        6-digit OTP code string.

    Raises:
        ImportError: If pyotp is not installed.
    """
    if pyotp is None:
        raise ImportError(
            "pyotp is required for OTP generation. "
            "Install it with: pip install pyotp"
        )

    totp = pyotp.TOTP(secret)
    return totp.now()


def get_otp_uri(secret: str, room_id: str, issuer: str = "SLEAP-RTC") -> str:
    """Generate an OTP URI for authenticator apps.

    Args:
        secret: Base32-encoded TOTP secret.
        room_id: Room identifier (used as account name).
        issuer: Issuer name shown in authenticator (default: SLEAP-RTC).

    Returns:
        otpauth:// URI string.

    Raises:
        ImportError: If pyotp is not installed.
    """
    if pyotp is None:
        raise ImportError(
            "pyotp is required for OTP URI generation. "
            "Install it with: pip install pyotp"
        )

    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=room_id, issuer_name=issuer)


def time_remaining() -> int:
    """Get seconds remaining until the current OTP expires.

    Returns:
        Seconds until next OTP code (0-30).

    Raises:
        ImportError: If pyotp is not installed.
    """
    if pyotp is None:
        raise ImportError(
            "pyotp is required for OTP timing. "
            "Install it with: pip install pyotp"
        )

    import time

    return 30 - (int(time.time()) % 30)
