# Design: Hybrid Path Resolution System

## Context

SLEAP-RTC enables remote training where clients submit jobs to GPU workers. The current system requires users to manually place files in the worker's `input_path` directory. This creates friction because:

1. Users have data files scattered across their filesystem
2. Client and worker see the same physical storage at different mount points (e.g., `/Volumes/talmo/amick/` on macOS vs `/home/jovyan/vast/amick/` on worker)
3. Users must manually copy files or know exact worker paths

### Stakeholders
- **End Users**: Researchers running SLEAP training jobs
- **System Administrators**: Configure mount aliases for their environment
- **Developers**: Maintain the path resolution system

### Constraints
- Must work with existing WebRTC data channel communication
- Must maintain security (prevent path traversal attacks)
- Must handle environments where automatic resolution fails
- Should not break existing `--pkg_path` behavior

## Goals / Non-Goals

### Goals
1. Users provide paths as they normally would with SLEAP; system resolves automatically
2. Support configurable mount aliases for predictable path translation
3. Provide browser-based fallback when automatic resolution fails
4. Maintain backward compatibility with existing RTC transfer

### Non-Goals
1. Full filesystem access (security restriction via `allowed_roots`)
2. File upload through browser (only selection/navigation)
3. Real-time filesystem monitoring
4. Support for symbolic links that escape allowed roots

## Decisions

### D1: Three-Stage Resolution Strategy

**Decision**: Implement resolution in three stages with escalating user interaction:

```
Stage 1: Mount Alias Translation (instant, no network)
    ↓ (if no alias matches)
Stage 2: Filename Search via WebRTC (fast, requires worker query)
    ↓ (if ambiguous or not found)
Stage 3: Browser/CLI Selection (requires user interaction)
```

**Rationale**: This minimizes user friction for common cases while providing escape hatches for edge cases.

**Alternatives considered**:
- Single-stage browser selection: Too much friction for simple cases
- Worker-side resolution only: Can't access client filesystem info for better matching

### D2: Extend FileManager vs New Class

**Decision**: Extend existing `FileManager` class in `file_manager.py` rather than creating a separate `WorkerFileSystem` class.

**Rationale**:
- `FileManager` already handles file validation and has access to I/O config
- Avoids fragmentation of filesystem operations across classes
- Consistent with existing codebase patterns

**Methods to add**:
```python
class FileManager:
    def get_allowed_roots(self) -> list[dict]
    def list_directory(self, path: str, depth: int = 1) -> dict
    def search_file(self, filename: str, max_results: int = 20) -> list[dict]
    def resolve_path(self, client_path: str, aliases: list, size: int = None) -> dict
```

### D3: Message Protocol Extension

**Decision**: Follow existing `MSG_*` pattern in `protocol.py`:

```python
# New message types
MSG_FS_GET_ROOTS = "FS_GET_ROOTS"
MSG_FS_GET_ROOTS_RESPONSE = "FS_GET_ROOTS_RESPONSE"
MSG_FS_LIST = "FS_LIST"
MSG_FS_LIST_RESPONSE = "FS_LIST_RESPONSE"
MSG_FS_SEARCH = "FS_SEARCH"
MSG_FS_SEARCH_RESPONSE = "FS_SEARCH_RESPONSE"
MSG_FS_RESOLVE = "FS_RESOLVE"
MSG_FS_RESOLVE_RESPONSE = "FS_RESOLVE_RESPONSE"
MSG_FS_ERROR = "FS_ERROR"
```

**Rationale**: Consistent with existing patterns, easy to parse, supports existing `format_message`/`parse_message` helpers.

### D4: Browser Bridge Architecture

**Decision**: Use aiohttp for local HTTP server with WebSocket relay to worker.

```
┌─────────────┐        ┌──────────────────┐        ┌────────────┐
│   Browser   │◄──────►│  Browser Bridge  │◄──────►│   Worker   │
│  (localhost)│  HTTP/ │  (aiohttp @8765) │ WebRTC │ FileManager│
│             │   WS   │                  │        │            │
└─────────────┘        └──────────────────┘        └────────────┘
```

**Rationale**:
- aiohttp integrates well with asyncio (already used throughout codebase)
- Local HTTP server is simpler than embedding browser in CLI
- WebSocket relay reuses existing WebRTC data channel

**Alternatives considered**:
- Electron app: Too heavy for this use case
- Terminal UI (curses/textual): Harder to navigate complex filesystems
- Existing websockets library: aiohttp better suited for HTTP+WS hybrid

### D5: Configuration Schema

**Decision**: Extend `[worker.io]` section with mount aliases:

```toml
[worker.io]
allowed_roots = ["/home/jovyan/vast", "/scratch"]

[[worker.io.mounts]]
name = "lab_data"
worker_path = "/home/jovyan/vast/amick"
client_paths = ["/Volumes/talmo/amick", "/mnt/talmo/amick", "Z:\\talmo\\amick"]
description = "Talmo Lab shared storage"
```

**Rationale**:
- Extends existing config section rather than creating new top-level
- `allowed_roots` controls what worker exposes for browsing
- `mounts` array allows multiple alias mappings

### D6: Security Model

**Decision**: Implement defense-in-depth:

1. **Allowed Roots**: Worker only exposes directories under `allowed_roots`
2. **Path Validation**: Reject paths with `..` or that escape allowed roots
3. **Filename Sanitization**: Strip path separators from incoming filenames
4. **No File Content Access**: Browser can list/search but not read file contents

**Rationale**: Filesystem browsing is inherently risky; multiple layers prevent path traversal attacks.

## Risks / Trade-offs

### R1: aiohttp Dependency
**Risk**: New dependency adds to package size and potential security surface
**Mitigation**: aiohttp is well-maintained; browser bridge is optional (CLI fallback works without it)

### R2: Browser Security
**Risk**: Local HTTP server could be accessed by malicious websites
**Mitigation**:
- Bind only to 127.0.0.1 (localhost)
- Use random port if 8765 is taken
- Session tokens for WebSocket authentication

### R3: Resolution Ambiguity
**Risk**: Multiple files with same name could lead to wrong file selection
**Mitigation**:
- Rank candidates by file size match, path overlap, modification time
- Display candidates with confidence scores
- Require explicit selection when confidence < 90%

### R4: Performance with Large Filesystems
**Risk**: Searching large filesystems could be slow
**Mitigation**:
- Configurable search depth (`search_depth` config)
- Search timeout (`search_timeout` config)
- Return results incrementally (first N matches)

## Migration Plan

### Phase 1: Core Path Resolution (No Browser)
1. Add mount alias configuration to `config.py`
2. Extend `FileManager` with filesystem operations
3. Add message types to `protocol.py`
4. Create `path_resolver.py` for client-side orchestration
5. Add `--worker-path` CLI option

### Phase 2: Browser UI
1. Add aiohttp dependency
2. Create `browser_bridge.py` with HTTP server
3. Create browser UI HTML/JS
4. Add `--browse` CLI flag

### Phase 3: Integration
1. Insert path resolution into `client_class.py` flow
2. Update worker message routing
3. Add comprehensive tests

### Rollback
- All new functionality is additive
- Existing `--pkg_path` behavior unchanged
- Remove browser bridge without affecting core resolution

## Open Questions

1. **Q**: Should we cache filesystem listings to avoid repeated queries?
   **A**: Start without caching; add if performance becomes an issue.

2. **Q**: Should browser UI support file preview (e.g., show number of frames in .slp)?
   **A**: Out of scope for initial implementation; can add later.

3. **Q**: How to handle case where client path exists locally but not on worker?
   **A**: Show clear error message with suggested actions (copy file, check mount).
