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
    """Create and install mock zmq module.

    The mock context's socket() method returns different mocks for PUB and
    SUB socket types. The SUB socket's poll() returns 0 (no messages) so the
    RemoteProgressBridge poll thread stays idle during tests.
    """
    mock_module = MagicMock()
    mock_module.PUB = 1
    mock_module.SUB = 2
    mock_module.POLLIN = 1
    mock_module.NOBLOCK = 1

    mock_context = MagicMock()

    def _make_socket(socket_type):
        sock = MagicMock()
        if socket_type == mock_module.SUB:
            sock.poll.return_value = 0  # No messages — poll thread stays idle
        return sock

    mock_context.socket.side_effect = _make_socket
    mock_module.Context.return_value = mock_context

    # Patch zmq in sys.modules so imports find it
    with patch.dict(sys.modules, {"zmq": mock_module}):
        yield mock_module


def _setup_zmq_mocks(mock_zmq):
    """Set up ZMQ mocks for tests that directly interact with sockets.

    Returns the PUB socket mock (the one used for send_string).
    Tests that need the PUB socket should call this instead of setting up
    mock_context.socket.return_value manually.
    """
    mock_context = mock_zmq.Context.return_value
    # The fixture's side_effect creates fresh mocks for each socket() call.
    # Create PUB and SUB sockets to capture their mocks, then reset the
    # side_effect so the bridge's start() creates fresh ones with the same
    # behavior.
    pub_socket = MagicMock()
    sub_socket = MagicMock()
    sub_socket.poll.return_value = 0

    def _make_socket(socket_type):
        if socket_type == mock_zmq.PUB:
            return pub_socket
        return sub_socket

    mock_context.socket.side_effect = _make_socket
    return pub_socket


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
        """Should create ZMQ PUB and SUB sockets on start."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        bridge = RemoteProgressBridge(publish_port=9001)
        bridge.start()

        # PUB socket must connect (not bind) — LossViewer owns the bind
        mock_socket.connect.assert_called_once_with("tcp://127.0.0.1:9001")
        mock_socket.bind.assert_not_called()
        # SUB socket also created and connected
        assert bridge._sub_socket is not None
        assert bridge._started

        bridge.stop()

    def test_stop_closes_socket(self, mock_zmq):
        """Should close both PUB and SUB sockets on stop."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        bridge = RemoteProgressBridge()
        bridge.start()
        sub_socket = bridge._sub_socket
        bridge.stop()

        mock_socket.close.assert_called_once()
        sub_socket.close.assert_called_once()
        assert not bridge._started

    def test_context_manager(self, mock_zmq):
        """Should work as context manager."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        with RemoteProgressBridge() as bridge:
            assert bridge._started
            sub_socket = bridge._sub_socket

        mock_socket.close.assert_called_once()
        sub_socket.close.assert_called_once()

    def test_on_progress_not_started(self):
        """Should not crash if bridge not started."""
        bridge = RemoteProgressBridge()
        event = ProgressEvent(event_type="train_begin")
        # Should not raise
        bridge.on_progress(event)

    def test_on_raw_zmq_message(self, mock_zmq):
        """on_raw_zmq_message should decode, inject 'what' if empty, and re-encode."""
        import jsonpickle

        mock_socket = _setup_zmq_mocks(mock_zmq)

        raw_msg = jsonpickle.encode({"event": "batch_end", "what": "centroid"})

        with RemoteProgressBridge() as bridge:
            bridge.on_raw_zmq_message(raw_msg)

        # Should preserve existing non-empty 'what'
        sent = jsonpickle.decode(mock_socket.send_string.call_args[0][0])
        assert sent["event"] == "batch_end"
        assert sent["what"] == "centroid"

    def test_on_raw_zmq_message_injects_what(self, mock_zmq):
        """on_raw_zmq_message should inject model_type when 'what' is empty."""
        import jsonpickle

        mock_socket = _setup_zmq_mocks(mock_zmq)

        # sleap-nn sends what="" by default
        raw_msg = jsonpickle.encode({"event": "batch_end", "what": ""})

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_raw_zmq_message(raw_msg)

        sent = jsonpickle.decode(mock_socket.send_string.call_args[0][0])
        assert sent["what"] == "centroid"

    def test_on_raw_zmq_message_not_started(self):
        """on_raw_zmq_message should not crash if bridge not started."""
        bridge = RemoteProgressBridge()
        # Should not raise
        bridge.on_raw_zmq_message('{"event": "batch_end"}')


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
        mock_socket = _setup_zmq_mocks(mock_zmq)

        event = ProgressEvent(event_type="train_begin")
        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        mock_socket.send_string.assert_called_once()
        mock_socket.send_multipart.assert_not_called()

    def test_uses_jsonpickle_encoding(self, mock_zmq):
        """Must use jsonpickle.encode, decodable by jsonpickle.decode."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

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
        mock_socket = _setup_zmq_mocks(mock_zmq)

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
        mock_socket = _setup_zmq_mocks(mock_zmq)

        event = ProgressEvent(event_type="epoch_begin", epoch=5)

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_progress(event)

        msg = _decode_zmq_message(mock_socket)
        assert msg["event"] == "epoch_begin"
        assert msg["what"] == "centroid"
        assert msg["epoch"] == 5

    def test_epoch_end_format_with_logs(self, mock_zmq):
        """epoch_end must wrap loss data in logs dict with sleap-nn keys."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

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
        mock_socket = _setup_zmq_mocks(mock_zmq)

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
        mock_socket = _setup_zmq_mocks(mock_zmq)

        event = ProgressEvent(event_type="train_end", success=True)

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_progress(event)

        msg = _decode_zmq_message(mock_socket)
        assert msg["event"] == "train_end"
        assert msg["what"] == "centroid"

    def test_model_type_in_all_events(self, mock_zmq):
        """All event types must include the what field."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

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
        mock_socket = _setup_zmq_mocks(mock_zmq)

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_progress(ProgressEvent(event_type="train_begin"))
            bridge.set_model_type("centered_instance")
            bridge.on_progress(ProgressEvent(event_type="train_begin"))

        messages = _decode_all_zmq_messages(mock_socket)
        assert messages[0]["what"] == "centroid"
        assert messages[1]["what"] == "centered_instance"

    def test_epoch_begin_synthesized_for_epoch_end(self, mock_zmq):
        """epoch_end should auto-emit epoch_begin so LossViewer tracks epoch."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        event = ProgressEvent(
            event_type="epoch_end", epoch=3, train_loss=0.1, val_loss=0.2
        )

        with RemoteProgressBridge(model_type="centroid") as bridge:
            bridge.on_progress(event)

        messages = _decode_all_zmq_messages(mock_socket)
        assert len(messages) == 2
        # First message: synthesized epoch_begin (0-indexed: 3 → 2)
        assert messages[0]["event"] == "epoch_begin"
        assert messages[0]["epoch"] == 2
        assert messages[0]["what"] == "centroid"
        # Second message: the actual epoch_end
        assert messages[1]["event"] == "epoch_end"
        assert messages[1]["logs"]["train/loss"] == 0.1

    def test_epoch_begin_not_duplicated(self, mock_zmq):
        """Explicit epoch_begin prevents duplicate synthesis."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        with RemoteProgressBridge(model_type="centroid") as bridge:
            # Explicit epoch_begin
            bridge.on_progress(ProgressEvent(event_type="epoch_begin", epoch=1))
            # epoch_end for same epoch — should NOT synthesize another epoch_begin
            bridge.on_progress(
                ProgressEvent(event_type="epoch_end", epoch=1, train_loss=0.5)
            )

        messages = _decode_all_zmq_messages(mock_socket)
        assert len(messages) == 2
        assert messages[0]["event"] == "epoch_begin"
        assert messages[1]["event"] == "epoch_end"

    def test_epoch_begin_only_on_new_epoch(self, mock_zmq):
        """Multiple epoch_end with same epoch should only synthesize once."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        with RemoteProgressBridge() as bridge:
            bridge.on_progress(
                ProgressEvent(event_type="epoch_end", epoch=1, train_loss=0.5)
            )
            bridge.on_progress(
                ProgressEvent(event_type="epoch_end", epoch=1, train_loss=0.4)
            )
            bridge.on_progress(
                ProgressEvent(event_type="epoch_end", epoch=2, train_loss=0.3)
            )

        messages = _decode_all_zmq_messages(mock_socket)
        events = [m["event"] for m in messages]
        # epoch_begin(1), epoch_end, epoch_end, epoch_begin(2), epoch_end
        assert events == [
            "epoch_begin", "epoch_end", "epoch_end",
            "epoch_begin", "epoch_end",
        ]

    def test_unknown_event_type(self, mock_zmq):
        """Unknown event types should be silently dropped."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

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
        mock_socket = _setup_zmq_mocks(mock_zmq)

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
    def test_on_raw_progress_wired_to_bridge(self, mock_run_training, mock_zmq):
        """Should wire on_raw_progress to bridge.on_raw_zmq_message."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        mock_run_training.return_value = MagicMock()

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
            model_type="centroid",
        )

        call_kwargs = mock_run_training.call_args[1]
        assert call_kwargs["on_raw_progress"] is not None

    @patch("sleap_rtc.api.run_training")
    def test_raw_zmq_passthrough(self, mock_run_training, mock_zmq):
        """Should forward raw ZMQ messages directly to LossViewer socket."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        def simulate_training(*args, **kwargs):
            on_raw = kwargs.get("on_raw_progress")
            if on_raw:
                on_raw('{"event": "batch_end", "what": "centroid"}')
                on_raw('{"event": "epoch_end", "what": "centroid"}')
            return MagicMock()

        mock_run_training.side_effect = simulate_training

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
        )

        assert mock_socket.send_string.call_count == 2
        # Raw strings should be passed through without re-encoding
        mock_socket.send_string.assert_any_call(
            '{"event": "batch_end", "what": "centroid"}'
        )
        mock_socket.send_string.assert_any_call(
            '{"event": "epoch_end", "what": "centroid"}'
        )

    @patch("sleap_rtc.api.run_training")
    def test_progress_callback_no_longer_publishes_to_zmq(self, mock_run_training, mock_zmq):
        """Progress callback should NOT publish to ZMQ (raw passthrough handles that)."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

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

        # No ZMQ messages from progress_callback — LossViewer is fed by raw passthrough
        mock_socket.send_string.assert_not_called()

    @patch("sleap_rtc.api.run_training")
    def test_custom_callback_called(self, mock_run_training, mock_zmq):
        """Should call custom progress callback."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

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
        mock_socket = _setup_zmq_mocks(mock_zmq)

        mock_run_training.return_value = MagicMock()

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
            model_type="centroid",
        )

        call_kwargs = mock_run_training.call_args[1]
        assert call_kwargs["model_type"] == "centroid"

    @patch("sleap_rtc.api.run_training")
    def test_on_log_passed_to_run_training(self, mock_run_training, mock_zmq):
        """Should pass on_log through to run_training API call."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        mock_run_training.return_value = MagicMock()

        log_lines = []
        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
            on_log=lambda line: log_lines.append(line),
        )

        # on_log should be passed through as-is
        call_kwargs = mock_run_training.call_args[1]
        assert call_kwargs["on_log"] is not None

    @patch("sleap_rtc.api.run_training")
    def test_default_on_log_prints_to_stdout(self, mock_run_training, mock_zmq, capsys):
        """When on_log is not provided, raw log lines should print to stdout."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        def simulate_training(*args, **kwargs):
            # Simulate the on_log callback being invoked with a raw log line
            on_log = kwargs.get("on_log")
            if on_log:
                on_log("Epoch 1/10: loss=0.5\n")
            return MagicMock()

        mock_run_training.side_effect = simulate_training

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
        )

        captured = capsys.readouterr()
        assert "Epoch 1/10: loss=0.5" in captured.out

    @patch("sleap_rtc.api.run_training")
    def test_custom_on_log_receives_lines(self, mock_run_training, mock_zmq):
        """Custom on_log callback should receive raw log lines."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        log_lines = []

        def simulate_training(*args, **kwargs):
            on_log = kwargs.get("on_log")
            if on_log:
                on_log("line 1\n")
                on_log("line 2\n")
            return MagicMock()

        mock_run_training.side_effect = simulate_training

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
            on_log=lambda line: log_lines.append(line),
        )

        assert log_lines == ["line 1\n", "line 2\n"]

    @patch("sleap_rtc.api.run_training")
    def test_progress_also_printed_to_terminal(self, mock_run_training, mock_zmq):
        """Structured progress events should also be formatted and sent to on_log."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        log_lines = []

        def simulate_training(*args, **kwargs):
            on_progress = kwargs.get("progress_callback")
            if on_progress:
                on_progress(
                    ProgressEvent(event_type="epoch_end", epoch=1, train_loss=0.5)
                )
            return MagicMock()

        mock_run_training.side_effect = simulate_training

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
            on_log=lambda line: log_lines.append(line),
        )

        # Should have received the formatted progress line
        assert len(log_lines) == 1
        assert "Epoch 1" in log_lines[0]
        assert "train_loss=0.5" in log_lines[0]

    @patch("sleap_rtc.api.run_training")
    def test_on_channel_ready_wired_to_bridge(self, mock_run_training, mock_zmq):
        """Should pass bridge.set_send_fn as on_channel_ready."""
        mock_socket = _setup_zmq_mocks(mock_zmq)

        mock_run_training.return_value = MagicMock()

        run_remote_training(
            config_path="/path/to/config.json",
            room_id="test-room",
        )

        call_kwargs = mock_run_training.call_args[1]
        assert call_kwargs["on_channel_ready"] is not None


# =============================================================================
# Stop/Cancel Command Tests
# =============================================================================


class TestStopCancelCommands:
    """Tests for stop/cancel command forwarding from LossViewer to worker."""

    def test_set_send_fn(self):
        """set_send_fn should store the send function."""
        bridge = RemoteProgressBridge()
        send_fn = MagicMock()
        bridge.set_send_fn(send_fn)
        assert bridge._send_fn is send_fn

    def test_poll_commands_stop(self, mock_zmq):
        """Should forward 'stop' command as MSG_JOB_STOP via send_fn."""
        import jsonpickle

        from sleap_rtc.protocol import MSG_JOB_STOP

        mock_socket = _setup_zmq_mocks(mock_zmq)
        mock_context = mock_zmq.Context.return_value

        # Get the SUB socket that will be created
        sub_sockets = []
        original_side_effect = mock_context.socket.side_effect

        def _capture_sockets(socket_type):
            sock = original_side_effect(socket_type)
            if socket_type == mock_zmq.SUB:
                sub_sockets.append(sock)
            return sock

        mock_context.socket.side_effect = _capture_sockets

        bridge = RemoteProgressBridge()
        send_fn = MagicMock()
        bridge.set_send_fn(send_fn)

        # Configure the SUB socket to return a stop command once, then nothing
        bridge.start()
        sub_sock = sub_sockets[0]
        sub_sock.poll.side_effect = [1, 0, 0, 0, 0]  # Message available once
        sub_sock.recv_string.return_value = jsonpickle.encode({"command": "stop"})

        # Give the poll thread time to process
        import time

        time.sleep(0.3)
        bridge.stop()

        send_fn.assert_called_with(MSG_JOB_STOP)

    def test_poll_commands_cancel(self, mock_zmq):
        """Should forward 'cancel' command as MSG_JOB_CANCEL via send_fn."""
        import jsonpickle

        from sleap_rtc.protocol import MSG_JOB_CANCEL

        mock_socket = _setup_zmq_mocks(mock_zmq)
        mock_context = mock_zmq.Context.return_value

        sub_sockets = []
        original_side_effect = mock_context.socket.side_effect

        def _capture_sockets(socket_type):
            sock = original_side_effect(socket_type)
            if socket_type == mock_zmq.SUB:
                sub_sockets.append(sock)
            return sock

        mock_context.socket.side_effect = _capture_sockets

        bridge = RemoteProgressBridge()
        send_fn = MagicMock()
        bridge.set_send_fn(send_fn)

        bridge.start()
        sub_sock = sub_sockets[0]
        sub_sock.poll.side_effect = [1, 0, 0, 0, 0]
        sub_sock.recv_string.return_value = jsonpickle.encode({"command": "cancel"})

        import time

        time.sleep(0.3)
        bridge.stop()

        send_fn.assert_called_with(MSG_JOB_CANCEL)

    def test_poll_no_send_fn(self, mock_zmq):
        """Should not crash if stop received but no send_fn set."""
        import jsonpickle

        mock_socket = _setup_zmq_mocks(mock_zmq)
        mock_context = mock_zmq.Context.return_value

        sub_sockets = []
        original_side_effect = mock_context.socket.side_effect

        def _capture_sockets(socket_type):
            sock = original_side_effect(socket_type)
            if socket_type == mock_zmq.SUB:
                sub_sockets.append(sock)
            return sock

        mock_context.socket.side_effect = _capture_sockets

        bridge = RemoteProgressBridge()
        # Don't set send_fn

        bridge.start()
        sub_sock = sub_sockets[0]
        sub_sock.poll.side_effect = [1, 0, 0, 0, 0]
        sub_sock.recv_string.return_value = jsonpickle.encode({"command": "stop"})

        import time

        time.sleep(0.3)
        bridge.stop()
        # Should not raise — just log a warning

    def test_controller_port_configurable(self):
        """Should accept custom controller_port."""
        bridge = RemoteProgressBridge(controller_port=8888)
        assert bridge._controller_port == 8888


# =============================================================================
# JobExecutor Stop/Cancel Tests
# =============================================================================


class TestJobExecutorStopCancel:
    """Tests for JobExecutor stop/cancel methods."""

    def test_stop_running_job_sends_sigint(self):
        """stop_running_job should send SIGINT to the process."""
        from sleap_rtc.worker.job_executor import JobExecutor

        executor = JobExecutor(worker=MagicMock(), capabilities=MagicMock())
        mock_process = MagicMock()
        mock_process.returncode = None  # Still running
        executor._running_process = mock_process

        executor.stop_running_job()

        import signal

        mock_process.send_signal.assert_called_once_with(signal.SIGINT)

    def test_cancel_running_job_sends_sigterm(self):
        """cancel_running_job should call terminate() on the process."""
        from sleap_rtc.worker.job_executor import JobExecutor

        executor = JobExecutor(worker=MagicMock(), capabilities=MagicMock())
        mock_process = MagicMock()
        mock_process.returncode = None
        executor._running_process = mock_process

        executor.cancel_running_job()

        mock_process.terminate.assert_called_once()

    def test_stop_no_running_process(self):
        """stop_running_job should not crash when no process is running."""
        from sleap_rtc.worker.job_executor import JobExecutor

        executor = JobExecutor(worker=MagicMock(), capabilities=MagicMock())
        executor._running_process = None

        # Should not raise
        executor.stop_running_job()

    def test_stop_already_exited_process(self):
        """stop_running_job should not signal an already-exited process."""
        from sleap_rtc.worker.job_executor import JobExecutor

        executor = JobExecutor(worker=MagicMock(), capabilities=MagicMock())
        mock_process = MagicMock()
        mock_process.returncode = 0  # Already exited
        executor._running_process = mock_process

        executor.stop_running_job()

        mock_process.send_signal.assert_not_called()
