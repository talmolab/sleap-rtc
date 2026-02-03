# CLI Migration Guide

This guide covers changes to the SLEAP-RTC CLI in the recent refactoring. Old commands continue to work with deprecation warnings, giving you time to update scripts.

## Command Renames

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `sleap-rtc client-train` | `sleap-rtc train` | Shorter, clearer |
| `sleap-rtc client-track` | `sleap-rtc track` | Shorter, clearer |
| `sleap-rtc client` | `sleap-rtc train` | Alias for client-train |
| `sleap-rtc browse` | `sleap-rtc test browse` | Moved to experimental |
| `sleap-rtc resolve-paths` | `sleap-rtc test resolve-paths` | Moved to experimental |

### Before
```bash
sleap-rtc client-train --room my-room --token abc123 --pkg-path package.zip
sleap-rtc client-track --room my-room --token abc123 --data-path data.slp --model-paths model.zip
```

### After
```bash
sleap-rtc train --room my-room --pkg-path package.zip
sleap-rtc track --room my-room --data-path data.slp --model-paths model.zip
```

## Authentication Changes

**JWT authentication is now the primary method.** Room tokens (`--token`) are optional and only needed for backward compatibility.

### Before
```bash
# Required: --token for room authentication
sleap-rtc client-train --room my-room --token abc123 --pkg-path package.zip
```

### After
```bash
# Step 1: Login once (stores JWT in ~/.sleap-rtc/credentials.json)
sleap-rtc login

# Step 2: Commands work without --token
sleap-rtc train --room my-room --pkg-path package.zip
```

If not logged in, commands will show a helpful error:
```
Error: Not logged in.

This command requires authentication. Please log in first:
  sleap-rtc login
```

## New Commands

### `sleap-rtc tui`
Interactive terminal UI for browsing workers and resolving paths.

```bash
sleap-rtc tui                          # Interactive mode
sleap-rtc tui --room my-room           # Connect directly to room
```

### `sleap-rtc status`
Check authentication status and stored credentials.

```bash
sleap-rtc status
```

### `sleap-rtc doctor`
Diagnose common issues with Python environment, network, and credentials.

```bash
sleap-rtc doctor
```

## Flag Changes

### Short Flags Added
| Long Flag | Short Flag |
|-----------|------------|
| `--room` | `-r` |
| `--token` | `-t` |
| `--worker-id` | `-w` |
| `--auto-select` | `-a` |
| `--pkg-path` | `-p` |
| `--data-path` | `-d` |
| `--model-paths` | `-m` |

### Example
```bash
# Old style
sleap-rtc train --room my-room --pkg-path package.zip --auto-select

# New style with short flags
sleap-rtc train -r my-room -p package.zip -a
```

### Underscore to Kebab-Case
Flags now use kebab-case consistently. Underscore versions still work.

| Old Flag | New Flag |
|----------|----------|
| `--pkg_path` | `--pkg-path` |
| `--data_path` | `--data-path` |
| `--model_paths` | `--model-paths` |
| `--session_string` | `--session-string` |
| `--room_id` | `--room` |

## Experimental Commands

Experimental features are now under `sleap-rtc test`:

```bash
# Browse worker filesystem
sleap-rtc test browse --room my-room

# Resolve video paths in SLP files
sleap-rtc test resolve-paths --room my-room --slp /path/to/file.slp
```

## Deprecation Timeline

- **Current**: Old commands work with deprecation warnings
- **Future**: Old commands may be removed in a major version

## Updating Scripts

### CI/CD Pipelines

```yaml
# Before
- run: sleap-rtc client-train --room $ROOM --token $TOKEN --pkg-path package.zip

# After (with service account JWT)
- run: sleap-rtc train --room $ROOM --pkg-path package.zip
```

### Shell Scripts

```bash
#!/bin/bash
# Before
sleap-rtc client-train --room-id "$ROOM" --token "$TOKEN" --pkg_path "$PKG"

# After
sleap-rtc login  # Run once, or use CI service account
sleap-rtc train --room "$ROOM" --pkg-path "$PKG"
```

## Help Reference

```bash
sleap-rtc --help              # Main help
sleap-rtc train --help        # Training command help
sleap-rtc track --help        # Tracking command help
sleap-rtc test --help         # Experimental commands
sleap-rtc status              # Auth status
sleap-rtc doctor              # Diagnose issues
```
