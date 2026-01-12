"""Interactive file selector for terminal-based file selection.

This module provides an arrow-key based selection UI for choosing files
from fuzzy search results, with fallback to numbered selection for
terminals that don't support cursor movement.
"""

import os
import sys
from typing import List, Optional, Callable

# Terminal capability detection
def _is_interactive_terminal() -> bool:
    """Check if we're running in an interactive terminal with cursor support."""
    # Check if stdin/stdout are TTYs
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False

    # Check for dumb terminal
    term = os.environ.get("TERM", "")
    if term in ("dumb", ""):
        return False

    # Check for common non-interactive environments
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        return False

    return True


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


class FileCandidate:
    """Represents a file candidate from resolution results."""

    def __init__(
        self,
        path: str,
        name: str,
        size: int,
        match_type: str,
        score: float = 0.0,
        modified: float = None,
    ):
        self.path = path
        self.name = name
        self.size = size
        self.match_type = match_type
        self.score = score
        self.modified = modified

    @classmethod
    def from_dict(cls, data: dict) -> "FileCandidate":
        """Create FileCandidate from dictionary."""
        return cls(
            path=data.get("path", ""),
            name=data.get("name", ""),
            size=data.get("size", 0),
            match_type=data.get("match_type", ""),
            score=data.get("score", 0.0),
            modified=data.get("modified"),
        )

    def format_display(self, selected: bool = False, max_path_len: int = 60) -> str:
        """Format candidate for display."""
        prefix = "> " if selected else "  "
        size_str = _format_size(self.size)

        # Truncate path if too long
        display_path = self.path
        if len(display_path) > max_path_len:
            display_path = "..." + display_path[-(max_path_len - 3) :]

        return f"{prefix}{display_path}  ({size_str})"


class ArrowSelector:
    """Interactive arrow-key based file selector.

    Provides a terminal UI for selecting files using arrow keys,
    with fallback to numbered selection for unsupported terminals.

    Usage:
        selector = ArrowSelector(candidates)
        selected = selector.run()
        if selected:
            print(f"Selected: {selected.path}")
    """

    def __init__(
        self,
        candidates: List[FileCandidate],
        title: str = "Select file:",
        allow_cancel: bool = True,
    ):
        """Initialize selector.

        Args:
            candidates: List of FileCandidate objects to select from.
            title: Title to display above the selection list.
            allow_cancel: Whether to allow canceling selection with Escape.
        """
        self.candidates = candidates
        self.title = title
        self.allow_cancel = allow_cancel
        self.selected_index = 0
        self.cancelled = False

    def run(self) -> Optional[FileCandidate]:
        """Run the selector and return the selected candidate.

        Returns:
            Selected FileCandidate, or None if cancelled/no selection.
        """
        if not self.candidates:
            return None

        if _is_interactive_terminal():
            return self._run_interactive()
        else:
            return self._run_numbered()

    def _run_interactive(self) -> Optional[FileCandidate]:
        """Run interactive arrow-key selection using prompt_toolkit."""
        try:
            from prompt_toolkit import Application
            from prompt_toolkit.key_binding import KeyBindings
            from prompt_toolkit.layout import Layout
            from prompt_toolkit.layout.containers import Window
            from prompt_toolkit.layout.controls import FormattedTextControl
            from prompt_toolkit.formatted_text import FormattedText
        except ImportError:
            # Fall back to numbered if prompt_toolkit not available
            return self._run_numbered()

        kb = KeyBindings()
        result = [None]  # Use list to allow mutation in closure

        @kb.add("up")
        @kb.add("k")  # vim-style
        def move_up(event):
            self.selected_index = (self.selected_index - 1) % len(self.candidates)

        @kb.add("down")
        @kb.add("j")  # vim-style
        def move_down(event):
            self.selected_index = (self.selected_index + 1) % len(self.candidates)

        @kb.add("enter")
        def confirm(event):
            result[0] = self.candidates[self.selected_index]
            event.app.exit()

        @kb.add("escape")
        @kb.add("q")
        def cancel(event):
            if self.allow_cancel:
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
            lines.append(("bold", f"\n{self.title}\n\n"))

            # Candidates
            for i, candidate in enumerate(self.candidates):
                selected = i == self.selected_index
                line = candidate.format_display(selected=selected)

                if selected:
                    lines.append(("bold fg:cyan", line + "\n"))
                else:
                    lines.append(("", line + "\n"))

            # Help text
            lines.append(("dim", "\n[↑/↓] Navigate  [Enter] Confirm  [Esc] Cancel\n"))

            return FormattedText(lines)

        # Create application
        layout = Layout(
            Window(content=FormattedTextControl(get_formatted_text))
        )

        app = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=False,
            mouse_support=False,
        )

        try:
            app.run()
        except Exception:
            # Fall back to numbered on any error
            return self._run_numbered()

        return result[0]

    def _run_numbered(self) -> Optional[FileCandidate]:
        """Run numbered selection for dumb terminals."""
        print(f"\n{self.title}\n")

        for i, candidate in enumerate(self.candidates, 1):
            size_str = _format_size(candidate.size)
            print(f"  {i}. {candidate.path}  ({size_str})")

        print()
        if self.allow_cancel:
            print("Enter number to select, or 'c' to cancel")
        else:
            print("Enter number to select")

        while True:
            try:
                choice = input("\nSelection: ").strip().lower()

                if choice == "c" and self.allow_cancel:
                    self.cancelled = True
                    return None

                idx = int(choice) - 1
                if 0 <= idx < len(self.candidates):
                    return self.candidates[idx]
                else:
                    print(f"Please enter a number between 1 and {len(self.candidates)}")

            except ValueError:
                print("Invalid input. Please enter a number.")
            except (EOFError, KeyboardInterrupt):
                self.cancelled = True
                return None


class NoMatchMenu:
    """Menu displayed when no matches are found.

    Offers options:
    - [B] Open filesystem browser
    - [P] Enter path manually
    - [W] Try wildcard search
    - [C] Cancel
    """

    def __init__(self, filename: str):
        """Initialize menu.

        Args:
            filename: The filename that wasn't found.
        """
        self.filename = filename

    def run(self) -> str:
        """Run the menu and return the selected action.

        Returns:
            One of: "browse", "manual", "wildcard", "cancel"
        """
        print(f"\nNo matches found for: {self.filename}\n")
        print("Options:")
        print("  [B] Open filesystem browser (run sleap-rtc browse)")
        print("  [P] Enter path manually")
        print("  [W] Try wildcard search")
        print("  [C] Cancel")

        while True:
            try:
                choice = input("\nSelect option: ").strip().lower()

                if choice == "b":
                    return "browse"
                elif choice == "p":
                    return "manual"
                elif choice == "w":
                    return "wildcard"
                elif choice == "c":
                    return "cancel"
                else:
                    print("Invalid option. Please enter B, P, W, or C.")

            except (EOFError, KeyboardInterrupt):
                return "cancel"


def prompt_wildcard_pattern(filename: str) -> Optional[str]:
    """Prompt user for a wildcard pattern.

    Args:
        filename: Original filename to suggest a pattern from.

    Returns:
        Wildcard pattern string, or None if cancelled.
    """
    # Generate suggested pattern from filename
    name_parts = filename.rsplit(".", 1)
    if len(name_parts) == 2:
        suggested = f"*{name_parts[0]}*.{name_parts[1]}"
    else:
        suggested = f"*{filename}*"

    print(f"\nEnter wildcard pattern (suggested: {suggested})")
    print("Wildcards: * (any chars), ? (single char), [abc] (char set)")
    print("Must contain at least 3 non-wildcard characters")

    try:
        pattern = input("\nPattern: ").strip()
        if not pattern:
            return suggested
        return pattern
    except (EOFError, KeyboardInterrupt):
        return None


def prompt_manual_path() -> Optional[str]:
    """Prompt user for a manual path entry.

    Returns:
        Path string, or None if cancelled.
    """
    print("\nEnter the full path on the Worker's filesystem:")

    try:
        path = input("\nPath: ").strip()
        return path if path else None
    except (EOFError, KeyboardInterrupt):
        return None


def select_file_from_candidates(
    candidates: List[dict],
    title: str = "Select file:",
    non_interactive: bool = False,
) -> Optional[str]:
    """High-level function to select a file from candidate dictionaries.

    Args:
        candidates: List of candidate dicts from FS_RESOLVE_RESPONSE.
        title: Title for the selection UI.
        non_interactive: If True, auto-select the first (best) candidate.

    Returns:
        Selected file path, or None if cancelled/no selection.
    """
    if not candidates:
        return None

    # Convert to FileCandidate objects
    file_candidates = [FileCandidate.from_dict(c) for c in candidates]

    # Non-interactive mode: auto-select first (highest-ranked)
    if non_interactive:
        return file_candidates[0].path

    # Interactive selection
    selector = ArrowSelector(file_candidates, title=title)
    result = selector.run()

    if result:
        return result.path
    return None
