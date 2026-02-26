## ADDED Requirements

### Requirement: LossViewer-Compatible ZMQ Message Format

The RemoteProgressBridge SHALL publish ZMQ messages in the exact format expected by SLEAP's LossViewer widget.

#### Scenario: Publish epoch_end with loss data

- **WHEN** a progress event with `event_type="epoch_end"` is received from WebRTC
- **AND** the event contains `train_loss=0.0045` and `val_loss=0.0051`
- **THEN** the bridge SHALL publish a single-frame ZMQ string message
- **AND** the message SHALL be encoded with `jsonpickle.encode()`
- **AND** the message SHALL contain `"event": "epoch_end"`
- **AND** the message SHALL contain `"what": "<model_type>"` matching the current training job
- **AND** the message SHALL contain `"logs": {"train/loss": 0.0045, "val/loss": 0.0051}`

#### Scenario: Publish train_begin with model type

- **WHEN** a progress event with `event_type="train_begin"` is received
- **THEN** the bridge SHALL publish a message with `"event": "train_begin"` and `"what": "<model_type>"`
- **AND** include `"wandb_url"` if present in the event

#### Scenario: Publish train_end

- **WHEN** a progress event with `event_type="train_end"` is received
- **THEN** the bridge SHALL publish a message with `"event": "train_end"` and `"what": "<model_type>"`

#### Scenario: Publish epoch_begin

- **WHEN** a progress event with `event_type="epoch_begin"` is received
- **THEN** the bridge SHALL publish a message with `"event": "epoch_begin"`, `"what": "<model_type>"`, and `"epoch": N`

### Requirement: PUB Socket Connects to LossViewer

The RemoteProgressBridge SHALL connect its PUB socket to the LossViewer's SUB socket rather than binding.

#### Scenario: Connect to LossViewer port

- **WHEN** the bridge starts
- **THEN** the bridge SHALL create a ZMQ PUB socket
- **AND** connect to `tcp://127.0.0.1:{publish_port}` (not bind)
- **AND** the LossViewer's SUB socket owns the bind on that port

#### Scenario: Port provided by caller

- **WHEN** `RemoteProgressBridge` is initialized with `publish_port=9001`
- **THEN** the bridge SHALL connect to `tcp://127.0.0.1:9001`
- **AND** the port SHALL match the LossViewer's bound port passed through from the SLEAP dialog

### Requirement: Model Type Tracking

The RemoteProgressBridge SHALL track the current model type for inclusion in all messages.

#### Scenario: Set model type at initialization

- **WHEN** the bridge is created with `model_type="centroid"`
- **THEN** all subsequent messages SHALL include `"what": "centroid"`

#### Scenario: Reset model type for multi-model training

- **WHEN** a new training phase begins (e.g., switching from centroid to centered_instance)
- **THEN** the caller SHALL update the model type via `bridge.set_model_type("centered_instance")`
- **AND** subsequent messages SHALL include the updated model type
