# worker-progress-reporting Specification

## Purpose
TBD - created by archiving change refactor-worker-modular. Update Purpose after archive.
## Requirements
### Requirement: ZMQ Control Socket Initialization

The progress reporter SHALL initialize ZMQ PUB socket for sending control messages to SLEAP trainer.

#### Scenario: Start control socket

- **WHEN** training job starts in GUI mode
- **THEN** progress reporter SHALL create ZMQ context
- **AND** create PUB socket
- **AND** bind to tcp://127.0.0.1:9000 (controller port)
- **AND** store socket for message publishing
- **AND** log "ZMQ control socket initialized"

### Requirement: Progress Listener

The progress reporter SHALL listen for ZMQ progress messages from SLEAP trainer and forward to client.

#### Scenario: Start progress listener

- **WHEN** training job starts with GUI mode enabled
- **THEN** progress reporter SHALL create ZMQ SUB socket
- **AND** bind to tcp://127.0.0.1:9001 (publish port)
- **AND** subscribe to all messages (empty filter)
- **AND** poll for messages every 50ms

#### Scenario: Forward progress to client

- **WHEN** progress message received from trainer ZMQ socket
- **THEN** progress reporter SHALL send "PROGRESS_REPORT::{msg}" to client
- **AND** include full progress JSON from trainer

#### Scenario: Handle ZMQ receive errors

- **WHEN** ZMQ recv_string raises zmq.Again (no message available)
- **THEN** progress reporter SHALL return None
- **AND** continue polling without error

#### Scenario: Handle channel send errors

- **WHEN** RTC channel send fails during progress forward
- **THEN** progress reporter SHALL log error
- **AND** continue listening for next message

### Requirement: Control Message Publishing

The progress reporter SHALL publish control messages from client to SLEAP trainer.

#### Scenario: Forward stop command

- **WHEN** client sends "ZMQ_CTRL::STOP" message
- **THEN** progress reporter SHALL extract "STOP" command
- **AND** publish to trainer via control PUB socket
- **AND** log "Sent control message to Trainer"

#### Scenario: Control socket not initialized

- **WHEN** control message received but ctrl_socket is None
- **THEN** progress reporter SHALL log error
- **AND** NOT raise exception

### Requirement: Progress Reporter Lifecycle

The progress reporter SHALL manage ZMQ socket lifecycle from initialization through cleanup.

#### Scenario: Start for GUI training

- **WHEN** training starts with gui=True flag
- **THEN** progress reporter SHALL initialize control socket
- **AND** start progress listener as asyncio task
- **AND** wait 1 second for SUB socket to connect

#### Scenario: Stop after training completion

- **WHEN** training completes successfully or fails
- **THEN** progress reporter SHALL cancel progress listener task
- **AND** close ZMQ sockets
- **AND** clean up ZMQ context

### Requirement: Non-Blocking ZMQ Operations

The progress reporter SHALL use non-blocking ZMQ operations to avoid blocking event loop.

#### Scenario: Non-blocking receive

- **WHEN** polling for trainer messages
- **THEN** progress reporter SHALL use NOBLOCK flag
- **AND** run recv_string in thread pool executor
- **AND** return to event loop between polls

#### Scenario: Async sleep between polls

- **WHEN** no message received
- **THEN** progress reporter SHALL await asyncio.sleep(0.05)
- **AND** allow other tasks to execute

### Requirement: CLI Mode Bypass

The progress reporter SHALL skip ZMQ initialization for CLI-only training.

#### Scenario: CLI training without GUI

- **WHEN** training starts with gui=False
- **THEN** progress reporter SHALL NOT initialize ZMQ sockets
- **AND** NOT start progress listener task
- **AND** training logs stream directly via stdout

