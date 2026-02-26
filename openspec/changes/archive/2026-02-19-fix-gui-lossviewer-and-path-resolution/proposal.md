## Why

The `RemoteProgressBridge` in `gui/runners.py` publishes ZMQ messages that are incompatible with SLEAP's `LossViewer` widget (`sleap/gui/widgets/monitor.py`). The LossViewer expects single-frame `jsonpickle`-encoded messages with a `what` field and loss data nested in a `logs` dict, but the bridge sends multipart `json.dumps`-encoded messages with flat loss fields. Additionally, the bridge **binds** a PUB socket, but the LossViewer **binds** its SUB socket — both cannot bind to the same port.

Separately, the `PathResolutionDialog` in `gui/widgets.py` asks users to manually type each missing video path. SLEAP's native `MissingFilesDialog` uses a smarter pattern: when the user resolves one file, it detects the prefix change (e.g., `/Volumes/talmo/amick/` → `/root/vast/amick/`) and offers to apply it to all other missing files automatically.

## What Changes

- Fix `RemoteProgressBridge` ZMQ message format to match LossViewer expectations:
  - Use `connect()` instead of `bind()` (LossViewer owns the bind)
  - Use `send_string(jsonpickle.encode(msg))` instead of `send_multipart([topic, json.dumps()])`
  - Add `what` field (model type) to all messages
  - Wrap loss data in `logs` dict (`{"logs": {"train/loss": X, "val/loss": Y}}`)
  - Add `epoch_begin` and `batch_end` event forwarding
- Improve `PathResolutionDialog` with automatic prefix detection:
  - When user resolves one video path, detect the common prefix change
  - Offer to apply the same prefix change to all other missing videos
  - Persist prefix mappings for future sessions

## Impact

- **New specs**:
  - `gui-progress-bridge`: ZMQ message bridge between WebRTC progress and LossViewer
  - `gui-remote-file-browser`: Native Qt column-view file browser for worker filesystem
  - `gui-path-resolution`: Prefix-based video path resolution for remote workers
- **Affected code**:
  - `sleap_rtc/gui/runners.py` — Fix `RemoteProgressBridge` message format and socket behavior
  - `sleap_rtc/gui/widgets.py` — Add `RemoteFileBrowser` widget, prefix detection, update `SlpPathDialog` and `PathResolutionDialog`
  - `sleap_rtc/gui/presubmission.py` — Pass data channel send/receive to dialogs for file browsing, pass model type for `what` field
  - `sleap_rtc/api.py` — Add `model_type` to `ProgressEvent` and training API, expose data channel for FS_* messaging

## Dependencies

- Builds on merged PR #46 (`add-presubmission-flow`)
- SLEAP `LossViewer` in `sleap/gui/widgets/monitor.py` (read-only reference)
- SLEAP `MissingFilesDialog` in `sleap/gui/dialogs/missingfiles.py` (design reference)
