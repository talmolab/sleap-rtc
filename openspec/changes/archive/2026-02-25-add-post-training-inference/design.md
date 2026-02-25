# Design: Post-Training Inference

## Message Sequence

```
CLIENT                          WORKER                      SLEAP-NN
  |                               |                            |
  +--JOB_SUBMIT::TrainJobSpec---->|                            |
  |<--JOB_ACCEPTED::job_id--------|                            |
  |                               |                            |
  |  [training phase — unchanged] |                            |
  |<--PROGRESS_REPORT (train_*)---|<--ZMQ pub (metrics)--------|
  |<--MODEL_TYPE:: (multi-model)--|                            |
  |<--JOB_COMPLETE:: -------------|  training done             |
  |                               |                            |
  |  [inference phase — new]      |                            |
  |<--INFERENCE_BEGIN::-----------|  spawn sleap track         |
  |<--INFERENCE_PROGRESS::--------|<--stdout JSON lines--------|
  |<--INFERENCE_COMPLETE::{path}--|  subprocess exits 0        |
  |                               |                            |
  client loads predictions from   |
  shared filesystem at {path}     |
```

## Worker Implementation

### 1. Checkpoint Path Tracking

In `worker_class.py` pipeline loop, derive checkpoint directory from written config after
each model trains:

```python
trained_model_paths = []
for i, cmd in enumerate(commands):
    await self.job_executor.execute_from_spec(channel, cmd, model_job_id, ...)
    ckpt_dir = _get_checkpoint_dir(spec.config_paths[i])  # parse save_ckpt_path + run_name
    trained_model_paths.append(ckpt_dir)
```

### 2. Inference Trigger

After the pipeline loop exits successfully (no cancellation, no failure):

```python
labels_path = Path(worker_labels_path)  # already-resolved worker path from training setup
predictions_path = labels_path.with_suffix("").with_suffix(".predictions.slp")

track_spec = TrackJobSpec(
    data_path=str(labels_path),
    model_paths=trained_model_paths,
    output_path=str(predictions_path),
    only_suggested_frames=True,  # sleap track handles fallback to all frames
)
track_cmd = builder.build_track_command(track_spec)

channel.send("INFERENCE_BEGIN::{}")
await self.job_executor.run_inference(channel, track_cmd, predictions_path)
```

### 3. `run_inference()` in `job_executor.py`

New method, same subprocess pattern as training:

```python
async def run_inference(self, channel, cmd, predictions_path):
    process = await asyncio.create_subprocess_exec(*cmd, ...)
    async for line in process.stdout:
        decoded = line.decode().rstrip()
        # Forward JSON progress lines only
        if decoded.startswith("{"):
            channel.send(f"INFERENCE_PROGRESS::{decoded}")
    await process.wait()
    if process.returncode == 0 and Path(predictions_path).exists():
        channel.send(f'INFERENCE_COMPLETE::{{"predictions_path": "{predictions_path}"}}')
    else:
        channel.send(f'INFERENCE_FAILED::{{"error": "exit code {process.returncode}"}}')
```

### 4. Skip Conditions

Inference is skipped (sends `INFERENCE_SKIPPED::`) when:
- Training was cancelled (`MSG_JOB_CANCEL`) — no checkpoint saved
- Any pipeline model failed — incomplete model set, can't run inference
- `save_ckpt=False` in config — no checkpoint available

## Client Implementation

### `InferenceProgressDialog`

New `QDialog` in `sleap_rtc/gui/` modelled on SLEAP's local `InferenceProgressDialog`:
- Status label: "Predicted: 450/500  FPS: 45.2  ETA: 3m 20s"
- Progress bar: current / total frames
- Log area: monospace, dark background

### Message Handling in `RemoteProgressBridge`

```python
elif msg.startswith("INFERENCE_BEGIN::"):
    self._open_inference_dialog()

elif msg.startswith("INFERENCE_PROGRESS::"):
    data = json.loads(msg.split("::", 1)[1])
    self._update_inference_dialog(data)

elif msg.startswith("INFERENCE_COMPLETE::"):
    data = json.loads(msg.split("::", 1)[1])
    self._finish_inference(data["predictions_path"])

elif msg.startswith("INFERENCE_FAILED::"):
    self._inference_error(json.loads(msg.split("::", 1)[1])["error"])

elif msg.startswith("INFERENCE_SKIPPED::"):
    self._inference_skipped()
```

### Predictions Merge

```python
def _finish_inference(self, predictions_path: str):
    self._inference_dialog.finish()
    new_labels = sio.load_slp(predictions_path)
    self._main_window.labels.merge(new_labels, frame="replace_predictions")
```

## Edge Cases

| Condition | Behavior |
|---|---|
| Training cancelled | `INFERENCE_SKIPPED::{"reason": "cancelled"}` |
| Training stopped early | Inference runs (checkpoint saved) |
| Any model failed | `INFERENCE_SKIPPED::{"reason": "training_failed"}` |
| No suggested frames | `--only_suggested_frames` falls back to all frames |
| `save_ckpt=False` | `INFERENCE_SKIPPED::{"reason": "no_checkpoint"}` |
| Inference subprocess crashes | `INFERENCE_FAILED::{"error": "..."}` |
| Predictions file not written | `INFERENCE_FAILED::{"error": "no output file"}` |
| RTC disconnect during inference | Inference completes on worker; client must load manually |
| Cancel during inference | `MSG_JOB_CANCEL` kills inference subprocess |
