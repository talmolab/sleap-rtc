"""Room selection screen for TUI.

This screen displays a list of rooms the user has access to and allows
them to select one to connect to.
"""

import asyncio
from typing import Optional, Callable

import requests
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, ListView, ListItem, Label
from textual.reactive import reactive

from sleap_rtc.config import get_config
from sleap_rtc.auth.credentials import get_user


class RoomListItem(ListItem):
    """A list item representing a room."""

    def __init__(self, room_data: dict, *args, **kwargs):
        """Initialize room list item.

        Args:
            room_data: Dict with room_id, role, joined_at, etc.
        """
        super().__init__(*args, **kwargs)
        self.room_data = room_data

    def compose(self) -> ComposeResult:
        room_id = self.room_data.get("room_id", "unknown")
        role = self.room_data.get("role", "member")
        name = self.room_data.get("name", room_id)

        # Role indicator
        role_icon = "" if role == "owner" else ""

        yield Label(f"{role_icon}  {name}")


class RoomSelectScreen(Screen):
    """Screen for selecting a room to connect to.

    Fetches rooms from the API and displays them in a list for selection.
    """

    CSS = """
    RoomSelectScreen {
        background: $background;
    }

    /* Custom header bar */
    #app-header {
        width: 100%;
        height: 1;
        padding: 0 1;
        background: $panel;
    }

    #header-title {
        text-style: bold;
    }

    #header-user {
        dock: right;
        color: $primary;
    }

    #room-container {
        align: center middle;
        height: 1fr;
    }

    #room-box {
        width: 60;
        height: auto;
        max-height: 80%;
        padding: 2 4;
        border: solid $primary;
    }

    .title {
        text-style: bold;
        text-align: center;
        color: $primary;
        margin-bottom: 1;
    }

    .subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    #room-list {
        height: auto;
        max-height: 20;
        margin: 1 0;
        border: solid $primary-darken-2;
    }

    #status {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }

    #error {
        text-align: center;
        color: $error;
        margin-top: 1;
    }

    .hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }

    #no-rooms {
        text-align: center;
        padding: 2;
        color: $warning;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    # Reactive properties (init=False to prevent watchers firing before mount)
    loading = reactive(True, init=False)
    error_message = reactive("", init=False)

    def __init__(
        self,
        on_room_selected: Optional[Callable[[dict], None]] = None,
        name: Optional[str] = None,
    ):
        """Initialize room select screen.

        Args:
            on_room_selected: Callback when room is selected (receives room dict).
            name: Screen name.
        """
        super().__init__(name=name)
        self.on_room_selected = on_room_selected
        self.rooms: list[dict] = []

    def compose(self) -> ComposeResult:
        # Get user info for profile display
        user = get_user()
        username = user.get("username", "unknown") if user else "unknown"

        # Custom header with profile
        with Horizontal(id="app-header"):
            yield Static("sleap-rtc", id="header-title")
            yield Static(f"👤 {username}", id="header-user")

        yield Container(
            Vertical(
                Static("Select a Room", classes="title"),
                Static("Choose a room to browse its workers", classes="subtitle"),
                ListView(id="room-list"),
                Static("Loading rooms...", id="status"),
                Static("", id="error"),
                Static("Press Enter to select, 'r' to refresh, 'q' to quit", classes="hint"),
                id="room-box",
            ),
            id="room-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Fetch rooms when screen is mounted."""
        self.fetch_rooms()

    def watch_loading(self, loading: bool) -> None:
        """Update UI when loading state changes."""
        try:
            status = self.query_one("#status", Static)
            if loading:
                status.update("Loading rooms...")
                status.display = True
            else:
                status.display = False
        except Exception:
            pass  # Widget not mounted yet

    def watch_error_message(self, message: str) -> None:
        """Update error display."""
        try:
            error = self.query_one("#error", Static)
            if message:
                error.update(f"Error: {message}")
                error.display = True
            else:
                error.display = False
        except Exception:
            pass  # Widget not mounted yet

    def fetch_rooms(self) -> None:
        """Fetch rooms from API."""
        self.loading = True
        self.error_message = ""
        asyncio.create_task(self._fetch_rooms_async())

    async def _fetch_rooms_async(self) -> None:
        """Async room fetching."""
        from sleap_rtc.auth.credentials import get_valid_jwt

        jwt_token = get_valid_jwt()
        if not jwt_token:
            self.loading = False
            self.error_message = "Not logged in or token expired. Run: sleap-rtc auth login"
            return

        config = get_config()
        endpoint = f"{config.get_http_url()}/api/auth/rooms"

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: requests.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {jwt_token}"},
                    timeout=30,
                )
            )

            if response.status_code != 200:
                error = response.json().get("error", response.text)
                self.loading = False
                self.error_message = f"Failed to fetch rooms: {error}"
                return

            data = response.json()
            self.rooms = data.get("rooms", [])
            self.loading = False

            # Update the list view
            self._populate_room_list()

        except requests.RequestException as e:
            self.loading = False
            self.error_message = f"Request failed: {e}"

    def _populate_room_list(self) -> None:
        """Populate the room list with fetched rooms."""
        room_list = self.query_one("#room-list", ListView)
        room_list.clear()

        if not self.rooms:
            # Show "no rooms" message
            item = ListItem(Label("No rooms found. Create one with: sleap-rtc room create"))
            room_list.append(item)
            return

        for room in self.rooms:
            item = RoomListItem(room)
            room_list.append(item)

        # Focus the list
        room_list.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle room selection."""
        if not self.rooms:
            return

        item = event.item
        if isinstance(item, RoomListItem):
            room_data = item.room_data

            # Call the selection callback
            if self.on_room_selected:
                self.on_room_selected(room_data)

    def action_refresh(self) -> None:
        """Refresh the room list."""
        self.fetch_rooms()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
