"""Remote training runners for SLEAP GUI integration.

This module provides the bridge between sleap-rtc's WebRTC-based progress
reporting and SLEAP's LossViewer which expects ZMQ messages.

The flow is:
    Worker (sleap-nn) → ZMQ → WebRTC DataChannel → Client → ZMQ → LossViewer
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable

from loguru import logger

if TYPE_CHECKING:
    from sleap_rtc.api import ProgressEvent, TrainingResult
    from sleap_rtc.jobs.spec import TrainJobSpec


class RemoteProgressBridge:
    """Bridge WebRTC progress messages to ZMQ for LossViewer compatibility.

    This class receives ProgressEvent objects from the sleap-rtc training API
    and re-emits them via ZMQ in the exact format expected by SLEAP's
    LossViewer widget (sleap/gui/widgets/monitor.py).

    LossViewer parses messages with ``jsonpickle.decode(sub.recv_string())``
    and expects:
    - ``what``: model type string for filtering (e.g., "centroid")
    - ``logs``: dict with ``train/loss`` and ``val/loss`` keys
    - ``event``: one of train_begin, epoch_begin, epoch_end, train_end

    The LossViewer SUB socket **binds** to a port, so this bridge's PUB
    socket must **connect** to it (not bind).
    """

    def __init__(self, publish_port: int = 9001, model_type: str = ""):
        """Initialize the progress bridge.

        Args:
            publish_port: ZMQ port where LossViewer's SUB socket is bound.
            model_type: Model type string for the ``what`` field (e.g.,
                "centroid", "centered_instance"). LossViewer uses this to
                filter messages when training multiple models sequentially.
        """
        self._publish_port = publish_port
        self._model_type = model_type
        self._socket = None
        self._context = None
        self._started = False
        self._lock = threading.Lock()

    def set_model_type(self, model_type: str):
        """Update the model type for subsequent messages.

        Call this when switching between training phases in multi-model
        training (e.g., centroid → centered_instance in top-down).

        Args:
            model_type: The new model type string.
        """
        self._model_type = model_type

    def start(self):
        """Start the ZMQ publisher socket.

        Connects to the LossViewer's SUB socket (which owns the bind).
        """
        import zmq

        with self._lock:
            if self._started:
                return

            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.PUB)
            self._socket.connect(f"tcp://127.0.0.1:{self._publish_port}")
            self._started = True
            logger.debug(
                f"RemoteProgressBridge connected to LossViewer on port "
                f"{self._publish_port}"
            )

    def stop(self):
        """Stop the ZMQ publisher socket."""
        with self._lock:
            if not self._started:
                return

            if self._socket:
                self._socket.close()
                self._socket = None
            if self._context:
                self._context.term()
                self._context = None
            self._started = False
            logger.debug("RemoteProgressBridge stopped")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False

    def on_progress(self, event: "ProgressEvent"):
        """Handle a progress event from the training job.

        This method converts the ProgressEvent to ZMQ message format and
        publishes it for LossViewer to consume.

        Args:
            event: The progress event from sleap-rtc training.
        """
        if not self._started or not self._socket:
            logger.warning("Progress bridge not started, dropping event")
            return

        message = self._format_message(event)
        if message:
            self._publish(message)

    def _format_message(self, event: "ProgressEvent") -> dict | None:
        """Convert ProgressEvent to LossViewer-compatible ZMQ message format.

        The LossViewer expects messages with:
        - ``event``: event type string
        - ``what``: model type for filtering
        - ``logs``: dict with loss values using sleap-nn keys

        Args:
            event: The progress event to format.

        Returns:
            Dictionary matching LossViewer's expected format.
        """
        if event.event_type == "train_begin":
            msg = {"event": "train_begin", "what": self._model_type}
            if event.wandb_url:
                msg["wandb_url"] = event.wandb_url
            return msg

        elif event.event_type == "epoch_begin":
            return {
                "event": "epoch_begin",
                "what": self._model_type,
                "epoch": event.epoch,
            }

        elif event.event_type == "epoch_end":
            logs = {}
            if event.train_loss is not None:
                logs["train/loss"] = event.train_loss
            if event.val_loss is not None:
                logs["val/loss"] = event.val_loss
            if event.metrics:
                logs.update(event.metrics)
            return {
                "event": "epoch_end",
                "what": self._model_type,
                "logs": logs,
            }

        elif event.event_type == "train_end":
            return {
                "event": "train_end",
                "what": self._model_type,
            }

        else:
            logger.warning(f"Unknown event type: {event.event_type}")
            return None

    def _publish(self, message: dict):
        """Publish a message to the ZMQ socket.

        Uses ``jsonpickle.encode`` and ``send_string`` to match the format
        that LossViewer reads with ``jsonpickle.decode(sub.recv_string())``.

        Args:
            message: The message dictionary to publish.
        """
        try:
            import jsonpickle

            self._socket.send_string(jsonpickle.encode(message))
            logger.debug(f"Published progress: {message.get('event')}")
        except Exception as e:
            logger.error(f"Failed to publish progress: {e}")


def run_remote_training(
    config_path: str | None = None,
    room_id: str = "",
    worker_id: str | None = None,
    publish_port: int = 9001,
    on_progress: Callable[["ProgressEvent"], None] | None = None,
    timeout: int | None = None,
    config_content: str | None = None,
    path_mappings: dict[str, str] | None = None,
    spec: "TrainJobSpec | None" = None,
    model_type: str = "",
) -> "TrainingResult":
    """Run remote training with progress forwarding to ZMQ.

    This is the main entry point for SLEAP GUI integration. It submits a
    training job to a remote worker and forwards progress events to a local
    ZMQ socket for LossViewer to consume.

    There are two ways to specify the job:
    1. Pass a pre-built ``spec`` (TrainJobSpec) — preferred for GUI integration.
    2. Pass individual parameters (``config_path`` or ``config_content``, etc.).

    Args:
        config_path: Path to the training configuration file.
        room_id: The room ID to connect to.
        worker_id: Optional specific worker ID (None for auto-select).
        publish_port: ZMQ port for LossViewer progress (default: 9001).
        on_progress: Optional callback for progress events (in addition to ZMQ).
        timeout: Optional timeout in seconds.
        config_content: Serialized training config (YAML string) sent over
            datachannel. Alternative to config_path for GUI integration.
        path_mappings: Maps original client-side paths to resolved worker paths.
        spec: A pre-built TrainJobSpec. When provided, config_path,
            config_content, and other spec fields are ignored.
        model_type: Model type string for LossViewer filtering (e.g.,
            "centroid", "centered_instance"). LossViewer uses this to track
            the correct training job in multi-model pipelines.

    Returns:
        TrainingResult with model paths and final status.

    Raises:
        AuthenticationError: If not logged in.
        RoomNotFoundError: If room doesn't exist or no access.
        JobError: If training fails.

    Example:
        # From SLEAP GUI with pre-built spec
        spec = TrainJobSpec(
            config_content=yaml_string,
            labels_path="/mnt/data/labels.slp",
            path_mappings=resolved_mappings,
        )
        result = run_remote_training(
            spec=spec,
            room_id="my-room",
            publish_port=9001,
            model_type="centroid",
        )
        print(f"Model saved to: {result.model_path}")
    """
    from sleap_rtc.api import run_training, ProgressEvent

    # Create progress bridge for ZMQ forwarding
    bridge = RemoteProgressBridge(
        publish_port=publish_port, model_type=model_type
    )

    def progress_handler(event: ProgressEvent):
        """Handle progress by forwarding to ZMQ and optional callback."""
        bridge.on_progress(event)
        if on_progress:
            on_progress(event)

    # Run training with progress forwarding
    kwargs = dict(
        config_path=config_path,
        room_id=room_id,
        worker_id=worker_id,
        progress_callback=progress_handler,
        config_content=config_content,
        path_mappings=path_mappings,
        spec=spec,
        model_type=model_type,
    )
    if timeout is not None:
        kwargs["timeout"] = timeout
    with bridge:
        result = run_training(**kwargs)

    return result


def format_progress_line(event: "ProgressEvent") -> str:
    """Format a progress event as a CLI-style line.

    This matches the formatting from the cleanup-cli-ux changes for
    consistency between CLI and GUI progress displays.

    Args:
        event: The progress event to format.

    Returns:
        Formatted progress line string.
    """
    if event.event_type == "train_begin":
        lines = ["─" * 60, "Training started"]
        if event.wandb_url:
            lines.append(f"WandB: {event.wandb_url}")
        if event.total_epochs:
            lines.append(f"Total epochs: {event.total_epochs}")
        lines.append("─" * 60)
        return "\n".join(lines)

    elif event.event_type == "epoch_end":
        parts = [f"Epoch {event.epoch}"]
        if event.total_epochs:
            parts[0] = f"Epoch {event.epoch}/{event.total_epochs}"

        metrics = []
        if event.train_loss is not None:
            metrics.append(f"train_loss={event.train_loss:.4f}")
        if event.val_loss is not None:
            metrics.append(f"val_loss={event.val_loss:.4f}")
        if event.metrics:
            for key, value in event.metrics.items():
                if isinstance(value, float):
                    metrics.append(f"{key}={value:.4f}")
                else:
                    metrics.append(f"{key}={value}")

        if metrics:
            parts.append(" | ".join(metrics))

        return " - ".join(parts)

    elif event.event_type == "train_end":
        lines = ["─" * 60]
        if event.success:
            lines.append("Training completed successfully")
        else:
            lines.append("Training failed")
            if event.error_message:
                lines.append(f"Error: {event.error_message}")
        lines.append("─" * 60)
        return "\n".join(lines)

    else:
        return f"Unknown event: {event.event_type}"
