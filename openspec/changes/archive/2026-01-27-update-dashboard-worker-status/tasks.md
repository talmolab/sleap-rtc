## 1. Relative Time Display (Frontend Only)

- [ ] 1.1 Add `formatRelativeTime()` helper function using `Intl.RelativeTimeFormat`
- [ ] 1.2 Update `renderRooms()` to use relative time for `joined_at` with title tooltip
- [ ] 1.3 Update `renderTokens()` to use relative time for `created_at` and `expires_at` with title tooltip
- [ ] 1.4 Add CSS for hover state on relative time elements

## 2. Room Name in Tokens Display

- [ ] 2.1 **Backend**: Modify GET /api/auth/tokens to JOIN with rooms table and include `room_name`
- [ ] 2.2 Update `renderTokens()` to display "Room Name (room_id...)" format
- [ ] 2.3 Update token creation success modal to show room name

## 3. Connected Workers Count Endpoint

- [ ] 3.1 **Backend**: Add GET /api/auth/tokens/{token_id}/workers endpoint
- [ ] 3.2 **Backend**: Query in-memory WebSocket connection map for workers using that token
- [ ] 3.3 **Backend**: Return `{workers: [{peer_id, connected_at}], count: N}`
- [ ] 3.4 **Backend**: Add authorization check (user must own the token)

## 4. Connected Workers Display in Dashboard

- [ ] 4.1 Add `loadTokenWorkers(tokenId)` method to fetch connected workers
- [ ] 4.2 Update `renderTokens()` to show "N workers connected" badge
- [ ] 4.3 Add collapsible "Connected Workers" section under each token
- [ ] 4.4 Extract hostname from peer_id for display (e.g., "labgpu1" from "worker-8f3a-labgpu1")
- [ ] 4.5 Show connection time in relative format for each worker
- [ ] 4.6 Style badge green when workers connected, grey when none

## 5. Modern UI Styling

- [ ] 5.1 Update CSS custom properties with new color palette (zinc grays + purple accents)
- [ ] 5.2 Add sidebar navigation structure to index.html
- [ ] 5.3 Update card styling with cleaner borders and hover states
- [ ] 5.4 Update button styling (primary, secondary, ghost variants)
- [ ] 5.5 Add responsive breakpoints for mobile view
- [ ] 5.6 Update scrollbar styling for dark theme

## 6. Testing & Validation

- [ ] 6.1 Test relative time display across different timezones
- [ ] 6.2 Test token display with and without room names
- [ ] 6.3 Test worker count display with 0, 1, and multiple workers
- [ ] 6.4 Test expand/collapse of connected workers list
- [ ] 6.5 Test API error handling (network failures, auth expiration)
- [ ] 6.6 Test responsive design on mobile viewports

## Dependencies

- Task 1.x is frontend-only, can start immediately
- Task 2.1 (backend) blocks 2.2-2.3
- Task 3.x (backend) blocks 4.x
- Task 5.x (styling) can be done in parallel with other tasks

## Out of Scope (Deferred to TUI/GUI)

The following are explicitly NOT part of this change:
- Dedicated Workers tab with detailed worker list
- Worker status (available/busy/offline)
- GPU information and utilization
- Current job details
- Real-time WebSocket updates
- File browsing

These features will be implemented in TUI/GUI which can connect directly to workers via WebRTC.
