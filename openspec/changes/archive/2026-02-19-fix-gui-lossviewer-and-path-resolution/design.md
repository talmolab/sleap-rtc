## Context

SLEAP's `LossViewer` widget is the standard way users monitor training progress. For local training, sleap-nn sends ZMQ messages directly to the LossViewer. For remote training via sleap-rtc, progress events arrive over WebRTC and must be re-emitted locally in the exact format LossViewer expects.

SLEAP's `MissingFilesDialog` handles missing video files when loading projects by detecting path prefix changes and applying them in bulk. Our remote `PathResolutionDialog` needs a similar approach since local-to-remote path differences typically share a common prefix.

## Goals / Non-Goals

- **Goals**:
  - LossViewer displays real-time loss curves during remote training (identical to local training UX)
  - Users can resolve all missing video paths by fixing one path (prefix auto-detection)
- **Non-Goals**:
  - Modifying the LossViewer widget itself (it's in the SLEAP codebase)
  - Building a full filesystem browser in the path resolution dialog (deferred)
  - Supporting batch_end events from remote (sleap-nn sends these locally via ZMQ, but the WebRTC progress API currently only relays epoch-level data)

## Decisions

### LossViewer Message Format

**Decision**: Match sleap-nn's ProgressReporterZMQ format exactly.

The LossViewer parses messages with:
```python
msg = jsonpickle.decode(self.sub.recv_string())
```

And expects:
```python
{
    "event": "epoch_end",
    "what": "centroid",          # Model type filter
    "logs": {
        "train/loss": 0.0045,   # sleap-nn naming
        "val/loss": 0.0051
    }
}
```

Our bridge currently sends:
```python
# WRONG: multipart, json.dumps, flat fields, no "what"
topic = b"progress"
payload = json.dumps({"event": "epoch_end", "train_loss": 0.0045}).encode()
socket.send_multipart([topic, payload])
```

Must change to:
```python
# CORRECT: single string, jsonpickle, nested logs, with "what"
socket.send_string(jsonpickle.encode({
    "event": "epoch_end",
    "what": model_type,
    "logs": {"train/loss": 0.0045, "val/loss": 0.0051}
}))
```

### ZMQ Socket Direction

**Decision**: Bridge PUB socket connects; LossViewer SUB socket binds.

SLEAP's LossViewer binds its SUB socket to a port (`sub.bind(publish_address)`). The publisher must connect to it. Our bridge currently binds, which causes an address conflict.

Flow:
```
LossViewer (SUB, binds tcp://127.0.0.1:9001)
    ↑ connects
RemoteProgressBridge (PUB, connects tcp://127.0.0.1:9001)
    ↑ receives WebRTC progress
sleap-rtc API (_run_training_async)
```

### Native Qt Remote File Browser

**Decision**: Build a `RemoteFileBrowser` PySide6 widget with macOS Finder-style column view, embedded inline in path resolution dialogs.

**Alternatives considered**:
- **Embedded QWebEngineView** (reuse existing HTML file browser): Heavyweight dependency (100MB+ QtWebEngine), fragile WebSocket plumbing, styling mismatch with native Qt.
- **Launch browser, copy-paste**: Context-switching problem — users already manage SLEAP GUI, dashboard, and worker container.
- **Standard QTreeView**: Simpler to build, but visually inconsistent with the existing web file browser and less intuitive than column navigation.

**Widget layout**:
```
RemoteFileBrowser(QWidget)
├── MountSelector (QListWidget, leftmost — shows configured mounts)
├── ColumnContainer (QScrollArea, horizontal)
│   ├── Column 0: QListWidget (mount root contents)
│   ├── Column 1: QListWidget (subdirectory)
│   └── Column N: QListWidget (deeper levels)
├── FilePreview (QWidget, rightmost — file name, size, date)
└── PathBar (QLineEdit, bottom — shows/edits full selected path)
```

**Transport**: The widget is transport-agnostic. It accepts `send_fn: Callable[[str], None]` and an `on_response(msg: str)` method. This lets it work with the existing WebRTC data channel during presubmission (reusing the open connection — the path check flow is paused while the dialog is showing) or with a mock for testing.

**Data channel reuse**: When the worker rejects an SLP path, the `on_path_rejected` callback fires and the path check async flow pauses. The data channel is idle. The file browser sends `FS_GET_MOUNTS` / `FS_LIST_DIR` messages on the same channel. Responses are routed to the widget via a thread-safe Qt signal bridging asyncio → Qt thread.

**File filtering**: The widget accepts `file_filter` (e.g., `*.slp`, `*.mp4,*.avi`). Non-matching files are shown greyed out but not selectable. Folders are always navigable.

### Prefix Detection for Path Resolution

**Decision**: Adopt SLEAP's `find_changed_subpath` pattern.

When the user provides a corrected path for one video (via the file browser or manual input), compare with the original:
```
Original: /Volumes/talmo/amick/project/video1.mp4
Resolved: /root/vast/amick/project/video1.mp4
Prefix:   /Volumes/talmo/amick → /root/vast/amick
```

Apply this prefix to all other missing paths. If the resulting paths exist on the worker, auto-resolve them. This is the same algorithm SLEAP uses in `MissingFilesDialog.setFilename()`.

## Risks / Trade-offs

- **jsonpickle dependency**: The bridge will need `jsonpickle` for encoding. This is already a SLEAP dependency but not a sleap-rtc dependency. We'll add it as an optional dependency (only needed when GUI integration is used).
- **Port coordination**: The bridge must know which port the LossViewer bound to. The SLEAP dialog already passes `zmq_ports` to training runners, so we can thread this through.
- **`what` field**: Requires the model type string (e.g., "centroid", "centered_instance") to be passed through from the SLEAP dialog to the bridge. This is available in the training config.
- **asyncio↔Qt bridging**: FS_* responses arrive on the asyncio thread but must update Qt widgets on the main thread. Using `QMetaObject.invokeMethod` with `Qt.QueuedConnection` or a dedicated Qt signal for thread-safe dispatch.

## Open Questions

- Should prefix mappings be persisted to sleap-rtc config (similar to SLEAP's `path_prefixes.yaml`)?
