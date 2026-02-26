## Context

The sleap-rtc CLI has evolved organically with multiple authentication patterns and UI approaches:
- Room token (deprecated) - simple bearer token for room access
- JWT - GitHub OAuth-based authentication for signaling server
- Room-secret - PSK for P2P WebRTC connection security

Current issues:
- Command names (`client-train`, `client-track`) are verbose
- Mixed UI libraries without clear roles
- Experimental features (`--browse`, `--resolve-paths`) embedded in production commands
- Inconsistent flag naming conventions

## Goals / Non-Goals

**Goals:**
- Consolidate to JWT + room-secret authentication (deprecate room token)
- Establish clear UI library responsibilities
- Simplify command names while preserving backward compatibility hints
- Move experimental features to separate `test` subcommand

**Non-Goals:**
- Complete rewrite of CLI internals
- Migration to different CLI framework (staying with Click/rich-click)
- Breaking existing automation scripts without deprecation period

## Decisions

### Authentication Strategy
**Decision:** JWT for API access, room-secret for P2P PSK.
- JWT authenticates with signaling server (user identity, room permissions)
- Room-secret provides zero-trust P2P connection via PSK
- Room token is redundant and deprecated

**Rationale:** JWT already provides room access control. Room-secret adds P2P security layer. Room token served no additional purpose.

### Command Naming
**Decision:** Rename `client-train` → `train`, `client-track` → `track`.
- Shorter names improve DX
- Add aliases for backward compatibility during transition

**Alternatives considered:**
- Keep `client-*` prefix: Rejected - verbose without benefit
- Use subcommand groups: Considered for future (e.g., `sleap-rtc model train`)

### UI Library Strategy
**Decision:** Three-library approach with clear responsibilities:

| Library | Responsibility |
|---------|----------------|
| rich-click | CLI help formatting, styled output |
| prompt_toolkit | Interactive selections (worker, room) |
| Textual TUI | Full-screen file browsing |

**Rationale:**
- rich-click integrates naturally with Click
- prompt_toolkit provides rich inline selections without full-screen takeover
- Textual TUI for complex workflows needing persistent state

### Experimental Features
**Decision:** Move `--browse` and `--resolve-paths` to `sleap-rtc test` subcommand.

**Rationale:** These are development/debugging tools, not production workflows. Separating them clarifies CLI scope.

### Flag Conventions
**Decision:**
- Use `-f/--force` for confirmation bypass (not `-y/--yes`)
- All multi-word flags use kebab-case
- Common options get short flags

**Standard short flags:**
- `-r` → `--room-id`
- `-s` → `--room-secret`
- `-w` → `--worker-id`
- `-f` → `--force`
- `-a` → `--auto-select`

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Breaking existing scripts | Deprecation warnings for 2 versions, aliases for old names |
| User confusion with new names | Clear migration guide in docs |
| Room token deprecation | JWT already required, minimal impact |

## Migration Plan

### Phase 1: Add New (non-breaking)
- Add `train`/`track` as aliases to existing commands
- Add `test` subcommand with experimental features
- Add `tui`, `status`, `doctor` commands
- Add room-secret credential persistence

### Phase 2: Deprecation Warnings
- Add deprecation warnings to `client-train`/`client-track`
- Add deprecation warnings to `--token` flag
- Document migration in changelog

### Phase 3: Removal (future version)
- Remove `client-train`/`client-track` aliases
- Remove `--token` flag support
- Remove `--browse`/`--resolve-paths` from main commands

## Open Questions

None - all decisions resolved during brainstorming session.
