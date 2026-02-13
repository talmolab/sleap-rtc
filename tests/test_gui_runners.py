"""Tests for sleap_rtc.gui.runners module."""

import sys
import pytest
from unittest.mock import MagicMock, patch

import jsonpickle

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


def _decode_zmq_message(mock_socket) -> dict:
    """Helper to decode the last ZMQ message sent on a mock socket."""
    encoded_str = mock_socket.send_string.call_args[0][0]
    return jsonpickle.decode(encoded_str)


def _decode_all_zmq_messages(mock_socket) -> list[dict]:
    """Helper to decode all ZMQ messages sent on a mock socket."""
    return [
        jsonpickle.decode(call[0][0])
        for call in mock_socket.send_string.call_args_list
    ]


# =============================================================================
# RemoteProgressBridge Tests
# =============================================================================


class TestRemoteProgressBridge:
    """Tests for RemoteProgressBridge class."""

    def test_init_default_port(self):
        """Should initialize with default port 9001."""
        bridge = RemoteProgressBridge()
        assert bridge._publish_port == 9001
        assert bridge._model_type == ""
        assert not bridge._started

    def test_init_custom_port_and_model_type(self):
        """Should accept custom port and model type."""
        bridge = RemoteProgressBridge(publish_port=9999, model_type="centroid")
        assert bridge._publish_port == 9999
        assert bridge._model_type == "centroid"

    def test_set_model_type(self):
        """Should update model type for subsequent messages."""
        bridge = RemoteProgressBridge(model_type="centroid")
        assert bridge._model_type == "centroid"
        bridge.set_model_type("centered_instance")
        assert bridge._model_type == "centered_instance"

    def test_start_connects_socket(self, mock_zmq):
        """Should create ZMQ PUB socket and connect (not bind) on start."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        bridge = RemoteProgressBridge(publish_port=9001)
        bridge.start()

        mock_zmq.Context.assert_called_once()
        mock_context.socket.assert_called_once_with(mock_zmq.PUB)
        # Must connect (not bind) — LossViewer owns the bind
        mock_socket.connect.assert_called_once_with("tcp://127.0.0.1:9001")
        mock_socket.bind.assert_not_called()
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

    def test_on_progress_not_started(self):
        """Should not crash if bridge not started."""
        bridge = RemoteProgressBridge()
        event = ProgressEvent(event_type="train_begin")
        # Should not raise
        bridge.on_progress(event)


# =============================================================================
# LossViewer Message Format Tests
# =============================================================================


class TestLossViewerMessageFormat:
    """Tests verifying message format matches SLEAP's LossViewer expectations.

    LossViewer (sleap/gui/widgets/monitor.py) reads messages with:
        msg = jsonpickle.decode(self.sub.recv_string())

    And expects:
    - "event": event type string
    - "what": model type for filtering
    - "logs": dict with "train/loss" and "val/loss" keys (for epoch_end)
    """

    def test_uses_send_string_not_multipart(self, mock_zmq):
        """Must use send_string, not send_multipart."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(event_type="train_begin")
        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        mock_socket.send_string.assert_called_once()
        mock_socket.send_multipart.assert_not_called()

    def test_uses_jsonpickle_encoding(self, mock_zmq):
        """Must use jsonpickle.encode, decodable by jsonpickle.decode."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(event_type="train_begin")
        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        encoded_str = mock_socket.send_string.call_args[0][0]
        # Must be decodable by jsonpickle (what LossViewer uses)
        decoded = jsonpickle.decode(encoded_str)
        assert isinstance(decoded, dict)
        assert decoded["event"] == "train_begin"

    def test_train_begin_format(self, mock_zmq):
        """train_begin must include what field and optional wandb_url."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(
            event_type="train_begin",
            wandb_url="https://wandb.ai/run/123",
        )

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_progress(event)

        msg = _decode_zmq_message(mock_socket)
        assert msg["event"] == "train_begin"
        assert msg["what"] == "centroid"
        assert msg["wandb_url"] == "https://wandb.ai/run/123"

    def test_epoch_begin_format(self, mock_zmq):
        """epoch_begin must include what and epoch fields."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(event_type="epoch_begin", epoch=5)

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_progress(event)

        msg = _decode_zmq_message(mock_socket)
        assert msg["event"] == "epoch_begin"
        assert msg["what"] == "centroid"
        assert msg["epoch"] == 5

    def test_epoch_end_format_with_logs(self, mock_zmq):
        """epoch_end must wrap loss data in logs dict with sleap-nn keys."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(
            event_type="epoch_end",
            epoch=10,
            train_loss=0.0045,
            val_loss=0.0051,
            metrics={"learning_rate": 0.001},
        )

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_progress(event)

        msg = _decode_zmq_message(mock_socket)
        assert msg["event"] == "epoch_end"
        assert msg["what"] == "centroid"
        # Loss data must be in "logs" dict with sleap-nn naming
        assert "logs" in msg
        assert msg["logs"]["train/loss"] == 0.0045
        assert msg["logs"]["val/loss"] == 0.0051
        assert msg["logs"]["learning_rate"] == 0.001
        # Loss must NOT be at top level (old format)
        assert "train_loss" not in msg
        assert "val_loss" not in msg

    def test_epoch_end_partial_loss(self, mock_zmq):
        """epoch_end with only train_loss should still work."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(
            event_type="epoch_end",
            epoch=1,
            train_loss=0.5,
        )

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_progress(event)

        msg = _decode_zmq_message(mock_socket)
        assert msg["logs"]["train/loss"] == 0.5
        assert "val/loss" not in msg["logs"]

    def test_train_end_format(self, mock_zmq):
        """train_end must include what field."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(event_type="train_end", success=True)

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_progress(event)

        msg = _decode_zmq_message(mock_socket)
        assert msg["event"] == "train_end"
        assert msg["what"] == "centroid"

    def test_model_type_in_all_events(self, mock_zmq):
        """All event types must include the what field."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        events = [
            ProgressEvent(event_type="train_begin"),
            ProgressEvent(event_type="epoch_begin", epoch=0),
            ProgressEvent(event_type="epoch_end", epoch=0, train_loss=0.5),
            ProgressEvent(event_type="train_end", success=True),
        ]

        with RemoteProgressBridge(model_type="centered_instance") as bridge:
            for event in events:
                bridge.on_progress(event)

        messages = _decode_all_zmq_messages(mock_socket)
        assert len(messages) == 4
        for msg in messages:
            assert msg["what"] == "centered_instance"

    def test_model_type_updates(self, mock_zmq):
        """set_model_type should affect subsequent messages."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_progress(ProgressEvent(event_type="train_begin"))
            bridge.set_model_type("centered_instance")
            bridge.on_progress(ProgressEvent(event_type="train_begin"))

        messages = _decode_all_zmq_messages(mock_socket)
        assert messages[0]["what"] == "centroid"
        assert messages[1]["what"] == "centered_instance"

    def test_unknown_event_type(self, mock_zmq):
        """Unknown event types should be silently dropped."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        event = ProgressEvent(event_type="unknown_event")

        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        mock_socket.send_string.assert_not_called()


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
    def test_model_type_passed_to_bridge(self, mock_run_training, mock_zmq):
        """Should pass model_type to RemoteProgressBridge."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        def simulate_training(*args, **kwargs):
            on_progress = kwargs.get("progress_callback")
            if on_progress:
                on_progress(ProgressEvent(event_type="train_begin"))
            return MagicMock()

        mock_run_training.side_effect = simulate_training

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
            model_type="centroid",
        )

        msg = _decode_zmq_message(mock_socket)
        assert msg["what"] == "centroid"

    @patch("sleap_rtc.api.run_training")
    def test_progress_forwarded_to_zmq(self, mock_run_training, mock_zmq):
        """Should forward progress events to ZMQ."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        def simulate_training(*args, **kwargs):
            on_progress = kwargs.get("progress_callback")
            if on_progress:
                on_progress(ProgressEvent(event_type="train_begin"))
                on_progress(
                    ProgressEvent(event_type="epoch_end", epoch=1, train_loss=0.5)
                )
                on_progress(ProgressEvent(event_type="train_end", success=True))
            return MagicMock()

        mock_run_training.side_effect = simulate_training

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
        )

        assert mock_socket.send_string.call_count == 3

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

        assert len(callback_events) == 1
        assert callback_events[0].event_type == "train_begin"

    @patch("sleap_rtc.api.run_training")
    def test_model_type_passed_to_run_training(self, mock_run_training, mock_zmq):
        """Should pass model_type through to run_training API call."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        mock_run_training.return_value = MagicMock()

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
            model_type="centroid",
        )

        call_kwargs = mock_run_training.call_args[1]
        assert call_kwargs["model_type"] == "centroid"
