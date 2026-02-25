## ADDED Requirements

### Requirement: Upload Option in SLP Path Resolution Dialog

The system SHALL offer an "Upload file to worker..." option in the SLP path
resolution dialog when the rejected file is a `.pkg.slp`, alongside the existing
browse option, so users without shared filesystem access can transfer the file
directly.

#### Scenario: Upload option shown for pkg.slp
- **WHEN** the worker rejects an SLP path
- **AND** the local file name ends in `.pkg.slp`
- **THEN** the SLP Path Resolution dialog displays an "Upload file to worker..."
  button in addition to "Browse worker filesystem..."

#### Scenario: Upload option not shown for regular .slp
- **WHEN** the worker rejects an SLP path
- **AND** the local file does not end in `.pkg.slp`
- **THEN** only the "Browse worker filesystem..." option is shown
- **AND** no upload button is present

#### Scenario: Upload completes and auto-fills worker path
- **WHEN** the user clicks "Upload file to worker..."
- **AND** selects a destination directory and confirms
- **AND** the transfer completes successfully
- **THEN** the Worker path field auto-fills with the absolute path on the worker
- **AND** the Continue button becomes enabled
- **AND** the training presubmission flow continues as if the user had typed the
  path manually

#### Scenario: Upload cancelled by user
- **WHEN** the user opens the upload destination picker
- **AND** closes it without selecting a directory
- **THEN** the dialog returns to its previous state
- **AND** no transfer is initiated

### Requirement: Skip Video-Path Resolution for Fully-Embedded pkg.slp

When a `.pkg.slp` file has all videos embedded the system SHALL skip the video
path resolution step because no external video files are required for training.

#### Scenario: All videos embedded — no resolution dialog
- **WHEN** the worker receives a `.pkg.slp` path
- **AND** `check_video_accessibility` returns `missing == 0` and `embedded > 0`
- **THEN** the presubmission flow proceeds directly to job submission
- **AND** the PathResolutionDialog is NOT shown

#### Scenario: Mixed embedded and external videos
- **WHEN** the worker receives a `.pkg.slp` path
- **AND** some videos are embedded and some are external files
- **AND** one or more external video files are missing on the worker
- **THEN** the PathResolutionDialog IS shown for the missing external videos only
