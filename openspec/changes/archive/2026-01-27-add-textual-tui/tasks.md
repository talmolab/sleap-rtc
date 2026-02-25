## 1. Foundation

- [ ] 1.1 Add `textual` dependency to pyproject.toml
- [ ] 1.2 Create `sleap_rtc/tui/` module structure
- [ ] 1.3 Implement `WebRTCBridge` class to wrap existing `BrowseClient` for async message passing
- [ ] 1.4 Create basic `TUIApp` with placeholder screen

## 2. Login & Room Selection Flow

- [ ] 2.1 Implement `LoginScreen` that displays dashboard login URL
- [ ] 2.2 Add JWT polling logic (reuse from `sleap_rtc/auth/github.py`)
- [ ] 2.3 Show countdown timer and "Waiting for login..." status
- [ ] 2.4 Implement `RoomSelectScreen` with list of user's rooms
- [ ] 2.5 Fetch rooms via `/api/auth/rooms` endpoint (reuse from `room list` command)
- [ ] 2.6 Display room info: name, role (owner/member), worker count
- [ ] 2.7 Handle room selection → transition to BrowserScreen
- [ ] 2.8 Skip login/room screens if `--room --token` flags provided (direct mode)

## 3. Miller Columns Widget

- [ ] 3.1 Implement `MillerColumns` widget with keyboard navigation (arrow keys, enter)
- [ ] 3.2 Add directory listing via `FS_LIST_DIR` messages through bridge
- [ ] 3.3 Handle pagination for large directories (offset parameter)
- [ ] 3.4 Add visual indicators for file types (directory, file, symlink)
- [ ] 3.5 Add loading states while waiting for worker responses

## 4. Worker Tabs

- [ ] 4.1 Implement `WorkerTabs` widget showing connected workers
- [ ] 4.2 Add tab switching with keyboard (number keys or tab)
- [ ] 4.3 Show worker status indicators (connected, mounts)
- [ ] 4.4 Handle worker discovery on room join

## 5. SLP Context Panel

- [ ] 5.1 Implement `SLPContextPanel` widget (hidden by default)
- [ ] 5.2 Show panel when `.slp` file selected
- [ ] 5.3 Display video paths with status (found/missing)
- [ ] 5.4 Add 'f' hotkey to fix missing videos (prefix resolution)
- [ ] 5.5 Integrate with existing resolve logic from `rtc_resolve.py`

## 6. CLI Integration

- [ ] 6.1 Add `tui` command to CLI with optional `--room`, `--token`, `--otp-secret`
- [ ] 6.2 Make `--room` and `--token` optional (JWT + room picker is primary flow)
- [ ] 6.3 Handle OTP prompt before launching TUI (when worker requires it)
- [ ] 6.4 Add deprecation notice to `browse` command pointing to `tui`

## 7. Testing & Polish

- [ ] 7.1 Manual testing: SSH workflow (no browser available)
- [ ] 7.2 Manual testing: Login flow (not logged in → login → room select → browse)
- [ ] 7.3 Manual testing: multi-worker room
- [ ] 7.4 Manual testing: SLP path resolution flow
- [ ] 7.5 Add keyboard shortcut help (? key)
- [ ] 7.6 Handle connection errors gracefully (reconnect, error messages)

## Dependencies

- Tasks 2.x (Login/Room) depend on 1.x (foundation must be complete)
- Tasks 3.x (Miller) can start after 1.x, parallel with 2.x
- Tasks 4.x (Worker Tabs) and 5.x (SLP Panel) can be parallelized after 3.x
- Task 6.x (CLI) can start after 1.4
- Task 7.x is final validation
