## Phase 1: Fix RemoteProgressBridge Message Format

- [ ] 1.1 Change `RemoteProgressBridge` PUB socket from `bind()` to `connect()` in `gui/runners.py`
- [ ] 1.2 Replace `send_multipart([topic, json.dumps()])` with `send_string(jsonpickle.encode())` in `_publish()`
- [ ] 1.3 Add `model_type` parameter to `RemoteProgressBridge.__init__()` and `set_model_type()` method
- [ ] 1.4 Update `_format_message()` to include `what` field and wrap loss data in `logs` dict using `train/loss` and `val/loss` keys
- [ ] 1.5 Add `epoch_begin` event type handling in `_format_message()`
- [ ] 1.6 Add `jsonpickle` to optional dependencies in `pyproject.toml`
- [ ] 1.7 Update `run_remote_training()` to accept and pass `model_type` to bridge
- [ ] 1.8 Update tests in `tests/test_gui_runners.py` for new message format

**Verification:** `uv run pytest tests/test_gui_runners.py -v`

## Phase 2: Thread Model Type Through API

- [ ] 2.1 Add `model_type` field to `ProgressEvent` dataclass in `api.py`
- [ ] 2.2 Update `_run_training_async()` to extract model type from config/spec and include in progress events
- [ ] 2.3 Update `run_remote_training()` in `runners.py` to pass model type from spec to bridge
- [ ] 2.4 Update SLEAP dialog `_run_remote_training()` to pass model type from training config
- [ ] 2.5 Add unit tests for model_type propagation

**Verification:** `uv run pytest tests/test_api.py tests/test_gui_runners.py -v`

## Phase 3: Native Qt Remote File Browser Widget

- [ ] 3.1 Create `RemoteFileBrowser(QWidget)` in `gui/widgets.py` with column-view layout:
  - `MountSelector` (QListWidget, leftmost column showing worker mounts)
  - `ColumnContainer` (QScrollArea, horizontal scroll with QListWidget per directory level)
  - `FilePreview` (QWidget, rightmost panel showing file name, size, modified date)
  - `PathBar` (QLineEdit, bottom bar showing/editing full selected path)
- [ ] 3.2 Implement transport-agnostic communication: `send_fn: Callable[[str], None]` for sending FS_* messages and `on_response(msg: str)` for receiving FS_* responses
- [ ] 3.3 Implement mount loading: send `FS_GET_MOUNTS`, parse `FS_MOUNTS_RESPONSE`, populate MountSelector
- [ ] 3.4 Implement directory navigation: send `FS_LIST_DIR::path::offset`, parse `FS_LIST_RESPONSE`, add/replace columns on folder click
- [ ] 3.5 Implement file selection: click file → highlight, show preview, fill PathBar; double-click or "Select" → emit `file_selected(path)` signal
- [ ] 3.6 Implement `file_filter` parameter (e.g., `*.slp`, `*.mp4,*.avi`) — non-matching files shown greyed out, not selectable
- [ ] 3.7 Implement pagination support: "Load more..." entry when `has_more=true` in response
- [ ] 3.8 Bridge asyncio↔Qt thread: route FS_* responses from data channel callback to widget via thread-safe Qt signal (`QMetaObject.invokeMethod` or similar)
- [ ] 3.9 Add unit tests for `RemoteFileBrowser` with mocked send/receive

**Verification:** `uv run pytest tests/test_gui_integration.py -v -k "file_browser"`

## Phase 4: Integrate File Browser into Path Dialogs

- [x] 4.1 Add collapsible "Browse worker filesystem..." panel to `SlpPathDialog` embedding `RemoteFileBrowser` with `file_filter="*.slp"`
- [x] 4.2 Wire `file_selected` signal to auto-fill the "Worker path" input field
- [x] 4.3 Pass the active data channel's `send` method and response routing from `on_path_rejected` callback in `presubmission.py`
- [x] 4.4 Add `on_videos_missing` callback to `api.check_video_paths()` / `_check_video_paths_async()` — called with `(videos, send_fn)` while data channel is alive, analogous to `on_path_rejected`. Bridge to main thread in `presubmission.py` to show `PathResolutionDialog` with a working `send_fn`.
- [x] 4.5 Make Video and Status columns read-only in `PathResolutionDialog` table
- [x] 4.6 Wire "Browse..." button per missing video row to open the shared `RemoteFileBrowser` panel and fill the selected row on file selection
- [ ] 4.7 Manual end-to-end test: SLP path resolution via browser, video path resolution via browser

**Verification:** Manual testing with SLEAP GUI + running worker

## Phase 5: Add Prefix Detection to PathResolutionDialog

- [ ] 5.1 Add `find_changed_prefix()` utility function to `gui/widgets.py` (detect common prefix change between two paths)
- [ ] 5.2 Update `PathResolutionDialog` to call `find_changed_prefix()` when a user resolves a video path (via browser or manual input)
- [ ] 5.3 Show confirmation dialog: "Apply this path change to N other missing videos?"
- [ ] 5.4 On confirmation, apply prefix replacement to all missing video paths and update table
- [ ] 5.5 Add unit tests for prefix detection and bulk application

**Verification:** `uv run pytest tests/test_gui_integration.py -v -k "path_resolution"`

## Phase 6: Prefix Persistence

- [ ] 6.1 Add `save_path_prefix()` and `load_path_prefixes()` functions to store mappings in sleap-rtc config
- [ ] 6.2 On dialog open, auto-apply saved prefixes to missing paths
- [ ] 6.3 Add unit tests for prefix persistence
- [ ] 6.4 Manual end-to-end test: resolve paths once, verify auto-applied on next run

**Verification:** `uv run pytest tests/test_gui_integration.py -v -k "prefix"`

## Phase 7: Forward Training Logs to Terminal

The worker already sends raw training log lines over the data channel
(`job_executor.py:634-637`) alongside structured `JOB_PROGRESS` messages.
The client currently drops unrecognized messages silently. This phase wires
them through so the GUI terminal shows live training output (matching the
`sleap-rtc train` CLI experience).

- [x] 7.1 Add `on_log` callback parameter to `run_training()` / `_run_training_async()` in `api.py` — invoked with each raw log line received on the data channel that doesn't match a known protocol prefix
- [x] 7.2 In the `_run_training_async()` message loop, forward unrecognized string messages to `on_log` instead of silently dropping them
- [x] 7.3 Add `on_log` parameter to `run_remote_training()` in `gui/runners.py` and wire it through to `api.run_training()`
- [x] 7.4 In `gui/runners.py`, call `format_progress_line()` from the `progress_handler` and print to terminal (or forward to an `on_log` callback) so structured progress events also appear in the terminal
- [x] 7.5 Update SLEAP dialog `_run_remote_training()` to connect `on_log` to a text widget or logger for live training output
- [x] 7.6 Add unit tests for log forwarding

**Verification:** `uv run pytest tests/test_api.py tests/test_gui_runners.py -v` + manual test showing logs in terminal during remote training

## Phase 8: Stop Early / Cancel Training via RTC

SLEAP's LossViewer sends `{"command": "stop"}` via a ZMQ PUB socket on the
controller port. Currently, `RemoteProgressBridge` only publishes TO the
LossViewer (one-way PUB). This phase adds the reverse path: listen for
stop/cancel commands from the LossViewer, forward them over RTC to the
worker, and have the worker terminate the training process.

- [x] 8.1 Add `MSG_JOB_STOP` and `MSG_JOB_CANCEL` message types to `protocol.py`
- [x] 8.2 Add a ZMQ SUB socket to `RemoteProgressBridge` that connects to LossViewer's controller port and listens for `{"command": "stop"}` / `{"command": "cancel"}` messages
- [x] 8.3 Add `on_stop` callback parameter to `RemoteProgressBridge` — invoked when a stop/cancel command is received from the LossViewer
- [x] 8.4 Add `on_channel_ready` parameter to `run_training()` / `_run_training_async()` in `api.py` enabling the client to send messages back to the worker during training (bidirectional data channel)
- [x] 8.5 Wire `RemoteProgressBridge.set_send_fn` as `on_channel_ready` callback to receive the thread-safe data channel send function, used by the poll thread to forward stop/cancel commands
- [x] 8.6 On the worker side in `job_executor.py`, add `stop_running_job()` and `cancel_running_job()` methods. Worker's `on_message` handler dispatches `MSG_JOB_STOP` / `MSG_JOB_CANCEL` to these methods.
- [x] 8.7 Handle graceful stop vs hard cancel: `stop` → `SIGINT` (allows sleap-nn to save checkpoint), `cancel` → `SIGTERM` (immediate termination)
- [x] 8.8 Send `JOB_COMPLETE` (with `stopped_early=true`) for SIGINT exit, `JOB_FAILED` (with "cancelled by user") for SIGTERM exit
- [x] 8.9 Add unit tests for stop/cancel message flow
- [ ] 8.10 Manual end-to-end test: start training, click "Stop Early" in LossViewer, verify process stops and model checkpoint is saved

**Verification:** `uv run pytest tests/test_api.py tests/test_gui_runners.py -v` + manual test with LossViewer stop button
