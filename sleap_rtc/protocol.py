"""Message protocol definitions for SLEAP-RTC.

This module defines the message types and protocol used for communication between
Client and Worker peers over WebRTC data channels.

Message Protocol Overview
-------------------------

SLEAP-RTC uses two transfer methods:

1. **RTC Transfer** (original): Sends files as chunked binary data over WebRTC
2. **Worker I/O Paths** (recommended): Worker has configured input/output paths;
   client sends just the filename, worker reads from its input directory

Transfer Method Selection
-------------------------

The Client automatically selects the transfer method:
- If Worker has I/O paths configured: Use Worker I/O Paths transfer
- Otherwise: Use RTC transfer (backward compatible)

Message Types
-------------

### Worker I/O Paths Messages

These messages are used when Worker has I/O paths configured (input_path, output_path).

**JOB_ID::{job_id}**
    Sent by: Client
    Purpose: Identifies a unique job for file transfer tracking
    Format: "JOB_ID::job_abc123"
    Example: "JOB_ID::job_f3a8b2c1"

**INPUT_FILE::{filename}**
    Sent by: Client
    Purpose: Tells Worker which file to use from its input directory
    Format: "INPUT_FILE::{filename}"
    Example: "INPUT_FILE::my_training.pkg.slp"
    Note: Just the filename, not a path. Worker resolves to {input_path}/{filename}

**FILE_EXISTS::{filename}**
    Sent by: Worker
    Purpose: Confirms the file exists and is readable in worker's input directory
    Format: "FILE_EXISTS::{filename}"
    Example: "FILE_EXISTS::my_training.pkg.slp"

**FILE_NOT_FOUND::{filename}::{reason}**
    Sent by: Worker
    Purpose: Reports that the file was not found or is not accessible
    Format: "FILE_NOT_FOUND::{filename}::{reason}"
    Example: "FILE_NOT_FOUND::missing.slp::File does not exist"

**JOB_OUTPUT_PATH::{path}**
    Sent by: Worker
    Purpose: Tells Client where job outputs will be written
    Format: "JOB_OUTPUT_PATH::{path}"
    Example: "JOB_OUTPUT_PATH::/mnt/shared/outputs/jobs/job_f3a8b2c1"

### RTC Transfer Messages (Original Protocol)

These messages are used for backward compatibility when shared storage is unavailable.

**FILE_META::{filename}::{file_size}::{chunk_count}**
    Sent by: Client or Worker
    Purpose: Announces an incoming file transfer
    Format: "FILE_META::{name}::{bytes}::{chunks}"
    Example: "FILE_META::training.zip::5368709120::163840"

**CHUNK::{chunk_index}::{chunk_data_base64}**
    Sent by: Client or Worker
    Purpose: Sends a chunk of file data
    Format: Binary message with chunk index and data

**FILE_COMPLETE::{filename}**
    Sent by: Client or Worker
    Purpose: Signals all chunks received, file is complete
    Format: "FILE_COMPLETE::{name}"
    Example: "FILE_COMPLETE::training.zip"

**TRANSFER_PROGRESS::{percent}**
    Sent by: Client or Worker
    Purpose: Reports file transfer progress
    Format: "TRANSFER_PROGRESS::{0-100}"
    Example: "TRANSFER_PROGRESS::47.3"

### Control Messages (Common to Both Protocols)

**READY**
    Sent by: Worker
    Purpose: Worker is ready to receive tasks
    Format: "READY"

**TRAINING_COMPLETE** / **INFERENCE_COMPLETE**
    Sent by: Worker
    Purpose: Job processing finished successfully
    Format: "TRAINING_COMPLETE" or "INFERENCE_COMPLETE"

**ERROR::{error_message}**
    Sent by: Either peer
    Purpose: Reports an error condition
    Format: "ERROR::{description}"
    Example: "ERROR::Model loading failed: missing checkpoint"

Message Flow Examples
---------------------

### Worker I/O Paths Transfer Flow

1. Client → Worker: JOB_ID::job_abc123
2. Client → Worker: INPUT_FILE::my_training.pkg.slp
3. Worker → Client: FILE_EXISTS::my_training.pkg.slp
4. Worker → Client: JOB_OUTPUT_PATH::/mnt/shared/outputs/jobs/job_abc123
5. Worker processes job (reads from input_path, writes to output_path/jobs/{job_id}/)
6. Worker → Client: TRAINING_COMPLETE

### RTC Transfer Flow (Fallback)

1. Client → Worker: FILE_META::training.zip::5368709120::163840
2. Client → Worker: CHUNK::0::{base64_data}
3. Client → Worker: CHUNK::1::{base64_data}
   ... (repeat for all chunks)
4. Client → Worker: FILE_COMPLETE::training.zip
5. Worker processes job
6. Worker → Client: TRAINING_COMPLETE
7. Worker → Client: FILE_META::results.zip::1024000::32
8. Worker → Client: (chunks...)
9. Worker → Client: FILE_COMPLETE::results.zip

Security Considerations
-----------------------

**Filename Validation (Worker I/O Paths):**
All filenames received from clients MUST be validated:
1. Reject filenames containing path separators (/, \\)
2. Reject parent directory references (..)
3. Resolve the full path: input_path / filename
4. Verify resolved path is within input_path (prevent traversal attacks)
5. Check file exists and is readable

**Example Attack Prevention:**
Bad input: "../../../etc/passwd"
Result: FILE_NOT_FOUND::../../../etc/passwd::Invalid filename (contains path separator)

**Recommended Implementation:**
```python
import os
filename = received_filename

# Reject path traversal attempts
if os.sep in filename or (os.altsep and os.altsep in filename) or ".." in filename:
    send(FILE_NOT_FOUND, filename, "Invalid filename")
    return

# Resolve full path
full_path = input_path / filename
if not full_path.exists():
    send(FILE_NOT_FOUND, filename, "File does not exist")
    return

send(FILE_EXISTS, filename)
```
"""

# Worker I/O Paths Message Types (COMMENTED OUT - reserved for future use)
# These constants were part of the Worker I/O Paths feature which has been removed.
# They are kept here for reference in case they're needed for debugging or future implementation.
# MSG_JOB_ID = "JOB_ID"
# MSG_INPUT_FILE = "INPUT_FILE"
# MSG_FILE_EXISTS = "FILE_EXISTS"
# MSG_FILE_NOT_FOUND = "FILE_NOT_FOUND"
# MSG_JOB_OUTPUT_PATH = "JOB_OUTPUT_PATH"

# RTC Transfer Message Types
MSG_FILE_META = "FILE_META"
MSG_CHUNK = "CHUNK"
MSG_FILE_COMPLETE = "FILE_COMPLETE"
MSG_TRANSFER_PROGRESS = "TRANSFER_PROGRESS"

# Control Message Types
MSG_READY = "READY"
MSG_TRAINING_COMPLETE = "TRAINING_COMPLETE"
MSG_INFERENCE_COMPLETE = "INFERENCE_COMPLETE"
MSG_ERROR = "ERROR"

# =============================================================================
# Filesystem Browser Message Types
# =============================================================================
#
# These messages enable Clients to browse and resolve file paths on Worker
# filesystems. All operations are read-only and restricted to configured mounts.
#
# Message Flows:
#
# 1. Get Worker Info (for browser status display):
#    Client → Worker: FS_GET_INFO
#    Worker → Client: FS_INFO_RESPONSE::{json}
#    Response: {"worker_id": "...", "working_dir": "...", "mounts": [...]}
#
# 2. Get Available Mounts:
#    Client → Worker: FS_GET_MOUNTS
#    Worker → Client: FS_MOUNTS_RESPONSE::{json}
#    Response: [{"path": "/mnt/data", "label": "Lab Data"}, ...]
#
# 3. Resolve File Path (fuzzy/wildcard matching):
#    Client → Worker: FS_RESOLVE::{pattern}::{file_size}::{max_depth}
#    Worker → Client: FS_RESOLVE_RESPONSE::{json}
#    Response: {"candidates": [...], "truncated": false, "timeout": false}
#
# 4. List Directory Contents:
#    Client → Worker: FS_LIST_DIR::{path}::{offset}
#    Worker → Client: FS_LIST_RESPONSE::{json}
#    Response: {"path": "...", "entries": [...], "total_count": N, "has_more": bool}
#
# 5. Error Response:
#    Worker → Client: FS_ERROR::{error_code}::{message}
#    Error codes: ACCESS_DENIED, PATTERN_TOO_BROAD, PATH_NOT_FOUND
#

# Filesystem info messages
MSG_FS_GET_INFO = "FS_GET_INFO"
MSG_FS_INFO_RESPONSE = "FS_INFO_RESPONSE"

# Mount discovery messages
MSG_FS_GET_MOUNTS = "FS_GET_MOUNTS"
MSG_FS_MOUNTS_RESPONSE = "FS_MOUNTS_RESPONSE"

# Path resolution messages (fuzzy/wildcard matching)
MSG_FS_RESOLVE = "FS_RESOLVE"
MSG_FS_RESOLVE_RESPONSE = "FS_RESOLVE_RESPONSE"

# Directory listing messages
MSG_FS_LIST_DIR = "FS_LIST_DIR"
MSG_FS_LIST_RESPONSE = "FS_LIST_RESPONSE"

# Filesystem error message
MSG_FS_ERROR = "FS_ERROR"

# Filesystem error codes
FS_ERROR_ACCESS_DENIED = "ACCESS_DENIED"
FS_ERROR_PATTERN_TOO_BROAD = "PATTERN_TOO_BROAD"
FS_ERROR_PATH_NOT_FOUND = "PATH_NOT_FOUND"
FS_ERROR_INVALID_REQUEST = "INVALID_REQUEST"

# =============================================================================
# Worker Path Messages
# =============================================================================
#
# These messages enable Clients to tell Workers to use a resolved path directly
# (without file transfer over RTC).
#
# Message Flow:
#
# 1. Client resolves path using FS_RESOLVE or uses --worker-path flag
# 2. Client → Worker: USE_WORKER_PATH::{resolved_path}
# 3. Worker validates the path exists and is accessible within mounts
# 4. Worker → Client: WORKER_PATH_OK::{resolved_path}
#    or: WORKER_PATH_ERROR::{error_message}
# 5. Worker proceeds to process the file from that path
#

# Worker path messages
MSG_USE_WORKER_PATH = "USE_WORKER_PATH"
MSG_WORKER_PATH_OK = "WORKER_PATH_OK"
MSG_WORKER_PATH_ERROR = "WORKER_PATH_ERROR"

# =============================================================================
# SLP Video Resolution Messages
# =============================================================================
#
# These messages enable automatic detection and resolution of missing video
# paths in SLP files. When a Worker loads an SLP file, it checks if the video
# paths are accessible. If not, the Client can use these messages to resolve
# the paths interactively.
#
# Message Flows:
#
# 1. Check Video Accessibility (triggered after WORKER_PATH_OK for .slp files):
#    Worker → Client: FS_CHECK_VIDEOS_RESPONSE::{json}
#    Response: {
#      "slp_path": "/mnt/vast/project/labels.slp",
#      "total_videos": 5,
#      "missing": [
#        {"filename": "video1.mp4", "original_path": "/Users/.../video1.mp4"},
#        {"filename": "video2.mp4", "original_path": "/Users/.../video2.mp4"}
#      ],
#      "accessible": 3
#    }
#
# 2. Scan Directory for Filenames (SLP Viewer style resolution):
#    Client → Worker: FS_SCAN_DIR::{json}
#    Request: {"directory": "/mnt/vast/project/", "filenames": ["video2.mp4", "video3.mp4"]}
#    Worker → Client: FS_SCAN_DIR_RESPONSE::{json}
#    Response: {
#      "directory": "/mnt/vast/project/",
#      "found": {"video2.mp4": "/mnt/vast/project/video2.mp4", "video3.mp4": null}
#    }
#
# 3. Write Corrected SLP File:
#    Client → Worker: FS_WRITE_SLP::{json}
#    Request: {
#      "slp_path": "/mnt/vast/project/labels.slp",
#      "output_dir": "/mnt/vast/project/",
#      "filename_map": {"/old/video1.mp4": "/new/video1.mp4", ...}
#    }
#    Worker → Client: FS_WRITE_SLP_OK::{json}
#    Response: {"output_path": "/mnt/.../resolved_20260113_labels.slp", "videos_updated": 2}
#    Or on error:
#    Worker → Client: FS_WRITE_SLP_ERROR::{json}
#    Response: {"error": "Permission denied writing to /mnt/vast/project/"}
#

# Video accessibility check (Worker sends after loading SLP)
MSG_FS_CHECK_VIDEOS_RESPONSE = "FS_CHECK_VIDEOS_RESPONSE"

# Directory scanning for filenames (SLP Viewer style)
MSG_FS_SCAN_DIR = "FS_SCAN_DIR"
MSG_FS_SCAN_DIR_RESPONSE = "FS_SCAN_DIR_RESPONSE"

# SLP file writing with corrected video paths
MSG_FS_WRITE_SLP = "FS_WRITE_SLP"
MSG_FS_WRITE_SLP_OK = "FS_WRITE_SLP_OK"
MSG_FS_WRITE_SLP_ERROR = "FS_WRITE_SLP_ERROR"

# Message separators
MSG_SEPARATOR = "::"


def format_message(msg_type: str, *args) -> str:
    """Format a protocol message with type and arguments.

    Args:
        msg_type: The message type constant (e.g., MSG_JOB_ID).
        *args: Message arguments to append.

    Returns:
        Formatted message string.

    Examples:
        >>> format_message(MSG_JOB_ID, "job_abc123")
        'JOB_ID::job_abc123'

        >>> format_message(MSG_INPUT_FILE, "my_training.pkg.slp")
        'INPUT_FILE::my_training.pkg.slp'

        >>> format_message(MSG_FILE_EXISTS, "my_training.pkg.slp")
        'FILE_EXISTS::my_training.pkg.slp'
    """
    if args:
        return (
            f"{msg_type}{MSG_SEPARATOR}{MSG_SEPARATOR.join(str(arg) for arg in args)}"
        )
    return msg_type


def parse_message(message: str) -> tuple[str, list[str]]:
    """Parse a protocol message into type and arguments.

    Args:
        message: The message string to parse.

    Returns:
        Tuple of (message_type, arguments_list).

    Examples:
        >>> parse_message("JOB_ID::job_abc123")
        ('JOB_ID', ['job_abc123'])

        >>> parse_message("FILE_EXISTS::my_training.pkg.slp")
        ('FILE_EXISTS', ['my_training.pkg.slp'])

        >>> parse_message("READY")
        ('READY', [])
    """
    parts = message.split(MSG_SEPARATOR, 1)
    msg_type = parts[0]
    args = parts[1].split(MSG_SEPARATOR) if len(parts) > 1 else []
    return msg_type, args
