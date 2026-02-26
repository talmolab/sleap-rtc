# Capability: Storage Backend

## Overview

The storage backend capability enables workers to serve jobs from any user by abstracting storage configuration into logical backend names. Workers configure base mount points; jobs specify which backend and user subdirectory to use.

---

## ADDED Requirements

### Requirement: Storage Backend Configuration

The system MUST support configuring multiple named storage backends via TOML configuration.

Each storage backend MUST have:
- `name`: Logical identifier (e.g., "vast", "gdrive", "scratch")
- `base_path`: Local filesystem path where the storage is mounted

Each storage backend MAY have:
- `type`: Storage type hint (e.g., "nfs", "local", "google_shared_drive")
- `description`: Human-readable description for logs and UI

#### Scenario: Configure single storage backend

**Given** a TOML configuration file with:
```toml
[storage.vast]
base_path = "/home/jovyan/vast"
```

**When** the configuration is loaded

**Then** the system has one storage backend named "vast" with base_path "/home/jovyan/vast"

#### Scenario: Configure multiple storage backends

**Given** a TOML configuration file with:
```toml
[storage.vast]
base_path = "/home/jovyan/vast"
type = "nfs"
description = "Institutional VAST storage"

[storage.scratch]
base_path = "/scratch"
type = "local"
description = "Fast local SSD"
```

**When** the configuration is loaded

**Then** the system has two storage backends: "vast" and "scratch"
**And** each has its respective base_path configured

#### Scenario: Missing base_path raises error

**Given** a TOML configuration file with:
```toml
[storage.incomplete]
type = "nfs"
```

**When** the configuration is loaded

**Then** a configuration error is raised indicating base_path is required

---

### Requirement: Backward Compatibility with SHARED_STORAGE_ROOT

The system MUST maintain backward compatibility with the existing `SHARED_STORAGE_ROOT` environment variable.

#### Scenario: Legacy environment variable creates default backend

**Given** the environment variable `SHARED_STORAGE_ROOT=/Volumes/talmo/amick` is set
**And** no `[storage.*]` sections exist in TOML configuration

**When** the configuration is loaded

**Then** a storage backend named "default" is created with base_path "/Volumes/talmo/amick"

#### Scenario: TOML config takes precedence over environment variable

**Given** the environment variable `SHARED_STORAGE_ROOT=/legacy/path` is set
**And** TOML configuration contains:
```toml
[storage.vast]
base_path = "/new/path"
```

**When** the configuration is loaded

**Then** the "vast" backend uses "/new/path"
**And** no "default" backend is created from the environment variable

---

### Requirement: Path Resolution

The system MUST resolve logical paths (backend + user_subdir + relative_path) to absolute local paths.

#### Scenario: Resolve path with all components

**Given** a storage backend "vast" with base_path "/home/jovyan/vast"

**When** resolving path with:
- backend_name: "vast"
- user_subdir: "amick"
- relative_path: "project/labels.slp"

**Then** the resolved path is "/home/jovyan/vast/amick/project/labels.slp"

#### Scenario: Resolve path with empty user_subdir

**Given** a storage backend "scratch" with base_path "/scratch"

**When** resolving path with:
- backend_name: "scratch"
- user_subdir: ""
- relative_path: "temp/data.zip"

**Then** the resolved path is "/scratch/temp/data.zip"

#### Scenario: Unknown backend raises error

**Given** configured backends are ["vast", "scratch"]

**When** resolving path with backend_name "gdrive"

**Then** a `StorageBackendNotFound` error is raised with message containing "gdrive"

---

### Requirement: Path Security Validation

The system MUST validate that resolved paths remain within the backend's base_path to prevent path traversal attacks.

#### Scenario: Valid path within base_path

**Given** a storage backend "vast" with base_path "/home/jovyan/vast"

**When** validating path "/home/jovyan/vast/amick/data.zip"

**Then** validation succeeds

#### Scenario: Path traversal attempt rejected

**Given** a storage backend "vast" with base_path "/home/jovyan/vast"

**When** resolving path with:
- backend_name: "vast"
- user_subdir: "../../../etc"
- relative_path: "passwd"

**Then** a `PathValidationError` is raised
**And** the error message indicates path escapes base directory

#### Scenario: Symlink traversal prevented

**Given** a storage backend "vast" with base_path "/home/jovyan/vast"
**And** a symlink at "/home/jovyan/vast/escape" pointing to "/etc"

**When** resolving and validating path with:
- backend_name: "vast"
- user_subdir: "escape"
- relative_path: "passwd"

**Then** a `PathValidationError` is raised after symlink resolution

---

### Requirement: Worker Storage Capability Advertisement

Workers MUST advertise their available storage backends when connecting to the signaling server.

#### Scenario: Worker announces storage backends

**Given** a worker with configured backends ["vast", "scratch"]

**When** the worker connects to the signaling server

**Then** the worker registration message includes:
```json
{
  "capabilities": {
    "storage_backends": ["vast", "scratch"]
  }
}
```

#### Scenario: Worker with no storage backends

**Given** a worker with no configured storage backends

**When** the worker connects to the signaling server

**Then** the worker registration message includes:
```json
{
  "capabilities": {
    "storage_backends": []
  }
}
```

---

### Requirement: Job Storage Specification

Job requests MUST support specifying storage backend and user subdirectory.

#### Scenario: Job request with storage specification

**Given** a client submitting a job

**When** the job uses shared storage

**Then** the job request includes:
```json
{
  "storage_backend": "vast",
  "user_subdir": "amick",
  "input_file": "project/labels.slp",
  "output_dir": "project/models"
}
```

#### Scenario: Job request without storage specification (legacy)

**Given** a client submitting a job without storage fields

**When** the worker receives the job

**Then** the worker uses legacy `SHARED_STORAGE_ROOT` behavior if configured
**Or** uses RTC transfer if no shared storage available

---

### Requirement: Storage Fallback to RTC Transfer

The system MUST fall back to RTC transfer when shared storage is unavailable.

#### Scenario: Worker lacks requested backend

**Given** a worker with configured backends ["scratch"]
**And** a job request with storage_backend "vast"

**When** the worker receives the job

**Then** the worker sends a `BACKEND_NOT_AVAILABLE` message
**And** the client falls back to RTC file transfer

#### Scenario: Path validation fails

**Given** a worker with configured backend "vast"
**And** a job request with non-existent path

**When** the worker attempts to access the path

**Then** the worker sends a `PATH_ERROR` message
**And** the client may fall back to RTC file transfer

---

## MODIFIED Requirements

### Requirement: SharedStorageConfig MUST Support Multiple Backends

The existing `SharedStorageConfig` class MUST be enhanced to support multiple named backends.

#### Scenario: get_shared_storage_root with backend parameter

**Given** configured backends including "vast" with base_path "/mnt/vast"

**When** calling `get_shared_storage_root(backend="vast")`

**Then** returns Path("/mnt/vast")

#### Scenario: has_shared_storage checks specific backend

**Given** configured backends ["vast", "scratch"]

**When** calling `has_shared_storage(backend="vast")`

**Then** returns True

**When** calling `has_shared_storage(backend="gdrive")`

**Then** returns False

---

## Related Capabilities

- **file-transfer**: Uses storage backend for shared filesystem transfer mode
- **worker**: Advertises storage capabilities, resolves paths for jobs
- **client**: Specifies storage backend in job requests
