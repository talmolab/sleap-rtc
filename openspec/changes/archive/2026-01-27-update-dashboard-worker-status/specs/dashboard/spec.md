## ADDED Requirements

### Requirement: Dashboard Authentication
The dashboard SHALL require GitHub OAuth authentication before displaying user data.

#### Scenario: Unauthenticated user visits dashboard
- **WHEN** a user visits the dashboard without being logged in
- **THEN** the system SHALL display a login prompt with GitHub OAuth button
- **AND** the system SHALL NOT display any rooms, tokens, or workers

#### Scenario: Successful GitHub login
- **WHEN** a user completes GitHub OAuth flow
- **THEN** the system SHALL store JWT in localStorage
- **AND** the system SHALL display the user's avatar and username
- **AND** the system SHALL load the user's rooms and tokens

### Requirement: Rooms Tab Display
The dashboard SHALL display a Rooms tab showing all rooms the user has access to.

#### Scenario: User views rooms list
- **WHEN** an authenticated user views the Rooms tab
- **THEN** the system SHALL display each room with its name and ID
- **AND** the system SHALL show the user's role (owner/member) as a badge
- **AND** the system SHALL display join date in relative time format (e.g., "2 days ago")
- **AND** the system SHALL show exact datetime on hover tooltip

#### Scenario: Room owner actions
- **WHEN** a user is the owner of a room
- **THEN** the system SHALL display View Details, Invite, and Delete buttons

### Requirement: Worker Tokens Tab Display
The dashboard SHALL display a Worker Tokens tab showing all tokens the user has created.

#### Scenario: User views tokens list
- **WHEN** an authenticated user views the Worker Tokens tab
- **THEN** the system SHALL display each token with its worker name
- **AND** the system SHALL display the associated room name with room ID in parentheses
- **AND** the system SHALL show token status (Active/Revoked) as a badge
- **AND** the system SHALL display created date in relative time format
- **AND** the system SHALL display expiration date in relative time format (if set)
- **AND** the system SHALL show exact datetime on hover tooltip

#### Scenario: Token displays room name
- **WHEN** a token is displayed
- **THEN** the system SHALL show format "Room Name (abc123...)" instead of just room ID

### Requirement: Connected Worker Count
The dashboard SHALL display the number of workers connected to each token.

#### Scenario: Token has connected workers
- **WHEN** a token has one or more workers currently connected
- **THEN** the system SHALL display "N workers connected" badge on the token card
- **AND** the badge SHALL use a green/success color

#### Scenario: Token has no connected workers
- **WHEN** a token has no workers currently connected
- **THEN** the system SHALL display "No workers connected" or "0 workers connected"
- **AND** the badge SHALL use a muted/grey color

### Requirement: Connected Worker Names Under Tokens
The dashboard SHALL display connected worker hostnames under each token.

#### Scenario: Viewing connected workers
- **WHEN** a user expands the "Connected Workers" section on a token card
- **THEN** the system SHALL display a list of connected worker hostnames
- **AND** each worker SHALL show when it connected (in relative time format)

#### Scenario: Worker hostname extraction
- **WHEN** displaying a connected worker
- **THEN** the system SHALL extract the hostname from the peer_id (e.g., "labgpu1" from "worker-8f3a-labgpu1")

### Requirement: Relative Time Display
The dashboard SHALL display all timestamps in human-readable relative format.

#### Scenario: Recent timestamp display
- **WHEN** a timestamp is less than 1 minute old
- **THEN** the system SHALL display "just now"

#### Scenario: Minutes ago display
- **WHEN** a timestamp is between 1 and 59 minutes old
- **THEN** the system SHALL display "X minutes ago"

#### Scenario: Hours ago display
- **WHEN** a timestamp is between 1 and 23 hours old
- **THEN** the system SHALL display "X hours ago"

#### Scenario: Days ago display
- **WHEN** a timestamp is 1 or more days old
- **THEN** the system SHALL display "X days ago" or "yesterday"

#### Scenario: Exact time tooltip
- **WHEN** a user hovers over a relative time display
- **THEN** the system SHALL show a tooltip with the exact date and time in local timezone

### Requirement: Token API Room Name Enhancement
The tokens API endpoint SHALL include room name in the response.

#### Scenario: Fetch tokens with room names
- **WHEN** an authenticated request is made to GET /api/auth/tokens
- **THEN** each token in the response SHALL include room_name field alongside room_id
- **AND** room_name SHALL be the human-readable name of the associated room

### Requirement: Connected Workers API Endpoint
The signaling server SHALL provide an endpoint to retrieve connected workers for a token.

#### Scenario: Fetch connected workers for token
- **WHEN** an authenticated request is made to GET /api/auth/tokens/{token_id}/workers
- **THEN** the system SHALL return a list of currently connected worker peer_ids
- **AND** each worker SHALL include peer_id and connected_at timestamp
- **AND** the response SHALL include a total count

#### Scenario: Query uses existing connection state
- **WHEN** the workers endpoint is called
- **THEN** the system SHALL query the in-memory WebSocket connection map
- **AND** the system SHALL NOT require additional database queries for worker status

#### Scenario: Unauthorized access
- **WHEN** a request is made without valid JWT or for a token the user doesn't own
- **THEN** the system SHALL return 401 or 403 status code
