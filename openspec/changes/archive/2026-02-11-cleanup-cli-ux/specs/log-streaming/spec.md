# log-streaming Specification Delta

## MODIFIED Requirements

### Requirement: Clean Training Log Display

Training logs streamed from worker SHALL be displayed without internal prefixes.

#### Scenario: Logs displayed without INFO prefix
- **WHEN** worker streams training output to client
- **AND** client displays logs in terminal
- **THEN** logs do NOT include `INFO:root:Client received:` prefix
- **AND** logs show only the actual message content

#### Scenario: Training progress displayed cleanly
- **WHEN** worker streams epoch progress (e.g., "Epoch 0: 42% | loss=0.003")
- **THEN** client displays progress without logging prefix
- **AND** progress updates are shown on same line when possible

## ADDED Requirements

### Requirement: Visual Structure for Training Output

Training output SHALL include visual structure to distinguish phases.

#### Scenario: Connection phase indication
- **WHEN** client begins connecting to worker
- **THEN** output shows "Connecting to worker {name}..."
- **AND** upon success, shows "✓ Connected" or similar indicator

#### Scenario: Training phase header
- **WHEN** training job starts executing
- **THEN** output shows section header (e.g., "Training {model_type} model")
- **AND** header is visually distinct from log content

#### Scenario: Visual separation between sections
- **WHEN** transitioning from connection to validation to training
- **THEN** output includes visual separators between sections
- **AND** separators are subtle (e.g., blank line or light horizontal rule)

### Requirement: Progress Bar Formatting

Training progress bars SHALL be formatted for terminal display.

#### Scenario: tqdm progress bar display
- **WHEN** worker streams tqdm-style progress output
- **THEN** client displays progress as formatted bar
- **AND** progress bar updates in place when terminal supports it
- **AND** metrics (loss, accuracy) are shown alongside progress

#### Scenario: Progress bar in non-TTY mode
- **WHEN** client output is not a TTY (e.g., piped to file)
- **THEN** progress updates are shown as separate lines
- **AND** each update shows current progress percentage and metrics

### Requirement: Setup Logs Display

Pre-training setup logs (model summary, sanity checking) SHALL be displayed in default mode.

#### Scenario: Model summary shown by default
- **WHEN** worker streams PyTorch Lightning model summary table
- **THEN** model summary table IS displayed in default mode
- **AND** table formatting is preserved
- **AND** parameter counts (Trainable params, etc.) are shown

#### Scenario: Sanity checking shown by default
- **WHEN** worker streams sanity checking DataLoader progress
- **THEN** sanity check output is displayed
- **AND** output streams as normal log lines (not in-place)

### Requirement: Progress Bar In-Place Updates

Epoch progress bars SHALL update in-place while setup logs stream normally.

#### Scenario: Switch to in-place mode on epoch start
- **WHEN** worker streams line matching `Epoch \d+:` pattern
- **THEN** client switches to in-place update mode for that line
- **AND** subsequent updates to same epoch overwrite previous line
- **AND** terminal cursor returns to start of line before each update

#### Scenario: New epoch starts new line
- **WHEN** epoch N completes and epoch N+1 starts
- **THEN** epoch N final state remains visible
- **AND** epoch N+1 progress starts on new line
- **AND** epoch N+1 updates in-place on its line

#### Scenario: Non-TTY output falls back to streaming
- **WHEN** client output is not a TTY (piped to file)
- **THEN** progress updates stream as separate lines
- **AND** no in-place updates are attempted
