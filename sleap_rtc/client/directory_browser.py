"""Interactive directory browser for remote filesystem navigation.

This module provides a terminal-based directory browser for navigating
the worker filesystem and selecting files. Used for path correction
when job submission fails due to invalid paths.
"""

import asyncio
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Callable, Any

from sleap_rtc.protocol import (
    MSG_FS_LIST_DIR,
    MSG_FS_LIST_RESPONSE,
    MSG_FS_ERROR,
    MSG_SEPARATOR,
    format_message,
)


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _is_interactive_terminal() -> bool:
    """Check if we're running in an interactive terminal."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False

    term = os.environ.get("TERM", "")
    if term in ("dumb", "", "unknown"):
        return False

    # Check for CI environments
    ci_env_vars = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL"]
    for env_var in ci_env_vars:
        if os.environ.get(env_var):
            return False

    return True


class DirectoryEntry:
    """Represents a directory entry (file or folder)."""

    def __init__(self, name: str, entry_type: str, size: int, modified: float):
        self.name = name
        self.type = entry_type  # "directory" or "file"
        self.size = size
        self.modified = modified

    @property
    def is_directory(self) -> bool:
        return self.type == "directory"

    @classmethod
    def from_dict(cls, data: dict) -> "DirectoryEntry":
        return cls(
            name=data.get("name", ""),
            entry_type=data.get("type", "file"),
            size=data.get("size", 0),
            modified=data.get("modified", 0),
        )


class DirectoryBrowser:
    """Interactive directory browser for remote filesystem navigation.

    Uses prompt_toolkit for arrow-key navigation with async directory
    listing refresh from the worker.

    Usage:
        browser = DirectoryBrowser(
            send_message=channel.send,
            receive_response=response_queue.get,
            start_path="/vast/data",
            file_filter=".slp",
        )
        selected = await browser.run()
        if selected:
            print(f"Selected: {selected}")
    """

    def __init__(
        self,
        send_message: Callable[[str], None],
        receive_response: Callable[[], Any],
        start_path: str = "/",
        file_filter: Optional[str] = None,
        title: str = "Browse remote filesystem:",
    ):
        """Initialize directory browser.

        Args:
            send_message: Function to send messages to worker (data_channel.send).
            receive_response: Async function to receive FS responses.
            start_path: Starting directory path.
            file_filter: Optional file extension filter (e.g., ".slp", ".yaml").
            title: Title to display above the browser.
        """
        self.send_message = send_message
        self.receive_response = receive_response
        self.current_path = start_path
        self.file_filter = file_filter.lower() if file_filter else None
        self.title = title

        self.entries: List[DirectoryEntry] = []
        self.selected_index = 0
        self.cancelled = False
        self.selected_path: Optional[str] = None
        self.error_message: Optional[str] = None
        self.loading = False

    async def _refresh_listing(self) -> None:
        """Fetch directory listing from worker."""
        self.loading = True
        self.error_message = None

        # Send FS_LIST_DIR request
        message = format_message(MSG_FS_LIST_DIR, self.current_path, "0")
        self.send_message(message)

        # Wait for response
        try:
            response = await asyncio.wait_for(self.receive_response(), timeout=30.0)
        except asyncio.TimeoutError:
            self.error_message = "Timeout waiting for directory listing"
            self.entries = []
            self.loading = False
            return

        # Parse response
        if response.startswith(MSG_FS_ERROR):
            parts = response.split(MSG_SEPARATOR)
            self.error_message = parts[2] if len(parts) > 2 else "Unknown error"
            self.entries = []
        elif response.startswith(MSG_FS_LIST_RESPONSE):
            try:
                json_str = response.split(MSG_SEPARATOR, 1)[1]
                data = json.loads(json_str)

                if "error" in data:
                    self.error_message = data["error"]
                    self.entries = []
                else:
                    self.current_path = data.get("path", self.current_path)
                    raw_entries = data.get("entries", [])

                    # Convert to DirectoryEntry objects
                    self.entries = [DirectoryEntry.from_dict(e) for e in raw_entries]

                    # Apply file filter (keep all directories, filter files)
                    if self.file_filter:
                        self.entries = [
                            e for e in self.entries
                            if e.is_directory or e.name.lower().endswith(self.file_filter)
                        ]

                    # Reset selection if out of bounds
                    if self.selected_index >= len(self.entries):
                        self.selected_index = max(0, len(self.entries) - 1)

            except (json.JSONDecodeError, IndexError) as e:
                self.error_message = f"Failed to parse response: {e}"
                self.entries = []
        else:
            self.error_message = f"Unexpected response: {response[:50]}"
            self.entries = []

        self.loading = False

    def _navigate_up(self) -> bool:
        """Navigate to parent directory. Returns True if path changed."""
        if self.current_path in ("/", ""):
            return False

        # Get parent path
        parent = os.path.dirname(self.current_path.rstrip("/"))
        if parent == self.current_path:
            return False

        self.current_path = parent if parent else "/"
        self.selected_index = 0
        return True

    def _navigate_into(self, entry: DirectoryEntry) -> bool:
        """Navigate into a directory. Returns True if path changed."""
        if not entry.is_directory:
            return False

        new_path = os.path.join(self.current_path, entry.name)
        self.current_path = new_path
        self.selected_index = 0
        return True

    def _select_file(self, entry: DirectoryEntry) -> bool:
        """Select a file. Returns True if file was selected."""
        if entry.is_directory:
            return False

        self.selected_path = os.path.join(self.current_path, entry.name)
        return True

    async def run(self) -> Optional[str]:
        """Run the directory browser and return selected path.

        Returns:
            Selected file path, or None if cancelled.
        """
        if not _is_interactive_terminal():
            return await self._run_simple()

        try:
            return await self._run_interactive()
        except ImportError:
            return await self._run_simple()

    async def _run_interactive(self) -> Optional[str]:
        """Run interactive prompt_toolkit-based browser."""
        from prompt_toolkit import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.formatted_text import FormattedText

        # Initial directory listing
        await self._refresh_listing()

        kb = KeyBindings()
        refresh_needed = [False]
        app_ref = [None]

        @kb.add("up")
        @kb.add("k")
        def move_up(event):
            if self.entries:
                self.selected_index = (self.selected_index - 1) % len(self.entries)

        @kb.add("down")
        @kb.add("j")
        def move_down(event):
            if self.entries:
                self.selected_index = (self.selected_index + 1) % len(self.entries)

        @kb.add("enter")
        @kb.add("right")
        @kb.add("l")
        def select_entry(event):
            if not self.entries:
                return

            entry = self.entries[self.selected_index]
            if entry.is_directory:
                self._navigate_into(entry)
                refresh_needed[0] = True
                event.app.exit()
            else:
                self._select_file(entry)
                event.app.exit()

        @kb.add("backspace")
        @kb.add("left")
        @kb.add("h")
        def go_back(event):
            if self._navigate_up():
                refresh_needed[0] = True
                event.app.exit()

        @kb.add("escape")
        @kb.add("q")
        def cancel(event):
            self.cancelled = True
            event.app.exit()

        @kb.add("c-c")
        def ctrl_c(event):
            self.cancelled = True
            event.app.exit()

        def get_formatted_text():
            """Generate formatted text for display."""
            lines = []

            # Title
            lines.append(("bold", f"\n{self.title}\n"))
            lines.append(("fg:ansibrightblack", f"Path: {self.current_path}\n\n"))

            if self.loading:
                lines.append(("fg:ansiyellow", "Loading...\n"))
            elif self.error_message:
                lines.append(("fg:ansired", f"Error: {self.error_message}\n"))
            elif not self.entries:
                lines.append(("fg:ansibrightblack", "(empty directory)\n"))
            else:
                # Show entries (max 15 visible)
                visible_start = max(0, self.selected_index - 7)
                visible_end = min(len(self.entries), visible_start + 15)

                if visible_start > 0:
                    lines.append(("fg:ansibrightblack", f"  ... {visible_start} more above\n"))

                for i in range(visible_start, visible_end):
                    entry = self.entries[i]
                    selected = i == self.selected_index

                    if entry.is_directory:
                        icon = "📁 " if selected else "   "
                        if selected:
                            lines.append(("bold fg:ansicyan", f"> {icon}{entry.name}/\n"))
                        else:
                            lines.append(("fg:ansicyan", f"  {icon}{entry.name}/\n"))
                    else:
                        icon = "📄 " if selected else "   "
                        size_str = _format_size(entry.size)
                        if selected:
                            lines.append(("bold fg:ansiwhite", f"> {icon}{entry.name}"))
                            lines.append(("fg:ansibrightblack", f"  ({size_str})\n"))
                        else:
                            lines.append(("", f"  {icon}{entry.name}"))
                            lines.append(("fg:ansibrightblack", f"  ({size_str})\n"))

                remaining = len(self.entries) - visible_end
                if remaining > 0:
                    lines.append(("fg:ansibrightblack", f"  ... {remaining} more below\n"))

            # Help text
            lines.append(("", "\n"))
            lines.append(("fg:ansibrightblack", "["))
            lines.append(("bold fg:ansiyellow", "↑/↓"))
            lines.append(("fg:ansibrightblack", "] Navigate  ["))
            lines.append(("bold fg:ansigreen", "Enter"))
            lines.append(("fg:ansibrightblack", "] Select  ["))
            lines.append(("bold fg:ansiyellow", "←/Backspace"))
            lines.append(("fg:ansibrightblack", "] Back  ["))
            lines.append(("bold fg:ansiyellow", "Esc"))
            lines.append(("fg:ansibrightblack", "] Cancel\n"))

            if self.file_filter:
                lines.append(("fg:ansibrightblack", f"Filter: *{self.file_filter}\n"))

            return FormattedText(lines)

        # Run browser loop
        while not self.cancelled and not self.selected_path:
            layout = Layout(
                Window(content=FormattedTextControl(get_formatted_text))
            )

            app = Application(
                layout=layout,
                key_bindings=kb,
                full_screen=False,
                mouse_support=False,
            )
            app_ref[0] = app

            def run_app():
                app.run()

            # Run prompt_toolkit in thread to avoid event loop conflicts
            try:
                loop = asyncio.get_running_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    await loop.run_in_executor(executor, run_app)
            except RuntimeError:
                app.run()

            if refresh_needed[0]:
                refresh_needed[0] = False
                await self._refresh_listing()

        return self.selected_path

    async def _run_simple(self) -> Optional[str]:
        """Run simple numbered selection for non-interactive terminals."""
        await self._refresh_listing()

        while not self.cancelled and not self.selected_path:
            print(f"\nPath: {self.current_path}")

            if self.error_message:
                print(f"Error: {self.error_message}")
            elif not self.entries:
                print("(empty directory)")
            else:
                for i, entry in enumerate(self.entries):
                    if entry.is_directory:
                        print(f"  [{i + 1}] 📁 {entry.name}/")
                    else:
                        size_str = _format_size(entry.size)
                        print(f"  [{i + 1}] 📄 {entry.name} ({size_str})")

            print("\nEnter number to select, '..' to go up, or 'q' to cancel:")

            try:
                choice = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                self.cancelled = True
                break

            if choice.lower() == "q":
                self.cancelled = True
                break
            elif choice == "..":
                if self._navigate_up():
                    await self._refresh_listing()
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(self.entries):
                        entry = self.entries[idx]
                        if entry.is_directory:
                            self._navigate_into(entry)
                            await self._refresh_listing()
                        else:
                            self._select_file(entry)
                    else:
                        print("Invalid number")
                except ValueError:
                    print("Invalid input")

        return self.selected_path


async def browse_for_file(
    send_message: Callable[[str], None],
    receive_response: Callable[[], Any],
    start_path: str = "/",
    file_filter: Optional[str] = None,
    title: str = "Select a file:",
) -> Optional[str]:
    """Convenience function to browse and select a file.

    Args:
        send_message: Function to send messages to worker.
        receive_response: Async function to receive FS responses.
        start_path: Starting directory path.
        file_filter: Optional file extension filter.
        title: Title for the browser.

    Returns:
        Selected file path, or None if cancelled.
    """
    browser = DirectoryBrowser(
        send_message=send_message,
        receive_response=receive_response,
        start_path=start_path,
        file_filter=file_filter,
        title=title,
    )
    return await browser.run()
