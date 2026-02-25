# worker-io Specification

## Purpose
TBD - created by archiving change simplify-worker-io-paths. Update Purpose after archive.
## Requirements
### Requirement: Worker I/O Path Configuration
Workers MUST support configuration of input and output paths for shared filesystem access.

#### Scenario: Worker loads I/O paths from config file
- **Given** a worker with `sleap-rtc.toml` containing:
  ```toml
  [worker.io]
  input_path = "/mnt/shared/inputs"
  output_path = "/mnt/shared/outputs"
  filesystem = "vast"
  ```
- **When** the worker starts
- **Then** the worker loads the I/O configuration
- **And** validates that `input_path` exists and is readable
- **And** validates that `output_path` exists and is writable
- **And** logs the configured paths

#### Scenario: Worker starts without I/O config
- **Given** a worker with `sleap-rtc.toml` without `[worker.io]` section
- **When** the worker starts
- **Then** the worker starts successfully without I/O path configuration
- **And** falls back to RTC transfer for file handling

#### Scenario: Worker fails on invalid input path
- **Given** a worker with `input_path = "/nonexistent/path"`
- **When** the worker starts
- **Then** the worker logs an error about inaccessible input path
- **And** continues startup without I/O path configuration (fallback mode)

---

### Requirement: Worker I/O Path Advertisement
Workers MUST advertise their I/O paths in registration metadata so clients can display them.

#### Scenario: Worker includes I/O paths in registration
- **Given** a worker with valid I/O path configuration
- **When** the worker registers with the signaling server
- **Then** the registration metadata includes:
  ```json
  {
    "io_paths": {
      "input": "/mnt/shared/inputs",
      "output": "/mnt/shared/outputs",
      "filesystem": "vast"
    }
  }
  ```

#### Scenario: Worker registers without I/O paths when not configured
- **Given** a worker without I/O path configuration
- **When** the worker registers with the signaling server
- **Then** the registration metadata does NOT include `io_paths`

---

### Requirement: Input File Validation
Workers MUST validate that input files exist in the configured input path before starting jobs.

#### Scenario: Worker validates existing input file
- **Given** a worker with `input_path = "/mnt/shared/inputs"`
- **And** a file exists at `/mnt/shared/inputs/training.zip`
- **When** the worker receives message `INPUT_FILE::training.zip`
- **Then** the worker resolves the full path: `/mnt/shared/inputs/training.zip`
- **And** verifies the file exists and is readable
- **And** responds with `FILE_EXISTS::training.zip`

#### Scenario: Worker rejects missing input file
- **Given** a worker with `input_path = "/mnt/shared/inputs"`
- **And** NO file exists at `/mnt/shared/inputs/missing.zip`
- **When** the worker receives message `INPUT_FILE::missing.zip`
- **Then** the worker responds with `FILE_NOT_FOUND::missing.zip::File does not exist`

#### Scenario: Worker prevents path traversal attacks
- **Given** a worker with `input_path = "/mnt/shared/inputs"`
- **When** the worker receives message `INPUT_FILE::../../../etc/passwd`
- **Then** the worker rejects the request
- **And** responds with `FILE_NOT_FOUND::../../../etc/passwd::Invalid filename`

---

### Requirement: Job Output Directory
Workers MUST write job outputs to the configured output path with proper directory structure.

#### Scenario: Worker creates job output directory
- **Given** a worker with `output_path = "/mnt/shared/outputs"`
- **When** a job with ID `job_abc123` starts
- **Then** the worker creates directory `/mnt/shared/outputs/jobs/job_abc123/`
- **And** creates subdirectory `models/` for trained models
- **And** creates subdirectory `logs/` for training logs

#### Scenario: Worker reports output location on completion
- **Given** a worker running job `job_abc123`
- **And** `output_path = "/mnt/shared/outputs"`
- **When** the job completes successfully
- **Then** the worker sends `JOB_OUTPUT::job_abc123::/mnt/shared/outputs/jobs/job_abc123`

---

### Requirement: Client I/O Path Display
Clients MUST display worker I/O paths when listing available workers.

#### Scenario: Client shows I/O paths in worker selection
- **Given** a client discovering workers in a room
- **And** worker "worker-abc" has I/O paths configured
- **When** the client displays the worker list
- **Then** the display includes:
  ```
  1. worker-abc
     GPU: NVIDIA A100 (40GB)
     Filesystem: vast
     Input:  /mnt/shared/inputs
     Output: /mnt/shared/outputs
  ```

#### Scenario: Client indicates workers without I/O paths
- **Given** a client discovering workers in a room
- **And** worker "worker-xyz" has NO I/O paths configured
- **When** the client displays the worker list
- **Then** the display indicates RTC transfer will be used:
  ```
  2. worker-xyz
     GPU: NVIDIA RTX 4090 (24GB)
     Transfer: RTC (no shared filesystem)
  ```

---

### Requirement: Client Job Submission with I/O Paths
Clients MUST send only the filename when the selected worker has I/O paths configured.

#### Scenario: Client sends filename to I/O-enabled worker
- **Given** a client connected to a worker with I/O paths
- **And** user specified `--pkg_path training.zip`
- **When** the client submits the job
- **Then** the client sends `INPUT_FILE::training.zip`
- **And** waits for `FILE_EXISTS` or `FILE_NOT_FOUND` response

#### Scenario: Client falls back to RTC transfer
- **Given** a client connected to a worker WITHOUT I/O paths
- **And** user specified `--pkg_path /local/path/training.zip`
- **When** the client submits the job
- **Then** the client transfers the file via RTC chunked transfer
- **And** uses existing `FILE_META::` and chunk protocol

#### Scenario: Client handles file not found
- **Given** a client connected to a worker with I/O paths
- **And** worker responds with `FILE_NOT_FOUND::training.zip::File does not exist`
- **When** the client receives this response
- **Then** the client displays error: "File 'training.zip' not found in worker input path"
- **And** suggests: "Please copy your file to: /mnt/shared/inputs/"

