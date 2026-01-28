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
    ):
        """Initialize the TUI app.

        Args:
            room_id: Optional room ID (bypasses room selection).
            token: Optional room token (not required for JWT auth, but kept for compatibility).
        """
        super().__init__()
        self.room_id = room_id
        self.token = token

        # Will be set during connection
        self.bridge = None

    def on_mount(self) -> None:
        """Called when app is mounted. Determines initial screen based on state."""
        # Check if room ID provided directly (direct mode)
        if self.room_id:
            # Skip login/room selection, go straight to browser
            # Token is optional for JWT auth (server validates via membership)
            self._show_browser(self.room_id, self.token or "")
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

            # For JWT auth, the server validates room access via membership,
            # not via room token. The token field is ignored by the server
            # when JWT is present. We pass an empty string for compatibility.
            # The room_data may include a token if the user owns the room,
            # but it's not required for connection.
            token = room_data.get("token", "")

            self._show_browser(room_id, token)

        room_screen = RoomSelectScreen(on_room_selected=on_room_selected)
        self.push_screen(room_screen)

    def _show_browser(self, room_id: str, token: str) -> None:
        """Show the file browser screen.

        Args:
            room_id: Room ID to browse.
            token: Room token for authentication.
        """
        browser_screen = BrowserScreen(
            room_id=room_id,
            token=token,
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
) -> None:
    """Run the TUI application.

    Args:
        room_id: Optional room ID to connect to directly.
        token: Optional room token (not required for JWT auth).
    """
    app = TUIApp(room_id=room_id, token=token)
    app.run()
