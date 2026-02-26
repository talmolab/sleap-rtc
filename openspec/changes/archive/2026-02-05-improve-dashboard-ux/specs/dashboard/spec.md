## ADDED Requirements

### Requirement: Consistent Visual Design
The dashboard SHALL maintain consistent visual styling across all pages including login, authentication callback, and main application views.

#### Scenario: Login page matches dashboard theme
- **WHEN** user visits the login page
- **THEN** the page uses the same color scheme, typography, and layout patterns as the main dashboard

#### Scenario: Callback page matches dashboard theme
- **WHEN** user is redirected after OAuth authentication
- **THEN** the callback/success page uses consistent styling with the main dashboard

#### Scenario: Brand logo displayed
- **WHEN** user views any dashboard page
- **THEN** the SLEAP logo is displayed in the header/sidebar

### Requirement: Search Functionality
The dashboard SHALL provide search capability to filter rooms and tokens.

#### Scenario: Search filters rooms
- **WHEN** user enters text in the search field
- **THEN** the rooms list is filtered to show only rooms matching the search query

#### Scenario: Search filters tokens
- **WHEN** user enters text in the search field while viewing tokens
- **THEN** the tokens list is filtered to show only tokens matching the search query

#### Scenario: Search keyboard shortcut
- **WHEN** user presses the `/` key
- **THEN** focus moves to the search input field

### Requirement: Settings Panel
The dashboard SHALL provide a settings panel for user preferences.

#### Scenario: Open settings
- **WHEN** user clicks the settings button
- **THEN** a settings panel or modal is displayed

#### Scenario: Settings persistence
- **WHEN** user changes a setting
- **THEN** the preference is persisted (localStorage or server-side)

### Requirement: Join Room Flow
The dashboard SHALL allow users to join rooms via invite code.

#### Scenario: Join room button visible
- **WHEN** user views the sidebar
- **THEN** a "Join Room" button is visible

#### Scenario: Join room modal
- **WHEN** user clicks "Join Room"
- **THEN** a modal is displayed for entering the invite code

### Requirement: Room Name Editing
The dashboard SHALL allow room owners to edit room names.

#### Scenario: Edit room name
- **WHEN** room owner clicks edit on a room name
- **THEN** an inline editor or modal allows changing the room name

#### Scenario: Non-owner cannot edit
- **WHEN** non-owner member views a room
- **THEN** the edit room name option is not available

### Requirement: Room Members Management
The dashboard SHALL display room members and allow owners to manage membership.

#### Scenario: View members list
- **WHEN** user views a room
- **THEN** a list of room members/collaborators is visible

#### Scenario: Remove member
- **WHEN** room owner clicks remove on a member
- **THEN** the member is removed from the room after confirmation

#### Scenario: Non-owner cannot remove
- **WHEN** non-owner member views the members list
- **THEN** the remove member option is not available

### Requirement: Token Expiration Warnings
The dashboard SHALL display visual warnings for tokens that will expire soon.

#### Scenario: Warning indicator shown
- **WHEN** a token will expire within 24 hours
- **THEN** a warning indicator (icon/badge) is displayed next to the token

#### Scenario: Expired token indicator
- **WHEN** a token has expired
- **THEN** an expired indicator is displayed and the token is visually distinguished

### Requirement: Loading States
The dashboard SHALL display skeleton loaders during data fetching.

#### Scenario: Skeleton loader for rooms
- **WHEN** rooms list is loading
- **THEN** skeleton placeholder elements are displayed instead of "Loading..." text

#### Scenario: Skeleton loader for tokens
- **WHEN** tokens list is loading
- **THEN** skeleton placeholder elements are displayed instead of "Loading..." text

### Requirement: Mobile Responsive Design
The dashboard SHALL provide usable experience on mobile devices.

#### Scenario: Sidebar collapses on mobile
- **WHEN** viewport width is below mobile breakpoint
- **THEN** sidebar collapses to a hamburger menu or overlay

#### Scenario: Touch-friendly interactions
- **WHEN** user interacts on touch device
- **THEN** all buttons and controls have adequate touch targets

### Requirement: Keyboard Navigation
The dashboard SHALL support keyboard shortcuts for common actions.

#### Scenario: Focus search with slash
- **WHEN** user presses `/` key (not in input field)
- **THEN** search input receives focus

#### Scenario: Close modal with escape
- **WHEN** user presses `Escape` key while modal is open
- **THEN** the modal closes
