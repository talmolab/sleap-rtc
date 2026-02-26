## 1. Design Consistency (Priority 1)

- [x] 1.1 Update login loading page (`index.html` loading state) to match dashboard design
- [x] 1.2 Update authentication success/callback page (`callback.html`) styling
- [x] 1.3 Replace placeholder logo with SLEAP logo (maintain 32x32 dimensions)
- [x] 1.4 Ensure consistent color scheme across all pages

## 2. Core Functionality (Priority 2)

- [x] 2.1 Implement search functionality
  - [x] 2.1.1 Add search state to app state
  - [x] 2.1.2 Create search input handler
  - [x] 2.1.3 Filter rooms list by search query
  - [x] 2.1.4 Filter tokens list by search query
- [x] 2.2 Add Settings panel
  - [x] 2.2.1 Create settings modal component
  - [x] 2.2.2 Wire up settings button click handler
  - [x] 2.2.3 Add user preferences (notification settings, etc.)
- [x] 2.3 Add "Join Room" button in sidebar
  - [x] 2.3.1 Add button element to sidebar
  - [x] 2.3.2 Wire up to existing join room modal
- [x] 2.4 Enable room name editing
  - [x] 2.4.1 Add edit button/icon to room header
  - [x] 2.4.2 Create inline edit or modal for room name
  - [x] 2.4.3 Call API to update room name
- [x] 2.5 Room members management
  - [x] 2.5.1 Add members list to room view
  - [x] 2.5.2 Add "Remove member" functionality
  - [x] 2.5.3 Style members list consistently

## 3. UX Polish (Priority 3)

- [x] 3.1 Add token expiration warnings
  - [x] 3.1.1 Calculate time until expiration
  - [x] 3.1.2 Add visual indicator (badge/icon) for soon-expiring tokens
  - [x] 3.1.3 Define "soon" threshold (3 days)
- [x] 3.2 Replace loading text with skeleton loaders
  - [x] 3.2.1 Create skeleton loader CSS styles
  - [x] 3.2.2 Add skeleton components for room list
  - [x] 3.2.3 Add skeleton components for token list
- [x] 3.3 Improve mobile responsiveness
  - [x] 3.3.1 Fix sidebar collapse behavior on small screens (hamburger menu)
  - [x] 3.3.2 Add sidebar overlay for mobile
- [x] 3.4 Add keyboard shortcuts (done in Priority 2)
  - [x] 3.4.1 Add `/` shortcut to focus search
  - [x] 3.4.2 Add `Escape` to close modals
  - [x] 3.4.3 Document shortcuts in settings/help

## 4. Nice to Have (Priority 4)

- [x] 4.1 Add light/dark mode toggle
  - [x] 4.1.1 Create CSS variables for theme colors
  - [x] 4.1.2 Add theme toggle button
  - [x] 4.1.3 Persist theme preference in localStorage
- [x] 4.2 Add About page
  - [x] 4.2.1 Create about modal with version info
  - [x] 4.2.2 Add links to docs and GitHub
- [x] 4.3 Add pagination for large lists
  - [x] 4.3.1 Implement virtual scrolling or pagination for rooms
  - [x] 4.3.2 Implement virtual scrolling or pagination for tokens

## 5. Testing

- [ ] 5.1 Test all new functionality manually
- [ ] 5.2 Test member-only room view (non-owner permissions)
- [ ] 5.3 Test on mobile devices
- [ ] 5.4 Verify no regressions in existing functionality
