## Why

The SLEAP-RTC dashboard has functional core features (room/token CRUD, OAuth login, worker discovery), but several UI elements are non-functional placeholders and the login experience still uses outdated styling. This creates a fragmented user experience and limits usability.

## What Changes

### Priority 1: Design Consistency
- Update login/authentication success pages to match main dashboard design
- Replace placeholder logo with actual SLEAP logo (maintain dimensions)

### Priority 2: Complete Missing Functionality
- Implement Search button functionality (filter rooms/tokens)
- Add Settings panel with user preferences
- Add "Join Room" button to trigger existing modal
- Enable room name editing
- Add room members/collaborators list view
- Enable removing members from rooms

### Priority 3: UX Polish
- Add token expiration warnings (visual indicator when tokens expire soon)
- Replace "Loading..." text with skeleton loaders
- Improve mobile responsive behavior (sidebar collapsing)
- Add keyboard shortcuts (e.g., `/` to focus search)

### Priority 4: Nice to Have
- Light/dark mode toggle
- Real-time worker status updates via WebSocket
- Pagination for large room/token lists
- About page with version and links

## Impact

- Affected specs: `authentication` (login flow), `worker-discovery` (worker status)
- Affected code: `dashboard/` (app.js, styles.css, index.html, callback.html)
- New spec: `dashboard` capability for UI-specific requirements
- No backend changes required for Priority 1-3 items
