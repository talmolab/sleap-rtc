## ADDED Requirements

### Requirement: Automatic Prefix Detection

The PathResolutionDialog SHALL detect the common path prefix change when a user resolves a missing video path.

#### Scenario: Detect prefix from single resolution

- **WHEN** user resolves video with original path `/Volumes/talmo/amick/project/video1.mp4`
- **AND** user provides worker path `/root/vast/amick/project/video1.mp4`
- **THEN** the dialog SHALL detect prefix change: `/Volumes/talmo/amick` → `/root/vast/amick`

#### Scenario: Handle paths with no common suffix

- **WHEN** user resolves video to a completely different path
- **AND** the original and resolved paths share no common suffix beyond the filename
- **THEN** the dialog SHALL not attempt prefix detection
- **AND** only the single resolved path SHALL be updated

### Requirement: Bulk Prefix Application

The PathResolutionDialog SHALL offer to apply a detected prefix change to all other missing video paths.

#### Scenario: Apply prefix to all missing videos

- **WHEN** a prefix change is detected (e.g., `/Volumes/talmo/amick` → `/root/vast/amick`)
- **AND** 3 other videos are missing
- **THEN** the dialog SHALL ask "Apply this path change to all other missing videos?"
- **AND** if user confirms, apply the prefix replacement to all missing video paths
- **AND** update the table to show newly resolved paths

#### Scenario: Partial prefix match

- **WHEN** prefix is applied to 3 missing videos
- **AND** 2 of 3 resulting paths are confirmed to exist on the worker
- **THEN** 2 videos SHALL be marked as resolved
- **AND** 1 video SHALL remain marked as missing

#### Scenario: User declines bulk application

- **WHEN** a prefix change is detected
- **AND** user declines to apply it to other videos
- **THEN** only the single resolved path SHALL be updated
- **AND** other missing videos remain unchanged

### Requirement: Prefix Persistence

The system SHALL persist path prefix mappings for reuse across sessions.

#### Scenario: Save prefix on resolution

- **WHEN** user resolves a video path with prefix change `/Volumes/talmo/amick` → `/root/vast/amick`
- **THEN** the mapping SHALL be saved to sleap-rtc configuration
- **AND** the mapping SHALL be associated with the current room or worker

#### Scenario: Auto-apply saved prefix

- **WHEN** the PathResolutionDialog opens with missing videos
- **AND** a saved prefix mapping matches the missing video paths
- **THEN** the dialog SHALL auto-apply the prefix and show the results
- **AND** user SHALL still confirm before proceeding
