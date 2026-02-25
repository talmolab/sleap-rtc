# SLP Video Resolution Capability

## ADDED Requirements

### Requirement: Automatic Video Accessibility Check

The system SHALL automatically check if video paths in an SLP file are accessible on the Worker filesystem after SLP path resolution.

#### Scenario: All videos accessible
- **WHEN** Worker resolves SLP file path
- **AND** all video paths in the SLP exist on the Worker filesystem
- **THEN** training proceeds without interruption

#### Scenario: Missing videos detected
- **WHEN** Worker resolves SLP file path
- **AND** 2 of 5 video paths do not exist on the Worker filesystem
- **THEN** Worker sends FS_CHECK_VIDEOS_RESPONSE with list of missing video filenames
- **AND** Client automatically launches the resolution UI

#### Scenario: Embedded videos excluded
- **WHEN** SLP file contains embedded video frames
- **THEN** embedded videos are not checked for filesystem accessibility

### Requirement: Video Resolution Web UI

The system SHALL provide a web UI at `/resolve` for resolving missing video paths.

#### Scenario: Display missing videos
- **WHEN** resolution UI is launched with 3 missing videos
- **THEN** UI displays a list of missing video filenames with their original paths
- **AND** each video shows status indicator (missing/resolved)

#### Scenario: Integrate filesystem browser
- **WHEN** resolution UI is displayed
- **THEN** UI includes the existing remote filesystem browser for navigation
- **AND** user can browse Worker mounts to locate videos

### Requirement: Manual Video Resolution

The system SHALL allow users to manually resolve individual missing video paths by browsing the Worker filesystem.

#### Scenario: Resolve single video via browser
- **WHEN** user navigates the filesystem browser
- **AND** user selects a video file (e.g., `/mnt/vast/project/video1.mp4`)
- **THEN** the corresponding missing video is marked as resolved
- **AND** the new path is stored for later SLP rewriting

### Requirement: Directory Scanning

The system SHALL scan a directory for other missing video filenames when user resolves a video (SLP Viewer style).

#### Scenario: Auto-find videos in same directory
- **WHEN** user selects `/mnt/vast/project/video1.mp4` to resolve video1.mp4
- **AND** video2.mp4 and video3.mp4 are also missing
- **THEN** system scans `/mnt/vast/project/` for video2.mp4 and video3.mp4
- **AND** if found, those videos are automatically marked as resolved

#### Scenario: Partial directory match
- **WHEN** user selects a video in directory `/mnt/vast/project/`
- **AND** system scans for 3 missing filenames
- **AND** only 2 of 3 are found in that directory
- **THEN** 2 videos are marked as resolved
- **AND** 1 video remains marked as missing

#### Scenario: Videos in different directories
- **WHEN** videos are located in different directories on the Worker
- **THEN** user resolves one video per directory
- **AND** each selection triggers a scan of that directory

### Requirement: SLP File Writing

The system SHALL write a corrected SLP file to the Worker filesystem with updated video paths using sleap-io.

#### Scenario: Save resolved SLP
- **WHEN** all videos are resolved
- **AND** user clicks "Save"
- **AND** user selects output directory
- **THEN** Worker creates `resolved_YYYYMMDD_<original>.slp` with updated paths
- **AND** original SLP file is preserved unchanged

#### Scenario: Use sleap-io for rewriting
- **WHEN** SLP file is rewritten
- **THEN** Worker uses `Labels.replace_filenames(filename_map={...})` from sleap-io
- **AND** all labels, instances, skeletons, and metadata are preserved

#### Scenario: Save with partial resolution
- **WHEN** user attempts to save with unresolved videos
- **THEN** system warns about unresolved videos
- **AND** allows saving if user confirms (training may fail for those videos)

### Requirement: Training Flow Integration

The system SHALL integrate video resolution into the training flow seamlessly.

#### Scenario: Resolution before training
- **WHEN** missing videos are detected during client-train
- **AND** user resolves all videos in the resolution UI
- **AND** user saves the corrected SLP
- **THEN** training proceeds using the corrected SLP file

#### Scenario: User cancels resolution
- **WHEN** user closes the resolution UI without saving
- **THEN** training is cancelled
- **AND** user is informed that videos must be resolved to proceed

### Requirement: Standalone Resolution Command

The system SHALL provide a standalone CLI command for pre-flight video path resolution.

#### Scenario: Resolve paths before training
- **WHEN** user runs `sleap-rtc resolve-paths --room ROOM --token TOKEN --slp /path/to/labels.slp`
- **THEN** system connects to Worker
- **AND** checks video accessibility for the specified SLP
- **AND** launches resolution UI if videos are missing

### Requirement: Path Security

The system SHALL validate that all resolved paths are within Worker's configured mounts.

#### Scenario: Reject path outside mounts
- **WHEN** user attempts to save SLP with a video path outside allowed mounts
- **THEN** system rejects the operation
- **AND** displays an error message

#### Scenario: Validate output directory
- **WHEN** user selects an output directory for the resolved SLP
- **THEN** system validates the directory is within allowed mounts
- **AND** user has write permission
