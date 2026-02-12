"""Pre-submission validation flow for remote training.

This module provides the validation sequence that runs before submitting a
training job to a remote worker. It checks:
1. Authentication status (prompts login if needed)
2. Video paths on worker (shows PathResolutionDialog if needed)
3. Config validation (shows ConfigValidationDialog if needed)

Only if all checks pass does the training proceed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from loguru import logger

if TYPE_CHECKING:
    from sleap_rtc.api import PathCheckResult, ValidationResult


@dataclass
class PresubmissionResult:
    """Result of the pre-submission validation sequence.

    Attributes:
        success: Whether all checks passed and training can proceed.
        cancelled: Whether the user cancelled during any dialog.
        error: Error message if validation failed.
        path_mappings: Resolved path mappings (original -> worker path).
        validation_result: Config validation result.
    """

    success: bool
    cancelled: bool = False
    error: str | None = None
    path_mappings: dict[str, str] | None = None
    validation_result: "ValidationResult | None" = None


def run_presubmission_checks(
    slp_path: str,
    room_id: str,
    worker_id: str | None = None,
    config_path: str | None = None,
    config_content: str | None = None,
    parent_widget=None,
    on_login_required: Callable[[], bool] | None = None,
) -> PresubmissionResult:
    """Run the complete pre-submission validation sequence.

    This function orchestrates the validation flow:
    1. Check authentication - if not logged in, call on_login_required callback
    2. Validate config - show ConfigValidationDialog if errors/warnings
       (skipped when config_content is provided, since config was built in-memory)
    3. Check video paths - show PathResolutionDialog if paths need resolution

    Args:
        slp_path: Path to the SLP file (for video path checking).
        room_id: The room ID to use for path checking.
        worker_id: Optional specific worker ID.
        config_path: Path to the training configuration file.
        config_content: Serialized config YAML string (alternative to
            config_path). When provided, config validation is skipped since
            the config was built from the dialog form.
        parent_widget: Parent Qt widget for dialogs.
        on_login_required: Callback called when login is required.
            Should return True if login succeeded, False otherwise.
            If not provided, authentication check will fail if not logged in.

    Returns:
        PresubmissionResult indicating whether training can proceed.

    Example:
        result = run_presubmission_checks(
            slp_path="/path/to/labels.slp",
            room_id="my-room",
            config_content=yaml_string,
            parent_widget=self,
            on_login_required=self._handle_login,
        )
        if result.success:
            spec = TrainJobSpec(
                config_content=yaml_string,
                labels_path=slp_path,
                path_mappings=result.path_mappings,
            )
            run_remote_training(spec=spec, room_id=room_id)
    """
    # Step 1: Check authentication
    auth_result = check_authentication(on_login_required)
    if not auth_result.success:
        return auth_result

    # Step 2: Validate config (skipped when config_content is provided,
    # since the config was built from the dialog form and doesn't need
    # file-based validation)
    if config_path and not config_content:
        config_result = check_config_validation(config_path, parent_widget)
        if not config_result.success:
            return config_result
    else:
        config_result = PresubmissionResult(success=True)

    # Step 3: Check video paths
    path_result = check_video_paths(
        slp_path, room_id, worker_id, parent_widget
    )
    if not path_result.success:
        return path_result

    # All checks passed
    return PresubmissionResult(
        success=True,
        path_mappings=path_result.path_mappings,
        validation_result=config_result.validation_result,
    )


def check_authentication(
    on_login_required: Callable[[], bool] | None = None,
) -> PresubmissionResult:
    """Check if user is authenticated, prompt for login if needed.

    Args:
        on_login_required: Callback to handle login. Returns True if login
            succeeded, False if cancelled or failed.

    Returns:
        PresubmissionResult indicating whether authentication check passed.
    """
    from sleap_rtc.api import is_logged_in

    if is_logged_in():
        logger.debug("Authentication check passed: already logged in")
        return PresubmissionResult(success=True)

    logger.info("User not logged in, prompting for login")

    if on_login_required is None:
        return PresubmissionResult(
            success=False,
            error="Not logged in. Please log in to continue.",
        )

    # Call the login callback
    login_success = on_login_required()

    if login_success:
        logger.info("Login successful")
        return PresubmissionResult(success=True)
    else:
        logger.info("Login cancelled or failed")
        return PresubmissionResult(
            success=False,
            cancelled=True,
            error="Login required to submit remote training job.",
        )


def check_config_validation(
    config_path: str,
    parent_widget=None,
) -> PresubmissionResult:
    """Validate the training configuration file.

    Shows ConfigValidationDialog if there are errors or warnings.
    - Errors block submission (user must fix config)
    - Warnings allow proceeding (user can click "Continue Anyway")

    Args:
        config_path: Path to the training configuration file.
        parent_widget: Parent Qt widget for the dialog.

    Returns:
        PresubmissionResult indicating whether validation passed.
    """
    from sleap_rtc.api import validate_config, ConfigurationError

    try:
        validation_result = validate_config(config_path)
    except ConfigurationError as e:
        return PresubmissionResult(
            success=False,
            error=f"Cannot read config file: {e}",
        )

    # If no errors and no warnings, we're good
    if validation_result.valid and not validation_result.warnings:
        logger.debug("Config validation passed: no errors or warnings")
        return PresubmissionResult(
            success=True,
            validation_result=validation_result,
        )

    # Show dialog for errors or warnings
    logger.info(
        f"Config validation: {len(validation_result.errors)} errors, "
        f"{len(validation_result.warnings)} warnings"
    )

    if parent_widget is not None:
        from sleap_rtc.gui.widgets import ConfigValidationDialog

        dialog = ConfigValidationDialog(validation_result, parent=parent_widget)
        result = dialog.exec()

        if validation_result.errors:
            # Errors: dialog only has OK button, always reject
            return PresubmissionResult(
                success=False,
                error="Configuration has validation errors that must be fixed.",
                validation_result=validation_result,
            )
        else:
            # Warnings only: check if user clicked "Continue Anyway"
            if result:  # accepted
                logger.info("User chose to continue despite warnings")
                return PresubmissionResult(
                    success=True,
                    validation_result=validation_result,
                )
            else:  # rejected/cancelled
                logger.info("User cancelled due to warnings")
                return PresubmissionResult(
                    success=False,
                    cancelled=True,
                    validation_result=validation_result,
                )
    else:
        # No parent widget, can't show dialog
        if validation_result.errors:
            error_msgs = [e.message for e in validation_result.errors]
            return PresubmissionResult(
                success=False,
                error=f"Configuration errors: {'; '.join(error_msgs)}",
                validation_result=validation_result,
            )
        else:
            # Warnings only, proceed without dialog
            logger.info("Config has warnings but no dialog to show, proceeding")
            return PresubmissionResult(
                success=True,
                validation_result=validation_result,
            )


def check_video_paths(
    slp_path: str,
    room_id: str,
    worker_id: str | None = None,
    parent_widget=None,
) -> PresubmissionResult:
    """Check if video paths exist on the worker.

    If any paths are missing, shows PathResolutionDialog for user to
    specify correct worker paths.

    Args:
        slp_path: Path to the SLP file on the worker filesystem.
        room_id: The room ID to check paths against.
        worker_id: Optional specific worker ID.
        parent_widget: Parent Qt widget for the dialog.

    Returns:
        PresubmissionResult with path mappings if successful.
    """
    from sleap_rtc.api import (
        check_video_paths as api_check_video_paths,
        AuthenticationError,
        RoomNotFoundError,
        ConfigurationError,
    )

    try:
        path_result = api_check_video_paths(
            slp_path=slp_path,
            room_id=room_id,
            worker_id=worker_id,
        )
    except AuthenticationError as e:
        return PresubmissionResult(
            success=False,
            error=f"Authentication error: {e}",
        )
    except RoomNotFoundError as e:
        return PresubmissionResult(
            success=False,
            error=f"Room error: {e}",
        )
    except ConfigurationError as e:
        return PresubmissionResult(
            success=False,
            error=f"Configuration error: {e}",
        )
    except Exception as e:
        logger.warning(f"Video path check failed: {e}")
        # If path check fails (e.g., network error), allow proceeding
        # with empty mappings - the worker will handle missing paths
        return PresubmissionResult(
            success=True,
            path_mappings={},
        )

    # If all paths found, we're good
    if path_result.all_found:
        logger.debug(f"All {path_result.total_videos} video paths found on worker")
        # Build path mappings from found videos
        mappings = {
            v.original_path: v.worker_path
            for v in path_result.videos
            if v.found and v.worker_path
        }
        return PresubmissionResult(
            success=True,
            path_mappings=mappings,
        )

    # Some paths missing, show dialog
    logger.info(
        f"Video path check: {path_result.found_count}/{path_result.total_videos} "
        f"found, {path_result.missing_count} missing"
    )

    if parent_widget is not None:
        from sleap_rtc.gui.widgets import PathResolutionDialog

        dialog = PathResolutionDialog(path_result.videos, parent=parent_widget)
        result = dialog.exec()

        if result:  # accepted
            resolved_paths = dialog.get_resolved_paths()
            logger.info(f"User resolved {len(resolved_paths)} video paths")
            return PresubmissionResult(
                success=True,
                path_mappings=resolved_paths,
            )
        else:  # rejected/cancelled
            logger.info("User cancelled path resolution")
            return PresubmissionResult(
                success=False,
                cancelled=True,
                error="Video path resolution cancelled.",
            )
    else:
        # No parent widget, can't show dialog
        missing_paths = [v.filename for v in path_result.videos if not v.found]
        return PresubmissionResult(
            success=False,
            error=f"Missing video paths on worker: {', '.join(missing_paths)}",
        )


class PresubmissionFlow:
    """Class-based interface for pre-submission validation.

    This provides a more flexible interface for GUI integration, allowing
    step-by-step validation with callbacks for each stage.

    Example:
        flow = PresubmissionFlow(
            config_path="/path/to/config.yaml",
            slp_path="/path/to/labels.slp",
            room_id="my-room",
        )
        flow.on_auth_required = self._handle_auth
        flow.on_validation_issues = self._handle_validation
        flow.on_path_resolution = self._handle_paths

        if flow.run(parent=self):
            # All checks passed, proceed with training
            run_remote_training(...)
    """

    def __init__(
        self,
        slp_path: str,
        room_id: str,
        worker_id: str | None = None,
        config_path: str | None = None,
        config_content: str | None = None,
    ):
        """Initialize the pre-submission flow.

        Args:
            slp_path: Path to the SLP file (for video path checking).
            room_id: The room ID to use for path checking.
            worker_id: Optional specific worker ID.
            config_path: Path to the training configuration file.
            config_content: Serialized config YAML string (alternative to
                config_path).
        """
        self.config_path = config_path
        self.config_content = config_content
        self.slp_path = slp_path
        self.room_id = room_id
        self.worker_id = worker_id

        # Callbacks (set by caller)
        self.on_auth_required: Callable[[], bool] | None = None
        self.on_validation_issues: Callable[["ValidationResult"], bool] | None = None
        self.on_path_resolution: Callable[["PathCheckResult"], dict | None] | None = None

        # Results
        self.result: PresubmissionResult | None = None
        self.path_mappings: dict[str, str] = {}
        self.validation_result: "ValidationResult | None" = None

    def run(self, parent=None) -> bool:
        """Run the complete pre-submission flow.

        Args:
            parent: Parent Qt widget for any dialogs.

        Returns:
            True if all checks passed and training can proceed.
        """
        self.result = run_presubmission_checks(
            slp_path=self.slp_path,
            room_id=self.room_id,
            worker_id=self.worker_id,
            config_path=self.config_path,
            config_content=self.config_content,
            parent_widget=parent,
            on_login_required=self.on_auth_required,
        )

        if self.result.success:
            self.path_mappings = self.result.path_mappings or {}
            self.validation_result = self.result.validation_result

        return self.result.success

    def get_error_message(self) -> str | None:
        """Get the error message if validation failed.

        Returns:
            Error message string, or None if no error.
        """
        if self.result:
            return self.result.error
        return None

    def was_cancelled(self) -> bool:
        """Check if the user cancelled during validation.

        Returns:
            True if user cancelled a dialog.
        """
        if self.result:
            return self.result.cancelled
        return False
