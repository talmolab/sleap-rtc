## ADDED Requirements

### Requirement: Column-View Remote File Browser Widget

The system SHALL provide a `RemoteFileBrowser` PySide6 widget that renders the worker's remote filesystem in a macOS Finder-style column view.

#### Scenario: Display worker mount points

- **WHEN** the file browser initializes
- **THEN** it SHALL send `FS_GET_MOUNTS` via the provided `send_fn`
- **AND** populate the leftmost MountSelector column with returned mount points (label and path)

#### Scenario: Navigate into directory

- **WHEN** user clicks a folder in column N
- **THEN** the browser SHALL send `FS_LIST_DIR::<path>::0` via `send_fn`
- **AND** add column N+1 with the directory contents
- **AND** remove any columns deeper than N+1
- **AND** scroll the column container to show the new column

#### Scenario: Select a file

- **WHEN** user clicks a file in any column
- **THEN** the browser SHALL highlight the file
- **AND** show file metadata (name, size, modified date) in the FilePreview panel
- **AND** fill the PathBar with the full path
- **AND** emit `file_selected(path: str)` signal on double-click or "Select" button

#### Scenario: Paginated directory listing

- **WHEN** a directory contains more entries than the page size
- **AND** the worker responds with `has_more=true`
- **THEN** the column SHALL show a "Load more..." entry at the bottom
- **AND** clicking it SHALL send `FS_LIST_DIR::<path>::<offset>` to fetch the next page

### Requirement: File Type Filtering

The `RemoteFileBrowser` SHALL support filtering selectable files by extension.

#### Scenario: Filter for SLP files

- **WHEN** the browser is initialized with `file_filter="*.slp"`
- **THEN** only `.slp` files SHALL be selectable (clickable, normal appearance)
- **AND** other files SHALL appear greyed out and not be selectable
- **AND** all folders SHALL remain navigable regardless of filter

#### Scenario: Filter for video files

- **WHEN** the browser is initialized with `file_filter="*.mp4,*.avi,*.mov,*.h264,*.mkv"`
- **THEN** only matching video files SHALL be selectable
- **AND** other files SHALL appear greyed out

### Requirement: Transport-Agnostic Communication

The `RemoteFileBrowser` SHALL communicate via injected callables rather than directly managing WebRTC connections.

#### Scenario: Reuse existing data channel

- **WHEN** the browser is embedded in `SlpPathDialog` during presubmission
- **AND** a WebRTC data channel is already open for path checking
- **THEN** the browser SHALL use the same data channel via `send_fn`
- **AND** FS_* responses SHALL be routed to `on_response()` via a thread-safe Qt signal

#### Scenario: Mock for testing

- **WHEN** the browser is instantiated in a test
- **THEN** `send_fn` can be a mock callable
- **AND** `on_response()` can be called directly with mock FS_* response strings

### Requirement: Inline Embedding in Path Dialogs

The `RemoteFileBrowser` SHALL be embeddable as a collapsible inline panel within existing path resolution dialogs.

#### Scenario: Expand browser in SlpPathDialog

- **WHEN** user clicks "Browse worker filesystem..." in the SLP path resolution dialog
- **THEN** the file browser panel SHALL expand below the existing UI
- **AND** selecting a file SHALL auto-fill the "Worker path" input field

#### Scenario: Browse for video in PathResolutionDialog

- **WHEN** user clicks "Browse..." next to a missing video row
- **THEN** the shared file browser panel SHALL expand
- **AND** selecting a file SHALL fill the worker path for that specific video row
