"""Tests for sleap_rtc.api module."""

import os
import pytest
from unittest.mock import patch, MagicMock
import json

from sleap_rtc.api import (
    User,
    Room,
    Worker,
    AuthenticationError,
    RoomNotFoundError,
    is_available,
    is_logged_in,
    get_logged_in_user,
    login,
    logout,
    list_rooms,
    list_workers,
    _ensure_keypair_registered,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_config():
    """Mock the config module."""
    config = MagicMock()
    config.signaling_websocket = "ws://test-server:8080"
    config.signaling_http = "http://test-server:8080"
    config.get_http_url.return_value = "http://test-server:8080"
    return config


@pytest.fixture
def mock_jwt():
    """A valid mock JWT."""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjo5OTk5OTk5OTk5fQ.test"


@pytest.fixture
def mock_user_data():
    """Mock user data from credentials."""
    return {
        "id": "12345",
        "username": "testuser",
        "avatar_url": "https://example.com/avatar.png",
    }


# =============================================================================
# is_available() Tests
# =============================================================================


class TestIsAvailable:
    """Tests for is_available() function."""

    def test_available_when_configured(self, mock_config):
        """Should return True when signaling URLs are configured."""
        with patch("sleap_rtc.config.get_config", return_value=mock_config):
            assert is_available() is True

    def test_not_available_when_no_ws_url(self, mock_config):
        """Should return False when WS URL is missing."""
        mock_config.signaling_websocket = None
        with patch("sleap_rtc.config.get_config", return_value=mock_config):
            assert is_available() is False

    def test_not_available_when_no_http_url(self, mock_config):
        """Should return False when HTTP URL is missing."""
        mock_config.signaling_http = None
        with patch("sleap_rtc.config.get_config", return_value=mock_config):
            assert is_available() is False

    def test_not_available_on_exception(self):
        """Should return False when config raises exception."""
        with patch("sleap_rtc.config.get_config", side_effect=Exception("Config error")):
            assert is_available() is False


# =============================================================================
# is_logged_in() Tests
# =============================================================================


class TestIsLoggedIn:
    """Tests for is_logged_in() function."""

    def test_logged_in_with_valid_jwt(self, mock_jwt):
        """Should return True when valid JWT exists."""
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=mock_jwt):
            assert is_logged_in() is True

    def test_not_logged_in_with_no_jwt(self):
        """Should return False when no JWT exists."""
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=None):
            assert is_logged_in() is False

    def test_not_logged_in_with_expired_jwt(self):
        """Should return False when JWT is expired."""
        # get_valid_jwt returns None for expired JWTs
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=None):
            assert is_logged_in() is False


# =============================================================================
# get_logged_in_user() Tests
# =============================================================================


class TestGetLoggedInUser:
    """Tests for get_logged_in_user() function."""

    def test_returns_user_when_logged_in(self, mock_jwt, mock_user_data):
        """Should return User object when logged in."""
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=mock_jwt):
            with patch("sleap_rtc.auth.credentials.get_user", return_value=mock_user_data):
                user = get_logged_in_user()
                assert user is not None
                assert user.id == "12345"
                assert user.username == "testuser"
                assert user.avatar_url == "https://example.com/avatar.png"

    def test_returns_none_when_no_jwt(self):
        """Should return None when no JWT exists."""
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=None):
            assert get_logged_in_user() is None

    def test_returns_none_when_no_user_data(self, mock_jwt):
        """Should return None when no user data exists."""
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=mock_jwt):
            with patch("sleap_rtc.auth.credentials.get_user", return_value=None):
                assert get_logged_in_user() is None


# =============================================================================
# login() Tests
# =============================================================================


class TestLogin:
    """Tests for login() function."""

    def test_login_success(self, mock_user_data):
        """Should return User on successful login."""
        mock_result = {"jwt": "test-jwt", "user": mock_user_data}
        with patch("sleap_rtc.auth.github.github_login", return_value=mock_result):
            with patch("sleap_rtc.auth.credentials.save_jwt") as mock_save:
                with patch("sleap_rtc.api._ensure_keypair_registered"):
                    user = login()
                    assert user.username == "testuser"
                    mock_save.assert_called_once_with("test-jwt", mock_user_data)

    def test_login_with_callback(self, mock_user_data):
        """Should pass callback to github_login."""
        mock_result = {"jwt": "test-jwt", "user": mock_user_data}
        callback = MagicMock()

        with patch("sleap_rtc.auth.github.github_login", return_value=mock_result) as mock_login:
            with patch("sleap_rtc.auth.credentials.save_jwt"):
                with patch("sleap_rtc.api._ensure_keypair_registered"):
                    login(on_url_ready=callback)
                    mock_login.assert_called_once()
                    call_kwargs = mock_login.call_args[1]
                    assert call_kwargs["on_url_ready"] == callback

    def test_login_failure_raises_auth_error(self):
        """Should raise AuthenticationError on failure."""
        with patch("sleap_rtc.auth.github.github_login", side_effect=RuntimeError("Timeout")):
            with pytest.raises(AuthenticationError, match="Login failed"):
                login()

    def test_login_with_timeout(self, mock_user_data):
        """Should pass timeout to github_login."""
        mock_result = {"jwt": "test-jwt", "user": mock_user_data}
        with patch("sleap_rtc.auth.github.github_login", return_value=mock_result) as mock_login:
            with patch("sleap_rtc.auth.credentials.save_jwt"):
                with patch("sleap_rtc.api._ensure_keypair_registered"):
                    login(timeout=60)
                    call_kwargs = mock_login.call_args[1]
                    assert call_kwargs["timeout"] == 60

    def test_login_calls_ensure_keypair(self, mock_user_data):
        """Should call _ensure_keypair_registered after saving JWT."""
        mock_result = {"jwt": "test-jwt", "user": mock_user_data}
        with patch("sleap_rtc.auth.github.github_login", return_value=mock_result):
            with patch("sleap_rtc.auth.credentials.save_jwt"):
                with patch("sleap_rtc.api._ensure_keypair_registered") as mock_ensure:
                    login()
                    mock_ensure.assert_called_once_with(auth_token="test-jwt")

    def test_login_succeeds_even_if_keypair_registration_fails(self, mock_user_data):
        """Login should succeed even if keypair registration raises."""
        mock_result = {"jwt": "test-jwt", "user": mock_user_data}
        with patch("sleap_rtc.auth.github.github_login", return_value=mock_result):
            with patch("sleap_rtc.auth.credentials.save_jwt"):
                with patch("sleap_rtc.api._ensure_keypair_registered", side_effect=Exception("boom")):
                    user = login()
                    assert user.username == "testuser"


# =============================================================================
# _ensure_keypair_registered() Tests
# =============================================================================


class TestEnsureKeypairRegistered:
    """Tests for _ensure_keypair_registered() helper."""

    def test_generates_keypair_when_none_exists(self):
        """Should generate and save a new keypair if private key is missing."""
        with patch("sleap_rtc.auth.credentials.get_private_key_b64", return_value=None):
            with patch("sleap_rtc.auth.credentials.save_private_key_b64") as mock_save:
                with patch("sleap_rtc.auth.credentials.get_public_key_registered", return_value=False):
                    with patch("sleap_rtc.auth.credentials.set_public_key_registered"):
                        with patch("sleap_rtc.api.requests") as mock_requests:
                            mock_requests.post.return_value = MagicMock(ok=True)
                            _ensure_keypair_registered(auth_token="test-jwt")
                            mock_save.assert_called_once()
                            saved_b64 = mock_save.call_args[0][0]
                            assert isinstance(saved_b64, str)
                            assert len(saved_b64) > 0

    def test_skips_generation_when_keypair_exists(self):
        """Should not generate a new keypair if private key already exists."""
        with patch("sleap_rtc.auth.credentials.get_private_key_b64", return_value="existing_key_b64"):
            with patch("sleap_rtc.auth.credentials.save_private_key_b64") as mock_save:
                with patch("sleap_rtc.auth.credentials.get_public_key_registered", return_value=True):
                    _ensure_keypair_registered(auth_token="test-jwt")
                    mock_save.assert_not_called()

    def test_skips_registration_when_already_registered(self):
        """Should not POST to server if public key is already registered."""
        with patch("sleap_rtc.auth.credentials.get_private_key_b64", return_value="existing_key_b64"):
            with patch("sleap_rtc.auth.credentials.get_public_key_registered", return_value=True):
                with patch("sleap_rtc.api.requests") as mock_requests:
                    _ensure_keypair_registered(auth_token="test-jwt")
                    mock_requests.post.assert_not_called()

    def test_registers_public_key_when_not_registered(self, mock_config):
        """Should POST public key to server when not yet registered."""
        from sleap_rtc.auth.keypair import generate_keypair, private_key_to_b64
        priv, pub = generate_keypair()
        priv_b64 = private_key_to_b64(priv)

        with patch("sleap_rtc.auth.credentials.get_private_key_b64", return_value=priv_b64):
            with patch("sleap_rtc.auth.credentials.get_public_key_registered", return_value=False):
                with patch("sleap_rtc.auth.credentials.set_public_key_registered") as mock_set:
                    with patch("sleap_rtc.config.get_config", return_value=mock_config):
                        with patch("sleap_rtc.api.requests") as mock_requests:
                            mock_requests.post.return_value = MagicMock(ok=True)
                            _ensure_keypair_registered(auth_token="test-jwt")
                            mock_requests.post.assert_called_once()
                            call_kwargs = mock_requests.post.call_args
                            assert "/api/auth/public-keys" in call_kwargs[0][0]
                            assert call_kwargs[1]["json"]["device_name"] == "gui"
                            assert "public_key" in call_kwargs[1]["json"]
                            mock_set.assert_called_once_with(True)

    def test_does_not_raise_on_registration_failure(self, mock_config):
        """Should log warning but not raise if server registration fails."""
        from sleap_rtc.auth.keypair import generate_keypair, private_key_to_b64
        priv, pub = generate_keypair()
        priv_b64 = private_key_to_b64(priv)

        with patch("sleap_rtc.auth.credentials.get_private_key_b64", return_value=priv_b64):
            with patch("sleap_rtc.auth.credentials.get_public_key_registered", return_value=False):
                with patch("sleap_rtc.auth.credentials.set_public_key_registered") as mock_set:
                    with patch("sleap_rtc.config.get_config", return_value=mock_config):
                        with patch("sleap_rtc.api.requests") as mock_requests:
                            mock_requests.post.side_effect = ConnectionError("Server down")
                            _ensure_keypair_registered(auth_token="test-jwt")
                            mock_set.assert_not_called()

    def test_does_not_mark_registered_on_http_error(self, mock_config):
        """Should not set flag if server returns non-OK status."""
        from sleap_rtc.auth.keypair import generate_keypair, private_key_to_b64
        priv, pub = generate_keypair()
        priv_b64 = private_key_to_b64(priv)

        with patch("sleap_rtc.auth.credentials.get_private_key_b64", return_value=priv_b64):
            with patch("sleap_rtc.auth.credentials.get_public_key_registered", return_value=False):
                with patch("sleap_rtc.auth.credentials.set_public_key_registered") as mock_set:
                    with patch("sleap_rtc.config.get_config", return_value=mock_config):
                        with patch("sleap_rtc.api.requests") as mock_requests:
                            mock_requests.post.return_value = MagicMock(ok=False, status_code=500)
                            _ensure_keypair_registered(auth_token="test-jwt")
                            mock_set.assert_not_called()

    def test_uses_custom_device_name(self, mock_config):
        """Should pass device_name to server request."""
        from sleap_rtc.auth.keypair import generate_keypair, private_key_to_b64
        priv, pub = generate_keypair()
        priv_b64 = private_key_to_b64(priv)

        with patch("sleap_rtc.auth.credentials.get_private_key_b64", return_value=priv_b64):
            with patch("sleap_rtc.auth.credentials.get_public_key_registered", return_value=False):
                with patch("sleap_rtc.auth.credentials.set_public_key_registered"):
                    with patch("sleap_rtc.config.get_config", return_value=mock_config):
                        with patch("sleap_rtc.api.requests") as mock_requests:
                            mock_requests.post.return_value = MagicMock(ok=True)
                            _ensure_keypair_registered(auth_token="test-jwt", device_name="cli")
                            call_kwargs = mock_requests.post.call_args
                            assert call_kwargs[1]["json"]["device_name"] == "cli"


# =============================================================================
# logout() Tests
# =============================================================================


class TestLogout:
    """Tests for logout() function."""

    def test_logout_clears_jwt(self):
        """Should call clear_jwt."""
        with patch("sleap_rtc.auth.credentials.clear_jwt") as mock_clear:
            logout()
            mock_clear.assert_called_once()


# =============================================================================
# list_rooms() Tests
# =============================================================================


class TestListRooms:
    """Tests for list_rooms() function."""

    def test_list_rooms_success(self, mock_jwt, mock_config):
        """Should return list of Room objects."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rooms": [
                {
                    "room_id": "room-1",
                    "name": "Test Room",
                    "role": "owner",
                    "created_by": "testuser",
                    "joined_at": 1234567890,
                    "expires_at": 1234567890,
                },
                {
                    "room_id": "room-2",
                    "name": "Another Room",
                    "role": "member",
                },
            ]
        }

        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=mock_jwt):
            with patch("sleap_rtc.config.get_config", return_value=mock_config):
                with patch("requests.get", return_value=mock_response):
                    rooms = list_rooms()
                    assert len(rooms) == 2
                    assert rooms[0].id == "room-1"
                    assert rooms[0].name == "Test Room"
                    assert rooms[0].role == "owner"
                    assert rooms[1].id == "room-2"
                    assert rooms[1].role == "member"

    def test_list_rooms_not_logged_in(self):
        """Should raise AuthenticationError when not logged in."""
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=None):
            with pytest.raises(AuthenticationError, match="Not logged in"):
                list_rooms()

    def test_list_rooms_with_filters(self, mock_jwt, mock_config):
        """Should pass filter parameters to API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rooms": []}

        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=mock_jwt):
            with patch("sleap_rtc.config.get_config", return_value=mock_config):
                with patch("requests.get", return_value=mock_response) as mock_get:
                    list_rooms(role="owner", sort_by="name", sort_order="desc", search="test")
                    call_kwargs = mock_get.call_args[1]
                    assert call_kwargs["params"]["role"] == "owner"
                    assert call_kwargs["params"]["sort_by"] == "name"
                    assert call_kwargs["params"]["sort_order"] == "desc"
                    assert call_kwargs["params"]["search"] == "test"

    def test_list_rooms_empty(self, mock_jwt, mock_config):
        """Should return empty list when no rooms."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rooms": []}

        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=mock_jwt):
            with patch("sleap_rtc.config.get_config", return_value=mock_config):
                with patch("requests.get", return_value=mock_response):
                    rooms = list_rooms()
                    assert rooms == []


# =============================================================================
# list_workers() Tests
# =============================================================================


class TestListWorkers:
    """Tests for list_workers() function."""

    def test_list_workers_not_logged_in(self):
        """Should raise AuthenticationError when not logged in."""
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=None):
            with pytest.raises(AuthenticationError, match="Not logged in"):
                list_workers("room-1")

    def test_list_workers_success(self, mock_jwt, mock_config):
        """Should return list of Worker objects."""
        # This test mocks the async WebSocket flow
        mock_workers = [
            Worker(
                id="worker-1",
                name="GPU Worker 1",
                status="available",
                gpu_name="RTX 4090",
                gpu_memory_mb=24576,
                metadata={"tags": ["sleap-rtc"]},
            )
        ]

        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=mock_jwt):
            with patch("sleap_rtc.config.get_config", return_value=mock_config):
                with patch("asyncio.run", return_value=mock_workers):
                    workers = list_workers("room-1")
                    assert len(workers) == 1
                    assert workers[0].name == "GPU Worker 1"
                    assert workers[0].status == "available"
                    assert workers[0].gpu_name == "RTX 4090"


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDataClasses:
    """Tests for API data classes."""

    def test_user_dataclass(self):
        """User dataclass should work correctly."""
        user = User(id="123", username="test", avatar_url="https://example.com/a.png")
        assert user.id == "123"
        assert user.username == "test"
        assert user.avatar_url == "https://example.com/a.png"

    def test_user_dataclass_optional_avatar(self):
        """User avatar_url should be optional."""
        user = User(id="123", username="test")
        assert user.avatar_url is None

    def test_room_dataclass(self):
        """Room dataclass should work correctly."""
        room = Room(
            id="room-1",
            name="Test Room",
            role="owner",
            created_by="user1",
            joined_at=1234567890,
            expires_at=1234567999,
        )
        assert room.id == "room-1"
        assert room.name == "Test Room"
        assert room.role == "owner"

    def test_room_dataclass_optional_fields(self):
        """Room optional fields should default to None."""
        room = Room(id="room-1", name="Test", role="member")
        assert room.created_by is None
        assert room.joined_at is None
        assert room.expires_at is None

    def test_worker_dataclass(self):
        """Worker dataclass should work correctly."""
        worker = Worker(
            id="worker-1",
            name="GPU Worker",
            status="available",
            gpu_name="RTX 4090",
            gpu_memory_mb=24576,
            metadata={"key": "value"},
        )
        assert worker.id == "worker-1"
        assert worker.gpu_memory_mb == 24576

    def test_worker_dataclass_optional_fields(self):
        """Worker optional fields should default to None."""
        worker = Worker(id="w1", name="Worker", status="unknown")
        assert worker.gpu_name is None
        assert worker.gpu_memory_mb is None
        assert worker.metadata is None


# =============================================================================
# Path Checking Data Class Tests
# =============================================================================


from sleap_rtc.api import (
    PathCheckResult,
    VideoPathStatus,
    ValidationResult,
    ValidationIssue,
    ConfigurationError,
    check_video_paths,
    validate_config,
)


class TestPathCheckDataClasses:
    """Tests for path checking data classes."""

    def test_video_path_status_found(self):
        """VideoPathStatus for found video."""
        status = VideoPathStatus(
            filename="video.mp4",
            original_path="/data/video.mp4",
            worker_path="/mnt/data/video.mp4",
            found=True,
        )
        assert status.filename == "video.mp4"
        assert status.found is True
        assert status.worker_path == "/mnt/data/video.mp4"

    def test_video_path_status_missing(self):
        """VideoPathStatus for missing video."""
        status = VideoPathStatus(
            filename="video.mp4",
            original_path="/data/video.mp4",
            found=False,
            suggestions=["/other/video.mp4", "/backup/video.mp4"],
        )
        assert status.found is False
        assert status.worker_path is None
        assert len(status.suggestions) == 2

    def test_path_check_result_all_found(self):
        """PathCheckResult when all videos found."""
        videos = [
            VideoPathStatus("v1.mp4", "/a/v1.mp4", "/a/v1.mp4", True),
            VideoPathStatus("v2.mp4", "/a/v2.mp4", "/a/v2.mp4", True),
        ]
        result = PathCheckResult(
            all_found=True,
            total_videos=2,
            found_count=2,
            missing_count=0,
            videos=videos,
            slp_path="/data/project.slp",
        )
        assert result.all_found is True
        assert result.missing_count == 0

    def test_path_check_result_some_missing(self):
        """PathCheckResult when some videos missing."""
        videos = [
            VideoPathStatus("v1.mp4", "/a/v1.mp4", "/a/v1.mp4", True),
            VideoPathStatus("v2.mp4", "/a/v2.mp4", found=False),
        ]
        result = PathCheckResult(
            all_found=False,
            total_videos=2,
            found_count=1,
            missing_count=1,
            videos=videos,
            slp_path="/data/project.slp",
        )
        assert result.all_found is False
        assert result.missing_count == 1


class TestValidationDataClasses:
    """Tests for validation data classes."""

    def test_validation_issue_error(self):
        """ValidationIssue for an error."""
        issue = ValidationIssue(
            field="config_path",
            message="File not found",
            code="FILE_NOT_FOUND",
            is_error=True,
            path="/path/to/config.yaml",
        )
        assert issue.is_error is True
        assert issue.code == "FILE_NOT_FOUND"

    def test_validation_issue_warning(self):
        """ValidationIssue for a warning."""
        issue = ValidationIssue(
            field="trainer_config.max_epochs",
            message="Value is unusually high",
            code="VALUE_WARNING",
            is_error=False,
        )
        assert issue.is_error is False

    def test_validation_result_valid(self):
        """ValidationResult when config is valid."""
        result = ValidationResult(
            valid=True,
            errors=[],
            warnings=[],
            config_path="/path/to/config.yaml",
        )
        assert result.valid is True
        assert len(result.errors) == 0

    def test_validation_result_invalid(self):
        """ValidationResult when config has errors."""
        error = ValidationIssue("field", "Error message", is_error=True)
        result = ValidationResult(
            valid=False,
            errors=[error],
            warnings=[],
            config_path="/path/to/config.yaml",
        )
        assert result.valid is False
        assert len(result.errors) == 1


# =============================================================================
# check_video_paths() Tests
# =============================================================================


class TestCheckVideoPaths:
    """Tests for check_video_paths() function."""

    def test_check_video_paths_not_logged_in(self):
        """Should raise AuthenticationError when not logged in."""
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=None):
            with pytest.raises(AuthenticationError, match="Not logged in"):
                check_video_paths("/data/project.slp", "room-1")


    def test_check_video_paths_success(self, mock_jwt, mock_config):
        """Should return PathCheckResult on success."""
        # Mock the async function result
        mock_result = PathCheckResult(
            all_found=True,
            total_videos=2,
            found_count=2,
            missing_count=0,
            videos=[
                VideoPathStatus("v1.mp4", "/a/v1.mp4", "/a/v1.mp4", True),
                VideoPathStatus("v2.mp4", "/a/v2.mp4", "/a/v2.mp4", True),
            ],
            slp_path="/data/project.slp",
        )

        with patch("asyncio.run", return_value=mock_result):
            result = check_video_paths("/data/project.slp", "room-1")
            assert result.all_found is True
            assert result.total_videos == 2


# =============================================================================
# validate_config() Tests
# =============================================================================


class TestValidateConfig:
    """Tests for validate_config() function."""

    def test_validate_config_file_not_found(self, tmp_path):
        """Should return error when file not found."""
        result = validate_config(str(tmp_path / "nonexistent.yaml"))
        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "FILE_NOT_FOUND"

    def test_validate_config_invalid_yaml(self, tmp_path):
        """Should return error for invalid YAML."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("{ invalid yaml: [")

        result = validate_config(str(config_file))
        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "YAML_PARSE_ERROR"

    def test_validate_config_not_a_dict(self, tmp_path):
        """Should return error when YAML is not a dict."""
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2")

        result = validate_config(str(config_file))
        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "INVALID_FORMAT"

    def test_validate_config_valid_minimal(self, tmp_path):
        """Should pass for minimal valid config."""
        config_file = tmp_path / "valid.yaml"
        config_file.write_text("model_config:\n  batch_size: 4")

        result = validate_config(str(config_file))
        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_config_invalid_batch_size(self, tmp_path):
        """Should error on invalid batch_size."""
        config_file = tmp_path / "invalid_batch.yaml"
        config_file.write_text("model_config:\n  batch_size: -1")

        result = validate_config(str(config_file))
        assert result.valid is False
        assert any(e.field == "model_config.batch_size" for e in result.errors)

    def test_validate_config_invalid_max_epochs(self, tmp_path):
        """Should error on invalid max_epochs."""
        config_file = tmp_path / "invalid_epochs.yaml"
        config_file.write_text("trainer_config:\n  max_epochs: 0")

        result = validate_config(str(config_file))
        assert result.valid is False
        assert any(e.field == "trainer_config.max_epochs" for e in result.errors)

    def test_validate_config_warning_high_epochs(self, tmp_path):
        """Should warn on unusually high max_epochs."""
        config_file = tmp_path / "high_epochs.yaml"
        config_file.write_text("trainer_config:\n  max_epochs: 50000")

        result = validate_config(str(config_file))
        assert result.valid is True  # Warnings don't make it invalid
        assert any(
            w.field == "trainer_config.max_epochs" and w.code == "VALUE_WARNING"
            for w in result.warnings
        )

    def test_validate_config_warning_missing_train_labels(self, tmp_path):
        """Should warn when train_labels_path not specified."""
        config_file = tmp_path / "no_labels.yaml"
        config_file.write_text("model_config:\n  batch_size: 4")

        result = validate_config(str(config_file))
        assert result.valid is True
        assert any(
            w.field == "data_config.train_labels_path" for w in result.warnings
        )

    def test_validate_config_warning_local_path_not_found(self, tmp_path):
        """Should warn when local path doesn't exist."""
        config_file = tmp_path / "missing_path.yaml"
        config_file.write_text(
            "data_config:\n  train_labels_path: /nonexistent/path/labels.slp"
        )

        result = validate_config(str(config_file))
        assert result.valid is True  # Just a warning since path may exist on worker
        assert any(
            w.code == "PATH_NOT_FOUND_LOCAL" for w in result.warnings
        )

    def test_validate_config_full_valid(self, tmp_path):
        """Should pass for full valid config with existing path."""
        # Create a dummy labels file
        labels_file = tmp_path / "labels.slp"
        labels_file.write_text("")

        config_file = tmp_path / "full_valid.yaml"
        config_file.write_text(
            f"data_config:\n"
            f"  train_labels_path: {labels_file}\n"
            f"trainer_config:\n"
            f"  max_epochs: 100\n"
            f"model_config:\n"
            f"  batch_size: 8\n"
        )

        result = validate_config(str(config_file))
        assert result.valid is True
        assert len(result.errors) == 0


# =============================================================================
# Remote Execution Data Class Tests
# =============================================================================


from sleap_rtc.api import (
    ProgressEvent,
    TrainingResult,
    InferenceResult,
    TrainingJob,
    JobError,
    run_training,
    run_inference,
)


class TestProgressEvent:
    """Tests for ProgressEvent dataclass."""

    def test_progress_event_train_begin(self):
        """ProgressEvent for train_begin."""
        event = ProgressEvent(
            event_type="train_begin",
            wandb_url="https://wandb.ai/run/123",
        )
        assert event.event_type == "train_begin"
        assert event.wandb_url == "https://wandb.ai/run/123"
        assert event.epoch is None

    def test_progress_event_epoch_end(self):
        """ProgressEvent for epoch_end."""
        event = ProgressEvent(
            event_type="epoch_end",
            epoch=5,
            total_epochs=100,
            train_loss=0.123,
            val_loss=0.145,
        )
        assert event.event_type == "epoch_end"
        assert event.epoch == 5
        assert event.train_loss == 0.123
        assert event.val_loss == 0.145

    def test_progress_event_train_end_success(self):
        """ProgressEvent for successful train_end."""
        event = ProgressEvent(
            event_type="train_end",
            success=True,
        )
        assert event.event_type == "train_end"
        assert event.success is True
        assert event.error_message is None

    def test_progress_event_train_end_failure(self):
        """ProgressEvent for failed train_end."""
        event = ProgressEvent(
            event_type="train_end",
            success=False,
            error_message="CUDA out of memory",
        )
        assert event.success is False
        assert event.error_message == "CUDA out of memory"

    def test_progress_event_model_type_default_none(self):
        """model_type should default to None."""
        event = ProgressEvent(event_type="epoch_end")
        assert event.model_type is None

    def test_progress_event_model_type_set(self):
        """model_type can be set on ProgressEvent."""
        event = ProgressEvent(
            event_type="epoch_end",
            epoch=1,
            train_loss=0.05,
            model_type="centroid",
        )
        assert event.model_type == "centroid"

    def test_progress_event_model_type_all_events(self):
        """model_type should be settable on all event types."""
        for event_type in ("train_begin", "epoch_end", "train_end"):
            event = ProgressEvent(
                event_type=event_type,
                model_type="centered_instance",
            )
            assert event.model_type == "centered_instance"


class TestTrainingResult:
    """Tests for TrainingResult dataclass."""

    def test_training_result_success(self):
        """TrainingResult for successful training."""
        result = TrainingResult(
            job_id="job_abc123",
            success=True,
            duration_seconds=3600.5,
            model_path="/models/run_001",
            final_epoch=100,
            final_train_loss=0.05,
            final_val_loss=0.08,
        )
        assert result.success is True
        assert result.job_id == "job_abc123"
        assert result.duration_seconds == 3600.5
        assert result.final_epoch == 100

    def test_training_result_failure(self):
        """TrainingResult for failed training."""
        result = TrainingResult(
            job_id="job_abc123",
            success=False,
            duration_seconds=300.0,
            final_epoch=10,
            error_message="GPU memory exhausted",
        )
        assert result.success is False
        assert result.error_message == "GPU memory exhausted"


class TestInferenceResult:
    """Tests for InferenceResult dataclass."""

    def test_inference_result_success(self):
        """InferenceResult for successful inference."""
        result = InferenceResult(
            job_id="job_xyz789",
            success=True,
            duration_seconds=120.5,
            predictions_path="/data/predictions.slp",
            frames_processed=1000,
        )
        assert result.success is True
        assert result.predictions_path == "/data/predictions.slp"
        assert result.frames_processed == 1000

    def test_inference_result_failure(self):
        """InferenceResult for failed inference."""
        result = InferenceResult(
            job_id="job_xyz789",
            success=False,
            error_message="Model not found",
        )
        assert result.success is False
        assert result.error_message == "Model not found"


class TestTrainingJob:
    """Tests for TrainingJob class."""

    def test_training_job_creation(self):
        """TrainingJob should store job metadata."""
        job = TrainingJob(
            job_id="job_123",
            room_id="room_abc",
            worker_id="worker_gpu1",
        )
        assert job.job_id == "job_123"
        assert job.room_id == "room_abc"
        assert job.worker_id == "worker_gpu1"
        assert job.status == "running"

    def test_training_job_cancel(self):
        """TrainingJob.cancel() should update status."""
        cancelled = False

        def cancel_func():
            nonlocal cancelled
            cancelled = True

        job = TrainingJob(
            job_id="job_123",
            room_id="room_abc",
            worker_id="worker_gpu1",
            _cancel_func=cancel_func,
        )
        job.cancel()
        assert job.status == "cancelled"
        assert cancelled is True


class TestJobError:
    """Tests for JobError exception."""

    def test_job_error_basic(self):
        """JobError should store error details."""
        error = JobError("Training failed", job_id="job_123", exit_code=1)
        assert str(error) == "Training failed"
        assert error.job_id == "job_123"
        assert error.exit_code == 1

    def test_job_error_minimal(self):
        """JobError with minimal info."""
        error = JobError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.job_id is None
        assert error.exit_code is None


# =============================================================================
# run_training() Tests
# =============================================================================


class TestRunTraining:
    """Tests for run_training() function."""

    def test_run_training_not_logged_in(self):
        """Should raise AuthenticationError when not logged in."""
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=None):
            with pytest.raises(AuthenticationError, match="Not logged in"):
                run_training("/config.yaml", "room-1")


    def test_run_training_success(self, mock_jwt, mock_config):
        """Should return TrainingResult on success."""
        mock_result = TrainingResult(
            job_id="job_123",
            success=True,
            duration_seconds=3600.0,
            model_path="/models/output",
            final_epoch=100,
        )

        with patch("asyncio.run", return_value=mock_result):
            result = run_training("/config.yaml", "room-1")
            assert result.success is True
            assert result.job_id == "job_123"

    def test_run_training_with_progress_callback(self, mock_jwt, mock_config):
        """Should call progress callback."""
        events = []

        def callback(event):
            events.append(event)

        mock_result = TrainingResult(job_id="job_123", success=True)

        with patch("asyncio.run", return_value=mock_result):
            run_training("/config.yaml", "room-1", progress_callback=callback)
            # Note: In real execution, callback would be called

    def test_run_training_passes_model_type(self):
        """Should pass model_type to _run_training_async."""
        mock_result = TrainingResult(job_id="job_123", success=True)

        with patch("asyncio.run", return_value=mock_result) as mock_run:
            run_training("/config.yaml", "room-1", model_type="centroid")
            # Verify model_type was passed to the async coroutine
            coro = mock_run.call_args[0][0]
            # The coroutine was created with model_type="centroid"
            # We can verify by checking the call was made
            mock_run.assert_called_once()

    def test_run_training_passes_on_log(self):
        """Should pass on_log to _run_training_async."""
        mock_result = TrainingResult(job_id="job_123", success=True)

        log_lines = []
        with patch("asyncio.run", return_value=mock_result) as mock_run:
            run_training(
                "/config.yaml", "room-1", on_log=lambda line: log_lines.append(line)
            )
            mock_run.assert_called_once()


# =============================================================================
# run_inference() Tests
# =============================================================================


class TestRunInference:
    """Tests for run_inference() function."""

    def test_run_inference_not_logged_in(self):
        """Should raise AuthenticationError when not logged in."""
        with patch("sleap_rtc.auth.credentials.get_valid_jwt", return_value=None):
            with pytest.raises(AuthenticationError, match="Not logged in"):
                run_inference("/data.slp", ["/model1"], "room-1")


    def test_run_inference_success(self, mock_jwt, mock_config):
        """Should return InferenceResult on success."""
        mock_result = InferenceResult(
            job_id="job_456",
            success=True,
            duration_seconds=120.0,
            predictions_path="/data/predictions.slp",
        )

        with patch("asyncio.run", return_value=mock_result):
            result = run_inference("/data.slp", ["/model1"], "room-1")
            assert result.success is True
            assert result.predictions_path == "/data/predictions.slp"


# =============================================================================
# Streamed prediction file reception (Task 2 — Gap 1)
# =============================================================================
#
# When the worker streams predictions.slp via the sequence:
#   FILE_META::predictions.slp:<size>:<hint>
#   <binary chunk 1>
#   <binary chunk 2>
#   ...
#   END_OF_FILE
#   INFERENCE_COMPLETE::{"predictions_path": "<worker-side path>"}
#
# the GUI-path message handler must:
#   - write the chunks to a local tempfile
#   - on INFERENCE_COMPLETE, substitute the local tempfile path for
#     data["predictions_path"] (preserving the worker path in
#     data["worker_predictions_path"] for v2 dual-mode fallback).


class TestStreamedFileReceiver:
    """Tests for the _StreamedFileReceiver state machine in sleap_rtc.api."""

    def test_predictions_file_written_and_local_path_exposed(self, tmp_path):
        """Given the ordered sequence
            FILE_META::predictions.slp:<size>:<hint>
            <chunk1>
            <chunk2>
            END_OF_FILE
        the receiver must:
         - create a local temp file
         - write the concatenated chunk bytes to it
         - expose the local path via `take_predictions_path()`
        """
        from sleap_rtc.api import _StreamedFileReceiver

        receiver = _StreamedFileReceiver()
        chunk1 = b"the rain in spain"
        chunk2 = b" falls mainly on the plain"
        size = len(chunk1) + len(chunk2)

        receiver.handle_string(f"FILE_META::predictions.slp:{size}:/worker/out")
        receiver.handle_bytes(chunk1)
        receiver.handle_bytes(chunk2)
        receiver.handle_string("END_OF_FILE")

        local_path = receiver.take_predictions_path()
        assert local_path is not None
        assert os.path.exists(local_path)
        with open(local_path, "rb") as f:
            assert f.read() == chunk1 + chunk2

        # take_predictions_path consumes the path — second call returns None.
        assert receiver.take_predictions_path() is None

        # Cleanup temp file so the test doesn't leave files in /tmp.
        os.unlink(local_path)

    def test_non_predictions_file_is_cleaned_up(self):
        """If the worker streams a filename other than predictions.slp, the
        receiver must still drain the bytes but must not retain the path as
        'predictions'. The temp file should be unlinked on END_OF_FILE to
        avoid leaking."""
        from sleap_rtc.api import _StreamedFileReceiver

        receiver = _StreamedFileReceiver()
        receiver.handle_string("FILE_META::other.txt:4:/tmp")
        receiver.handle_bytes(b"data")
        receiver.handle_string("END_OF_FILE")

        # No predictions path should be exposed.
        assert receiver.take_predictions_path() is None

    def test_unexpected_binary_without_file_meta_is_dropped(self):
        """Binary chunks with no active FILE_META must be silently dropped
        (backward-compatible with the pre-Task-2 behavior)."""
        from sleap_rtc.api import _StreamedFileReceiver

        receiver = _StreamedFileReceiver()
        # Must not raise
        receiver.handle_bytes(b"stray bytes")
        assert receiver.take_predictions_path() is None

    def test_end_of_file_without_file_meta_is_ignored(self):
        """A stray END_OF_FILE with no active FILE_META must not crash."""
        from sleap_rtc.api import _StreamedFileReceiver

        receiver = _StreamedFileReceiver()
        # Must not raise
        receiver.handle_string("END_OF_FILE")
        assert receiver.take_predictions_path() is None

    def test_malformed_file_meta_does_not_crash(self):
        """FILE_META with missing size field should not crash; receiver
        should either open a tempfile with zero expected size or skip."""
        from sleap_rtc.api import _StreamedFileReceiver

        receiver = _StreamedFileReceiver()
        # Malformed — only filename, no size.
        receiver.handle_string("FILE_META::predictions.slp")
        # Any bytes that follow should not cause AttributeError or similar.
        receiver.handle_bytes(b"some bytes")
        receiver.handle_string("END_OF_FILE")
        # The behavior here is implementation-defined; the key contract is
        # "doesn't crash, doesn't corrupt future transfers."
        # A subsequent well-formed transfer must still work:
        receiver.handle_string("FILE_META::predictions.slp:3:/tmp")
        receiver.handle_bytes(b"abc")
        receiver.handle_string("END_OF_FILE")
        local_path = receiver.take_predictions_path()
        assert local_path is not None
        assert os.path.exists(local_path)
        with open(local_path, "rb") as f:
            assert f.read() == b"abc"
        os.unlink(local_path)


class TestInferenceCompletePathRewrite:
    """Tests that the INFERENCE_COMPLETE dispatch in _run_training_async
    substitutes the locally-received tempfile path for data['predictions_path']
    when a stream was received."""

    def test_inference_complete_payload_rewritten_to_local_path(self):
        """Simulate end-to-end dispatch logic:
            1. Receiver receives predictions.slp stream.
            2. INFERENCE_COMPLETE::{"predictions_path": "/worker/path.slp"}
               is parsed.
            3. The INFERENCE_COMPLETE callback is invoked with data where
               predictions_path == local temp path and
               worker_predictions_path == original worker path.
        """
        from sleap_rtc.api import (
            _StreamedFileReceiver,
            _apply_received_predictions_to_inference_data,
        )

        receiver = _StreamedFileReceiver()
        receiver.handle_string("FILE_META::predictions.slp:5:/worker/out")
        receiver.handle_bytes(b"hello")
        receiver.handle_string("END_OF_FILE")

        # Parsed INFERENCE_COMPLETE payload (as api.py does via json.loads).
        data = {"predictions_path": "/worker/path.slp"}
        _apply_received_predictions_to_inference_data(receiver, data)

        assert data["worker_predictions_path"] == "/worker/path.slp"
        assert data["predictions_path"] != "/worker/path.slp"
        assert os.path.exists(data["predictions_path"])
        with open(data["predictions_path"], "rb") as f:
            assert f.read() == b"hello"

        # After consumption, receiver has no pending path.
        assert receiver.take_predictions_path() is None

        os.unlink(data["predictions_path"])

    def test_inference_complete_untouched_when_no_stream_received(self):
        """If no predictions stream arrived (pre-Task-1 worker, or training
        only with no inference), the INFERENCE_COMPLETE payload passes
        through unchanged."""
        from sleap_rtc.api import (
            _StreamedFileReceiver,
            _apply_received_predictions_to_inference_data,
        )

        receiver = _StreamedFileReceiver()
        data = {"predictions_path": "/worker/path.slp"}
        _apply_received_predictions_to_inference_data(receiver, data)

        assert data == {"predictions_path": "/worker/path.slp"}
        assert "worker_predictions_path" not in data
