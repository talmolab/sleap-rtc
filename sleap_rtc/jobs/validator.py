"""Job specification validation.

This module provides validation for job specifications, checking:
- Paths are within allowed mounts
- Paths exist on the filesystem
- Numeric values are within valid ranges
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from sleap_rtc.jobs.spec import TrainJobSpec, TrackJobSpec


@dataclass
class ValidationError:
    """A validation error for a job specification field.

    Attributes:
        field: Name of the field that failed validation
        message: Human-readable error message
        code: Error code for programmatic handling (e.g., PATH_NOT_FOUND)
        path: The invalid path (if path-related error)
    """

    field: str
    message: str
    code: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {"field": self.field, "message": self.message}
        if self.code is not None:
            result["code"] = self.code
        if self.path is not None:
            result["path"] = self.path
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationError":
        """Create from dictionary."""
        return cls(
            field=data["field"],
            message=data["message"],
            code=data.get("code"),
            path=data.get("path"),
        )


# Numeric constraints for job parameters
NUMERIC_CONSTRAINTS = {
    "max_epochs": {"min": 1, "max": 10000},
    "batch_size": {"min": 1, "max": 256},
    "learning_rate": {"min": 1e-10, "max": 1.0},
    "peak_threshold": {"min": 0.0, "max": 1.0},
}


class JobValidator:
    """Validates job specifications before execution.

    The validator checks that:
    - All paths are within allowed mount points
    - All paths that should exist do exist
    - Numeric values are within valid ranges

    Attributes:
        file_manager: FileManager instance for path validation (optional)
        mounts: List of mount configurations (used if file_manager not provided)
    """

    def __init__(
        self,
        file_manager=None,
        mounts: Optional[List] = None,
    ):
        """Initialize validator.

        Args:
            file_manager: FileManager instance (has mounts and _is_path_allowed)
            mounts: List of MountConfig objects (alternative to file_manager)

        Note:
            Either file_manager or mounts must be provided. If both are provided,
            file_manager takes precedence.
        """
        self.file_manager = file_manager
        self._mounts = mounts

    @property
    def mounts(self) -> List:
        """Get the list of mounts."""
        if self.file_manager is not None:
            return self.file_manager.mounts
        return self._mounts or []

    def validate_train_spec(self, spec: TrainJobSpec) -> List[ValidationError]:
        """Validate a training job specification.

        Args:
            spec: TrainJobSpec to validate

        Returns:
            List of ValidationError objects (empty if valid)
        """
        errors = []

        # Validate config path (required)
        error = self._validate_path(spec.config_path, "config_path", must_exist=True)
        if error:
            errors.append(error)

        # Validate labels path if provided
        if spec.labels_path:
            error = self._validate_path(
                spec.labels_path, "labels_path", must_exist=True
            )
            if error:
                errors.append(error)

        # Validate val_labels path if provided
        if spec.val_labels_path:
            error = self._validate_path(
                spec.val_labels_path, "val_labels_path", must_exist=True
            )
            if error:
                errors.append(error)

        # Validate resume checkpoint if provided
        if spec.resume_ckpt_path:
            error = self._validate_path(
                spec.resume_ckpt_path, "resume_ckpt_path", must_exist=True
            )
            if error:
                errors.append(error)

        # Validate numeric fields
        if spec.max_epochs is not None:
            error = self._validate_numeric("max_epochs", spec.max_epochs)
            if error:
                errors.append(error)

        if spec.batch_size is not None:
            error = self._validate_numeric("batch_size", spec.batch_size)
            if error:
                errors.append(error)

        if spec.learning_rate is not None:
            error = self._validate_numeric("learning_rate", spec.learning_rate)
            if error:
                errors.append(error)

        return errors

    def validate_track_spec(self, spec: TrackJobSpec) -> List[ValidationError]:
        """Validate a tracking/inference job specification.

        Args:
            spec: TrackJobSpec to validate

        Returns:
            List of ValidationError objects (empty if valid)
        """
        errors = []

        # Validate data path (required)
        error = self._validate_path(spec.data_path, "data_path", must_exist=True)
        if error:
            errors.append(error)

        # Validate model paths (required, must be non-empty)
        if not spec.model_paths:
            errors.append(
                ValidationError(
                    field="model_paths",
                    message="At least one model path is required",
                )
            )
        else:
            for i, model_path in enumerate(spec.model_paths):
                error = self._validate_path(
                    model_path, f"model_paths[{i}]", must_exist=True
                )
                if error:
                    errors.append(error)

        # Validate output path directory if provided
        if spec.output_path:
            parent = str(Path(spec.output_path).parent)
            error = self._validate_path(
                parent, "output_path (parent directory)", must_exist=True
            )
            if error:
                errors.append(error)

        # Validate numeric fields
        if spec.batch_size is not None:
            error = self._validate_numeric("batch_size", spec.batch_size)
            if error:
                errors.append(error)

        if spec.peak_threshold is not None:
            error = self._validate_numeric("peak_threshold", spec.peak_threshold)
            if error:
                errors.append(error)

        return errors

    def validate(
        self, spec: Union[TrainJobSpec, TrackJobSpec]
    ) -> List[ValidationError]:
        """Validate any job specification.

        Args:
            spec: TrainJobSpec or TrackJobSpec to validate

        Returns:
            List of ValidationError objects (empty if valid)
        """
        if isinstance(spec, TrainJobSpec):
            return self.validate_train_spec(spec)
        elif isinstance(spec, TrackJobSpec):
            return self.validate_track_spec(spec)
        else:
            return [
                ValidationError(
                    field="type",
                    message=f"Unknown job spec type: {type(spec).__name__}",
                )
            ]

    def _validate_path(
        self, path: str, field: str, must_exist: bool = True
    ) -> Optional[ValidationError]:
        """Validate a path is within allowed mounts and optionally exists.

        Args:
            path: Path string to validate
            field: Field name for error reporting
            must_exist: Whether the path must exist

        Returns:
            ValidationError if invalid, None if valid
        """
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError) as e:
            return ValidationError(
                field, f"Invalid path: {e}", code="INVALID_PATH", path=path
            )

        # Check path is within allowed mounts
        if not self._is_path_allowed(resolved):
            return ValidationError(
                field, "Path not within allowed mounts", code="NOT_ALLOWED", path=path
            )

        # Check path exists
        if must_exist and not resolved.exists():
            return ValidationError(
                field, "Path does not exist", code="PATH_NOT_FOUND", path=path
            )

        return None

    def _is_path_allowed(self, path: Path) -> bool:
        """Check if a path is within an allowed mount.

        Uses FileManager's method if available, otherwise checks mounts directly.

        Args:
            path: Path to check

        Returns:
            True if path is within a configured mount
        """
        # Use FileManager's method if available
        if self.file_manager is not None:
            return self.file_manager._is_path_allowed(path)

        # Otherwise, check mounts directly
        if not self.mounts:
            return False

        try:
            resolved = path.resolve()
        except (OSError, ValueError):
            return False

        for mount in self.mounts:
            mount_path = Path(mount.path).resolve()
            try:
                resolved.relative_to(mount_path)
                return True
            except ValueError:
                continue

        return False

    def _validate_numeric(
        self, field: str, value: Union[int, float]
    ) -> Optional[ValidationError]:
        """Validate a numeric value is within allowed range.

        Args:
            field: Field name for error reporting
            value: Numeric value to validate

        Returns:
            ValidationError if invalid, None if valid
        """
        if field not in NUMERIC_CONSTRAINTS:
            return None

        constraints = NUMERIC_CONSTRAINTS[field]
        min_val = constraints["min"]
        max_val = constraints["max"]

        if value < min_val or value > max_val:
            return ValidationError(
                field,
                f"Value must be between {min_val} and {max_val}, got {value}",
            )

        return None
