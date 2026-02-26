# Design: Structured Job Specifications

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interfaces                        │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│  CLI        │  TUI        │  Python API │  SLEAP GUI       │
│  (this PR)  │  (this PR)  │  (future)   │  (future)        │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬─────────┘
       │             │             │               │
       └─────────────┴─────────────┴───────────────┘
                           │
                    ┌──────▼──────┐
                    │  JobSpec    │  ← Single source of truth
                    │  (Python)   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Validator  │  ← Security layer
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Protocol   │  ← JSON over WebRTC
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Worker     │  ← Builds & runs sleap-nn command
                    └─────────────┘
```

## Component Design

### 1. JobSpec Data Structures (`sleap_rtc/jobs/spec.py`)

```python
from dataclasses import dataclass, asdict
from typing import Optional, List
import json

@dataclass
class TrainJobSpec:
    """Specification for a training job."""
    config_path: str                      # Required: full path to config YAML
    labels_path: Optional[str] = None     # Override data_config.train_labels_path
    val_labels_path: Optional[str] = None # Override data_config.val_labels_path
    max_epochs: Optional[int] = None
    batch_size: Optional[int] = None
    learning_rate: Optional[float] = None
    run_name: Optional[str] = None
    resume_ckpt_path: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps({"type": "train", **asdict(self)})

    @classmethod
    def from_json(cls, data: str) -> "TrainJobSpec":
        parsed = json.loads(data)
        parsed.pop("type", None)
        return cls(**parsed)


@dataclass
class TrackJobSpec:
    """Specification for an inference job."""
    data_path: str                        # Required: path to .slp or video
    model_paths: List[str]                # Required: paths to model directories
    output_path: Optional[str] = None
    batch_size: Optional[int] = None
    peak_threshold: Optional[float] = None
    only_suggested_frames: bool = False
    frames: Optional[str] = None          # Frame range string e.g., "0-100,200-300"

    def to_json(self) -> str:
        return json.dumps({"type": "track", **asdict(self)})

    @classmethod
    def from_json(cls, data: str) -> "TrackJobSpec":
        parsed = json.loads(data)
        parsed.pop("type", None)
        return cls(**parsed)
```

### 2. JobValidator (`sleap_rtc/jobs/validator.py`)

```python
from pathlib import Path
from typing import Union
from dataclasses import dataclass

@dataclass
class ValidationError:
    field: str
    message: str
    path: Optional[str] = None

NUMERIC_CONSTRAINTS = {
    "max_epochs": {"min": 1, "max": 10000},
    "batch_size": {"min": 1, "max": 256},
    "learning_rate": {"min": 1e-10, "max": 1.0},
    "peak_threshold": {"min": 0.0, "max": 1.0},
}

class JobValidator:
    """Validates job specifications before execution."""

    def __init__(self, file_manager):
        self.file_manager = file_manager

    def validate_train_spec(self, spec: TrainJobSpec) -> List[ValidationError]:
        errors = []

        # Validate config path
        error = self._validate_path(spec.config_path, "config_path", must_exist=True)
        if error:
            errors.append(error)

        # Validate labels path if provided
        if spec.labels_path:
            error = self._validate_path(spec.labels_path, "labels_path", must_exist=True)
            if error:
                errors.append(error)

        # Validate val_labels path if provided
        if spec.val_labels_path:
            error = self._validate_path(spec.val_labels_path, "val_labels_path", must_exist=True)
            if error:
                errors.append(error)

        # Validate resume checkpoint if provided
        if spec.resume_ckpt_path:
            error = self._validate_path(spec.resume_ckpt_path, "resume_ckpt_path", must_exist=True)
            if error:
                errors.append(error)

        # Validate numeric fields
        if spec.max_epochs is not None:
            error = self._validate_numeric("max_epochs", spec.max_epochs)
            if error:
                errors.append(error)

        if spec.batch_size is not None:
            error = self._validate_numeric("batch_size", spec.batch_size)
            if error:
                errors.append(error)

        if spec.learning_rate is not None:
            error = self._validate_numeric("learning_rate", spec.learning_rate)
            if error:
                errors.append(error)

        return errors

    def validate_track_spec(self, spec: TrackJobSpec) -> List[ValidationError]:
        errors = []

        # Validate data path
        error = self._validate_path(spec.data_path, "data_path", must_exist=True)
        if error:
            errors.append(error)

        # Validate model paths
        for i, model_path in enumerate(spec.model_paths):
            error = self._validate_path(model_path, f"model_paths[{i}]", must_exist=True)
            if error:
                errors.append(error)

        # Validate output path directory if provided
        if spec.output_path:
            parent = str(Path(spec.output_path).parent)
            error = self._validate_path(parent, "output_path (parent)", must_exist=True)
            if error:
                errors.append(error)

        # Validate numeric fields
        if spec.batch_size is not None:
            error = self._validate_numeric("batch_size", spec.batch_size)
            if error:
                errors.append(error)

        if spec.peak_threshold is not None:
            error = self._validate_numeric("peak_threshold", spec.peak_threshold)
            if error:
                errors.append(error)

        return errors

    def _validate_path(self, path: str, field: str, must_exist: bool = True) -> Optional[ValidationError]:
        """Validate a path is within allowed mounts and optionally exists."""
        resolved = Path(path).resolve()

        if not self.file_manager._is_path_allowed(resolved):
            return ValidationError(field, "Path not within allowed mounts", str(path))

        if must_exist and not resolved.exists():
            return ValidationError(field, "Path does not exist", str(path))

        return None

    def _validate_numeric(self, field: str, value: float) -> Optional[ValidationError]:
        """Validate a numeric value is within allowed range."""
        if field not in NUMERIC_CONSTRAINTS:
            return None

        constraints = NUMERIC_CONSTRAINTS[field]
        if value < constraints["min"] or value > constraints["max"]:
            return ValidationError(
                field,
                f"Value must be between {constraints['min']} and {constraints['max']}, got {value}"
            )
        return None
```

### 3. CommandBuilder (`sleap_rtc/jobs/builder.py`)

```python
from typing import List

class CommandBuilder:
    """Builds sleap-nn commands from validated job specs."""

    def build_train_command(self, spec: TrainJobSpec, zmq_ports: dict = None) -> List[str]:
        """Build sleap-nn train command from job spec."""
        cmd = ["sleap-nn", "train"]

        # Config path - split into name and dir
        config_path = Path(spec.config_path)
        cmd.extend(["--config-name", config_path.name])
        cmd.extend(["--config-dir", str(config_path.parent)])

        # Data path overrides (Hydra syntax)
        if spec.labels_path:
            cmd.append(f"data_config.train_labels_path={spec.labels_path}")

        if spec.val_labels_path:
            cmd.append(f"data_config.val_labels_path={spec.val_labels_path}")

        # Training overrides
        if spec.max_epochs is not None:
            cmd.append(f"trainer_config.max_epochs={spec.max_epochs}")

        if spec.batch_size is not None:
            cmd.append(f"trainer_config.train_data_loader.batch_size={spec.batch_size}")
            cmd.append(f"trainer_config.val_data_loader.batch_size={spec.batch_size}")

        if spec.learning_rate is not None:
            cmd.append(f"trainer_config.optimizer.lr={spec.learning_rate}")

        if spec.run_name:
            cmd.append(f"trainer_config.run_name={spec.run_name}")

        if spec.resume_ckpt_path:
            cmd.append(f"trainer_config.resume_ckpt_path={spec.resume_ckpt_path}")

        # ZMQ ports for progress reporting
        zmq_ports = zmq_ports or {}
        cmd.append(f"trainer_config.zmq.controller_port={zmq_ports.get('controller', 9000)}")
        cmd.append(f"trainer_config.zmq.publish_port={zmq_ports.get('publish', 9001)}")

        return cmd

    def build_track_command(self, spec: TrackJobSpec) -> List[str]:
        """Build sleap-nn track command from job spec."""
        cmd = ["sleap-nn", "track"]

        # Required arguments
        cmd.extend(["--data_path", spec.data_path])

        for model_path in spec.model_paths:
            cmd.extend(["--model_paths", model_path])

        # Optional arguments
        if spec.output_path:
            cmd.extend(["-o", spec.output_path])

        if spec.batch_size is not None:
            cmd.extend(["--batch_size", str(spec.batch_size)])

        if spec.peak_threshold is not None:
            cmd.extend(["--peak_threshold", str(spec.peak_threshold)])

        if spec.only_suggested_frames:
            cmd.append("--only_suggested_frames")

        if spec.frames:
            cmd.extend(["--frames", spec.frames])

        return cmd
```

### 4. Protocol Messages

New message types for job submission:

```python
# In sleap_rtc/protocol.py

MSG_JOB_SUBMIT = "JOB_SUBMIT"           # Client → Worker: Submit job spec as JSON
MSG_JOB_ACCEPTED = "JOB_ACCEPTED"       # Worker → Client: Job validated, starting
MSG_JOB_REJECTED = "JOB_REJECTED"       # Worker → Client: Validation failed with details
MSG_JOB_PROGRESS = "JOB_PROGRESS"       # Worker → Client: Training/inference progress
MSG_JOB_COMPLETE = "JOB_COMPLETE"       # Worker → Client: Job finished successfully
MSG_JOB_FAILED = "JOB_FAILED"           # Worker → Client: Job failed with error
```

Message formats:

```
JOB_SUBMIT::{json_spec}
JOB_ACCEPTED::{job_id}
JOB_REJECTED::{json_errors}  # List of ValidationError objects
JOB_PROGRESS::{json_progress}
JOB_COMPLETE::{json_result}
JOB_FAILED::{json_error}
```

### 5. DirectoryBrowser (`sleap_rtc/client/directory_browser.py`)

```python
from typing import Callable, Awaitable, Optional, List
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText

class DirectoryBrowser:
    """Interactive directory browser for CLI using prompt_toolkit.

    Provides VSCode-style navigation:
    - Arrow keys to navigate
    - Enter to select file or enter directory
    - Backspace or select '..' to go up
    - Escape to cancel
    """

    def __init__(
        self,
        fetch_listing: Callable[[str], Awaitable[List[dict]]],
        start_path: str = "/",
        file_filter: Optional[str] = None,  # e.g., "*.slp", "*.yaml"
        title: str = "Select file:",
    ):
        self.fetch_listing = fetch_listing
        self.current_path = start_path
        self.file_filter = file_filter
        self.title = title
        self.selected_index = 0
        self.entries: List[dict] = []
        self.result: Optional[str] = None
        self.cancelled = False

    async def run(self) -> Optional[str]:
        """Run the browser and return selected path or None if cancelled."""
        # Fetch initial listing
        await self._refresh_listing()

        kb = KeyBindings()

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
        async def confirm(event):
            if not self.entries:
                return

            entry = self.entries[self.selected_index]
            if entry["type"] == "dir":
                # Navigate into directory
                if entry["name"] == "..":
                    self.current_path = str(Path(self.current_path).parent)
                else:
                    self.current_path = entry["path"]
                self.selected_index = 0
                await self._refresh_listing()
            else:
                # Select file
                self.result = entry["path"]
                event.app.exit()

        @kb.add("backspace")
        async def go_up(event):
            self.current_path = str(Path(self.current_path).parent)
            self.selected_index = 0
            await self._refresh_listing()

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
            lines = []
            lines.append(("bold", f"\n{self.title}\n"))
            lines.append(("fg:ansibrightblack", f"  Current: {self.current_path}\n\n"))

            for i, entry in enumerate(self.entries):
                selected = i == self.selected_index
                name = entry["name"]
                entry_type = entry["type"]

                if entry_type == "dir":
                    suffix = "/" if name != ".." else ""
                    type_label = "[parent]" if name == ".." else "[dir]"
                    if selected:
                        lines.append(("bold fg:ansicyan", f"> {name}{suffix}"))
                        lines.append(("fg:ansibrightblack", f"  {type_label}\n"))
                    else:
                        lines.append(("", f"  {name}{suffix}"))
                        lines.append(("fg:ansibrightblack", f"  {type_label}\n"))
                else:
                    size = self._format_size(entry.get("size", 0))
                    if selected:
                        lines.append(("bold fg:ansicyan", f"> {name}"))
                        lines.append(("fg:ansibrightblack", f"  ({size})\n"))
                    else:
                        lines.append(("", f"  {name}"))
                        lines.append(("fg:ansibrightblack", f"  ({size})\n"))

            lines.append(("", "\n"))
            lines.append(("fg:ansibrightblack", "["))
            lines.append(("bold fg:ansiyellow", "↑/↓"))
            lines.append(("fg:ansibrightblack", "] Navigate  ["))
            lines.append(("bold fg:ansigreen", "Enter"))
            lines.append(("fg:ansibrightblack", "] Select/Open  ["))
            lines.append(("bold fg:ansiyellow", "Backspace"))
            lines.append(("fg:ansibrightblack", "] Back  ["))
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

        await app.run_async()
        return self.result

    async def _refresh_listing(self):
        """Fetch and update directory listing."""
        raw_entries = await self.fetch_listing(self.current_path)

        # Add parent directory entry
        self.entries = [{"name": "..", "type": "dir", "path": str(Path(self.current_path).parent)}]

        # Sort: directories first, then files
        dirs = [e for e in raw_entries if e.get("type") == "dir"]
        files = [e for e in raw_entries if e.get("type") == "file"]

        # Apply file filter if specified
        if self.file_filter:
            import fnmatch
            files = [f for f in files if fnmatch.fnmatch(f["name"], self.file_filter)]

        dirs.sort(key=lambda e: e["name"].lower())
        files.sort(key=lambda e: e["name"].lower())

        self.entries.extend(dirs)
        self.entries.extend(files)

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
```

## Message Flow

### Happy Path: Training Job

```
Client                              Worker
   |                                   |
   |-- JOB_SUBMIT::{train_spec} ------>|
   |                                   | (validate paths, numerics)
   |<-- JOB_ACCEPTED::{job_id} --------|
   |                                   | (build sleap-nn train command)
   |                                   | (execute subprocess)
   |<-- JOB_PROGRESS::{epoch, loss} ---|
   |<-- JOB_PROGRESS::{epoch, loss} ---|
   |         ...                       |
   |<-- JOB_COMPLETE::{model_path} ----|
```

### Path Correction Flow

```
Client                              Worker
   |                                   |
   |-- JOB_SUBMIT::{train_spec} ------>|
   |                                   | (validate paths)
   |<-- JOB_REJECTED::{errors} --------|  # labels_path not found
   |                                   |
   | [DirectoryBrowser opens]          |
   | [User navigates and selects]      |
   |                                   |
   |-- JOB_SUBMIT::{corrected_spec} -->|
   |<-- JOB_ACCEPTED::{job_id} --------|
   |         ...                       |
```

## Backward Compatibility

The existing `--pkg-path` workflow continues to work:

1. If user provides `--pkg-path`, use existing shell script parsing
2. If user provides `--config`, use new structured job spec
3. Deprecation warning when using `--pkg-path`

```python
# In cli.py train command
if pkg_path:
    logging.warning(
        "The --pkg-path option is deprecated. "
        "Use --config with --labels for the new workflow."
    )
    # Use existing RTCClient.run_client() flow
else:
    # Use new structured job submission
```
