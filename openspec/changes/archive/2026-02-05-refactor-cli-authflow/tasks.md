## 1. CLI Framework Migration (rich-click)

- [ ] 1.1 Add rich-click dependency to pyproject.toml
- [ ] 1.2 Replace `import click` with `import rich_click as click` in cli.py
- [ ] 1.3 Configure rich-click styling (colors, help formatting)
- [ ] 1.4 Verify all existing commands render correctly with new styling

## 2. Command Renaming

- [ ] 2.1 Rename `client-train` command to `train`
  - [ ] 2.1.1 Update function name and decorator
  - [ ] 2.1.2 Add `client-train` as alias for backward compatibility
  - [ ] 2.1.3 Add deprecation warning when alias used
- [ ] 2.2 Rename `client-track` command to `track`
  - [ ] 2.2.1 Update function name and decorator
  - [ ] 2.2.2 Add `client-track` as alias for backward compatibility
  - [ ] 2.2.3 Add deprecation warning when alias used
- [ ] 2.3 Update all CLI help text to reflect new names

## 3. Test Subcommand (Experimental Features)

- [ ] 3.1 Create `test` command group
- [ ] 3.2 Move `--browse` functionality to `sleap-rtc test browse`
- [ ] 3.3 Move `--resolve-paths` functionality to `sleap-rtc test resolve-paths`
- [ ] 3.4 Add deprecation warnings when old flags used
- [ ] 3.5 Update help text to explain experimental nature

## 4. New Commands

- [ ] 4.1 Add `sleap-rtc tui` command
  - [ ] 4.1.1 Wire up to existing Textual TUI app
  - [ ] 4.1.2 Add options for room-id, room-secret
  - [ ] 4.1.3 Add help text explaining TUI features
- [ ] 4.2 TUI room-secret resolution
  - [ ] 4.2.1 Load room-secret from credentials when connecting to room
  - [ ] 4.2.2 Add input screen/modal to prompt for room-secret when missing
  - [ ] 4.2.3 Save room-secret to credentials after successful auth
  - [ ] 4.2.4 Display clear error when PSK auth fails with retry option
  - [ ] 4.2.5 Pass room-secret from app to bridge when connecting to worker
- [ ] 4.3 Add `sleap-rtc status` command
  - [ ] 4.3.1 Display current auth status (JWT validity, user info)
  - [ ] 4.3.2 Display any cached room-secrets
  - [ ] 4.3.3 Display credential file location
- [ ] 4.4 Add `sleap-rtc doctor` command
  - [ ] 4.4.1 Check Python environment
  - [ ] 4.4.2 Check network connectivity to signaling server
  - [ ] 4.4.3 Check credential file permissions
  - [ ] 4.4.4 Format output with rich-click styling

## 5. Flag Standardization

- [ ] 5.1 Rename `--token` to `--room-secret` across all commands
- [ ] 5.2 Add deprecation warning for `--token` usage
- [ ] 5.3 Add short flags:
  - [ ] 5.3.1 `-r` for `--room-id`
  - [ ] 5.3.2 `-s` for `--room-secret`
  - [ ] 5.3.3 `-w` for `--worker-id`
  - [ ] 5.3.4 `-f` for `--force`
  - [ ] 5.3.5 `-a` for `--auto-select`
- [ ] 5.4 Ensure all multi-word flags use kebab-case

## 6. Room-Secret Credential Persistence

- [ ] 6.1 Update credentials.py to store room-secrets
  - [ ] 6.1.1 Add `room_secrets: Dict[str, str]` field (room_id → secret)
  - [ ] 6.1.2 Add `get_room_secret(room_id)` method
  - [ ] 6.1.3 Add `save_room_secret(room_id, secret)` method
- [ ] 6.2 Modify commands to persist room-secret after first use
- [ ] 6.3 Modify commands to load saved room-secret when `--room-secret` not provided
- [ ] 6.4 Add room-secret to `status` command output

## 7. Authentication Flow Consolidation

- [ ] 7.1 Remove room token support from signaling client
- [ ] 7.2 Update all commands to use JWT + room-secret pattern
- [ ] 7.3 Add clear error messages when JWT expired/missing
- [ ] 7.4 Add prompts to run `sleap-rtc login` when credentials invalid

## 8. Interactive Selection Enhancement

- [ ] 8.1 Verify prompt_toolkit selectors work in all terminal types
- [ ] 8.2 Add fallback to numbered selection when terminal doesn't support ANSI
- [ ] 8.3 Improve selector styling to match rich-click theme

## 9. Testing & Documentation

- [ ] 9.1 Add tests for new commands (tui, status, doctor)
- [ ] 9.2 Add tests for command aliases and deprecation warnings
- [ ] 9.3 Update CLI documentation with new command structure
- [ ] 9.4 Add migration guide for existing users

## 10. Verification

- [ ] 10.1 Run full CLI test suite
- [ ] 10.2 Manual test: `sleap-rtc train` workflow
- [ ] 10.3 Manual test: `sleap-rtc track` workflow
- [ ] 10.4 Manual test: `sleap-rtc tui` command
- [ ] 10.5 Manual test: `sleap-rtc status` command
- [ ] 10.6 Manual test: `sleap-rtc doctor` command
- [ ] 10.7 Manual test: Deprecation warnings display correctly
