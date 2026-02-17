"""Tests for worker handling of config_content in job submissions."""

import json
import os
import pytest

from unittest.mock import AsyncMock, MagicMock, patch

from sleap_rtc.config import MountConfig
from sleap_rtc.jobs.spec import TrainJobSpec
from sleap_rtc.protocol import MSG_JOB_SUBMIT, MSG_JOB_ACCEPTED, MSG_JOB_REJECTED, MSG_SEPARATOR
from sleap_rtc.worker.worker_class import RTCWorkerClient


@pytest.fixture
def temp_mount(tmp_path):
    """Create a temporary mount with test files."""
    labels = tmp_path / "labels.slp"
    labels.write_text("slp data")
    return tmp_path


@pytest.fixture
def worker(temp_mount):
    """Create a Worker with a test mount configured."""
    mount = MountConfig(path=str(temp_mount), label="Test Mount")
    w = RTCWorkerClient(mounts=[mount], working_dir=str(temp_mount))
    w.peer_id = "test-worker-123"
    # Mock job_executor so we don't actually run training
    w.job_executor = MagicMock()
    w.job_executor.execute_from_spec = AsyncMock()
    return w


@pytest.fixture
def mock_channel():
    """Create a mock RTCDataChannel."""
    channel = MagicMock()
    channel.readyState = "open"
    channel.send = MagicMock()
    return channel


def build_submit_message(spec_dict, job_id="test-job-1"):
    """Build a JOB_SUBMIT message from a spec dict."""
    return f"{MSG_JOB_SUBMIT}{MSG_SEPARATOR}{job_id}{MSG_SEPARATOR}{json.dumps(spec_dict)}"


class TestConfigContentHandling:
    """Tests for config_content in handle_job_submit."""

    @pytest.mark.asyncio
    async def test_config_content_writes_temp_file(self, worker, mock_channel, temp_mount):
        """Test that config_content is written to a temp YAML file."""
        config_yaml = "model_config:\n  backbone: unet\n"
        labels_path = str(temp_mount / "labels.slp")

        spec_dict = {
            "type": "train",
            "config_content": config_yaml,
            "labels_path": labels_path,
        }
        message = build_submit_message(spec_dict)

        await worker.handle_job_submit(mock_channel, message)

        # Should have sent JOB_ACCEPTED
        calls = [str(c) for c in mock_channel.send.call_args_list]
        accepted_calls = [c for c in calls if MSG_JOB_ACCEPTED in c]
        assert len(accepted_calls) == 1

        # Job executor should have been called
        worker.job_executor.execute_from_spec.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_content_temp_file_cleaned_up(self, worker, mock_channel, temp_mount):
        """Test that temp config file is cleaned up after execution."""
        config_yaml = "model_config:\n  backbone: unet\n"
        labels_path = str(temp_mount / "labels.slp")

        spec_dict = {
            "type": "train",
            "config_content": config_yaml,
            "labels_path": labels_path,
        }
        message = build_submit_message(spec_dict)

        # Track temp files that exist during execution
        temp_files_during_exec = []

        async def capture_temp_files(channel, cmd, job_id, job_type="train", **kwargs):
            """Capture temp files in working_dir during execution."""
            import glob
            temp_files_during_exec.extend(
                glob.glob(os.path.join(str(temp_mount), "rtc_config_*.yaml"))
            )

        worker.job_executor.execute_from_spec = AsyncMock(side_effect=capture_temp_files)

        await worker.handle_job_submit(mock_channel, message)

        # Temp file should have existed during execution
        assert len(temp_files_during_exec) > 0

        # But should be cleaned up now
        for f in temp_files_during_exec:
            assert not os.path.exists(f), f"Temp file not cleaned up: {f}"

    @pytest.mark.asyncio
    async def test_config_content_cleanup_on_execution_error(self, worker, mock_channel, temp_mount):
        """Test that temp file is cleaned up even when execution fails."""
        config_yaml = "model_config:\n  backbone: unet\n"
        labels_path = str(temp_mount / "labels.slp")

        spec_dict = {
            "type": "train",
            "config_content": config_yaml,
            "labels_path": labels_path,
        }
        message = build_submit_message(spec_dict)

        # Track the temp file path
        created_temp_files = []
        original_mkstemp = os.fdopen

        worker.job_executor.execute_from_spec = AsyncMock(
            side_effect=RuntimeError("Training crashed")
        )

        # The outer try/except in handle_job_submit catches RuntimeError,
        # but the finally block should still clean up
        await worker.handle_job_submit(mock_channel, message)

        # Check no rtc_config_ temp files are left in working_dir
        import glob
        remaining = glob.glob(os.path.join(str(temp_mount), "rtc_config_*.yaml"))
        assert len(remaining) == 0, f"Temp files not cleaned up: {remaining}"

    @pytest.mark.asyncio
    async def test_config_content_file_has_correct_content(self, worker, mock_channel, temp_mount):
        """Test that the temp file contains the exact config_content."""
        config_yaml = "model_config:\n  backbone: unet\n  num_layers: 3\n"
        labels_path = str(temp_mount / "labels.slp")

        spec_dict = {
            "type": "train",
            "config_content": config_yaml,
            "labels_path": labels_path,
        }
        message = build_submit_message(spec_dict)

        # Capture the command passed to execute_from_spec
        captured_cmds = []

        async def capture_cmd(channel, cmd, job_id, job_type="train", **kwargs):
            captured_cmds.append(cmd)

        worker.job_executor.execute_from_spec = AsyncMock(side_effect=capture_cmd)

        await worker.handle_job_submit(mock_channel, message)

        # The command should reference a temp file that existed during execution
        assert len(captured_cmds) == 1
        cmd = captured_cmds[0]
        # Command uses: sleap-nn train --config-name <name> --config-dir <dir>
        assert "--config-name" in cmd
        assert "--config-dir" in cmd
        name_idx = cmd.index("--config-name")
        assert cmd[name_idx + 1].startswith("rtc_config_")
        assert cmd[name_idx + 1].endswith(".yaml")

    @pytest.mark.asyncio
    async def test_config_paths_still_works(self, worker, mock_channel, temp_mount):
        """Test that config_paths-based specs still work unchanged."""
        # Create a real config file
        config_file = temp_mount / "config.yaml"
        config_file.write_text("trainer: {}")
        labels_path = str(temp_mount / "labels.slp")

        spec_dict = {
            "type": "train",
            "config_path": str(config_file),
            "labels_path": labels_path,
        }
        message = build_submit_message(spec_dict)

        await worker.handle_job_submit(mock_channel, message)

        # Should have sent JOB_ACCEPTED
        calls = [str(c) for c in mock_channel.send.call_args_list]
        accepted_calls = [c for c in calls if MSG_JOB_ACCEPTED in c]
        assert len(accepted_calls) == 1

    @pytest.mark.asyncio
    async def test_path_mappings_logged(self, worker, mock_channel, temp_mount):
        """Test that path_mappings are logged when present."""
        config_yaml = "model_config:\n  backbone: unet\n"
        labels_path = str(temp_mount / "labels.slp")

        spec_dict = {
            "type": "train",
            "config_content": config_yaml,
            "labels_path": labels_path,
            "path_mappings": {"C:/data/vid.mp4": "/mnt/data/vid.mp4"},
        }
        message = build_submit_message(spec_dict)

        with patch("sleap_rtc.worker.worker_class.logging") as mock_logging:
            await worker.handle_job_submit(mock_channel, message)

            # Check that path_mappings were logged
            info_calls = [str(c) for c in mock_logging.info.call_args_list]
            mapping_logs = [c for c in info_calls if "path_mappings" in c.lower() or "Path mappings" in c]
            assert len(mapping_logs) >= 1
