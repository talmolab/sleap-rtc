"""Tests for job specification data types."""

import json
import pytest

from sleap_rtc.jobs.spec import TrainJobSpec, TrackJobSpec, parse_job_spec


class TestTrainJobSpec:
    """Tests for TrainJobSpec dataclass."""

    def test_create_with_required_fields(self):
        """Test creating spec with only required config_path."""
        spec = TrainJobSpec(config_path="/vast/project/centroid.yaml")

        assert spec.config_path == "/vast/project/centroid.yaml"
        assert spec.labels_path is None
        assert spec.val_labels_path is None
        assert spec.max_epochs is None
        assert spec.batch_size is None
        assert spec.learning_rate is None
        assert spec.run_name is None
        assert spec.resume_ckpt_path is None

    def test_create_with_all_fields(self):
        """Test creating spec with all fields populated."""
        spec = TrainJobSpec(
            config_path="/vast/project/centroid.yaml",
            labels_path="/vast/data/labels.slp",
            val_labels_path="/vast/data/val_labels.slp",
            max_epochs=100,
            batch_size=8,
            learning_rate=0.0001,
            run_name="experiment-1",
            resume_ckpt_path="/vast/models/checkpoint.ckpt",
        )

        assert spec.config_path == "/vast/project/centroid.yaml"
        assert spec.labels_path == "/vast/data/labels.slp"
        assert spec.val_labels_path == "/vast/data/val_labels.slp"
        assert spec.max_epochs == 100
        assert spec.batch_size == 8
        assert spec.learning_rate == 0.0001
        assert spec.run_name == "experiment-1"
        assert spec.resume_ckpt_path == "/vast/models/checkpoint.ckpt"

    def test_to_json_minimal(self):
        """Test JSON serialization with minimal fields."""
        spec = TrainJobSpec(config_path="/vast/project/centroid.yaml")
        json_str = spec.to_json()
        parsed = json.loads(json_str)

        assert parsed["type"] == "train"
        assert parsed["config_path"] == "/vast/project/centroid.yaml"
        # None values should be omitted
        assert "labels_path" not in parsed
        assert "max_epochs" not in parsed

    def test_to_json_full(self):
        """Test JSON serialization with all fields."""
        spec = TrainJobSpec(
            config_path="/vast/project/centroid.yaml",
            labels_path="/vast/data/labels.slp",
            max_epochs=100,
            batch_size=8,
            learning_rate=0.0001,
            run_name="exp1",
        )
        json_str = spec.to_json()
        parsed = json.loads(json_str)

        assert parsed["type"] == "train"
        assert parsed["config_path"] == "/vast/project/centroid.yaml"
        assert parsed["labels_path"] == "/vast/data/labels.slp"
        assert parsed["max_epochs"] == 100
        assert parsed["batch_size"] == 8
        assert parsed["learning_rate"] == 0.0001
        assert parsed["run_name"] == "exp1"

    def test_from_json(self):
        """Test JSON deserialization."""
        json_str = json.dumps(
            {
                "type": "train",
                "config_path": "/vast/project/centroid.yaml",
                "labels_path": "/vast/data/labels.slp",
                "max_epochs": 100,
            }
        )
        spec = TrainJobSpec.from_json(json_str)

        assert spec.config_path == "/vast/project/centroid.yaml"
        assert spec.labels_path == "/vast/data/labels.slp"
        assert spec.max_epochs == 100
        assert spec.batch_size is None

    def test_roundtrip(self):
        """Test JSON serialization roundtrip."""
        original = TrainJobSpec(
            config_path="/vast/project/centroid.yaml",
            labels_path="/vast/data/labels.slp",
            max_epochs=100,
            batch_size=8,
        )
        json_str = original.to_json()
        restored = TrainJobSpec.from_json(json_str)

        assert restored.config_path == original.config_path
        assert restored.labels_path == original.labels_path
        assert restored.max_epochs == original.max_epochs
        assert restored.batch_size == original.batch_size

    def test_to_dict(self):
        """Test dictionary conversion."""
        spec = TrainJobSpec(config_path="/vast/config.yaml", max_epochs=50)
        d = spec.to_dict()

        assert d["type"] == "train"
        assert d["config_path"] == "/vast/config.yaml"
        assert d["max_epochs"] == 50
        assert "labels_path" not in d  # None values omitted

    def test_from_dict(self):
        """Test creating spec from dictionary."""
        d = {
            "type": "train",
            "config_path": "/vast/config.yaml",
            "max_epochs": 50,
        }
        spec = TrainJobSpec.from_dict(d)

        assert spec.config_path == "/vast/config.yaml"
        assert spec.max_epochs == 50


class TestTrackJobSpec:
    """Tests for TrackJobSpec dataclass."""

    def test_create_with_required_fields(self):
        """Test creating spec with required fields."""
        spec = TrackJobSpec(
            data_path="/vast/data/labels.slp",
            model_paths=["/vast/models/centroid"],
        )

        assert spec.data_path == "/vast/data/labels.slp"
        assert spec.model_paths == ["/vast/models/centroid"]
        assert spec.output_path is None
        assert spec.batch_size is None
        assert spec.peak_threshold is None
        assert spec.only_suggested_frames is False
        assert spec.frames is None

    def test_create_with_all_fields(self):
        """Test creating spec with all fields."""
        spec = TrackJobSpec(
            data_path="/vast/data/labels.slp",
            model_paths=["/vast/models/centroid", "/vast/models/instance"],
            output_path="/vast/predictions.slp",
            batch_size=8,
            peak_threshold=0.3,
            only_suggested_frames=True,
            frames="0-100,200-300",
        )

        assert spec.data_path == "/vast/data/labels.slp"
        assert len(spec.model_paths) == 2
        assert spec.output_path == "/vast/predictions.slp"
        assert spec.batch_size == 8
        assert spec.peak_threshold == 0.3
        assert spec.only_suggested_frames is True
        assert spec.frames == "0-100,200-300"

    def test_to_json_minimal(self):
        """Test JSON serialization with minimal fields."""
        spec = TrackJobSpec(
            data_path="/vast/data/labels.slp",
            model_paths=["/vast/models/centroid"],
        )
        json_str = spec.to_json()
        parsed = json.loads(json_str)

        assert parsed["type"] == "track"
        assert parsed["data_path"] == "/vast/data/labels.slp"
        assert parsed["model_paths"] == ["/vast/models/centroid"]
        # False/None values should be omitted
        assert "only_suggested_frames" not in parsed
        assert "output_path" not in parsed

    def test_to_json_full(self):
        """Test JSON serialization with all fields."""
        spec = TrackJobSpec(
            data_path="/vast/data/labels.slp",
            model_paths=["/vast/models/centroid", "/vast/models/instance"],
            output_path="/vast/predictions.slp",
            batch_size=8,
            peak_threshold=0.3,
            only_suggested_frames=True,
            frames="0-100",
        )
        json_str = spec.to_json()
        parsed = json.loads(json_str)

        assert parsed["type"] == "track"
        assert parsed["data_path"] == "/vast/data/labels.slp"
        assert parsed["model_paths"] == [
            "/vast/models/centroid",
            "/vast/models/instance",
        ]
        assert parsed["output_path"] == "/vast/predictions.slp"
        assert parsed["batch_size"] == 8
        assert parsed["peak_threshold"] == 0.3
        assert parsed["only_suggested_frames"] is True
        assert parsed["frames"] == "0-100"

    def test_from_json(self):
        """Test JSON deserialization."""
        json_str = json.dumps(
            {
                "type": "track",
                "data_path": "/vast/data/labels.slp",
                "model_paths": ["/vast/models/centroid"],
                "batch_size": 16,
            }
        )
        spec = TrackJobSpec.from_json(json_str)

        assert spec.data_path == "/vast/data/labels.slp"
        assert spec.model_paths == ["/vast/models/centroid"]
        assert spec.batch_size == 16
        assert spec.only_suggested_frames is False

    def test_roundtrip(self):
        """Test JSON serialization roundtrip."""
        original = TrackJobSpec(
            data_path="/vast/data/labels.slp",
            model_paths=["/vast/models/centroid", "/vast/models/instance"],
            batch_size=8,
            only_suggested_frames=True,
        )
        json_str = original.to_json()
        restored = TrackJobSpec.from_json(json_str)

        assert restored.data_path == original.data_path
        assert restored.model_paths == original.model_paths
        assert restored.batch_size == original.batch_size
        assert restored.only_suggested_frames == original.only_suggested_frames

    def test_multiple_model_paths(self):
        """Test spec with multiple model paths."""
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=[
                "/vast/models/centroid",
                "/vast/models/centered_instance",
                "/vast/models/topdown",
            ],
        )
        json_str = spec.to_json()
        parsed = json.loads(json_str)

        assert len(parsed["model_paths"]) == 3
        assert "/vast/models/centroid" in parsed["model_paths"]
        assert "/vast/models/centered_instance" in parsed["model_paths"]
        assert "/vast/models/topdown" in parsed["model_paths"]

    def test_to_dict(self):
        """Test dictionary conversion."""
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=["/vast/models/model"],
            batch_size=16,
        )
        d = spec.to_dict()

        assert d["type"] == "track"
        assert d["data_path"] == "/vast/data.slp"
        assert d["model_paths"] == ["/vast/models/model"]
        assert d["batch_size"] == 16
        assert "only_suggested_frames" not in d  # False value omitted

    def test_from_dict(self):
        """Test creating spec from dictionary."""
        d = {
            "type": "track",
            "data_path": "/vast/data.slp",
            "model_paths": ["/vast/models/model"],
        }
        spec = TrackJobSpec.from_dict(d)

        assert spec.data_path == "/vast/data.slp"
        assert spec.model_paths == ["/vast/models/model"]


class TestParseJobSpec:
    """Tests for parse_job_spec utility function."""

    def test_parse_train_spec(self):
        """Test parsing a train job spec."""
        json_str = json.dumps(
            {
                "type": "train",
                "config_path": "/vast/config.yaml",
                "max_epochs": 100,
            }
        )
        spec = parse_job_spec(json_str)

        assert isinstance(spec, TrainJobSpec)
        assert spec.config_path == "/vast/config.yaml"
        assert spec.max_epochs == 100

    def test_parse_track_spec(self):
        """Test parsing a track job spec."""
        json_str = json.dumps(
            {
                "type": "track",
                "data_path": "/vast/data.slp",
                "model_paths": ["/vast/models/model"],
            }
        )
        spec = parse_job_spec(json_str)

        assert isinstance(spec, TrackJobSpec)
        assert spec.data_path == "/vast/data.slp"
        assert spec.model_paths == ["/vast/models/model"]

    def test_parse_unknown_type(self):
        """Test parsing with unknown type raises error."""
        json_str = json.dumps({"type": "unknown", "some_field": "value"})

        with pytest.raises(ValueError, match="Unknown job type"):
            parse_job_spec(json_str)

    def test_parse_missing_type(self):
        """Test parsing without type raises error."""
        json_str = json.dumps({"config_path": "/vast/config.yaml"})

        with pytest.raises(ValueError, match="Unknown job type"):
            parse_job_spec(json_str)
