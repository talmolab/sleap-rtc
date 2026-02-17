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

    Bidirectional support:
    - **PUB socket** (publish_port): Sends progress updates TO LossViewer.
    - **SUB socket** (controller_port): Receives stop/cancel commands FROM
      LossViewer's controller PUB socket. Commands are forwarded over the
      RTC data channel via ``send_fn``.
    """

    def __init__(
        self,
        publish_port: int = 9001,
        controller_port: int = 9000,
        model_type: str = "",
    ):
        """Initialize the progress bridge.

        Args:
            publish_port: ZMQ port where LossViewer's SUB socket is bound.
            controller_port: ZMQ port where LossViewer's controller PUB
                socket is bound. The bridge connects a SUB socket here to
                receive stop/cancel commands.
            model_type: Model type string for the ``what`` field (e.g.,
                "centroid", "centered_instance"). LossViewer uses this to
                filter messages when training multiple models sequentially.
        """
        self._publish_port = publish_port
        self._controller_port = controller_port
        self._model_type = model_type
        self._socket = None
        self._sub_socket = None
        self._context = None
        self._started = False
        self._lock = threading.Lock()
        self._send_fn: Callable[[str], None] | None = None
        self._poll_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_epoch: int | None = None

    def set_model_type(self, model_type: str):
        """Update the model type for subsequent messages.

        Call this when switching between training phases in multi-model
        training (e.g., centroid → centered_instance in top-down).

        Args:
            model_type: The new model type string.
        """
        self._model_type = model_type

    def set_send_fn(self, send_fn: Callable[[str], None]):
        """Store a thread-safe send function for the RTC data channel.

        Called by ``run_remote_training`` once the data channel is open.
        The bridge uses this to forward stop/cancel commands to the worker.

        Args:
            send_fn: Thread-safe function that sends a string message over
                the RTC data channel.
        """
        self._send_fn = send_fn

    def start(self):
        """Start the ZMQ publisher and subscriber sockets.

        - PUB connects to LossViewer's SUB socket (publish_port).
        - SUB connects to LossViewer's controller PUB socket
          (controller_port) and starts a background poll thread.
        """
        import zmq

        with self._lock:
            if self._started:
                return

            self._context = zmq.Context()

            # PUB socket for sending progress to LossViewer
            self._socket = self._context.socket(zmq.PUB)
            self._socket.connect(f"tcp://127.0.0.1:{self._publish_port}")

            # SUB socket for receiving commands from LossViewer
            self._sub_socket = self._context.socket(zmq.SUB)
            self._sub_socket.subscribe(b"")  # Subscribe to all messages
            self._sub_socket.connect(
                f"tcp://127.0.0.1:{self._controller_port}"
            )

            self._started = True
            self._stop_event.clear()

            # Start background thread to poll for commands
            self._poll_thread = threading.Thread(
                target=self._poll_commands, daemon=True
            )
            self._poll_thread.start()

            logger.debug(
                f"RemoteProgressBridge connected to LossViewer "
                f"(publish={self._publish_port}, "
                f"controller={self._controller_port})"
            )

    def stop(self):
        """Stop the ZMQ sockets and poll thread."""
        with self._lock:
            if not self._started:
                return
            self._started = False

        # Signal the poll thread to stop and wait for it
        self._stop_event.set()
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=2.0)
            self._poll_thread = None

        with self._lock:
            if self._sub_socket:
                self._sub_socket.close()
                self._sub_socket = None
            if self._socket:
                self._socket.close()
                self._socket = None
            if self._context:
                self._context.term()
                self._context = None
            self._send_fn = None
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

        # Track explicit epoch_begin events to avoid duplicate synthesis.
        if event.event_type == "epoch_begin" and event.epoch is not None:
            self._last_epoch = event.epoch

        # Synthesize epoch_begin before epoch_end so LossViewer tracks
        # the epoch number (it only reads epoch from epoch_begin messages).
        # Subtract 1 to convert from 1-indexed (sleap-nn text output) to
        # 0-indexed (LossViewer internal convention).
        if (
            event.event_type == "epoch_end"
            and event.epoch is not None
            and event.epoch != self._last_epoch
        ):
            self._last_epoch = event.epoch
            self._publish(
                {
                    "event": "epoch_begin",
                    "what": self._model_type,
                    "epoch": max(0, event.epoch - 1),
                }
            )

        message = self._format_message(event)
        if message:
            self._publish(message)

    def on_raw_zmq_message(self, raw_msg: str):
        """Publish raw jsonpickle ZMQ message directly to LossViewer.

        This bypasses the ProgressEvent conversion and sends the original
        sleap-nn ZMQ message straight through, preserving all event types
        including batch_end (for scatter dots).

        Args:
            raw_msg: Raw jsonpickle-encoded string from the worker's
                ProgressReporter (received via ``PROGRESS_REPORT::``).
        """
        if not self._started or not self._socket:
            return
        try:
            import jsonpickle

            msg = jsonpickle.decode(raw_msg)
            if isinstance(msg, dict) and "what" not in msg:
                msg["what"] = self._model_type
            self._socket.send_string(jsonpickle.encode(msg))
        except Exception as e:
            logger.error(f"Failed to publish raw ZMQ progress: {e}")

    def _poll_commands(self):
        """Background thread: poll ZMQ SUB for stop/cancel from LossViewer.

        Reads messages from the controller SUB socket and forwards them
        as ``MSG_JOB_STOP`` / ``MSG_JOB_CANCEL`` over the RTC data channel.
        """
        import zmq

        from sleap_rtc.protocol import MSG_JOB_CANCEL, MSG_JOB_STOP

        while not self._stop_event.is_set():
            try:
                with self._lock:
                    sub = self._sub_socket
                if sub is None:
                    break

                # Poll with 100ms timeout so we can check stop_event
                if sub.poll(100, zmq.POLLIN):
                    raw = sub.recv_string(zmq.NOBLOCK)
                    try:
                        import jsonpickle

                        msg = jsonpickle.decode(raw)
                    except Exception:
                        logger.warning(f"Could not decode controller message: {raw!r}")
                        continue

                    command = msg.get("command") if isinstance(msg, dict) else None
                    if command in ("stop", "cancel"):
                        logger.info(f"LossViewer sent command: {command}")
                        rtc_msg = (
                            MSG_JOB_STOP if command == "stop" else MSG_JOB_CANCEL
                        )
                        send_fn = self._send_fn
                        if send_fn is not None:
                            try:
                                send_fn(rtc_msg)
                                logger.debug(f"Forwarded {rtc_msg} to worker")
                            except Exception as e:
                                logger.error(f"Failed to send {rtc_msg}: {e}")
                        else:
                            logger.warning(
                                f"Received {command} but no send_fn available"
                            )
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Error in command poll: {e}")
                break

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
    controller_port: int = 9000,
    on_progress: Callable[["ProgressEvent"], None] | None = None,
    timeout: int | None = None,
    config_content: str | None = None,
    path_mappings: dict[str, str] | None = None,
    spec: "TrainJobSpec | None" = None,
    model_type: str = "",
    on_log: Callable[[str], None] | None = None,
    on_model_type: "Callable[[str], None] | None" = None,
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
        controller_port: ZMQ port for LossViewer controller (default: 9000).
            The bridge listens here for stop/cancel commands.
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
        on_log: Optional callback invoked with each raw log line from the
            worker. When not provided, raw log lines are printed to stdout.
        on_model_type: Optional callback invoked when the worker switches
            model type during multi-model training. When not provided,
            defaults to calling ``bridge.set_model_type()``.

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

    # Create progress bridge for ZMQ forwarding (bidirectional)
    bridge = RemoteProgressBridge(
        publish_port=publish_port,
        controller_port=controller_port,
        model_type=model_type,
    )

    # Default on_log prints raw log lines to stdout
    log_fn = on_log if on_log is not None else lambda line: print(line, end="")

    def progress_handler(event: ProgressEvent):
        """Handle progress by forwarding to terminal and optional callback.

        LossViewer is now fed by raw ZMQ passthrough (on_raw_progress),
        so we no longer call bridge.on_progress() here.
        """
        # Print structured progress to terminal
        line = format_progress_line(event)
        if line:
            log_fn(line + "\n")
        if on_progress:
            on_progress(event)

    # Default on_model_type updates the bridge so LossViewer switches
    model_type_fn = on_model_type if on_model_type is not None else bridge.set_model_type

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
        on_log=log_fn,
        on_channel_ready=bridge.set_send_fn,
        on_raw_progress=bridge.on_raw_zmq_message,
        on_model_type=model_type_fn,
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
