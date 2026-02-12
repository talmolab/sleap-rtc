"""Integration tests for sleap-rtc GUI components.

These tests verify the integration between sleap-rtc GUI components and
simulate how they would be used within SLEAP's training dialog.

Testing Approach for SLEAP Maintainers
======================================

This module demonstrates how to test sleap-rtc GUI integration without
requiring a live server or actual SLEAP installation. The key patterns are:

1. **Mock SLEAP Preferences**: Use `MockSLEAPPreferences` to simulate
   SLEAP's preference system for the experimental features flag.

2. **Mock API Responses**: Patch `sleap_rtc.api` functions to return
   controlled test data without network calls.

3. **Mock Qt Dialogs**: Patch dialog classes to simulate user interactions
   (clicking OK, Cancel, entering data).

4. **ZMQ Mocking**: Use `sys.modules` patching to mock the zmq module
   since it's imported lazily inside functions.

Example usage in SLEAP tests:

    from tests.test_gui_integration import MockSLEAPPreferences

    def test_remote_training_disabled_by_default():
        prefs = MockSLEAPPreferences()
        assert not prefs.get("enable_experimental_features", False)
        # Widget should not be visible when experimental features disabled
"""

import json
import pytest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Any

from sleap_rtc.api import (
    User,
    Room,
    Worker,
    ProgressEvent,
    TrainingResult,
    ValidationResult,
    ValidationIssue,
    PathCheckResult,
    VideoPathStatus,
    AuthenticationError,
    RoomNotFoundError,
    ConfigurationError,
    JobError,
)


# =============================================================================
# Mock SLEAP Preferences
# =============================================================================


class MockSLEAPPreferences:
    """Mock implementation of SLEAP's preference system.

    This simulates how SLEAP stores user preferences, including the
    experimental features flag that controls sleap-rtc visibility.

    Usage:
        prefs = MockSLEAPPreferences()
        prefs.set("enable_experimental_features", True)
        assert prefs.get("enable_experimental_features") is True
    """

    def __init__(self, defaults: dict[str, Any] | None = None):
        self._defaults = {
            "enable_experimental_features": False,
            "default_room_id": None,
            "auto_select_worker": True,
        }
        if defaults:
            self._defaults.update(defaults)
        self._values = dict(self._defaults)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a preference value."""
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a preference value."""
        self._values[key] = value

    def reset(self, key: str) -> None:
        """Reset a preference to its default value."""
        if key in self._defaults:
            self._values[key] = self._defaults[key]
        elif key in self._values:
            del self._values[key]

    def reset_all(self) -> None:
        """Reset all preferences to defaults."""
        self._values = dict(self._defaults)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_prefs():
    """Create mock SLEAP preferences."""
    return MockSLEAPPreferences()


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    return User(
        id="user-123",
        username="testuser",
        avatar_url="https://github.com/testuser.png",
    )


@pytest.fixture
def mock_rooms():
    """Create mock rooms list."""
    return [
        Room(
            id="room-1",
            name="Test Lab GPU",
            role="owner",
            created_by="user-123",
            joined_at=1700000000,
        ),
        Room(
            id="room-2",
            name="Shared Cluster",
            role="member",
            created_by="user-456",
            joined_at=1700100000,
        ),
    ]


@pytest.fixture
def mock_workers():
    """Create mock workers list."""
    return [
        Worker(
            id="worker-1",
            name="GPU Server A",
            status="available",
            gpu_name="NVIDIA RTX 4090",
            gpu_memory_mb=24576,
        ),
        Worker(
            id="worker-2",
            name="GPU Server B",
            status="busy",
            gpu_name="NVIDIA A100",
            gpu_memory_mb=81920,
        ),
    ]


@pytest.fixture
def mock_zmq():
    """Create and install mock zmq module."""
    mock_module = MagicMock()
    mock_module.PUB = 1
    mock_module.Context.return_value = MagicMock()

    with patch.dict("sys.modules", {"zmq": mock_module}):
        yield mock_module


# =============================================================================
# SLEAP Preferences Integration Tests
# =============================================================================


class TestSLEAPPreferencesIntegration:
    """Tests for SLEAP preferences integration."""

    def test_mock_preferences_defaults(self, mock_prefs):
        """Should have correct default values."""
        assert mock_prefs.get("enable_experimental_features") is False
        assert mock_prefs.get("default_room_id") is None
        assert mock_prefs.get("auto_select_worker") is True

    def test_mock_preferences_set_get(self, mock_prefs):
        """Should allow setting and getting values."""
        mock_prefs.set("enable_experimental_features", True)
        assert mock_prefs.get("enable_experimental_features") is True

        mock_prefs.set("default_room_id", "room-123")
        assert mock_prefs.get("default_room_id") == "room-123"

    def test_mock_preferences_reset(self, mock_prefs):
        """Should reset to defaults."""
        mock_prefs.set("enable_experimental_features", True)
        mock_prefs.reset("enable_experimental_features")
        assert mock_prefs.get("enable_experimental_features") is False

    def test_experimental_features_flag_controls_visibility(self, mock_prefs):
        """Experimental features flag should control widget visibility.

        This simulates how SLEAP would check the flag before showing
        the RemoteTrainingWidget.
        """
        # Default: experimental features disabled
        assert not mock_prefs.get("enable_experimental_features", False)

        # Widget visibility would be controlled by this flag
        should_show_widget = mock_prefs.get("enable_experimental_features", False)
        assert should_show_widget is False

        # Enable experimental features
        mock_prefs.set("enable_experimental_features", True)
        should_show_widget = mock_prefs.get("enable_experimental_features", False)
        assert should_show_widget is True


# =============================================================================
# Widget Visibility Tests
# =============================================================================


class TestWidgetVisibility:
    """Tests for widget visibility based on feature flags."""

    def test_widget_hidden_when_experimental_disabled(self, mock_prefs):
        """Widget should be hidden when experimental features disabled."""
        mock_prefs.set("enable_experimental_features", False)

        # Simulate SLEAP's logic for showing/hiding the widget
        show_remote_training = (
            mock_prefs.get("enable_experimental_features", False)
        )

        assert show_remote_training is False

    def test_widget_visible_when_experimental_enabled(self, mock_prefs):
        """Widget should be visible when experimental features enabled."""
        mock_prefs.set("enable_experimental_features", True)

        show_remote_training = (
            mock_prefs.get("enable_experimental_features", False)
        )

        assert show_remote_training is True

    @patch("sleap_rtc.api.is_available")
    def test_widget_hidden_when_rtc_unavailable(self, mock_is_available, mock_prefs):
        """Widget should be hidden when sleap-rtc is not available."""
        mock_prefs.set("enable_experimental_features", True)
        mock_is_available.return_value = False

        from sleap_rtc.api import is_available

        # Both conditions must be true
        show_remote_training = (
            mock_prefs.get("enable_experimental_features", False)
            and is_available()
        )

        assert show_remote_training is False

    @patch("sleap_rtc.api.is_available")
    def test_widget_visible_when_all_conditions_met(self, mock_is_available, mock_prefs):
        """Widget should be visible when all conditions are met."""
        mock_prefs.set("enable_experimental_features", True)
        mock_is_available.return_value = True

        from sleap_rtc.api import is_available

        show_remote_training = (
            mock_prefs.get("enable_experimental_features", False)
            and is_available()
        )

        assert show_remote_training is True


# =============================================================================
# Full Training Flow Tests
# =============================================================================


class TestFullTrainingFlow:
    """Tests for the complete training workflow."""

    @patch("sleap_rtc.api.run_training")
    @patch("sleap_rtc.api.check_video_paths")
    @patch("sleap_rtc.api.validate_config")
    @patch("sleap_rtc.api.list_workers")
    @patch("sleap_rtc.api.list_rooms")
    @patch("sleap_rtc.api.is_logged_in")
    def test_successful_training_flow(
        self,
        mock_is_logged_in,
        mock_list_rooms,
        mock_list_workers,
        mock_validate_config,
        mock_check_video_paths,
        mock_run_training,
        mock_user,
        mock_rooms,
        mock_workers,
    ):
        """Test complete successful training flow."""
        # Setup mocks
        mock_is_logged_in.return_value = True
        mock_list_rooms.return_value = mock_rooms
        mock_list_workers.return_value = mock_workers
        mock_validate_config.return_value = ValidationResult(
            valid=True,
            errors=[],
            warnings=[],
            config_path="/path/to/config.yaml",
        )
        mock_check_video_paths.return_value = PathCheckResult(
            all_found=True,
            total_videos=1,
            found_count=1,
            missing_count=0,
            videos=[
                VideoPathStatus(
                    filename="video.mp4",
                    original_path="/local/video.mp4",
                    worker_path="/data/video.mp4",
                    found=True,
                )
            ],
            slp_path="/data/labels.slp",
        )

        progress_events = []

        def capture_progress(event):
            progress_events.append(event)

        mock_run_training.return_value = TrainingResult(
            job_id="job-123",
            success=True,
            duration_seconds=3600.0,
            model_path="/models/run-123",
            final_epoch=100,
            final_train_loss=0.01,
            final_val_loss=0.02,
        )

        # Execute flow
        from sleap_rtc.api import (
            is_logged_in,
            list_rooms,
            list_workers,
            validate_config,
            check_video_paths,
            run_training,
        )

        # Step 1: Check authentication
        assert is_logged_in() is True

        # Step 2: Get rooms and workers
        rooms = list_rooms()
        assert len(rooms) == 2

        workers = list_workers(rooms[0].id)
        assert len(workers) == 2

        # Step 3: Validate config
        validation = validate_config("/path/to/config.yaml")
        assert validation.valid is True

        # Step 4: Check video paths
        path_result = check_video_paths("/data/labels.slp", rooms[0].id)
        assert path_result.all_found is True

        # Step 5: Run training
        result = run_training(
            config_path="/path/to/config.yaml",
            room_id=rooms[0].id,
            worker_id=workers[0].id,
        )

        assert result.success is True
        assert result.job_id == "job-123"
        assert result.model_path == "/models/run-123"

    @patch("sleap_rtc.api.run_training")
    @patch("sleap_rtc.api.is_logged_in")
    def test_training_flow_not_logged_in(
        self,
        mock_is_logged_in,
        mock_run_training,
    ):
        """Test training flow fails when not logged in."""
        mock_is_logged_in.return_value = False

        from sleap_rtc.gui.presubmission import check_authentication

        result = check_authentication()

        assert result.success is False
        assert "Not logged in" in result.error
        mock_run_training.assert_not_called()


# =============================================================================
# Progress Forwarding Tests
# =============================================================================


class TestProgressForwarding:
    """Tests for progress forwarding end-to-end."""

    def test_progress_bridge_formats_train_begin(self, mock_zmq):
        """Should format train_begin event correctly."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        from sleap_rtc.gui.runners import RemoteProgressBridge

        event = ProgressEvent(
            event_type="train_begin",
            total_epochs=100,
            wandb_url="https://wandb.ai/run/123",
        )

        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        # Verify message format
        mock_socket.send_multipart.assert_called_once()
        args = mock_socket.send_multipart.call_args[0][0]
        assert args[0] == b"progress"

        payload = json.loads(args[1])
        assert payload["event"] == "train_begin"
        assert payload["total_epochs"] == 100
        assert payload["wandb_url"] == "https://wandb.ai/run/123"

    def test_progress_bridge_formats_epoch_end(self, mock_zmq):
        """Should format epoch_end event correctly."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        from sleap_rtc.gui.runners import RemoteProgressBridge

        event = ProgressEvent(
            event_type="epoch_end",
            epoch=50,
            total_epochs=100,
            train_loss=0.05,
            val_loss=0.06,
        )

        with RemoteProgressBridge() as bridge:
            bridge.on_progress(event)

        args = mock_socket.send_multipart.call_args[0][0]
        payload = json.loads(args[1])

        assert payload["event"] == "epoch_end"
        assert payload["epoch"] == 50
        assert payload["total_epochs"] == 100
        assert payload["train_loss"] == 0.05
        assert payload["val_loss"] == 0.06

    def test_progress_bridge_formats_train_end(self, mock_zmq):
        """Should format train_end event correctly."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        from sleap_rtc.gui.runners import RemoteProgressBridge

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

    @patch("sleap_rtc.api.run_training")
    def test_run_remote_training_forwards_progress(self, mock_run_training, mock_zmq):
        """Should forward all progress events through bridge."""
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        # Simulate training with progress events
        def simulate_training(*args, **kwargs):
            # The handler is passed as 'progress_callback' to run_training
            on_progress = kwargs.get("progress_callback")
            if on_progress:
                on_progress(ProgressEvent(event_type="train_begin", total_epochs=10))
                for i in range(1, 11):
                    on_progress(ProgressEvent(
                        event_type="epoch_end",
                        epoch=i,
                        total_epochs=10,
                        train_loss=1.0 / i,
                    ))
                on_progress(ProgressEvent(event_type="train_end", success=True))
            return TrainingResult(job_id="test", success=True)

        mock_run_training.side_effect = simulate_training

        from sleap_rtc.gui.runners import run_remote_training

        result = run_remote_training(
            config_path="/path/to/config.yaml",
            room_id="room-1",
        )

        # Should have published: train_begin + 10 epoch_end + train_end = 12
        assert mock_socket.send_multipart.call_count == 12


# =============================================================================
# Failure Scenario Tests
# =============================================================================


class TestFailureScenarios:
    """Tests for error handling and failure scenarios."""

    @patch("sleap_rtc.api.list_rooms")
    @patch("sleap_rtc.api.is_logged_in")
    def test_network_error_on_list_rooms(self, mock_is_logged_in, mock_list_rooms):
        """Should handle network errors when listing rooms."""
        mock_is_logged_in.return_value = True
        mock_list_rooms.side_effect = Exception("Network timeout")

        from sleap_rtc.api import list_rooms

        with pytest.raises(Exception) as exc_info:
            list_rooms()

        assert "Network timeout" in str(exc_info.value)

    @patch("sleap_rtc.api.validate_config")
    def test_validation_error_handling(self, mock_validate_config):
        """Should handle validation errors correctly."""
        mock_validate_config.return_value = ValidationResult(
            valid=False,
            errors=[
                ValidationIssue(
                    field="max_epochs",
                    message="Value must be positive",
                    code="INVALID_VALUE",
                ),
                ValidationIssue(
                    field="batch_size",
                    message="Value must be integer",
                    code="INVALID_TYPE",
                ),
            ],
            warnings=[],
            config_path="/path/to/config.yaml",
        )

        from sleap_rtc.gui.presubmission import check_config_validation

        result = check_config_validation("/path/to/config.yaml", parent_widget=None)

        assert result.success is False
        assert "Value must be positive" in result.error

    @patch("sleap_rtc.api.check_video_paths")
    def test_path_resolution_error_handling(self, mock_check_paths):
        """Should handle path resolution errors correctly."""
        mock_check_paths.return_value = PathCheckResult(
            all_found=False,
            total_videos=2,
            found_count=0,
            missing_count=2,
            videos=[
                VideoPathStatus(
                    filename="video1.mp4",
                    original_path="/local/video1.mp4",
                    found=False,
                ),
                VideoPathStatus(
                    filename="video2.mp4",
                    original_path="/local/video2.mp4",
                    found=False,
                ),
            ],
            slp_path="/data/labels.slp",
        )

        from sleap_rtc.gui.presubmission import check_video_paths

        result = check_video_paths("/data/labels.slp", "room-1", parent_widget=None)

        assert result.success is False
        assert "video1.mp4" in result.error
        assert "video2.mp4" in result.error

    @patch("sleap_rtc.api.run_training")
    def test_training_error_handling(self, mock_run_training):
        """Should handle training errors correctly."""
        mock_run_training.side_effect = JobError(
            "CUDA out of memory",
            job_id="job-123",
            exit_code=1,
        )

        from sleap_rtc.api import run_training

        with pytest.raises(JobError) as exc_info:
            run_training(
                config_path="/path/to/config.yaml",
                room_id="room-1",
            )

        assert "CUDA out of memory" in str(exc_info.value)
        assert exc_info.value.job_id == "job-123"

    @patch("sleap_rtc.api.is_logged_in")
    def test_authentication_error_handling(self, mock_is_logged_in):
        """Should handle authentication errors correctly."""
        mock_is_logged_in.return_value = False

        from sleap_rtc.gui.presubmission import run_presubmission_checks

        result = run_presubmission_checks(
            config_path="/path/to/config.yaml",
            slp_path="/path/to/labels.slp",
            room_id="room-1",
        )

        assert result.success is False
        assert "Not logged in" in result.error

    @patch("sleap_rtc.api.list_workers")
    @patch("sleap_rtc.api.is_logged_in")
    def test_room_not_found_error(self, mock_is_logged_in, mock_list_workers):
        """Should handle room not found errors."""
        mock_is_logged_in.return_value = True
        mock_list_workers.side_effect = RoomNotFoundError("Room not found")

        from sleap_rtc.api import list_workers

        with pytest.raises(RoomNotFoundError):
            list_workers("nonexistent-room")

    @patch("sleap_rtc.api.validate_config")
    def test_config_file_not_found(self, mock_validate_config):
        """Should handle missing config file."""
        mock_validate_config.side_effect = ConfigurationError("File not found")

        from sleap_rtc.gui.presubmission import check_config_validation

        result = check_config_validation("/nonexistent/config.yaml")

        assert result.success is False
        assert "Cannot read config file" in result.error


# =============================================================================
# End-to-End Presubmission Flow Tests
# =============================================================================


class TestPresubmissionEndToEnd:
    """End-to-end tests for the presubmission validation flow."""

    @patch("sleap_rtc.api.check_video_paths")
    @patch("sleap_rtc.api.validate_config")
    @patch("sleap_rtc.api.is_logged_in")
    def test_full_presubmission_success(
        self,
        mock_is_logged_in,
        mock_validate_config,
        mock_check_video_paths,
    ):
        """Test successful presubmission flow."""
        mock_is_logged_in.return_value = True
        mock_validate_config.return_value = ValidationResult(
            valid=True,
            errors=[],
            warnings=[],
            config_path="/path/to/config.yaml",
        )
        mock_check_video_paths.return_value = PathCheckResult(
            all_found=True,
            total_videos=1,
            found_count=1,
            missing_count=0,
            videos=[
                VideoPathStatus(
                    filename="video.mp4",
                    original_path="/local/video.mp4",
                    worker_path="/data/video.mp4",
                    found=True,
                )
            ],
            slp_path="/data/labels.slp",
        )

        from sleap_rtc.gui.presubmission import run_presubmission_checks

        result = run_presubmission_checks(
            config_path="/path/to/config.yaml",
            slp_path="/data/labels.slp",
            room_id="room-1",
        )

        assert result.success is True
        assert result.path_mappings == {"/local/video.mp4": "/data/video.mp4"}

    @patch("sleap_rtc.api.check_video_paths")
    @patch("sleap_rtc.api.validate_config")
    @patch("sleap_rtc.api.is_logged_in")
    def test_presubmission_stops_on_auth_failure(
        self,
        mock_is_logged_in,
        mock_validate_config,
        mock_check_video_paths,
    ):
        """Test presubmission stops when authentication fails."""
        mock_is_logged_in.return_value = False

        from sleap_rtc.gui.presubmission import run_presubmission_checks

        result = run_presubmission_checks(
            config_path="/path/to/config.yaml",
            slp_path="/data/labels.slp",
            room_id="room-1",
        )

        assert result.success is False
        # Should not call validation or path check if auth fails
        mock_validate_config.assert_not_called()
        mock_check_video_paths.assert_not_called()

    @patch("sleap_rtc.api.check_video_paths")
    @patch("sleap_rtc.api.validate_config")
    @patch("sleap_rtc.api.is_logged_in")
    def test_presubmission_stops_on_validation_error(
        self,
        mock_is_logged_in,
        mock_validate_config,
        mock_check_video_paths,
    ):
        """Test presubmission stops when config validation fails."""
        mock_is_logged_in.return_value = True
        mock_validate_config.return_value = ValidationResult(
            valid=False,
            errors=[
                ValidationIssue(
                    field="max_epochs",
                    message="Invalid value",
                    code="INVALID_VALUE",
                )
            ],
            warnings=[],
            config_path="/path/to/config.yaml",
        )

        from sleap_rtc.gui.presubmission import run_presubmission_checks

        result = run_presubmission_checks(
            config_path="/path/to/config.yaml",
            slp_path="/data/labels.slp",
            room_id="room-1",
        )

        assert result.success is False
        # Should not call path check if validation fails
        mock_check_video_paths.assert_not_called()


# =============================================================================
# Documentation for SLEAP Maintainers
# =============================================================================


class TestDocumentation:
    """Tests that serve as documentation for SLEAP integration.

    These tests demonstrate the expected patterns for integrating
    sleap-rtc into SLEAP's GUI.
    """

    def test_example_sleap_integration_pattern(self, mock_prefs):
        """Example: How SLEAP should integrate the RemoteTrainingWidget.

        This test demonstrates the recommended pattern for integrating
        sleap-rtc widgets into SLEAP's training configuration dialog.
        """
        # Step 1: Check if experimental features are enabled
        show_remote_training = mock_prefs.get("enable_experimental_features", False)

        if show_remote_training:
            # Step 2: Check if sleap-rtc is available
            # In real code: from sleap_rtc.api import is_available
            # if is_available():
            #     # Step 3: Create and add the widget
            #     from sleap_rtc.gui import RemoteTrainingWidget
            #     remote_widget = RemoteTrainingWidget()
            #     layout.addWidget(remote_widget)
            pass

        # When experimental features are disabled, widget is not created
        assert show_remote_training is False

    def test_example_presubmission_integration(self):
        """Example: How SLEAP should use presubmission validation.

        This test demonstrates how to use the presubmission flow
        before starting remote training.
        """
        # In real SLEAP code:
        # from sleap_rtc.gui import run_presubmission_checks
        #
        # result = run_presubmission_checks(
        #     config_path=self.config_path,
        #     slp_path=self.labels.filename,
        #     room_id=self.remote_widget.get_selected_room_id(),
        #     worker_id=self.remote_widget.get_selected_worker_id(),
        #     parent_widget=self,
        #     on_login_required=self._handle_login,
        # )
        #
        # if result.success:
        #     # Proceed with training using result.path_mappings
        #     pass
        # elif result.cancelled:
        #     # User cancelled, do nothing
        #     pass
        # else:
        #     # Show error message
        #     QMessageBox.critical(self, "Error", result.error)
        pass

    def test_example_progress_forwarding(self, mock_zmq):
        """Example: How to use progress forwarding with LossViewer.

        This test demonstrates how progress events are forwarded
        to SLEAP's LossViewer via ZMQ.
        """
        mock_context = MagicMock()
        mock_socket = MagicMock()
        mock_zmq.Context.return_value = mock_context
        mock_context.socket.return_value = mock_socket

        # In real SLEAP code:
        # from sleap_rtc.gui import run_remote_training
        #
        # # LossViewer subscribes to port 9001 by default
        # result = run_remote_training(
        #     config_path=config_path,
        #     room_id=room_id,
        #     worker_id=worker_id,
        #     publish_port=9001,  # Same port LossViewer listens on
        # )
        #
        # The progress events will be published in the format:
        # - Topic: b"progress"
        # - Payload: JSON with "event" field
        #
        # LossViewer will receive these and update the loss plot.

        from sleap_rtc.gui.runners import RemoteProgressBridge

        with RemoteProgressBridge(publish_port=9001) as bridge:
            bridge.on_progress(ProgressEvent(
                event_type="epoch_end",
                epoch=1,
                train_loss=0.5,
                val_loss=0.6,
            ))

        # Verify message was published
        mock_socket.send_multipart.assert_called_once()
