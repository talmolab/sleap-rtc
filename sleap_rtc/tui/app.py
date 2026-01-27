"""Main TUI application for sleap-rtc.

This module provides the TUIApp class that manages the overall TUI experience,
including login flow, room selection, and file browsing.
"""

from typing import Optional

from textual.app import App
from textual.binding import Binding

from sleap_rtc.tui.screens.login import LoginScreen
from sleap_rtc.tui.screens.room_select import RoomSelectScreen
from sleap_rtc.tui.screens.browser import BrowserScreen
from sleap_rtc.tui.screens.token_input import TokenInputScreen


class TUIApp(App):
    """Main TUI application for sleap-rtc file browser.

    This app manages:
    - Login flow (if not authenticated)
    - Room selection (if logged in)
    - File browser with Miller columns
    - SLP path resolution
    """

    TITLE = "sleap-rtc"
    SUB_TITLE = "File Browser"

    CSS = """
    /* Basic styling */
    .status-connected {
        color: $success;
    }

    .status-disconnected {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
    ]

    def __init__(
        self,
        room_id: Optional[str] = None,
        token: Optional[str] = None,
        otp_secret: Optional[str] = None,
    ):
        """Initialize the TUI app.

        Args:
            room_id: Optional room ID (bypasses room selection).
            token: Optional room token (required with room_id).
            otp_secret: Optional OTP secret for auto-authentication.
        """
        super().__init__()
        self.room_id = room_id
        self.token = token
        self.otp_secret = otp_secret

        # Will be set during connection
        self.bridge = None

    def on_mount(self) -> None:
        """Called when app is mounted. Determines initial screen based on state."""
        # Check if room credentials provided directly (direct mode)
        if self.room_id and self.token:
            # Skip login/room selection, go straight to browser
            self._show_browser(self.room_id, self.token)
            return

        # Check if user is logged in
        from sleap_rtc.auth.credentials import is_logged_in

        if is_logged_in():
            # Show room selection
            self._show_room_select()
        else:
            # Show login screen
            self._show_login()

    def _show_login(self) -> None:
        """Show the login screen."""
        def on_login_success(jwt: str, user: dict) -> None:
            """Called when login succeeds."""
            self.notify(f"Logged in as {user.get('username', 'unknown')}")
            # After login, show room selection
            self._show_room_select()

        login_screen = LoginScreen(on_login_success=on_login_success)
        self.push_screen(login_screen)

    def _show_room_select(self) -> None:
        """Show the room selection screen."""
        def on_room_selected(room_data: dict) -> None:
            """Called when a room is selected."""
            room_id = room_data.get("room_id")
            room_name = room_data.get("name", room_id)

            # Try to get token from room data or stored credentials
            token = room_data.get("token", "")

            if not token:
                # Try to get token from stored credentials
                from sleap_rtc.auth.credentials import get_credentials
                creds = get_credentials()
                tokens = creds.get("tokens", {})
                room_token = tokens.get(room_id, {})
                token = room_token.get("api_key", "")

            if not token:
                # Show token input screen
                self._show_token_input(room_id, room_name)
                return

            self._show_browser(room_id, token)

        room_screen = RoomSelectScreen(on_room_selected=on_room_selected)
        self.push_screen(room_screen)

    def _show_token_input(self, room_id: str, room_name: str) -> None:
        """Show the token input screen.

        Args:
            room_id: Room ID to connect to.
            room_name: Display name for the room.
        """
        def on_token_entered(token: str) -> None:
            """Called when token is entered and saved."""
            # Pop the token input screen
            self.pop_screen()
            # Pop the room select screen
            self.pop_screen()
            # Show the browser
            self._show_browser(room_id, token)

        def on_cancel() -> None:
            """Called when user cancels token input."""
            self.pop_screen()

        token_screen = TokenInputScreen(
            room_id=room_id,
            room_name=room_name,
            on_token_entered=on_token_entered,
            on_cancel=on_cancel,
        )
        self.push_screen(token_screen)

    def _show_browser(self, room_id: str, token: str) -> None:
        """Show the file browser screen.

        Args:
            room_id: Room ID to browse.
            token: Room token for authentication.
        """
        browser_screen = BrowserScreen(
            room_id=room_id,
            token=token,
            otp_secret=self.otp_secret,
        )
        self.push_screen(browser_screen)

    def action_help(self) -> None:
        """Show help information."""
        self.notify(
            "Navigation: Arrow keys | Enter: Select | q: Quit | ?: Help",
            timeout=5,
        )


def run_tui(
    room_id: Optional[str] = None,
    token: Optional[str] = None,
    otp_secret: Optional[str] = None,
) -> None:
    """Run the TUI application.

    Args:
        room_id: Optional room ID to connect to directly.
        token: Optional room token (required with room_id).
        otp_secret: Optional OTP secret for auto-authentication.
    """
    app = TUIApp(room_id=room_id, token=token, otp_secret=otp_secret)
    app.run()
