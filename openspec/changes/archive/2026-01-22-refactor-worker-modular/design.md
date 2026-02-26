# Worker Modularization Design

## Context

The `RTCWorkerClient` class has grown to ~2200 lines handling 7+ distinct responsibilities:
1. GPU hardware detection and capability reporting
2. Training and inference job execution
3. File transfer and compression
4. Peer-to-peer job coordination messaging
5. Worker state and room registration
6. WebRTC connection lifecycle management
7. ZMQ progress reporting

This monolithic design creates several problems:
- **Maintainability**: Hard to locate and modify specific functionality
- **Testability**: Difficult to unit test individual concerns
- **Extensibility**: Adding worker-to-worker mesh for room registry will further complicate the class
- **Cognitive load**: Understanding the full class requires parsing 2200 lines

## Goals / Non-Goals

### Goals
- Extract 6 specialized modules with single responsibilities
- Maintain backward compatibility for public API (`RTCWorkerClient` constructor and `run_worker()`)
- Reduce `RTCWorkerClient` to ~300 lines as an orchestrator
- Enable easier testing of individual components
- Prepare for worker-to-worker mesh networking implementation

### Non-Goals
- Changing worker behavior or functionality
- Adding new features (this is pure refactoring)
- Modifying client code or CLI interfaces
- Performance optimization (maintain current performance characteristics)

## Decisions

### Architecture Pattern: Composition over Inheritance

**Decision**: Use composition with manager classes injected into `RTCWorkerClient`

**Rationale**:
- Clear separation of concerns
- Easy to mock individual managers for testing
- Manager classes can be reused in future worker-to-worker mesh
- Avoids multiple inheritance complexity

**Implementation**:
```python
class RTCWorkerClient:
    def __init__(self, ...):
        self.capabilities = WorkerCapabilities(gpu_id=gpu_id)
        self.state_manager = StateManager(self)
        self.file_manager = FileManager(shared_storage_root)
        self.job_coordinator = JobCoordinator(self)
        self.progress_reporter = ProgressReporter()
        self.job_executor = JobExecutor(
            capabilities=self.capabilities,
            file_manager=self.file_manager,
            progress_reporter=self.progress_reporter
        )
        # WebRTC connection management stays in RTCWorkerClient
```

### Module Boundaries

**Decision**: Group methods by domain responsibility, not by technical layer

**Modules**:
1. **`WorkerCapabilities`**: GPU detection, job compatibility, resource queries
2. **`JobExecutor`**: Training/inference execution, script parsing, shared storage jobs
3. **`FileManager`**: File transfer, compression, shared storage validation
4. **`JobCoordinator`**: Peer messaging, job request/assignment handling
5. **`StateManager`**: Worker status, registration, room management
6. **`ProgressReporter`**: ZMQ socket management, progress streaming
7. **`RTCWorkerClient`**: WebRTC connection lifecycle (orchestrator)

**Rationale**:
- Domain-based boundaries are more stable than technical layers
- Each module can evolve independently
- Clear ownership of functionality

### Dependency Flow

**Decision**: Unidirectional dependency flow from specific → general

```
RTCWorkerClient (orchestrator)
    ├─> StateManager (uses websocket from RTCWorkerClient)
    ├─> JobCoordinator (uses websocket from RTCWorkerClient)
    ├─> FileManager (independent)
    ├─> ProgressReporter (independent)
    ├─> WorkerCapabilities (independent)
    └─> JobExecutor
            ├─> WorkerCapabilities (dependency injection)
            ├─> FileManager (dependency injection)
            └─> ProgressReporter (dependency injection)
```

**Rationale**:
- Avoids circular dependencies
- Makes testing easier (inject mocks for dependencies)
- Clear data flow for debugging

### Backward Compatibility Strategy

**Decision**: Maintain exact public API surface of `RTCWorkerClient`

**Preserved Interface**:
- Constructor signature: `__init__(chunk_size, gpu_id, shared_storage_root)`
- Public method: `run_worker(pc, DNS, port_number, room_id, token)`
- Public attributes: `status`, `gpu_memory_mb`, `gpu_model`, `cuda_version`

**Migration**:
- No changes required in client code
- Imports continue to work: `from sleap_rtc.worker.worker_class import RTCWorkerClient`
- Internal implementation changes are transparent

### WebRTC Connection Handling

**Decision**: Keep WebRTC connection logic in `RTCWorkerClient` as orchestrator

**Methods retained in RTCWorkerClient**:
- `handle_connection()`: Route incoming messages to managers
- `on_datachannel()`: Delegate datachannel messages to managers
- `on_iceconnectionstatechange()`: Handle ICE state transitions
- `run_worker()`: Main worker lifecycle
- `clean_exit()`: Cleanup all managers
- `keep_ice_alive()`: Keepalive messages

**Rationale**:
- WebRTC is the core coordination mechanism
- Distributing connection logic across modules would create coupling
- Orchestrator pattern: RTCWorkerClient coordinates, managers execute

### Message Routing Strategy

**Decision**: RTCWorkerClient routes datachannel messages to appropriate managers based on message type

**Example routing**:
```python
async def on_message(self, message):
    msg_type, msg_args = parse_message(message)

    # Route to appropriate manager
    if msg_type in (MSG_JOB_ID, MSG_SHARED_INPUT_PATH, ...):
        await self.file_manager.handle_message(msg_type, msg_args, channel)
    elif msg_type == "PACKAGE_TYPE":
        await self.job_executor.set_package_type(msg_args[0])
    elif "PROGRESS_REPORT" in message:
        # Already handled by ProgressReporter ZMQ
        pass
    # ...
```

**Rationale**:
- Centralized routing keeps message protocol visible
- Managers focus on domain logic, not protocol parsing
- Easy to extend with new message types

## Alternatives Considered

### Alternative 1: Extract to Functions (Not Classes)

**Option**: Create modules with standalone functions instead of classes
- `capabilities.py`: `detect_gpu_memory()`, `check_job_compatibility()`, etc.
- Call functions from `RTCWorkerClient` instead of manager instances

**Rejected because**:
- No state encapsulation (would need to pass many parameters)
- Harder to mock for testing
- Doesn't prepare well for worker-to-worker mesh (will need stateful managers)

### Alternative 2: Full Async Actor Pattern

**Option**: Each manager is an independent async task with message queues
- Manager instances run in separate asyncio tasks
- Communication via asyncio.Queue

**Rejected because**:
- Over-engineering for current needs
- Adds concurrency complexity without clear benefit
- Makes debugging harder (distributed state)
- Current call-based model is simpler and sufficient

### Alternative 3: Keep Everything in One File, Use Private Methods

**Option**: Keep single file, organize with clear section comments
- Group related methods with `# ========== CAPABILITIES ==========` headers
- Use naming conventions like `_cap_`, `_job_`, `_file_` prefixes

**Rejected because**:
- Doesn't solve testability problem (still one giant class)
- Doesn't reduce cognitive load (still 2200 lines)
- Harder to navigate than separate files
- Doesn't prepare for worker mesh (will need independent managers)

## Risks / Trade-offs

### Risk: Regression in Worker Behavior

**Mitigation**:
- No behavioral changes, only structural refactoring
- Comprehensive manual testing checklist (see tasks.md section 9)
- Test all workflows: training, inference, shared storage, reconnection
- Keep PR focused on refactoring only (no feature additions)

### Risk: Import Path Confusion

**Mitigation**:
- Keep `RTCWorkerClient` export in `worker_class.py` unchanged
- Document new module structure in code comments
- Update imports in PR to show example usage

### Risk: Over-Abstraction

**Mitigation**:
- Each manager is a concrete class with clear responsibilities
- No abstract base classes or complex inheritance
- Simple composition pattern (inject dependencies)
- If a manager is too small (<50 lines), merge it back

### Trade-off: More Files vs Simpler Files

**Trade-off**: 1 file (2200 lines) → 7 files (~300 lines each)

**Accepted because**:
- Modern IDEs handle multiple files easily
- Each file has clear, focused purpose
- Easier to review changes (affected file shows scope)
- Prepares for worker mesh (managers become reusable)

## Migration Plan

### Phase 1: Extract Modules (This Change)
1. Create 6 new manager modules
2. Refactor `RTCWorkerClient` to use composition
3. Test all worker workflows manually
4. Merge as single PR (keep atomic)

### Phase 2: Add Unit Tests (Follow-up PR)
1. Add pytest tests for each manager independently
2. Mock dependencies (e.g., mock `WorkerCapabilities` in `JobExecutor` tests)
3. Test edge cases that are hard to test with full integration

### Phase 3: Worker Mesh Implementation (Future)
1. Use extracted managers as building blocks
2. `RTCWorkerClient` manages client connection + worker mesh
3. `JobCoordinator` handles both client jobs and worker state sync

### Rollback Plan
- If issues found after merge:
  1. Revert PR (restores original monolithic class)
  2. Fix issues in separate branch
  3. Re-apply refactoring with fixes

## Open Questions

**Q: Should managers share state or have independent state?**
- A: Independent state preferred, but managers can query RTCWorkerClient for shared state (e.g., websocket connection)

**Q: Should we add unit tests in this PR or separate PR?**
- A: Separate PR. This refactoring maintains behavior; tests can be added incrementally afterward.

**Q: How to handle circular references (manager needs RTCWorkerClient reference)?**
- A: Pass specific resources (e.g., websocket) instead of entire RTCWorkerClient when possible. If full reference needed (e.g., StateManager updating self.status), pass `self` explicitly.

**Q: Should progress reporter be sync or async?**
- A: Keep async for ZMQ operations (current implementation uses asyncio.sleep polling)
