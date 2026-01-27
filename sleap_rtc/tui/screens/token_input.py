"""Token input screen for TUI.

This screen prompts the user to enter a room token when one is not found
in the stored credentials.
"""

from typing import Optional, Callable

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, Button
from textual.binding import Binding



class TokenInputScreen(Screen):
    """Screen for entering a room token.

    Shown when a room is selected but no token is found in credentials.
    """

    CSS = """
    TokenInputScreen {
        background: $background;
    }

    #token-container {
        align: center middle;
        height: 100%;
    }

    #token-box {
        width: 70;
        height: auto;
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
        margin-bottom: 2;
    }

    #room-info {
        text-align: center;
        margin-bottom: 1;
    }

    #token-input {
        margin: 1 0;
    }

    #token-input:focus {
        border: solid $primary;
    }

    #error-message {
        color: $error;
        text-align: center;
        margin-top: 1;
    }

    .hint {
        color: $text-muted;
        margin-top: 1;
    }

    #buttons {
        margin-top: 2;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "submit", "Submit", show=False),
    ]

    def __init__(
        self,
        room_id: str,
        room_name: Optional[str] = None,
        on_token_entered: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        name: Optional[str] = None,
    ):
        """Initialize token input screen.

        Args:
            room_id: The room ID requiring a token.
            room_name: Optional display name for the room.
            on_token_entered: Callback when token is entered (receives token string).
            on_cancel: Callback when user cancels.
            name: Screen name.
        """
        super().__init__(name=name)
        self.room_id = room_id
        self.room_name = room_name or room_id
        self.on_token_entered = on_token_entered
        self.on_cancel = on_cancel

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Vertical(
                Static("Enter Room Token", classes="title"),
                Static(
                    "A token is required to connect to workers in this room",
                    classes="subtitle",
                ),
                Static(f"Room: {self.room_name} ({self.room_id})", id="room-info"),
                Input(
                    placeholder="Paste your token (slp__...)",
                    id="token-input",
                    password=False,
                ),
                Static("", id="error-message"),
                Static(
                    "Get a token with: sleap-rtc token create --room " + self.room_id,
                    classes="hint",
                ),
                Container(
                    Button("Connect", variant="primary", id="submit-btn"),
                    Button("Cancel", variant="default", id="cancel-btn"),
                    id="buttons",
                ),
                id="token-box",
            ),
            id="token-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.query_one("#token-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "submit-btn":
            self._submit_token()
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self._submit_token()

    def _submit_token(self) -> None:
        """Validate and submit the token."""
        token_input = self.query_one("#token-input", Input)
        token = token_input.value.strip()

        error_msg = self.query_one("#error-message", Static)

        if not token:
            error_msg.update("Please enter a token")
            return

        if not token.startswith("slp_"):
            error_msg.update("Token should start with 'slp_'")
            return

        # Token looks valid, save and callback
        self._save_and_continue(token)

    def _save_and_continue(self, token: str) -> None:
        """Save the token and call the callback."""
        from sleap_rtc.auth.credentials import save_token

        # Save token to credentials
        save_token(self.room_id, token, "tui-client")

        # Call callback
        if self.on_token_entered:
            self.on_token_entered(token)

    def action_cancel(self) -> None:
        """Cancel and go back."""
        if self.on_cancel:
            self.on_cancel()
        else:
            self.app.pop_screen()

    def action_submit(self) -> None:
        """Submit the token."""
        self._submit_token()
