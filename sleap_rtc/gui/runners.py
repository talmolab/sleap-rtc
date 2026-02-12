"""Remote training runners for SLEAP GUI integration.

This module provides the bridge between sleap-rtc's WebRTC-based progress
reporting and SLEAP's LossViewer which expects ZMQ messages.

The flow is:
    Worker (sleap-nn) → ZMQ → WebRTC DataChannel → Client → ZMQ → LossViewer
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from typing import TYPE_CHECKING, Callable

from loguru import logger

if TYPE_CHECKING:
    from sleap_rtc.api import ProgressEvent, TrainingResult


class RemoteProgressBridge:
    """Bridge WebRTC progress messages to ZMQ for LossViewer compatibility.

    This class receives ProgressEvent objects from the sleap-rtc training API
    and re-emits them via ZMQ in the format expected by SLEAP's LossViewer.

    The message format matches sleap-nn's ProgressReporterZMQ:
    - train_begin: {"event": "train_begin", "wandb_url": "..."}
    - epoch_end: {"event": "epoch_end", "epoch": N, "train_loss": X, ...}
    - train_end: {"event": "train_end", "success": bool}
    """

    def __init__(self, publish_port: int = 9001):
        """Initialize the progress bridge.

        Args:
            publish_port: ZMQ PUB socket port for LossViewer (default: 9001).
        """
        self._publish_port = publish_port
        self._socket = None
        self._context = None
        self._started = False
        self._lock = threading.Lock()

    def start(self):
        """Start the ZMQ publisher socket."""
        import zmq

        with self._lock:
            if self._started:
                return

            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.PUB)
            self._socket.bind(f"tcp://*:{self._publish_port}")
            self._started = True
            logger.debug(f"RemoteProgressBridge started on port {self._publish_port}")

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

        # Convert to sleap-nn compatible message format
        message = self._format_message(event)
        if message:
            self._publish(message)

    def _format_message(self, event: "ProgressEvent") -> dict | None:
        """Convert ProgressEvent to sleap-nn ZMQ message format.

        Args:
            event: The progress event to format.

        Returns:
            Dictionary in sleap-nn's ProgressReporterZMQ format.
        """
        if event.event_type == "train_begin":
            msg = {"event": "train_begin"}
            if event.wandb_url:
                msg["wandb_url"] = event.wandb_url
            if event.total_epochs:
                msg["total_epochs"] = event.total_epochs
            return msg

        elif event.event_type == "epoch_end":
            msg = {
                "event": "epoch_end",
                "epoch": event.epoch,
            }
            if event.train_loss is not None:
                msg["train_loss"] = event.train_loss
            if event.val_loss is not None:
                msg["val_loss"] = event.val_loss
            if event.total_epochs is not None:
                msg["total_epochs"] = event.total_epochs
            if event.metrics:
                msg["metrics"] = event.metrics
            return msg

        elif event.event_type == "train_end":
            msg = {
                "event": "train_end",
                "success": event.success if event.success is not None else True,
            }
            if event.error_message:
                msg["error"] = event.error_message
            return msg

        else:
            logger.warning(f"Unknown event type: {event.event_type}")
            return None

    def _publish(self, message: dict):
        """Publish a message to the ZMQ socket.

        Args:
            message: The message dictionary to publish.
        """
        try:
            # sleap-nn sends messages as JSON with topic prefix
            topic = b"progress"
            payload = json.dumps(message).encode("utf-8")
            self._socket.send_multipart([topic, payload])
            logger.debug(f"Published progress: {message.get('event')}")
        except Exception as e:
            logger.error(f"Failed to publish progress: {e}")


def run_remote_training(
    config_path: str,
    room_id: str,
    worker_id: str | None = None,
    publish_port: int = 9001,
    on_progress: Callable[["ProgressEvent"], None] | None = None,
    timeout: int | None = None,
) -> "TrainingResult":
    """Run remote training with progress forwarding to ZMQ.

    This is the main entry point for SLEAP GUI integration. It submits a
    training job to a remote worker and forwards progress events to a local
    ZMQ socket for LossViewer to consume.

    Args:
        config_path: Path to the training configuration file.
        room_id: The room ID to connect to.
        worker_id: Optional specific worker ID (None for auto-select).
        publish_port: ZMQ port for LossViewer progress (default: 9001).
        on_progress: Optional callback for progress events (in addition to ZMQ).
        timeout: Optional timeout in seconds.

    Returns:
        TrainingResult with model paths and final status.

    Raises:
        AuthenticationError: If not logged in.
        RoomNotFoundError: If room doesn't exist or no access.
        JobError: If training fails.

    Example:
        # From SLEAP GUI
        result = run_remote_training(
            config_path="/path/to/config.json",
            room_id="my-room",
            publish_port=9001,  # LossViewer listens here
        )
        print(f"Model saved to: {result.model_path}")
    """
    from sleap_rtc.api import run_training, ProgressEvent

    # Create progress bridge for ZMQ forwarding
    bridge = RemoteProgressBridge(publish_port=publish_port)

    def progress_handler(event: ProgressEvent):
        """Handle progress by forwarding to ZMQ and optional callback."""
        bridge.on_progress(event)
        if on_progress:
            on_progress(event)

    # Run training with progress forwarding
    with bridge:
        result = run_training(
            config_path=config_path,
            room_id=room_id,
            worker_id=worker_id,
            on_progress=progress_handler,
            timeout=timeout,
        )

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
