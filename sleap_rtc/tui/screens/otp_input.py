"""OTP input screen for TUI.

This screen prompts the user to enter a 6-digit OTP code when a worker
requires authentication.
"""

from typing import Optional, Callable

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button
from textual.binding import Binding



class OTPInputScreen(ModalScreen):
    """Modal screen for entering OTP code.

    Shown when a worker requires OTP authentication.
    """

    CSS = """
    OTPInputScreen {
        align: center middle;
    }

    #otp-box {
        width: 50;
        height: auto;
        padding: 2 4;
        border: solid $primary;
        background: $surface;
    }

    .title {
        text-style: bold;
        text-align: center;
        color: $warning;
        margin-bottom: 1;
    }

    .subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }

    #worker-info {
        text-align: center;
        margin-bottom: 1;
    }

    #otp-input {
        margin: 1 0;
        text-align: center;
    }

    #otp-input:focus {
        border: solid $primary;
    }

    #error-message {
        color: $error;
        text-align: center;
        margin-top: 1;
    }

    .hint {
        color: $text-muted;
        text-align: center;
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
        worker_name: str,
        on_otp_entered: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        name: Optional[str] = None,
    ):
        """Initialize OTP input screen.

        Args:
            worker_name: Name of the worker requiring auth.
            on_otp_entered: Callback when OTP is entered (receives 6-digit code).
            on_cancel: Callback when user cancels.
            name: Screen name.
        """
        super().__init__(name=name)
        self.worker_name = worker_name
        self.on_otp_entered = on_otp_entered
        self.on_cancel = on_cancel

    def compose(self) -> ComposeResult:
        yield Container(
            Vertical(
                Static("Authentication Required", classes="title"),
                Static(
                    "Enter the 6-digit code from your authenticator app",
                    classes="subtitle",
                ),
                Static(f"Worker: {self.worker_name}", id="worker-info"),
                Input(
                    placeholder="Enter 6-digit OTP code",
                    id="otp-input",
                    max_length=6,
                ),
                Static("", id="error-message"),
                Static(
                    "Code refreshes every 30 seconds",
                    classes="hint",
                ),
                Container(
                    Button("Authenticate", variant="primary", id="submit-btn"),
                    Button("Cancel", variant="default", id="cancel-btn"),
                    id="buttons",
                ),
                id="otp-box",
            ),
        )

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.query_one("#otp-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "submit-btn":
            self._submit_otp()
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self._submit_otp()

    def _submit_otp(self) -> None:
        """Validate and submit the OTP code."""
        otp_input = self.query_one("#otp-input", Input)
        code = otp_input.value.strip()

        error_msg = self.query_one("#error-message", Static)

        if not code:
            error_msg.update("Please enter the OTP code")
            return

        if len(code) != 6 or not code.isdigit():
            error_msg.update("OTP must be exactly 6 digits")
            return

        # Code looks valid, submit it
        if self.on_otp_entered:
            self.on_otp_entered(code)

    def show_error(self, message: str) -> None:
        """Show an error message (e.g., invalid code)."""
        error_msg = self.query_one("#error-message", Static)
        error_msg.update(message)
        # Clear the input for retry
        otp_input = self.query_one("#otp-input", Input)
        otp_input.value = ""
        otp_input.focus()

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        if self.on_cancel:
            self.on_cancel()
        self.dismiss()

    def action_submit(self) -> None:
        """Submit the OTP code."""
        self._submit_otp()
