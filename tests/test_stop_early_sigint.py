"""Tests for Stop Early SIGINT behaviour.

When a CONTROL_COMMAND with {"command": "stop"} is forwarded through
send_control_message, the entire subprocess process group must receive
SIGINT so that all distributed workers (rank 0, rank 1, …) exit together,
preventing rank 1 from keeping stdout open and blocking the pipeline.

The subprocess must be started in its own process group (start_new_session=True)
so that os.killpg is safe to call without affecting the worker process itself.
"""

import json
import signal
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from sleap_rtc.worker.job_executor import JobExecutor


class TestStopEarlySendsSignal:

    def _make_executor(self, running=True):
        executor = JobExecutor(worker=MagicMock(), capabilities=MagicMock())
        executor._progress_reporter = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None if running else 0
        executor._running_process = mock_process
        return executor

    def test_stop_command_kills_process_group_with_sigint(self):
        """send_control_message('{"command":"stop"}') must SIGINT the whole process group."""
        executor = self._make_executor()
        with patch("os.killpg") as mock_killpg, \
             patch("os.getpgid", return_value=99999):
            executor.send_control_message('{"command": "stop"}')
            mock_killpg.assert_called_once_with(99999, signal.SIGINT)

    def test_stop_command_still_forwards_zmq_message(self):
        """ZMQ forwarding must not be skipped when the process group is signalled."""
        executor = self._make_executor()
        with patch("os.killpg"), patch("os.getpgid", return_value=99999):
            executor.send_control_message('{"command": "stop"}')
        executor._progress_reporter.send_control_message.assert_called_once_with(
            '{"command": "stop"}'
        )

    def test_non_stop_command_does_not_kill_process_group(self):
        """Non-stop ZMQ commands must not signal the process group."""
        executor = self._make_executor()
        with patch("os.killpg") as mock_killpg:
            executor.send_control_message('{"command": "pause"}')
        mock_killpg.assert_not_called()

    def test_stop_command_does_not_kill_already_exited_process(self):
        """Process group must not be signalled when the process has already exited."""
        executor = self._make_executor(running=False)
        with patch("os.killpg") as mock_killpg:
            executor.send_control_message('{"command": "stop"}')
        mock_killpg.assert_not_called()

    def test_stop_command_with_no_running_process_does_not_raise(self):
        """send_control_message must not raise when no subprocess is running."""
        executor = self._make_executor()
        executor._running_process = None
        executor.send_control_message('{"command": "stop"}')  # must not raise


class TestStopRunningJob:

    def _make_executor(self, pid=12345, running=True):
        executor = JobExecutor(worker=MagicMock(), capabilities=MagicMock())
        mock_process = MagicMock()
        mock_process.pid = pid
        mock_process.returncode = None if running else 0
        executor._running_process = mock_process
        return executor

    def test_stop_running_job_kills_process_group_with_sigint(self):
        """stop_running_job must send SIGINT to the process group, not just the PID."""
        executor = self._make_executor()
        with patch("os.killpg") as mock_killpg, \
             patch("os.getpgid", return_value=99999):
            executor.stop_running_job()
        mock_killpg.assert_called_once_with(99999, signal.SIGINT)

    def test_cancel_running_job_kills_process_group_with_sigterm(self):
        """cancel_running_job must send SIGTERM to the process group, not just the PID."""
        executor = self._make_executor()
        with patch("os.killpg") as mock_killpg, \
             patch("os.getpgid", return_value=99999):
            executor.cancel_running_job()
        mock_killpg.assert_called_once_with(99999, signal.SIGTERM)

    def test_stop_running_job_no_op_when_already_exited(self):
        """stop_running_job must not signal a process that has already exited."""
        executor = self._make_executor(running=False)
        with patch("os.killpg") as mock_killpg:
            executor.stop_running_job()
        mock_killpg.assert_not_called()


class TestSubprocessNewSession:

    @pytest.mark.asyncio
    async def test_subprocess_started_in_new_session(self):
        """execute_from_spec must pass start_new_session=True to create_subprocess_exec."""
        executor = JobExecutor(worker=MagicMock(), capabilities=MagicMock())

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_process.stdout = AsyncMock()
        mock_process.stdout.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock()

        mock_channel = MagicMock()
        mock_channel.readyState = "open"

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)) as mock_exec:
            await executor.execute_from_spec(
                mock_channel, ["echo", "done"], "job_1",
                job_type="train",
                zmq_ports={"controller": 9000, "publish": 9001},
                progress_reporter=MagicMock(),
            )
            _, kwargs = mock_exec.call_args
            assert kwargs.get("start_new_session") is True, (
                "subprocess must be started in its own session so killpg is safe"
            )
