## Context

This change integrates sleap-rtc into the SLEAP GUI, enabling remote training/inference directly from the Training Configuration dialog. The integration spans two codebases (sleap-rtc and SLEAP) and introduces a new dependency relationship.

**Stakeholders:**
- SLEAP GUI users who want remote training without CLI
- sleap-rtc maintainers
- SLEAP maintainers

**Constraints:**
- sleap-rtc cannot be a hard dependency of SLEAP (optional integration)
- Must reuse existing SLEAP UI patterns (LossViewer, preferences system)
- Must not break existing local training workflow
- Feature should be opt-in via experimental features flag
- Single remote job at a time (no parallel job tracking for now)

## Goals / Non-Goals

**Goals:**
- Provide seamless remote training from SLEAP GUI
- Reuse existing LossViewer for progress visualization
- Make sleap-rtc installation optional (graceful degradation)
- Minimize changes to SLEAP codebase
- Guide new users through worker setup
- Validate paths and configs before submission with clear dialogs

**Non-Goals:**
- Full parity with CLI features (e.g., advanced streaming options)
- Automatic sleap-rtc installation from SLEAP
- Real-time inference preview in GUI (future work)
- Multiple simultaneous remote jobs (future work)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SLEAP GUI                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ Training Configuration Dialog (LearningDialog)                       ││
│  │  ┌─────────────────────────────────────────────────────────────────┐││
│  │  │ MainTabWidget                                                    │││
│  │  │  ├── Pipeline type, Input data, Performance, WandB, Output      │││
│  │  │  └── [NEW] RemoteTrainingWidget (conditional)                   │││
│  │  └─────────────────────────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ Pre-submission Dialogs (NEW)                                         ││
│  │  - PathResolutionDialog (fix missing video paths)                   ││
│  │  - ConfigValidationDialog (show config errors)                      ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ runners.py                                                           ││
│  │  run_learning_pipeline() ──► if remote_enabled:                     ││
│  │                                  run_remote_training()              ││
│  │                              else:                                   ││
│  │                                  run_gui_training()                 ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         sleap-rtc Package                                │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ sleap_rtc.api (NEW)                                                  ││
│  │  - is_available() → bool                                            ││
│  │  - is_logged_in() → bool                                            ││
│  │  - login() → opens browser                                          ││
│  │  - logout()                                                          ││
│  │  - list_rooms() → List[Room]                                        ││
│  │  - list_workers(room_id) → List[Worker]                             ││
│  │  - check_video_paths(slp_path, room_id) → PathCheckResult           ││
│  │  - validate_config(config_path) → ValidationResult                  ││
│  │  - run_training(config, room_id, worker_id, progress_callback)      ││
│  │  - run_inference(...)                                                ││
│  └─────────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ sleap_rtc.gui.widgets (NEW)                                          ││
│  │  - RemoteTrainingWidget(QGroupBox)                                  ││
│  │  - RoomBrowserDialog(QDialog)                                       ││
│  │  - WorkerSetupDialog(QDialog) - onboarding for new users            ││
│  │  - PathResolutionDialog(QDialog) - fix video paths                  ││
│  │  - ConfigValidationDialog(QDialog) - show validation errors         ││
│  └─────────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ sleap_rtc.gui.runners (NEW)                                          ││
│  │  - run_remote_training()                                            ││
│  │  - RemoteProgressBridge (WebRTC → ZMQ for LossViewer)               ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼ WebRTC
┌─────────────────────────────────────────────────────────────────────────┐
│                         Remote Worker                                    │
│  sleap-nn training → ProgressReporterZMQ → WebRTC → Client             │
└─────────────────────────────────────────────────────────────────────────┘
```

## Decisions

### Decision 1: Feature Gate via SLEAP Preferences

**What:** Add `enable_experimental_features: False` to SLEAP's `prefs.py` defaults.

**Why:**
- SLEAP already has a mature preferences system (`sleap/prefs.py`)
- Preferences persist across sessions (YAML file in `~/.sleap/`)
- Allows runtime toggle via menu without restart

**Alternatives considered:**
- Environment variable (`SLEAP_EXPERIMENTAL=1`) - Less discoverable, harder for non-technical users
- Compile-time flag - Too rigid, requires reinstall

### Decision 2: Optional Import Pattern

**What:** Use try/except import pattern in SLEAP to handle missing sleap-rtc.

```python
# In sleap/gui/learning/main_tab.py
try:
    from sleap_rtc.gui.widgets import RemoteTrainingWidget
    SLEAP_RTC_AVAILABLE = True
except ImportError:
    SLEAP_RTC_AVAILABLE = False
```

**Why:**
- sleap-rtc should not be a hard dependency of SLEAP
- Allows users without GPU workers to use SLEAP normally
- Clean separation of concerns

### Decision 3: ZMQ Progress Forwarding

**What:** sleap-rtc client receives progress from worker via WebRTC and re-emits via local ZMQ for LossViewer compatibility.

**Why:**
- SLEAP's `LossViewer` already listens on ZMQ for progress updates
- sleap-nn's `ProgressReporterZMQ` callback uses standard message format
- Zero changes needed to LossViewer

**Message flow:**
```
Worker (sleap-nn) → ZMQ → WebRTC DataChannel → Client → ZMQ → LossViewer
```

**Message format (already defined by sleap-nn):**
- `train_begin` - Training started, optional wandb_url
- `epoch_end` - Epoch complete, includes metrics dict
- `train_end` - Training finished

### Decision 4: Widgets Live in sleap-rtc Package

**What:** Qt widgets (`RemoteTrainingWidget`, etc.) are defined in `sleap_rtc.gui.widgets`, not in SLEAP.

**Why:**
- Keeps SLEAP changes minimal (just conditional import/display)
- sleap-rtc controls its own UI without SLEAP releases
- Easier to iterate on UI without SLEAP PRs

### Decision 5: High-Level Python API

**What:** Create `sleap_rtc.api` module with simple functions wrapping CLI/client functionality.

**Why:**
- Clean interface for GUI integration
- Hides WebRTC/signaling complexity from SLEAP
- Can be used for scripting/notebooks too
- Testable without GUI

### Decision 6: Worker Setup Onboarding

**What:** Provide a "Setup Worker" helper dialog for users who don't have a worker running.

When a user selects a room with 0 workers, show a dialog with:
```
┌─ No Workers Available ───────────────────────────────────────────────┐
│                                                                      │
│  This room has no workers connected. You need a worker running on    │
│  a GPU machine to train remotely.                                    │
│                                                                      │
│  Quick Setup:                                                        │
│                                                                      │
│  1. On your GPU machine, install sleap-rtc:                          │
│     pip install sleap-rtc                                            │
│                                                                      │
│  2. Generate an API key from the dashboard:                          │
│     [ Open Dashboard ]  →  sleap-rtc-signaling.duckdns.org           │
│                                                                      │
│  3. Start the worker:                                                │
│     sleap-rtc worker --api-key YOUR_KEY --name "My GPU Server"       │
│                                                                      │
│  [ Copy Commands ]  [ Open Documentation ]  [ Close ]                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Why:**
- First-time users won't know how to set up a worker
- Dashboard already handles API key generation
- Reduces friction for adoption

### Decision 7: Worker Refresh Button

**What:** Add a refresh button (🔄) next to the worker dropdown to manually refresh the worker list.

```
Worker Selection:                                   [🔄 Refresh]
  ○ Auto-select best available
  ● Choose worker: [ gpu-server-01 (RTX 4090, 24GB)     ▼]
```

**Why:**
- Workers may come online after dialog opens
- Users expect manual refresh capability
- Avoids polling overhead

### Decision 8: Path Resolution Dialog

**What:** Before submitting a job, check if video paths in the SLP are accessible on the worker. If not, show a `PathResolutionDialog` similar to the `resolve-paths` CLI command.

```
┌─ Video Path Resolution Required ─────────────────────────────────────┐
│                                                                      │
│  Some video files cannot be found on the worker. Please provide      │
│  the correct paths.                                                  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Video                          │ Status    │ Worker Path       │  │
│  ├────────────────────────────────┼───────────┼───────────────────│  │
│  │ experiment_01.mp4              │ ✓ Found   │ /mnt/data/exp01.. │  │
│  │ experiment_02.mp4              │ ✗ Missing │ [ Browse... ]     │  │
│  │ experiment_03.mp4              │ ✗ Missing │ [ Browse... ]     │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  [ Auto-detect in folder... ]                                        │
│                                                                      │
│                              [ Cancel ]  [ Continue with Resolved ]  │
└──────────────────────────────────────────────────────────────────────┘
```

**Why:**
- Client and worker often have different filesystem layouts
- Same pattern as `sleap-rtc test resolve-paths` CLI command
- Prevents cryptic errors during training

### Decision 9: Config Validation Dialog

**What:** Validate the training config before submission and show any errors in a dialog.

```
┌─ Configuration Validation Failed ────────────────────────────────────┐
│                                                                      │
│  The training configuration has errors that must be fixed:           │
│                                                                      │
│  ✗ model_config.backbone.max_stride: Must be power of 2, got 30     │
│  ✗ trainer_config.max_epochs: Must be positive, got -1              │
│  ⚠ trainer_config.save_ckpt: Disabled - no checkpoints will save   │
│                                                                      │
│  Tip: Review the config in the Model Configuration tabs.             │
│                                                                      │
│                                          [ OK ]                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Why:**
- Catch errors before file transfer and job submission
- Faster feedback than waiting for remote failure
- Similar pattern to sleap-nn's config validation

### Decision 10: Progress Display Formatting

**What:** Match the CLI formatting from the `cleanup-cli-ux` PR for consistency.

LossViewer title bar:
```
Training Monitor - Remote (gpu-server-01)
```

Progress section header (in LossViewer or console):
```
────────────────────────────────────────────────────────────────
Running Training Remotely on gpu-server-01...
────────────────────────────────────────────────────────────────
```

Completion message:
```
────────────────────────────────────────────────────────────────
Remote Training Completed Successfully
────────────────────────────────────────────────────────────────
```

**Why:**
- Visual consistency with CLI experience
- Users familiar with CLI will recognize the format

### Decision 11: Partial Progress on Failure

**What:** If training fails partway through, preserve any saved checkpoints and notify user.

**How SLEAP/sleap-nn handles this:**
- sleap-nn uses PyTorch Lightning's `ModelCheckpoint` callback
- Checkpoints saved every N epochs to `{run_dir}/checkpoints/`
- On failure, SLEAP GUI shows error dialog but checkpoints remain on disk
- User can manually resume from checkpoint

**For remote training:**
1. If training fails, show error dialog with details
2. Inform user that checkpoints may exist on worker
3. Provide checkpoint path for manual resume:
   ```
   ┌─ Remote Training Failed ──────────────────────────────────────────┐
   │                                                                   │
   │  Training failed after epoch 42 of 100.                           │
   │                                                                   │
   │  Error: CUDA out of memory                                        │
   │                                                                   │
   │  Checkpoints saved on worker:                                     │
   │    /mnt/data/runs/2026-02-11_14-32-01/checkpoints/               │
   │                                                                   │
   │  To resume training, use the CLI:                                 │
   │    sleap-rtc train --room ROOM --config CONFIG \                 │
   │      --resume-ckpt /mnt/data/runs/.../last.ckpt                  │
   │                                                                   │
   │                                              [ OK ]               │
   └───────────────────────────────────────────────────────────────────┘
   ```

**Why:**
- Matches existing SLEAP behavior
- Preserves partial work
- CLI can be used for advanced recovery

### Decision 12: Single Remote Job

**What:** Support only one remote job at a time. The "Run" button is disabled while a remote job is active.

**Why:**
- Simpler implementation
- Matches current SLEAP behavior (one training at a time)
- Multiple job tracking is complex (different rooms, workers, progress)
- Can be added in future if needed

**Future consideration:** If multiple jobs are desired, would need:
- Job queue/list UI
- Per-job progress tracking
- Worker allocation strategy

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Version incompatibility between SLEAP and sleap-rtc | API versioning, clear minimum version requirements |
| Network issues during training | Clear error messages, option to cancel/retry |
| Worker selection confusion | Auto-select sensible default, show worker details |
| Authentication complexity | Use existing auth flow with browser redirect |
| LossViewer port conflicts | Use configurable port, detect conflicts |
| Path mismatches between client/worker | PathResolutionDialog before submission |
| Invalid configs submitted | ConfigValidationDialog before submission |
| Training failure mid-job | Preserve checkpoints, show recovery instructions |

## Migration Plan

**Phase 1: sleap-rtc changes (this proposal)**
1. Implement `sleap_rtc.api` module
2. Implement `sleap_rtc.gui.widgets` module (including dialogs)
3. Implement `sleap_rtc.gui.runners` module
4. Add tests with qt-testing skill

**Phase 2: SLEAP changes (separate PRs to talmolab/sleap)**
1. PR 1: Add `enable_experimental_features` preference + menu toggle
2. PR 2: Add conditional RemoteTrainingWidget to MainTabWidget
3. PR 3: Add remote training path to runners.py

## Open Questions (Resolved)

1. ~~**Worker discovery latency:** Should we cache worker list? How often to refresh?~~
   **Resolution:** Manual refresh button, no automatic polling.

2. ~~**Config validation:** Should we validate training config before submission?~~
   **Resolution:** Yes, with ConfigValidationDialog.

3. ~~**Partial progress on failure:** How to handle training that partially completes?~~
   **Resolution:** Preserve checkpoints, show recovery dialog with CLI instructions.

4. ~~**Multiple simultaneous jobs:** Should GUI support tracking multiple remote jobs?~~
   **Resolution:** No, single job for now. Future work if needed.

## Technical Decisions (Clarified)

### Qt Binding: qtpy
Use `qtpy` for Qt imports (same as SLEAP) for maximum compatibility:
```python
from qtpy.QtWidgets import QGroupBox, QVBoxLayout, QCheckBox
from qtpy.QtCore import Signal, QThread
```

### Async Handling: QThread + Signals
Run async operations (WebRTC, API calls) in QThread, emit signals to update GUI:
```python
class WorkerThread(QThread):
    rooms_loaded = Signal(list)
    error = Signal(str)

    def run(self):
        try:
            rooms = asyncio.run(fetch_rooms())
            self.rooms_loaded.emit(rooms)
        except Exception as e:
            self.error.emit(str(e))
```

### Remote File Browser: Embedded Qt Tree View
Use native `QTreeView` that fetches directories via API - feels integrated, no browser popup:
```python
class RemoteFileSystemModel(QAbstractItemModel):
    """Model that fetches directories from worker via API."""
    def fetchMore(self, parent):
        # Fetch children via WebRTC/API
        pass
```

### Config Validation: Call sleap-nn
Import and call sleap-nn's config validation for authoritative checking:
```python
from sleap_nn.config import validate_config  # If available
# Or call sleap-nn CLI: sleap-nn-train --config X --validate-only
```

### Room/Worker Discovery
- `list_rooms()`: HTTP API call to `/api/auth/rooms` (existing endpoint)
- `list_workers(room_id)`: Brief WebSocket connection to get `peer_list`, then disconnect
  - Reuses existing pattern from TUI (`bridge.py:discover_workers`)
  - No persistent connection needed just for listing

## Qt Widget Testing

Use the `qt-testing` skill to verify GUI changes:

```python
import sys
sys.path.insert(0, ".claude/skills/qt-testing")
from scripts.qt_capture import capture_widget, init_qt
from sleap_rtc.gui.widgets import RemoteTrainingWidget

app = init_qt()
widget = RemoteTrainingWidget()
path = capture_widget(widget, "remote_training_widget")
print(f"Screenshot: {path}")
```

Screenshots save to `scratch/.qt-screenshots/` for visual verification.
