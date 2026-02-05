"""Job specification data types for structured job submission.

This module defines the data structures for training and inference jobs
that can be serialized, validated, and converted to sleap-nn commands.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional, List, Union
import json


@dataclass
class TrainJobSpec:
    """Specification for a training job.

    Attributes:
        config_path: Full path to config YAML file (required)
        labels_path: Override for data_config.train_labels_path
        val_labels_path: Override for data_config.val_labels_path
        max_epochs: Maximum training epochs
        batch_size: Batch size for training and validation
        learning_rate: Learning rate for optimizer
        run_name: Name for the training run (used in checkpoint directory)
        resume_ckpt_path: Path to checkpoint for resuming training
    """

    config_path: str
    labels_path: Optional[str] = None
    val_labels_path: Optional[str] = None
    max_epochs: Optional[int] = None
    batch_size: Optional[int] = None
    learning_rate: Optional[float] = None
    run_name: Optional[str] = None
    resume_ckpt_path: Optional[str] = None

    def to_json(self) -> str:
        """Serialize spec to JSON string."""
        data = {"type": "train", **asdict(self)}
        # Remove None values for cleaner JSON
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data)

    @classmethod
    def from_json(cls, data: str) -> "TrainJobSpec":
        """Deserialize spec from JSON string."""
        parsed = json.loads(data)
        parsed.pop("type", None)
        return cls(**parsed)

    def to_dict(self) -> dict:
        """Convert spec to dictionary with type field."""
        data = {"type": "train", **asdict(self)}
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "TrainJobSpec":
        """Create spec from dictionary."""
        data = dict(data)  # Make a copy
        data.pop("type", None)
        return cls(**data)


@dataclass
class TrackJobSpec:
    """Specification for an inference/tracking job.

    Attributes:
        data_path: Path to .slp file or video for inference (required)
        model_paths: Paths to model directories (required, can be multiple)
        output_path: Path for output predictions file
        batch_size: Batch size for inference
        peak_threshold: Peak detection threshold (0.0-1.0)
        only_suggested_frames: Only run inference on suggested frames
        frames: Frame range string (e.g., "0-100,200-300")
    """

    data_path: str
    model_paths: List[str] = field(default_factory=list)
    output_path: Optional[str] = None
    batch_size: Optional[int] = None
    peak_threshold: Optional[float] = None
    only_suggested_frames: bool = False
    frames: Optional[str] = None

    def to_json(self) -> str:
        """Serialize spec to JSON string."""
        data = {"type": "track", **asdict(self)}
        # Remove None values and False booleans for cleaner JSON
        data = {
            k: v
            for k, v in data.items()
            if v is not None and v is not False and v != []
        }
        # Always include model_paths even if empty (it's required)
        if "model_paths" not in data:
            data["model_paths"] = self.model_paths
        return json.dumps(data)

    @classmethod
    def from_json(cls, data: str) -> "TrackJobSpec":
        """Deserialize spec from JSON string."""
        parsed = json.loads(data)
        parsed.pop("type", None)
        return cls(**parsed)

    def to_dict(self) -> dict:
        """Convert spec to dictionary with type field."""
        data = {"type": "track", **asdict(self)}
        return {
            k: v
            for k, v in data.items()
            if v is not None and v is not False and v != []
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrackJobSpec":
        """Create spec from dictionary."""
        data = dict(data)  # Make a copy
        data.pop("type", None)
        return cls(**data)


def parse_job_spec(json_str: str) -> Union[TrainJobSpec, TrackJobSpec]:
    """Parse a JSON string into the appropriate job spec type.

    Args:
        json_str: JSON string with "type" field indicating spec type

    Returns:
        TrainJobSpec or TrackJobSpec depending on type field

    Raises:
        ValueError: If type field is missing or unknown
    """
    parsed = json.loads(json_str)
    job_type = parsed.get("type")

    if job_type == "train":
        return TrainJobSpec.from_json(json_str)
    elif job_type == "track":
        return TrackJobSpec.from_json(json_str)
    else:
        raise ValueError(f"Unknown job type: {job_type}")
