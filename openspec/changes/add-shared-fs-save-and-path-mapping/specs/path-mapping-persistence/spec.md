# path-mapping-persistence Specification

## ADDED Requirements

### Requirement: Path Mapping Storage in Config

`Config` SHALL support reading and writing directory prefix mappings to
`~/.sleap-rtc/config.toml` under a `[[path_mappings]]` table.

#### Scenario: Save a new mapping
- **GIVEN** no existing mapping for `/Users/amickl/repos/data`
- **WHEN** `config.save_path_mapping("/Users/amickl/repos/data", "/root/vast/amick/data")`
  is called
- **THEN** `~/.sleap-rtc/config.toml` gains:
  ```toml
  [[path_mappings]]
  local = "/Users/amickl/repos/data"
  worker = "/root/vast/amick/data"
  ```

#### Scenario: Duplicate mapping not written twice
- **GIVEN** an existing mapping `local="/Users/amickl/repos/data"` → `worker="/root/vast/amick/data"`
- **WHEN** `save_path_mapping` is called with the same values
- **THEN** no duplicate entry is added to the config file

#### Scenario: Remove an existing mapping
- **GIVEN** an existing mapping for local prefix `/Users/amickl/repos/data`
- **WHEN** `config.remove_path_mapping("/Users/amickl/repos/data", "/root/vast/amick/data")`
  is called
- **THEN** that entry is removed from `~/.sleap-rtc/config.toml`
- **AND** other mappings are preserved

#### Scenario: Read all mappings
- **GIVEN** `~/.sleap-rtc/config.toml` contains two `[[path_mappings]]` entries
- **WHEN** `config.get_path_mappings()` is called
- **THEN** a list of two `PathMapping` objects is returned
- **AND** each has `local` and `worker` string fields

---

### Requirement: Auto-fill Worker Path in SLP Path Resolution Dialog

When `SlpPathDialog` opens, it SHALL check saved path mappings and pre-populate
the worker path field if any saved `local` prefix matches the local file path.

#### Scenario: Matching prefix auto-fills worker path
- **GIVEN** saved mapping `local="/Users/amickl/repos/data"` → `worker="/root/vast/amick/data"`
- **AND** `SlpPathDialog` opens with `local_path="/Users/amickl/repos/data/labels.slp"`
- **WHEN** the dialog initialises
- **THEN** the worker path field is pre-filled with `/root/vast/amick/data/labels.slp`

#### Scenario: No matching prefix leaves field empty
- **GIVEN** no saved mapping matches the local path prefix
- **WHEN** the dialog initialises
- **THEN** the worker path field is empty (placeholder text shown)

#### Scenario: Longest matching prefix wins
- **GIVEN** two saved mappings:
  - `local="/Users/amickl"` → `worker="/root"`
  - `local="/Users/amickl/repos/data"` → `worker="/root/vast/amick/data"`
- **AND** `local_path="/Users/amickl/repos/data/labels.slp"`
- **WHEN** the dialog initialises
- **THEN** the more specific (longer) prefix is used for auto-fill

---

### Requirement: Save-Mapping Prompt on Continue

The system SHALL offer to save the directory prefix mapping after the user
presses Continue with a valid local→worker path pair in `SlpPathDialog`.

#### Scenario: Prompt shown when paths differ in prefix only
- **GIVEN** `local_path="/Users/amickl/repos/data/labels.slp"`
- **AND** user enters `worker_path="/root/vast/amick/data/labels.slp"`
- **WHEN** the user presses Continue
- **THEN** a prompt appears:
  "Save path mapping for future use?
   /Users/amickl/repos/data → /root/vast/amick/data"
  with **Save** and **Skip** buttons

#### Scenario: User saves the mapping
- **GIVEN** the save-mapping prompt is shown
- **WHEN** the user clicks Save
- **THEN** `config.save_path_mapping(local_dir, worker_dir)` is called
- **AND** the dialog closes normally

#### Scenario: User skips the mapping
- **GIVEN** the save-mapping prompt is shown
- **WHEN** the user clicks Skip
- **THEN** no mapping is saved
- **AND** the dialog closes normally

#### Scenario: Prompt not shown when mapping already exists
- **GIVEN** saved mapping already covers the local→worker prefix pair
- **WHEN** the user presses Continue
- **THEN** no save-mapping prompt is shown

---

### Requirement: Save-Mapping Prompt After Video Path Resolution

After `PathResolutionDialog` resolves video paths, the system SHALL offer to
save each new local→worker directory prefix mapping using the same prompt.

#### Scenario: Video resolution triggers mapping prompt
- **GIVEN** user resolves video `/root/vast/amick/videos/cam1.mp4`
  for local path `/Users/amickl/repos/data/videos/cam1.mp4`
- **WHEN** the user completes video resolution and presses Continue
- **THEN** the save-mapping prompt is shown for
  `/Users/amickl/repos/data/videos` → `/root/vast/amick/videos`

---

### Requirement: CLI Path Mapping Management

The CLI SHALL expose `sleap-rtc config add-path-mapping` and
`sleap-rtc config remove-path-mapping` subcommands for managing mappings
without opening the GUI.

#### Scenario: Add mapping via CLI
- **GIVEN** the user runs:
  `sleap-rtc config add-path-mapping --local /Users/amickl/repos/data --worker /root/vast/amick/data`
- **WHEN** the command executes
- **THEN** the mapping is appended to `~/.sleap-rtc/config.toml`
- **AND** a confirmation message is printed

#### Scenario: Remove mapping via CLI
- **GIVEN** the user runs:
  `sleap-rtc config remove-path-mapping --local /Users/amickl/repos/data --worker /root/vast/amick/data`
- **WHEN** the command executes
- **THEN** the matching entry is removed from `~/.sleap-rtc/config.toml`
- **AND** a confirmation message is printed

#### Scenario: Remove non-existent mapping
- **GIVEN** no matching mapping exists
- **WHEN** `remove-path-mapping` is run
- **THEN** a warning is printed indicating no match was found
- **AND** the config file is unchanged

#### Scenario: List mappings via CLI
- **GIVEN** two saved mappings
- **WHEN** the user runs `sleap-rtc config list-path-mappings`
- **THEN** both mappings are printed in `local → worker` format
