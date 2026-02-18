"""Tests for Stop Early SIGINT behaviour.

When a CONTROL_COMMAND with {"command": "stop"} is forwarded through
send_control_message, the running subprocess must also receive SIGINT so
that PyTorch Lightning exits immediately instead of hanging in validation.
"""

import json
import signal
from unittest.mock import MagicMock

from sleap_rtc.worker.job_executor import JobExecutor


class TestStopEarlySendsSignal:

    def _make_executor(self, running=True):
        executor = JobExecutor(worker=MagicMock(), capabilities=MagicMock())
        executor._progress_reporter = MagicMock()
        mock_process = MagicMock()
        mock_process.returncode = None if running else 0
        executor._running_process = mock_process
        return executor

    def test_stop_command_sends_sigint_to_subprocess(self):
        """send_control_message('{"command":"stop"}') must SIGINT the running process."""
        executor = self._make_executor()
        executor.send_control_message('{"command": "stop"}')
        executor._running_process.send_signal.assert_called_once_with(signal.SIGINT)

    def test_stop_command_still_forwards_zmq_message(self):
        """ZMQ forwarding must not be skipped when SIGINT is also sent."""
        executor = self._make_executor()
        executor.send_control_message('{"command": "stop"}')
        executor._progress_reporter.send_control_message.assert_called_once_with(
            '{"command": "stop"}'
        )

    def test_non_stop_command_does_not_send_sigint(self):
        """Non-stop ZMQ commands must not signal the subprocess."""
        executor = self._make_executor()
        executor.send_control_message('{"command": "pause"}')
        executor._running_process.send_signal.assert_not_called()

    def test_stop_command_does_not_sigint_already_exited_process(self):
        """SIGINT must not be sent when the process has already exited (returncode set)."""
        executor = self._make_executor(running=False)
        executor.send_control_message('{"command": "stop"}')
        executor._running_process.send_signal.assert_not_called()

    def test_stop_command_with_no_running_process_does_not_raise(self):
        """send_control_message must not raise when no subprocess is running."""
        executor = self._make_executor()
        executor._running_process = None
        executor.send_control_message('{"command": "stop"}')  # must not raise
