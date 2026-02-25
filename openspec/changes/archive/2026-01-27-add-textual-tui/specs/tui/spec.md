## ADDED Requirements

### Requirement: TUI Application Launch
The system SHALL provide a `sleap-rtc tui` command that launches a terminal-based file browser connected to a worker room.

#### Scenario: Launch with room and token
- **WHEN** user runs `sleap-rtc tui --room ROOM_ID --token TOKEN`
- **THEN** the TUI connects to the signaling server
- **AND** discovers available workers in the room
- **AND** displays Miller columns file browser

#### Scenario: Launch with stored credentials
- **WHEN** user runs `sleap-rtc tui --room ROOM_ID` without explicit token
- **AND** valid credentials exist in `~/.sleap-rtc/credentials.json`
- **THEN** the TUI uses stored JWT and room token

#### Scenario: OTP authentication
- **WHEN** user runs `sleap-rtc tui --room ROOM_ID --otp-secret SECRET`
- **THEN** the TUI prompts for OTP code before connecting
- **AND** verifies OTP with worker before establishing data channel

### Requirement: Miller Columns File Browser
The system SHALL display worker filesystem contents in a Miller columns layout with keyboard navigation.

#### Scenario: Display mount points
- **WHEN** TUI connects to a worker
- **THEN** the leftmost column shows available mount points from worker configuration

#### Scenario: Navigate directories
- **WHEN** user presses right arrow or Enter on a directory
- **THEN** the next column shows directory contents
- **AND** previous columns remain visible

#### Scenario: Navigate back
- **WHEN** user presses left arrow
- **THEN** focus moves to the parent directory column
- **AND** child columns are cleared

#### Scenario: Scroll within column
- **WHEN** directory contains more entries than visible
- **THEN** user can scroll with up/down arrows
- **AND** pagination requests additional entries from worker

### Requirement: Worker Tab Navigation
The system SHALL display connected workers as tabs and allow switching between them.

#### Scenario: Display worker tabs
- **WHEN** TUI is connected to a room with multiple workers
- **THEN** tabs show each worker's identifier at the top of the screen

#### Scenario: Switch workers
- **WHEN** user clicks a worker tab or presses corresponding number key
- **THEN** the file browser switches to that worker's filesystem
- **AND** previous navigation state is preserved per worker

#### Scenario: Worker connection status
- **WHEN** a worker disconnects during session
- **THEN** the tab shows disconnected status
- **AND** file browser displays reconnection message

### Requirement: SLP Context Panel
The system SHALL display video path status when an SLP file is selected, enabling inline path resolution.

#### Scenario: Show SLP video status
- **WHEN** user selects a `.slp` file in the browser
- **THEN** a context panel appears below the Miller columns
- **AND** lists all video paths in the SLP with found/missing indicators

#### Scenario: All videos found
- **WHEN** all video paths in the SLP exist on the worker
- **THEN** each video shows a ✓ indicator
- **AND** the panel indicates the SLP is ready to use

#### Scenario: Missing videos
- **WHEN** one or more video paths are not found
- **THEN** missing videos show a ✗ indicator
- **AND** the panel shows instructions to navigate and fix

#### Scenario: Fix missing video with prefix
- **WHEN** user navigates to the correct video location
- **AND** presses 'f' (fix) hotkey
- **THEN** the system proposes a prefix-based path resolution
- **AND** user can confirm to update the SLP

### Requirement: Keyboard Navigation
The system SHALL support keyboard-driven navigation throughout the TUI.

#### Scenario: Arrow key navigation
- **WHEN** user presses arrow keys
- **THEN** left/right navigate columns, up/down navigate within column

#### Scenario: Quick exit
- **WHEN** user presses 'q' or Ctrl+C
- **THEN** the TUI exits gracefully and closes WebRTC connection

#### Scenario: Help overlay
- **WHEN** user presses '?'
- **THEN** a help overlay shows available keyboard shortcuts
