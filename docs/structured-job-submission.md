# Structured Job Submission

This document describes the structured job submission system for SLEAP-RTC, which provides a cleaner, more maintainable way to submit training and inference jobs to remote workers.

## Overview

The structured job submission system replaces the legacy file-transfer-based workflow with a configuration-based approach that:

- Uses sleap-nn config YAML files directly on the worker filesystem
- Validates job specifications before execution
- Provides clear error messages for path and parameter issues
- Supports interactive path correction when paths are invalid
- Streams job progress and output in real-time

## Training Workflow

### Basic Usage

```bash
# Login first (required for room-based discovery)
sleap-rtc login

# Submit a training job with a config file
sleap-rtc train --room my-room --config /vast/project/centroid.yaml
```

### With Overrides

You can override specific config values without modifying the YAML file:

```bash
sleap-rtc train --room my-room \
    --config /vast/project/centroid.yaml \
    --labels /vast/data/labels.slp \
    --val-labels /vast/data/val_labels.slp \
    --max-epochs 100 \
    --batch-size 8 \
    --learning-rate 0.0001 \
    --run-name "experiment-1"
```

### Available Options

| Option | Description |
|--------|-------------|
| `--config`, `-c` | Path to sleap-nn config YAML file on worker filesystem |
| `--labels` | Override training labels path (`data_config.train_labels_path`) |
| `--val-labels` | Override validation labels path (`data_config.val_labels_path`) |
| `--max-epochs` | Maximum training epochs (`trainer_config.max_epochs`) |
| `--batch-size` | Batch size for training and validation |
| `--learning-rate` | Learning rate for optimizer |
| `--run-name` | Name for the training run (used in checkpoint directory) |
| `--resume` | Path to checkpoint for resuming training |

### Worker Selection

```bash
# Auto-select best worker by GPU memory
sleap-rtc train --room my-room --auto-select --config /vast/project/config.yaml

# Filter by minimum GPU memory
sleap-rtc train --room my-room --auto-select --min-gpu-memory 8000 \
    --config /vast/project/config.yaml

# Connect to specific worker
sleap-rtc train --room my-room --worker-id worker-abc123 \
    --config /vast/project/config.yaml
```

## Inference/Tracking Workflow

### Basic Usage

```bash
sleap-rtc track --room my-room \
    --data-path /vast/data/labels.slp \
    --model-paths /vast/models/centroid
```

### Multi-Model Pipeline

For top-down or multi-stage pipelines, specify multiple model paths:

```bash
sleap-rtc track --room my-room \
    --data-path /vast/data/labels.slp \
    --model-paths /vast/models/centroid \
    --model-paths /vast/models/centered_instance \
    --output /vast/output/predictions.slp
```

### Available Options

| Option | Description |
|--------|-------------|
| `--data-path`, `-d` | Path to .slp file on worker filesystem (required) |
| `--model-paths`, `-m` | Paths to trained model directories (required, can specify multiple) |
| `--output`, `-o` | Output predictions filename (default: `predictions.slp`) |
| `--batch-size` | Batch size for inference |
| `--peak-threshold` | Peak detection threshold (0.0-1.0) |
| `--only-suggested-frames` | Only run inference on suggested frames |
| `--frames` | Frame range string (e.g., `"0-100"` or `"0-100,500-600"`) |

### Examples

```bash
# Inference with custom batch size and threshold
sleap-rtc track --room my-room \
    --data-path /vast/data/labels.slp \
    --model-paths /vast/models/topdown \
    --batch-size 16 \
    --peak-threshold 0.3

# Process only specific frame ranges
sleap-rtc track --room my-room \
    --data-path /vast/data/labels.slp \
    --model-paths /vast/models/centroid \
    --frames "0-100,500-600"

# Process only suggested frames
sleap-rtc track --room my-room \
    --data-path /vast/data/labels.slp \
    --model-paths /vast/models/centroid \
    --only-suggested-frames
```

## Path Correction

When a job is rejected due to invalid paths, the CLI offers interactive path correction:

1. The error message shows which path is invalid
2. You're prompted to browse the worker filesystem
3. An interactive browser lets you navigate and select the correct file
4. The job is automatically resubmitted with the corrected path

```
Job rejected by worker:
  - config_path: Path not found: /vast/wrong/path.yaml

Path error detected for 'config_path': /vast/wrong/path.yaml
Would you like to browse the worker filesystem to find the correct path?
[y/N]: y

Select correct path for 'config_path':
Path: /vast/project

  📁 configs/
  📁 data/
  📄 centroid.yaml  (2.3 KB)
  📄 topdown.yaml  (2.1 KB)

[↑/↓] Navigate  [Enter] Select  [←/Backspace] Back  [Esc] Cancel
Filter: *.yaml
```

## Migration from pkg-path

The `--pkg-path` option is deprecated. Here's how to migrate:

### Before (deprecated)

```bash
sleap-rtc train --room my-room --pkg-path /local/path/to/training_package.zip
```

### After (recommended)

```bash
sleap-rtc train --room my-room \
    --config /vast/project/centroid.yaml \
    --labels /vast/data/labels.slp
```

### Key Differences

| Aspect | pkg-path (deprecated) | config (recommended) |
|--------|----------------------|---------------------|
| Files | Transfers zip package | Uses files on worker |
| Config | Embedded in package | Separate YAML file |
| Labels | Embedded in package | Specified via `--labels` |
| Flexibility | Fixed at package creation | Override any parameter |
| Path validation | After transfer | Before execution |

### Migration Steps

1. **Identify your config file**: The training package contains a config YAML. Copy this to shared storage accessible by workers.

2. **Identify your labels file**: The package contains your labels .slp file. Ensure this is on shared storage.

3. **Update your command**:
   ```bash
   # Old
   sleap-rtc train --room my-room --pkg-path ./package.zip

   # New
   sleap-rtc train --room my-room \
       --config /shared/project/config.yaml \
       --labels /shared/data/labels.slp
   ```

4. **Test with a short run**: Use `--max-epochs 1` to verify the setup before full training.

## Job Protocol

The structured job submission uses a message-based protocol:

1. **JOB_SUBMIT**: Client sends job specification (JSON)
2. **JOB_ACCEPTED**: Worker validates spec and accepts job
3. **JOB_REJECTED**: Worker rejects job with error details
4. **JOB_PROGRESS**: Worker streams execution output
5. **JOB_COMPLETE**: Job finished successfully
6. **JOB_FAILED**: Job failed during execution

This protocol provides:
- Early validation before execution
- Detailed error messages
- Real-time progress streaming
- Clear success/failure indication

## Troubleshooting

### "Path not found" errors

Ensure paths exist on the worker filesystem. Use shared storage (e.g., `/vast`) that's accessible to all workers.

### "Access denied" errors

The path may be outside the worker's configured mounts. Check with your administrator which paths are allowed.

### Job timeout

Long-running jobs have a 10-minute timeout for responses. For very long training jobs, ensure the worker is sending progress updates.

### Connection issues

1. Verify you're logged in: `sleap-rtc login`
2. Check room exists: `sleap-rtc rooms list`
3. Verify workers are online: `sleap-rtc rooms workers --room my-room`
