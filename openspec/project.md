# Project Context

## Purpose
sleap-RTC enables remote training and inference for SLEAP (Social LEAP Estimates Animal Poses), a deep learning framework for animal pose estimation. The system provides:
- Remote authenticated CLI training with SLEAP
- WebRTC-based peer-to-peer communication between clients and GPU workers
- Real-time progress monitoring via RTC data channels
- Secure session-based connections coordinated by a signaling server

## Tech Stack
- **Language**: Python 3.11+
- **Networking**: WebRTC (aiortc), WebSockets
- **IPC**: ZeroMQ (pyzmq) for local SLEAP communication
- **CLI**: Click
- **Logging**: Loguru
- **Cloud**: AWS (boto3, EC2 for signaling server)
- **ML Framework**: sleap-nn with PyTorch backend
- **Serialization**: jsonpickle
- **Containerization**: Docker (GitHub Container Registry)

## Project Conventions

**IMPORTANT**: See `DEVELOPMENT.md` for complete development workflow and best practices, including:
- Git workflow (never commit to main, always use PRs, squash merge)
- Commit practices (selective staging, descriptive messages)
- PR workflow using `gh` CLI
- CI/CD monitoring

### Code Style
- **Formatter**: Black with line length 88
- **Linter**: Ruff with pydocstyle rules enabled
- **Docstring Convention**: Google-style docstrings
- **Type Hints**: Use Python type hints (typing module: List, Optional, Text, Tuple, etc.)
- **Naming**:
  - Snake_case for functions and variables
  - PascalCase for classes (e.g., RTCClient, RTCWorkerClient)
  - UPPER_CASE for module-level constants

### Architecture Patterns
- **Client-Worker Architecture**: Decoupled client and worker nodes communicating via WebRTC
- **Peer-to-Peer Communication**: Direct RTC connections after signaling server coordination
- **Session-Based Authentication**: Encoded session strings containing room_id, token, and peer_id
- **Chunked Data Transfer**: Large file transfers split into 64KB chunks over RTC data channels
- **ZMQ Sockets**: Local IPC between client and SLEAP processes (controller and publish ports)
- **Async/Await**: Extensive use of asyncio for concurrent operations
- **Class-Based Design**: Main logic in RTCClient and RTCWorkerClient classes

### Testing Strategy
- **Testing Framework**: pytest (available in dev dependencies)
- **Current Status**: No test files present yet (greenfield for test development)
- **CI/CD**: GitHub Actions workflows for Docker builds
  - worker_test.yml: Test workflow (non-main branches)
  - worker_production.yml: Production workflow with multi-platform builds

### Git Workflow
- **Main Branch**: `main` (target for PRs)
- **Branching Strategy**: Feature branch workflow (e.g., `feature/add-xyz`, `fix/bug-name`)
  - **NEVER commit directly to main** - always work on a branch
  - **NEVER merge without PR** - all changes go through pull requests
  - **ALWAYS squash merge** - use "Squash and merge" in GitHub UI
- **Commit Convention**: Conventional commits with prefixes:
  - `feat:` for new features
  - `fix:` for bug fixes
  - `refactor:`, `docs:`, `test:`, etc.
  - Write descriptive messages explaining why, not just what
- **PR Management**:
  - Use `gh` CLI for all GitHub operations
  - Monitor CI checks: `gh pr checks`, `gh run view --log`
  - Review changes carefully before staging: `git diff`, `git add -p`
- **CI Triggers**:
  - Builds on push to non-main branches when worker/** or workflow files change
  - Deploys to GitHub Container Registry

## Domain Context
- **SLEAP**: A deep learning framework for animal pose estimation that requires GPU resources for training
- **WebRTC**: Enables peer-to-peer connections for low-latency data transfer between client and worker
- **Training Workflow**: Client packages SLEAP training data → transfers to remote worker → worker runs training → streams progress back
- **ZMQ Ports**: Default controller port 9000, publish port 9001 for SLEAP communication
- **Session Strings**: Base64-encoded JSON with format `sleap-session:{encoded}` containing room/token/peer info
- **Worker Requirements**: GPU-enabled machines for optimal model training/inference

## Important Constraints
- **Python Version**: Requires Python 3.11 or higher
- **GPU Dependency**: Workers should have GPU available for optimal performance
- **Signaling Server**: Currently hardcoded to specific AWS EC2 instance (ws://ec2-54-176-92-10.us-west-1.compute.amazonaws.com:8080)
- **Chunk Size**: File transfers use 64KB chunks (CHUNK_SIZE constant)
- **Connection Stability**: Implements reconnection logic (MAX_RECONNECT_ATTEMPTS = 5, RETRY_DELAY = 5s)
- **Platform Support**: Docker builds for linux/amd64, macOS runners don't support Docker in CI

## External Dependencies
- **AWS EC2 Signaling Server**:
  - WebSocket endpoint: ws://ec2-54-176-92-10.us-west-1.compute.amazonaws.com:8080
  - HTTP API: http://ec2-54-176-92-10.us-west-1.compute.amazonaws.com:8001
  - Routes: `/create-room`, `/delete-peers-and-room`, `/anonymous-signin`
- **GitHub Container Registry**: Docker image storage at ghcr.io/talmolab/sleap-rtc-worker
- **SLEAP Framework**: External dependency (sleap-nn) that runs as separate process
- **PyTorch**: Backend for sleap-nn neural network operations
