"""GitHub OAuth flow for SLEAP-RTC CLI.

Implements browser-based OAuth flow:
1. Open browser to GitHub authorization URL
2. User authorizes the app
3. GitHub redirects to callback URL with auth code
4. CLI exchanges code for JWT via signaling server
"""

import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests
from loguru import logger

from sleap_rtc.config import get_config

# GitHub OAuth endpoints
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"

# Local callback server settings
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8642
CALLBACK_PATH = "/callback"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    auth_code: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def do_GET(self):
        """Handle GET request from OAuth redirect."""
        parsed = urlparse(self.path)

        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return

        # Parse query parameters
        params = parse_qs(parsed.query)

        if "error" in params:
            OAuthCallbackHandler.error = params["error"][0]
            self._send_error_page(params.get("error_description", ["Unknown error"])[0])
            return

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            OAuthCallbackHandler.state = params.get("state", [None])[0]
            self._send_success_page()
            return

        self._send_error_page("Missing authorization code")

    def _send_success_page(self):
        """Send success HTML page."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>SLEAP-RTC - Login Successful</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    text-align: center;
                    background: white;
                    padding: 40px 60px;
                    border-radius: 12px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                }
                h1 { color: #28a745; margin-bottom: 10px; }
                p { color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Login Successful</h1>
                <p>You can close this window and return to the terminal.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def _send_error_page(self, error_msg: str):
        """Send error HTML page."""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SLEAP-RTC - Login Failed</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    text-align: center;
                    background: white;
                    padding: 40px 60px;
                    border-radius: 12px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                }}
                h1 {{ color: #dc3545; margin-bottom: 10px; }}
                p {{ color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Login Failed</h1>
                <p>{error_msg}</p>
                <p>Please try again from the terminal.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())


def github_login(client_id: str, timeout: int = 120) -> dict:
    """Perform browser-based GitHub OAuth login.

    Args:
        client_id: GitHub OAuth App client ID.
        timeout: Maximum seconds to wait for callback (default: 120).

    Returns:
        Dictionary with jwt, user info from signaling server.

    Raises:
        RuntimeError: If login fails or times out.
    """
    config = get_config()

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Build authorization URL
    redirect_uri = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}"
    auth_url = (
        f"{GITHUB_AUTHORIZE_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read:user"
        f"&state={state}"
    )

    # Reset handler state
    OAuthCallbackHandler.auth_code = None
    OAuthCallbackHandler.state = None
    OAuthCallbackHandler.error = None

    # Start local server
    server = HTTPServer((CALLBACK_HOST, CALLBACK_PORT), OAuthCallbackHandler)
    server.timeout = 1  # Check for shutdown every second

    # Run server in background thread
    server_thread = Thread(target=lambda: _run_server(server, timeout))
    server_thread.daemon = True
    server_thread.start()

    # Open browser
    logger.info(f"Opening browser for GitHub login...")
    logger.info(f"If browser doesn't open, visit: {auth_url}")
    webbrowser.open(auth_url)

    # Wait for callback
    start_time = time.time()
    while server_thread.is_alive():
        if OAuthCallbackHandler.auth_code or OAuthCallbackHandler.error:
            break
        if time.time() - start_time > timeout:
            server.shutdown()
            raise RuntimeError(f"Login timed out after {timeout} seconds")
        time.sleep(0.5)

    server.shutdown()

    # Check for errors
    if OAuthCallbackHandler.error:
        raise RuntimeError(f"GitHub OAuth error: {OAuthCallbackHandler.error}")

    if not OAuthCallbackHandler.auth_code:
        raise RuntimeError("No authorization code received")

    # Verify state
    if OAuthCallbackHandler.state != state:
        raise RuntimeError("State mismatch - possible CSRF attack")

    # Exchange code for JWT via signaling server
    logger.info("Exchanging authorization code for JWT...")
    return _exchange_code(
        OAuthCallbackHandler.auth_code,
        redirect_uri,
        config.get_http_url(),
    )


def _run_server(server: HTTPServer, timeout: int):
    """Run HTTP server until timeout or callback received."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if OAuthCallbackHandler.auth_code or OAuthCallbackHandler.error:
            break
        server.handle_request()


def _exchange_code(code: str, redirect_uri: str, server_url: str) -> dict:
    """Exchange authorization code for JWT via signaling server.

    Args:
        code: GitHub authorization code.
        redirect_uri: Redirect URI used in authorization.
        server_url: Signaling server HTTP base URL.

    Returns:
        Dictionary with jwt, user from server response.
    """
    endpoint = f"{server_url}/api/auth/github/callback"

    response = requests.post(
        endpoint,
        json={
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )

    if response.status_code != 200:
        error_msg = response.json().get("error", response.text)
        raise RuntimeError(f"Token exchange failed: {error_msg}")

    data = response.json()

    # Server returns 'token' not 'jwt'
    if "token" not in data or "user" not in data:
        raise RuntimeError("Invalid response from server")

    # Normalize to 'jwt' for consistency
    data["jwt"] = data.pop("token")
    return data


def github_device_login(client_id: str) -> dict:
    """Perform device flow GitHub OAuth login (for headless environments).

    This is an alternative flow for when a browser can't be opened locally.
    User visits a URL and enters a code manually.

    Args:
        client_id: GitHub OAuth App client ID.

    Returns:
        Dictionary with jwt, user info from signaling server.

    Raises:
        RuntimeError: If login fails.
        NotImplementedError: Device flow not yet implemented.
    """
    # Device flow requires a different OAuth app configuration
    # For now, fall back to browser-based flow
    raise NotImplementedError(
        "Device flow not yet implemented. "
        "Please use browser-based login (github_login)."
    )
