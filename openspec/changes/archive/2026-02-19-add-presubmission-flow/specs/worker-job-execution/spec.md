## MODIFIED Requirements

### Requirement: Training Job Execution

The Worker SHALL execute training jobs from submitted specs, supporting both file-path configs and inline config content.

#### Scenario: Execute job with config_content

- **WHEN** Worker receives JOB_SUBMIT with a TrainJobSpec containing config_content
- **THEN** Worker writes config_content to a temporary YAML file in the working directory
- **AND** Worker sets config_paths to [temp_file_path]
- **AND** Worker proceeds with validation and execution using the temp file
- **AND** Worker cleans up the temp file after job completes or fails

#### Scenario: Execute job with config_paths (existing behavior)

- **WHEN** Worker receives JOB_SUBMIT with a TrainJobSpec containing config_paths
- **AND** config_content is not set
- **THEN** Worker uses config_paths directly for validation and execution

#### Scenario: Temp file cleanup on failure

- **WHEN** Worker writes config_content to a temp file
- **AND** validation or execution raises an exception
- **THEN** the temp file is deleted in the finally block
- **AND** the exception is propagated normally

#### Scenario: Job with path_mappings

- **WHEN** Worker receives JOB_SUBMIT with path_mappings
- **THEN** Worker logs the path mappings for debugging
- **AND** Worker uses the spec's labels_path (already resolved to worker path) directly

### Requirement: Log Streaming via RTC Data Channel

The Worker SHALL stream training logs to the Client over the RTC data channel in real time.

#### Scenario: Stream training progress

- **WHEN** training is running with gui=True
- **THEN** Worker forwards sleap-nn ZMQ progress messages over the data channel
- **AND** messages include epoch, loss values, and learning rate

#### Scenario: Report training completion

- **WHEN** training completes successfully
- **THEN** Worker sends JOB_COMPLETE with result summary
- **AND** includes final model checkpoint path
