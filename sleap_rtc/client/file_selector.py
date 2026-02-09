"""Interactive file selector for terminal-based file selection.

This module provides an arrow-key based selection UI for choosing files
from fuzzy search results, with fallback to numbered selection for
terminals that don't support cursor movement.
"""

import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Callable

# Rich console for styled fallback output (lazy loaded)
_console = None


def _get_console():
    """Get or create Rich console for styled output."""
    global _console
    if _console is None:
        try:
            from rich.console import Console
            _console = Console()
        except ImportError:
            _console = False  # Mark as unavailable
    return _console if _console else None


# Terminal capability detection
def _is_interactive_terminal() -> bool:
    """Check if we're running in an interactive terminal with cursor support.

    Returns:
        True if terminal supports interactive cursor-based selection,
        False if we should fall back to numbered selection.
    """
    # Check if stdin/stdout are TTYs
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False

    # Check for dumb terminal
    term = os.environ.get("TERM", "")
    if term in ("dumb", "", "unknown"):
        return False

    # Check for common CI/CD environments
    ci_env_vars = [
        "CI",                    # Generic CI flag
        "GITHUB_ACTIONS",        # GitHub Actions
        "GITLAB_CI",             # GitLab CI
        "JENKINS_URL",           # Jenkins
        "TRAVIS",                # Travis CI
        "CIRCLECI",              # CircleCI
        "BUILDKITE",             # Buildkite
        "TEAMCITY_VERSION",      # TeamCity
        "TF_BUILD",              # Azure DevOps
        "CODEBUILD_BUILD_ID",    # AWS CodeBuild
    ]
    for env_var in ci_env_vars:
        if os.environ.get(env_var):
            return False

    # Check for non-interactive shells
    if os.environ.get("NONINTERACTIVE") or os.environ.get("DEBIAN_FRONTEND") == "noninteractive":
        return False

    # Check for Emacs shell mode
    if os.environ.get("INSIDE_EMACS"):
        return False

    # Check for piped input (common in scripts)
    try:
        if hasattr(sys.stdin, 'fileno'):
            import select
            # If stdin has data waiting, we're likely being piped to
            if select.select([sys.stdin], [], [], 0)[0]:
                return False
    except (ImportError, OSError, ValueError):
        pass  # select not available or stdin not selectable

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


async def confirm_prompt(message: str, details: str = None) -> bool:
    """Display a confirmation prompt with Y/N options.

    Uses prompt_toolkit for interactive terminals, falls back to input() otherwise.

    Args:
        message: The question to ask (e.g., "Browse filesystem?")
        details: Optional details to show above the question

    Returns:
        True if user confirms, False otherwise
    """
    if _is_interactive_terminal():
        try:
            from prompt_toolkit import Application
            from prompt_toolkit.key_binding import KeyBindings
            from prompt_toolkit.layout import Layout
            from prompt_toolkit.layout.containers import Window
            from prompt_toolkit.layout.controls import FormattedTextControl
            from prompt_toolkit.formatted_text import FormattedText

            result = [None]
            selected_yes = [True]  # Default to Yes

            kb = KeyBindings()

            @kb.add("left")
            @kb.add("h")
            def move_left(event):
                selected_yes[0] = True

            @kb.add("right")
            @kb.add("l")
            def move_right(event):
                selected_yes[0] = False

            @kb.add("y")
            def select_yes(event):
                result[0] = True
                event.app.exit()

            @kb.add("n")
            def select_no(event):
                result[0] = False
                event.app.exit()

            @kb.add("enter")
            def confirm(event):
                result[0] = selected_yes[0]
                event.app.exit()

            @kb.add("escape")
            @kb.add("q")
            @kb.add("c-c")
            def cancel(event):
                result[0] = False
                event.app.exit()

            def get_formatted_text():
                lines = []
                if details:
                    lines.append(("fg:ansiyellow", f"\n{details}\n"))
                lines.append(("", f"\n{message}\n\n"))

                # Yes/No buttons
                if selected_yes[0]:
                    lines.append(("bold fg:ansigreen bg:ansibrightblack", " Yes "))
                    lines.append(("", "  "))
                    lines.append(("fg:ansibrightblack", " No "))
                else:
                    lines.append(("fg:ansibrightblack", " Yes "))
                    lines.append(("", "  "))
                    lines.append(("bold fg:ansired bg:ansibrightblack", " No "))

                lines.append(("", "\n\n"))
                lines.append(("fg:ansibrightblack", "["))
                lines.append(("bold fg:ansiyellow", "←/→"))
                lines.append(("fg:ansibrightblack", "] Select  ["))
                lines.append(("bold fg:ansigreen", "Enter"))
                lines.append(("fg:ansibrightblack", "] Confirm  ["))
                lines.append(("bold fg:ansiyellow", "y/n"))
                lines.append(("fg:ansibrightblack", "] Quick select\n"))
                return FormattedText(lines)

            layout = Layout(Window(content=FormattedTextControl(get_formatted_text)))
            app = Application(
                layout=layout,
                key_bindings=kb,
                full_screen=False,
                mouse_support=False,
            )

            await app.run_async()
            return result[0] if result[0] is not None else False

        except ImportError:
            pass  # Fall through to simple input
        except Exception:
            pass  # Fall through to simple input

    # Fallback to simple input
    console = _get_console()
    if console:
        if details:
            console.print(f"\n[yellow]{details}[/yellow]")
        console.print(f"\n{message}")
        console.print("[dim]Enter 'y' for Yes, 'n' for No[/dim]")
    else:
        if details:
            print(f"\n{details}")
        print(f"\n{message}")

    try:
        choice = input("[y/N]: ").strip().lower()
        return choice == "y"
    except (EOFError, KeyboardInterrupt):
        return False


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

            # Title (matching rich-click bold style)
            lines.append(("bold", f"\n{self.title}\n\n"))

            # Candidates
            for i, candidate in enumerate(self.candidates):
                selected = i == self.selected_index
                size_str = _format_size(candidate.size)

                if selected:
                    # Selected: bold cyan (matching rich-click STYLE_OPTION)
                    lines.append(("bold fg:ansicyan", f"> {candidate.path}"))
                    lines.append(("fg:ansicyan", f"  ({size_str})\n"))
                else:
                    lines.append(("", f"  {candidate.path}"))
                    lines.append(("fg:ansibrightblack", f"  ({size_str})\n"))

            # Help text with highlighted keys (matching rich-click style)
            lines.append(("", "\n"))
            lines.append(("fg:ansibrightblack", "["))
            lines.append(("bold fg:ansiyellow", "↑/↓"))
            lines.append(("fg:ansibrightblack", "] Navigate  ["))
            lines.append(("bold fg:ansigreen", "Enter"))
            lines.append(("fg:ansibrightblack", "] Confirm  ["))
            lines.append(("bold fg:ansiyellow", "Esc"))
            lines.append(("fg:ansibrightblack", "] Cancel\n"))

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

        def run_app():
            """Run the prompt_toolkit app (for use in thread)."""
            app.run()

        try:
            # Check if we're inside an existing event loop
            try:
                asyncio.get_running_loop()
                # We're in an async context - run prompt_toolkit in a separate thread
                # to avoid event loop conflicts
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_app)
                    future.result()  # Wait for completion
            except RuntimeError:
                # No running loop - can run directly
                app.run()
        except Exception as e:
            # Fall back to numbered on any error
            import logging
            logging.debug(f"Interactive selection failed, falling back to numbered: {e}")
            return self._run_numbered()

        return result[0]

    def _run_numbered(self) -> Optional[FileCandidate]:
        """Run numbered selection for dumb terminals with Rich styling."""
        console = _get_console()

        if console:
            # Rich-styled output matching rich-click theme
            console.print()
            console.print(f"[bold]{self.title}[/bold]")
            console.print()

            for i, candidate in enumerate(self.candidates, 1):
                size_str = _format_size(candidate.size)
                console.print(f"  [bold cyan]{i}.[/bold cyan] {candidate.path}  [dim]({size_str})[/dim]")

            console.print()
            if self.allow_cancel:
                console.print("[dim]Enter number to select, or 'c' to cancel[/dim]")
            else:
                console.print("[dim]Enter number to select[/dim]")
        else:
            # Plain fallback
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
                    console = _get_console()
                    if console:
                        console.print(f"[yellow]Please enter a number between 1 and {len(self.candidates)}[/yellow]")
                    else:
                        print(f"Please enter a number between 1 and {len(self.candidates)}")

            except ValueError:
                console = _get_console()
                if console:
                    console.print("[yellow]Invalid input. Please enter a number.[/yellow]")
                else:
                    print("Invalid input. Please enter a number.")
            except (EOFError, KeyboardInterrupt):
                self.cancelled = True
                return None


class MountSelector:
    """Interactive mount selection using arrow keys.

    Allows users to select which filesystem mount to search when
    multiple mounts are configured on the worker.

    Usage:
        selector = MountSelector(mounts)
        selected = selector.run()
        if selected:
            print(f"Selected: {selected}")  # mount label or "all"
    """

    def __init__(
        self,
        mounts: List[dict],
        title: str = "Select filesystem to search:",
        allow_all: bool = True,
        allow_cancel: bool = True,
    ):
        """Initialize selector.

        Args:
            mounts: List of mount dicts with 'label' and 'path' keys.
            title: Title to display above the selection list.
            allow_all: Whether to include "All filesystems" option.
            allow_cancel: Whether to allow canceling selection with Escape.
        """
        self.mounts = mounts
        self.title = title
        self.allow_all = allow_all
        self.allow_cancel = allow_cancel
        self.selected_index = 0
        self.cancelled = False

    def _get_options(self) -> List[tuple]:
        """Get list of (label, display_text) options."""
        options = []
        for mount in self.mounts:
            label = mount.get("label", "Unknown")
            path = mount.get("path", "")
            options.append((label, f"{label} ({path})"))
        if self.allow_all:
            options.append(("all", "All filesystems"))
        return options

    def run(self) -> Optional[str]:
        """Run the selector and return the selected mount label.

        Returns:
            Mount label string, "all", or None if cancelled.
        """
        options = self._get_options()
        if not options:
            return None

        if _is_interactive_terminal():
            return self._run_interactive(options)
        else:
            return self._run_numbered(options)

    def _run_interactive(self, options: List[tuple]) -> Optional[str]:
        """Run interactive arrow-key selection using prompt_toolkit."""
        try:
            from prompt_toolkit import Application
            from prompt_toolkit.key_binding import KeyBindings
            from prompt_toolkit.layout import Layout
            from prompt_toolkit.layout.containers import Window
            from prompt_toolkit.layout.controls import FormattedTextControl
            from prompt_toolkit.formatted_text import FormattedText
        except ImportError:
            return self._run_numbered(options)

        kb = KeyBindings()
        result = [None]

        @kb.add("up")
        @kb.add("k")
        def move_up(event):
            self.selected_index = (self.selected_index - 1) % len(options)

        @kb.add("down")
        @kb.add("j")
        def move_down(event):
            self.selected_index = (self.selected_index + 1) % len(options)

        @kb.add("enter")
        def confirm(event):
            result[0] = options[self.selected_index][0]
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
            lines = []
            lines.append(("bold", f"\n{self.title}\n\n"))

            for i, (label, display) in enumerate(options):
                selected = i == self.selected_index

                if selected:
                    # Selected: bold cyan (matching rich-click STYLE_OPTION)
                    lines.append(("bold fg:ansicyan", f"> {display}\n"))
                else:
                    lines.append(("", f"  {display}\n"))

            # Help text with highlighted keys (matching rich-click style)
            lines.append(("", "\n"))
            lines.append(("fg:ansibrightblack", "["))
            lines.append(("bold fg:ansiyellow", "↑/↓"))
            lines.append(("fg:ansibrightblack", "] Navigate  ["))
            lines.append(("bold fg:ansigreen", "Enter"))
            lines.append(("fg:ansibrightblack", "] Confirm  ["))
            lines.append(("bold fg:ansiyellow", "Esc"))
            lines.append(("fg:ansibrightblack", "] Cancel\n"))
            return FormattedText(lines)

        layout = Layout(Window(content=FormattedTextControl(get_formatted_text)))
        app = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=False,
            mouse_support=False,
        )

        def run_app():
            app.run()

        try:
            try:
                asyncio.get_running_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_app)
                    future.result()
            except RuntimeError:
                app.run()
        except Exception as e:
            import logging
            logging.debug(f"Interactive mount selection failed, falling back to numbered: {e}")
            return self._run_numbered(options)

        return result[0]

    def _run_numbered(self, options: List[tuple]) -> Optional[str]:
        """Run numbered selection for dumb terminals with Rich styling."""
        console = _get_console()

        if console:
            # Rich-styled output matching rich-click theme
            console.print()
            console.print(f"[bold]{self.title}[/bold]")
            console.print()

            for i, (label, display) in enumerate(options, 1):
                console.print(f"  [bold cyan]{i}.[/bold cyan] {display}")

            console.print()
            if self.allow_cancel:
                console.print("[dim]Enter number to select, or 'c' to cancel[/dim]")
            else:
                console.print("[dim]Enter number to select[/dim]")
        else:
            # Plain fallback
            print(f"\n{self.title}\n")

            for i, (label, display) in enumerate(options, 1):
                print(f"  {i}. {display}")

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
                if 0 <= idx < len(options):
                    return options[idx][0]
                else:
                    console = _get_console()
                    if console:
                        console.print(f"[yellow]Please enter a number between 1 and {len(options)}[/yellow]")
                    else:
                        print(f"Please enter a number between 1 and {len(options)}")

            except ValueError:
                console = _get_console()
                if console:
                    console.print("[yellow]Invalid input. Please enter a number.[/yellow]")
                else:
                    print("Invalid input. Please enter a number.")
            except (EOFError, KeyboardInterrupt):
                self.cancelled = True
                return None


class WorkerSelector:
    """Interactive worker selection using arrow keys (async-native).

    Uses prompt_toolkit's run_async() for native async support, avoiding
    the thread workaround needed for sync contexts.

    Usage:
        selector = WorkerSelector(workers)
        selected = await selector.run()
        if selected:
            print(f"Selected: {selected['peer_id']}")
    """

    def __init__(
        self,
        workers: List[dict],
        title: str = "Select worker to connect:",
        allow_cancel: bool = True,
    ):
        """Initialize selector.

        Args:
            workers: List of worker dicts with 'peer_id' and 'properties' keys.
            title: Title to display above the selection list.
            allow_cancel: Whether to allow canceling selection with Escape.
        """
        self.workers = workers
        self.title = title
        self.allow_cancel = allow_cancel
        self.selected_index = 0
        self.cancelled = False

    def _format_worker(self, worker: dict, selected: bool = False) -> str:
        """Format worker for display."""
        prefix = "> " if selected else "  "
        peer_id = worker.get("peer_id", "unknown")
        props = worker.get("properties", {})
        platform = props.get("platform", "unknown")
        status = props.get("status", "available")
        return f"{prefix}{peer_id}  ({platform}, {status})"

    async def run(self) -> Optional[dict]:
        """Run the selector and return the selected worker.

        Returns:
            Selected worker dict, or None if cancelled/no selection.
        """
        if not self.workers:
            return None

        if _is_interactive_terminal():
            return await self._run_interactive()
        else:
            return self._run_numbered()

    async def _run_interactive(self) -> Optional[dict]:
        """Run interactive arrow-key selection using prompt_toolkit async API."""
        try:
            from prompt_toolkit import Application
            from prompt_toolkit.key_binding import KeyBindings
            from prompt_toolkit.layout import Layout
            from prompt_toolkit.layout.containers import Window
            from prompt_toolkit.layout.controls import FormattedTextControl
            from prompt_toolkit.formatted_text import FormattedText
        except ImportError:
            return self._run_numbered()

        kb = KeyBindings()
        result = [None]

        @kb.add("up")
        @kb.add("k")
        def move_up(event):
            self.selected_index = (self.selected_index - 1) % len(self.workers)

        @kb.add("down")
        @kb.add("j")
        def move_down(event):
            self.selected_index = (self.selected_index + 1) % len(self.workers)

        @kb.add("enter")
        def confirm(event):
            result[0] = self.workers[self.selected_index]
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
            lines = []
            lines.append(("bold", f"\n{self.title}\n\n"))

            for i, worker in enumerate(self.workers):
                selected = i == self.selected_index
                peer_id = worker.get("peer_id", "unknown")
                # Support both direct properties and metadata.properties structure
                props = worker.get("properties", {})
                if not props and "metadata" in worker:
                    props = worker.get("metadata", {}).get("properties", {})

                name = props.get("name", "")
                gpu_model = props.get("gpu_model", "Unknown GPU")
                gpu_memory_mb = props.get("gpu_memory_mb", 0)
                gpu_memory_gb = gpu_memory_mb / 1024 if gpu_memory_mb else 0

                # Show name if available, otherwise truncated peer_id
                display_name = name if name else peer_id[:20]

                if selected:
                    # Selected: bold cyan with GPU info
                    lines.append(("bold fg:ansicyan", f"> {display_name}\n"))
                    lines.append(("fg:ansibrightblack", f"    "))
                    lines.append(("fg:ansiwhite", f"{gpu_model}"))
                    lines.append(("fg:ansibrightblack", f"  •  "))
                    lines.append(("fg:ansigreen", f"{gpu_memory_gb:.1f} GB\n"))
                else:
                    lines.append(("", f"  {display_name}\n"))
                    lines.append(("fg:ansibrightblack", f"    {gpu_model}  •  {gpu_memory_gb:.1f} GB\n"))

            # Help text with highlighted keys (matching rich-click style)
            lines.append(("", "\n"))
            lines.append(("fg:ansibrightblack", "["))
            lines.append(("bold fg:ansiyellow", "↑/↓"))
            lines.append(("fg:ansibrightblack", "] Navigate  ["))
            lines.append(("bold fg:ansigreen", "Enter"))
            lines.append(("fg:ansibrightblack", "] Confirm  ["))
            lines.append(("bold fg:ansiyellow", "Esc"))
            lines.append(("fg:ansibrightblack", "] Cancel\n"))
            return FormattedText(lines)

        layout = Layout(Window(content=FormattedTextControl(get_formatted_text)))
        app = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=False,
            mouse_support=False,
        )

        try:
            # Use native async API - no thread workaround needed
            await app.run_async()
        except Exception as e:
            import logging
            logging.debug(f"Interactive worker selection failed: {e}")
            return self._run_numbered()

        return result[0]

    def _run_numbered(self) -> Optional[dict]:
        """Run numbered selection for dumb terminals with Rich styling."""
        console = _get_console()

        if console:
            # Rich-styled output matching rich-click theme
            console.print()
            console.print(f"[bold]{self.title}[/bold]")
            console.print()

            for i, worker in enumerate(self.workers, 1):
                peer_id = worker.get("peer_id", "unknown")
                # Support both direct properties and metadata.properties structure
                props = worker.get("properties", {})
                if not props and "metadata" in worker:
                    props = worker.get("metadata", {}).get("properties", {})

                name = props.get("name", "")
                gpu_model = props.get("gpu_model", "Unknown GPU")
                gpu_memory_mb = props.get("gpu_memory_mb", 0)
                gpu_memory_gb = gpu_memory_mb / 1024 if gpu_memory_mb else 0

                # Show name if available, otherwise peer_id
                display_name = name if name else peer_id[:20]
                console.print(
                    f"  [bold cyan]{i}.[/bold cyan] {display_name}"
                )
                console.print(
                    f"      [dim]{gpu_model}[/dim]  •  [green]{gpu_memory_gb:.1f} GB[/green]"
                )

            console.print()
            if self.allow_cancel:
                console.print("[dim]Enter number to select, or 'c' to cancel[/dim]")
            else:
                console.print("[dim]Enter number to select[/dim]")
        else:
            # Plain fallback
            print(f"\n{self.title}\n")

            for i, worker in enumerate(self.workers, 1):
                peer_id = worker.get("peer_id", "unknown")
                # Support both direct properties and metadata.properties structure
                props = worker.get("properties", {})
                if not props and "metadata" in worker:
                    props = worker.get("metadata", {}).get("properties", {})

                name = props.get("name", "")
                gpu_model = props.get("gpu_model", "Unknown GPU")
                gpu_memory_mb = props.get("gpu_memory_mb", 0)
                gpu_memory_gb = gpu_memory_mb / 1024 if gpu_memory_mb else 0

                display_name = name if name else peer_id[:20]
                print(f"  {i}. {display_name}")
                print(f"      {gpu_model}  •  {gpu_memory_gb:.1f} GB")

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
                if 0 <= idx < len(self.workers):
                    return self.workers[idx]
                else:
                    console = _get_console()
                    if console:
                        console.print(f"[yellow]Please enter a number between 1 and {len(self.workers)}[/yellow]")
                    else:
                        print(f"Please enter a number between 1 and {len(self.workers)}")

            except ValueError:
                console = _get_console()
                if console:
                    console.print("[yellow]Invalid input. Please enter a number.[/yellow]")
                else:
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
        console = _get_console()

        if console:
            console.print()
            console.print(f"[yellow]No matches found for:[/yellow] {self.filename}")
            console.print()
            console.print("[bold]Options:[/bold]")
            console.print("  [bold cyan]B[/bold cyan] - Open filesystem browser [dim](run sleap-rtc browse)[/dim]")
            console.print("  [bold cyan]P[/bold cyan] - Enter path manually")
            console.print("  [bold cyan]W[/bold cyan] - Try wildcard search")
            console.print("  [bold cyan]C[/bold cyan] - Cancel")
        else:
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
                    console = _get_console()
                    if console:
                        console.print("[yellow]Invalid option. Please enter B, P, W, or C.[/yellow]")
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
