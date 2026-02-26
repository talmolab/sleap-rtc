# cli-directory-browser

## Purpose

Provide an interactive directory browser in the CLI for path correction when job validation fails.

## ADDED Requirements

### Requirement: Directory Browser Display

The CLI SHALL display an interactive directory browser using prompt_toolkit.

#### Scenario: Display directory listing

- **GIVEN** DirectoryBrowser is initialized with start path `/vast/project`
- **WHEN** browser fetches listing from worker
- **THEN** display SHALL show current path header
- **AND** display SHALL show ".." entry for parent navigation
- **AND** display SHALL show directories with "/" suffix and "[dir]" label
- **AND** display SHALL show files with size in human-readable format
- **AND** directories SHALL appear before files in listing

#### Scenario: Display with file filter

- **GIVEN** DirectoryBrowser initialized with file_filter="*.slp"
- **WHEN** directory contains .slp and .yaml files
- **THEN** display SHALL show only .slp files
- **AND** display SHALL still show all directories

#### Scenario: Highlight selected entry

- **WHEN** user navigates to an entry
- **THEN** selected entry SHALL have ">" prefix
- **AND** selected entry SHALL be displayed in cyan/bold

#### Scenario: Display navigation hints

- **WHEN** browser is displayed
- **THEN** footer SHALL show key bindings:
  - [↑/↓] Navigate
  - [Enter] Select/Open
  - [Backspace] Back
  - [Esc] Cancel

---

### Requirement: Directory Navigation

The browser SHALL support keyboard navigation through the filesystem.

#### Scenario: Navigate up with arrow key

- **GIVEN** multiple entries in listing
- **AND** selection is on second entry
- **WHEN** user presses up arrow
- **THEN** selection SHALL move to first entry

#### Scenario: Navigate down with arrow key

- **GIVEN** multiple entries in listing
- **AND** selection is on first entry
- **WHEN** user presses down arrow
- **THEN** selection SHALL move to second entry

#### Scenario: Wrap navigation at top

- **GIVEN** selection is on first entry
- **WHEN** user presses up arrow
- **THEN** selection SHALL wrap to last entry

#### Scenario: Wrap navigation at bottom

- **GIVEN** selection is on last entry
- **WHEN** user presses down arrow
- **THEN** selection SHALL wrap to first entry

#### Scenario: Vim-style navigation

- **WHEN** user presses 'j'
- **THEN** selection SHALL move down (same as down arrow)
- **WHEN** user presses 'k'
- **THEN** selection SHALL move up (same as up arrow)

---

### Requirement: Directory Entry Selection

The browser SHALL handle selection of directories and files differently.

#### Scenario: Enter directory on selection

- **GIVEN** selection is on a directory entry
- **WHEN** user presses Enter
- **THEN** browser SHALL navigate into that directory
- **AND** browser SHALL fetch new listing from worker
- **AND** selection SHALL reset to first entry
- **AND** current path SHALL update to new directory

#### Scenario: Select parent directory

- **GIVEN** selection is on ".." entry
- **WHEN** user presses Enter
- **THEN** browser SHALL navigate to parent directory
- **AND** current path SHALL update to parent

#### Scenario: Return file path on selection

- **GIVEN** selection is on a file entry
- **WHEN** user presses Enter
- **THEN** browser SHALL return full path of selected file
- **AND** browser SHALL close

#### Scenario: Navigate up with backspace

- **WHEN** user presses Backspace
- **THEN** browser SHALL navigate to parent directory
- **AND** effect SHALL be same as selecting ".." entry

---

### Requirement: Browser Cancellation

The browser SHALL support cancellation without selection.

#### Scenario: Cancel with Escape

- **WHEN** user presses Escape
- **THEN** browser SHALL close
- **AND** browser SHALL return None

#### Scenario: Cancel with 'q'

- **WHEN** user presses 'q'
- **THEN** browser SHALL close
- **AND** browser SHALL return None

#### Scenario: Cancel with Ctrl+C

- **WHEN** user presses Ctrl+C
- **THEN** browser SHALL close gracefully
- **AND** browser SHALL return None
- **AND** no exception SHALL propagate to caller

---

### Requirement: Worker Filesystem Fetching

The browser SHALL fetch directory listings from the worker via RTC.

#### Scenario: Fetch initial listing

- **GIVEN** browser initialized with start_path
- **WHEN** browser runs
- **THEN** browser SHALL call fetch_listing callback with start_path
- **AND** browser SHALL wait for async response

#### Scenario: Fetch listing on navigation

- **WHEN** user navigates into a directory
- **THEN** browser SHALL call fetch_listing with new path
- **AND** display SHALL update when response arrives

#### Scenario: Handle fetch error

- **WHEN** fetch_listing raises exception or returns error
- **THEN** browser SHALL display error message
- **AND** browser SHALL remain open
- **AND** user SHALL be able to navigate elsewhere

---

### Requirement: File Size Formatting

The browser SHALL display file sizes in human-readable format.

#### Scenario: Format bytes

- **GIVEN** file size is 500 bytes
- **THEN** display SHALL show "500 B"

#### Scenario: Format kilobytes

- **GIVEN** file size is 2048 bytes
- **THEN** display SHALL show "2.0 KB"

#### Scenario: Format megabytes

- **GIVEN** file size is 5242880 bytes (5 MB)
- **THEN** display SHALL show "5.0 MB"

#### Scenario: Format gigabytes

- **GIVEN** file size is 2147483648 bytes (2 GB)
- **THEN** display SHALL show "2.0 GB"

---

### Requirement: Sorting

The browser SHALL sort entries consistently.

#### Scenario: Directories before files

- **GIVEN** directory contains both files and subdirectories
- **WHEN** listing is displayed
- **THEN** ".." SHALL appear first
- **AND** directories SHALL appear before files
- **AND** directories SHALL be sorted alphabetically (case-insensitive)
- **AND** files SHALL be sorted alphabetically (case-insensitive)

---

### Requirement: Integration with Path Correction Flow

The DirectoryBrowser SHALL integrate with job submission path correction.

#### Scenario: Launch browser for missing labels path

- **GIVEN** JOB_REJECTED with error on labels_path field
- **AND** error indicates path does not exist
- **WHEN** user confirms path correction
- **THEN** browser SHALL launch with file_filter="*.slp"
- **AND** browser SHALL start in parent directory of invalid path
- **AND** selected path SHALL be used to update labels_path in job spec

#### Scenario: Launch browser for missing config path

- **GIVEN** JOB_REJECTED with error on config_path field
- **WHEN** user confirms path correction
- **THEN** browser SHALL launch with file_filter="*.yaml"
- **AND** selected path SHALL be used to update config_path

#### Scenario: Launch browser for missing model path

- **GIVEN** JOB_REJECTED with error on model_paths field
- **WHEN** user confirms path correction
- **THEN** browser SHALL allow directory selection (not just files)
- **AND** selected directory SHALL be used to update model_paths entry
