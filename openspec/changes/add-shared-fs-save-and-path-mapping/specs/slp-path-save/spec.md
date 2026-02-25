# slp-path-save Specification

## ADDED Requirements

### Requirement: Save to Folder Buttons in SLP Path Resolution Dialog

The SLP Path Resolution dialog SHALL display "Save as .slp to folder..." and
"Save as .pkg.slp to folder..." buttons when the caller supplies the
corresponding save callables, positioned above the upload and browse sections
and separated from them by a horizontal rule.

#### Scenario: Save buttons shown when callables provided
- **GIVEN** `SlpPathDialog` is constructed with `save_fn` and `convert_fn` both non-None
- **AND** the local file is a plain `.slp`
- **WHEN** the dialog opens
- **THEN** a "Save as .slp to folder..." button is visible
- **AND** a "Save as .pkg.slp to folder..." button is visible
- **AND** both buttons appear above the upload/browse section
- **AND** a horizontal separator divides the save section from the rest

#### Scenario: Save buttons hidden when callables not provided
- **GIVEN** `SlpPathDialog` is constructed without `save_fn` and `convert_fn`
- **WHEN** the dialog opens
- **THEN** no save-to-folder buttons are shown
- **AND** dialog layout is unchanged from existing behaviour

#### Scenario: Save as .slp to folder
- **GIVEN** the user clicks "Save as .slp to folder..."
- **WHEN** a folder is selected via the system file dialog
- **THEN** `save_fn(output_path)` is called with `<chosen_dir>/<original_stem>.slp`
- **AND** a status label confirms the save location
- **AND** a hint reads "Now use Browse worker filesystem to locate this file on the worker."

#### Scenario: Save as .pkg.slp to folder
- **GIVEN** the user clicks "Save as .pkg.slp to folder..."
- **WHEN** a folder is selected via the system file dialog
- **THEN** `convert_fn(output_path)` is called with `<chosen_dir>/<original_stem>.pkg.slp`
- **AND** a status label confirms the save location
- **AND** a hint reads "Now use Browse worker filesystem to locate this file on the worker."

#### Scenario: Save dialog cancelled
- **GIVEN** the user clicks either save button
- **WHEN** the folder picker is dismissed without selecting
- **THEN** no file is written
- **AND** the dialog returns to its previous state unchanged

#### Scenario: Save error shown inline
- **GIVEN** the save callable raises an exception
- **WHEN** the save operation fails
- **THEN** an error message is shown in the status label in red
- **AND** the save button is re-enabled for retry

### Requirement: Save Callable Threading

`run_presubmission_checks` and `check_video_paths` SHALL accept a `save_fn`
parameter and thread it through to `SlpPathDialog`, following the same pattern
as the existing `convert_fn`.

#### Scenario: save_fn threaded from SLEAP dialog
- **GIVEN** SLEAP's `LearningDialog` supplies `save_fn=lambda p: labels.save(p)`
- **WHEN** `run_presubmission_checks` is called
- **THEN** `save_fn` reaches `SlpPathDialog` unchanged
- **AND** the save buttons are shown

#### Scenario: Existing callers unaffected
- **GIVEN** a caller that does not pass `save_fn`
- **WHEN** `run_presubmission_checks` is called
- **THEN** `save_fn` defaults to `None`
- **AND** no save buttons appear in the dialog
