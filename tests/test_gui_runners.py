"""Tests for sleap_rtc.gui.runners module."""

import json
import sys
import pytest
from unittest.mock import MagicMock, patch

from sleap_rtc.api import ProgressEvent
from sleap_rtc.gui.runners import (
    RemoteProgressBridge,
    run_remote_training,
    format_progress_line,
)


# Create a mock zmq module for testing
@pytest.fixture
def mock_zmq():
    """Create and install mock zmq module."""
    mock_module = MagicMock()
    mock_module.PUB = 1
    mock_module.Context.return_value = MagicMock()

    # Patch zmq in sys.modules so imports find it
    with patch.dict(sys.modules, {"zmq": mock_module}):
        yield mock_module


# =============================================================================
# RemoteProgressBridge Tests
# =============================================================================


class TestRemoteProgressBridge:
    """Tests for RemoteProgressBridge class."""

    def test_init_default_port(self):
        """Should initialize with default port 9001."""
        bridge = RemoteProgressBridge()
        assert bridge._publish_port == 9001
        assert not bridge._started

    def test_init_custom_port(self):
        """Should accept custom port."""
        bridge = RemoteProgressBridge(publish_port=9999)
        assert bridge._publish_port == 9999

    def test_start_creates_socket(self, mock_zmq):
        """Should create ZMQ PUB socket on start."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        bridge = RemoteProgressBridge(publish_port=9001)
        bridge.start()

        mock_zmq.Context.assert_called_once()
        mock_context.socket.assert_called_once_with(mock_zmq.PUB)
        mock_socket.bind.assert_called_once_with("tcp://*:9001")
        assert bridge._started

    def test_stop_closes_socket(self, mock_zmq):
        """Should close socket and context on stop."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        bridge = RemoteProgressBridge()
        bridge.start()
        bridge.stop()

        mock_socket.close.assert_called_once()
        mock_context.term.assert_called_once()
        assert not bridge._started

    def test_context_manager(self, mock_zmq):
        """Should work as context manager."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        with RemoteProgressBridge() as bridge:
            assert bridge._started

        mock_socket.close.assert_called_once()

    def test_on_progress_train_begin(self, mock_zmq):
        """Should format train_begin event correctly."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(
            event_type="train_begin",
            total_epochs=100,
            wandb_url="https://wandb.ai/run/123",
        )

        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        # Check the published message
        mock_socket.send_multipart.assert_called_once()
        args = mock_socket.send_multipart.call_args[0][0]
        assert args[0] == b"progress"
        payload = json.loads(args[1])
        assert payload["event"] == "train_begin"
        assert payload["total_epochs"] == 100
        assert payload["wandb_url"] == "https://wandb.ai/run/123"

    def test_on_progress_epoch_end(self, mock_zmq):
        """Should format epoch_end event correctly."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(
            event_type="epoch_end",
            epoch=10,
            total_epochs=100,
            train_loss=0.5,
            val_loss=0.6,
            metrics={"learning_rate": 0.001},
        )

        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        args = mock_socket.send_multipart.call_args[0][0]
        payload = json.loads(args[1])
        assert payload["event"] == "epoch_end"
        assert payload["epoch"] == 10
        assert payload["total_epochs"] == 100
        assert payload["train_loss"] == 0.5
        assert payload["val_loss"] == 0.6
        assert payload["metrics"]["learning_rate"] == 0.001

    def test_on_progress_train_end_success(self, mock_zmq):
        """Should format train_end success event correctly."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(
            event_type="train_end",
            success=True,
        )

        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        args = mock_socket.send_multipart.call_args[0][0]
        payload = json.loads(args[1])
        assert payload["event"] == "train_end"
        assert payload["success"] is True

    def test_on_progress_train_end_failure(self, mock_zmq):
        """Should format train_end failure event correctly."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(
            event_type="train_end",
            success=False,
            error_message="CUDA OOM",
        )

        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        args = mock_socket.send_multipart.call_args[0][0]
        payload = json.loads(args[1])
        assert payload["event"] == "train_end"
        assert payload["success"] is False
        assert payload["error"] == "CUDA OOM"

    def test_on_progress_not_started(self):
        """Should not crash if bridge not started."""
        bridge = RemoteProgressBridge()
        event = ProgressEvent(event_type="train_begin")
        # Should not raise
        bridge.on_progress(event)


# =============================================================================
# format_progress_line Tests
# =============================================================================


class TestFormatProgressLine:
    """Tests for format_progress_line function."""

    def test_format_train_begin(self):
        """Should format train_begin with separators."""
        event = ProgressEvent(
            event_type="train_begin",
            total_epochs=100,
            wandb_url="https://wandb.ai/run/123",
        )
        line = format_progress_line(event)

        assert "Training started" in line
        assert "WandB: https://wandb.ai/run/123" in line
        assert "Total epochs: 100" in line
        assert "─" * 60 in line

    def test_format_epoch_end(self):
        """Should format epoch_end with metrics."""
        event = ProgressEvent(
            event_type="epoch_end",
            epoch=10,
            total_epochs=100,
            train_loss=0.5,
            val_loss=0.6,
        )
        line = format_progress_line(event)

        assert "Epoch 10/100" in line
        assert "train_loss=0.5000" in line
        assert "val_loss=0.6000" in line

    def test_format_epoch_end_no_total(self):
        """Should format epoch without total epochs."""
        event = ProgressEvent(
            event_type="epoch_end",
            epoch=10,
            train_loss=0.5,
        )
        line = format_progress_line(event)

        assert "Epoch 10 -" in line
        assert "/100" not in line

    def test_format_train_end_success(self):
        """Should format successful train_end."""
        event = ProgressEvent(
            event_type="train_end",
            success=True,
        )
        line = format_progress_line(event)

        assert "Training completed successfully" in line
        assert "─" * 60 in line

    def test_format_train_end_failure(self):
        """Should format failed train_end with error."""
        event = ProgressEvent(
            event_type="train_end",
            success=False,
            error_message="CUDA out of memory",
        )
        line = format_progress_line(event)

        assert "Training failed" in line
        assert "Error: CUDA out of memory" in line


# =============================================================================
# run_remote_training Tests
# =============================================================================


class TestRunRemoteTraining:
    """Tests for run_remote_training function."""

    @patch("sleap_rtc.api.run_training")
    def test_basic_call(self, mock_run_training, mock_zmq):
        """Should call run_training with correct args."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        mock_result = MagicMock()
        mock_run_training.return_value = mock_result

        result = run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
            worker_id="worker-1",
        )

        mock_run_training.assert_called_once()
        call_kwargs = mock_run_training.call_args[1]
        assert call_kwargs["config_path"] == "/path/to/config.json"
        assert call_kwargs["room_id"] == "test-room"
        assert call_kwargs["worker_id"] == "worker-1"
        assert result == mock_result

    @patch("sleap_rtc.api.run_training")
    def test_progress_forwarded_to_zmq(self, mock_run_training, mock_zmq):
        """Should forward progress events to ZMQ."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        # Make run_training call the progress handler DURING execution
        def simulate_training(*args, **kwargs):
            on_progress = kwargs.get("progress_callback")
            if on_progress:
                # Simulate progress events during training
                on_progress(ProgressEvent(event_type="train_begin"))
                on_progress(ProgressEvent(event_type="epoch_end", epoch=1))
                on_progress(ProgressEvent(event_type="train_end", success=True))
            return MagicMock()

        mock_run_training.side_effect = simulate_training

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
        )

        # Verify ZMQ publish was called for each event
        assert mock_socket.send_multipart.call_count == 3

    @patch("sleap_rtc.api.run_training")
    def test_custom_callback_called(self, mock_run_training, mock_zmq):
        """Should call custom progress callback."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        callback_events = []

        def my_callback(event):
            callback_events.append(event)

        # Make run_training call the progress handler DURING execution
        def simulate_training(*args, **kwargs):
            on_progress = kwargs.get("progress_callback")
            if on_progress:
                on_progress(ProgressEvent(event_type="train_begin"))
            return MagicMock()

        mock_run_training.side_effect = simulate_training

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
            on_progress=my_callback,
        )

        # Verify our custom callback was called
        assert len(callback_events) == 1
        assert callback_events[0].event_type == "train_begin"


# =============================================================================
# LossViewer Compatibility Test
# =============================================================================


class TestLossViewerCompatibility:
    """Tests verifying compatibility with SLEAP's LossViewer."""

    def test_message_format_matches_sleap_nn(self, mock_zmq):
        """Verify message format matches sleap-nn's ProgressReporterZMQ.

        sleap-nn sends messages as:
        - Topic: b"progress"
        - Payload: JSON with "event" field and event-specific data

        LossViewer expects this exact format.
        """
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        with RemoteProgressBridge() as bridge:
            # Test all event types
            events = [
                ProgressEvent(
                    event_type="train_begin",
                    total_epochs=50,
                    wandb_url="https://wandb.ai/test",
                ),
                ProgressEvent(
                    event_type="epoch_end",
                    epoch=1,
                    total_epochs=50,
                    train_loss=1.234,
                    val_loss=1.456,
                    metrics={"lr": 0.001},
                ),
                ProgressEvent(
                    event_type="train_end",
                    success=True,
                ),
            ]

            for event in events:
                bridge.on_progress(event)

        # Verify each message
        calls = mock_socket.send_multipart.call_args_list
        assert len(calls) == 3

        for call in calls:
            parts = call[0][0]
            # Must be multipart with topic + payload
            assert len(parts) == 2
            # Topic must be "progress"
            assert parts[0] == b"progress"
            # Payload must be valid JSON
            payload = json.loads(parts[1])
            # Must have "event" field
            assert "event" in payload
            assert payload["event"] in ["train_begin", "epoch_end", "train_end"]

    def test_epoch_end_has_required_fields(self, mock_zmq):
        """Verify epoch_end has fields LossViewer needs for plotting."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(
            event_type="epoch_end",
            epoch=10,
            train_loss=0.123,
            val_loss=0.456,
        )

        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        payload = json.loads(mock_socket.send_multipart.call_args[0][0][1])

        # LossViewer needs these fields for plotting
        assert "epoch" in payload
        assert "train_loss" in payload
        assert "val_loss" in payload
        assert isinstance(payload["epoch"], int)
        assert isinstance(payload["train_loss"], float)
        assert isinstance(payload["val_loss"], float)
