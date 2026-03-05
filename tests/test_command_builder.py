"""Tests for command building from job specifications."""

import pytest

from sleap_rtc.jobs.spec import TrainJobSpec, TrackJobSpec
from sleap_rtc.jobs.builder import CommandBuilder, DEFAULT_ZMQ_PORTS


class TestBuildTrainCommand:
    """Tests for building train commands."""

    def test_minimal_spec(self):
        """Test command with only required config_path."""
        builder = CommandBuilder()
        spec = TrainJobSpec(config_path="/vast/project/centroid.yaml")

        cmd = builder.build_train_command(spec)

        assert cmd[0] == "sleap-nn"
        assert cmd[1] == "train"
        assert "--config-name" in cmd
        assert "centroid.yaml" in cmd
        assert "--config-dir" in cmd
        assert "/vast/project" in cmd

    def test_config_path_splitting(self):
        """Test config path is correctly split into name and directory."""
        builder = CommandBuilder()
        spec = TrainJobSpec(config_path="/vast/project/configs/centroid.yaml")

        cmd = builder.build_train_command(spec)

        name_idx = cmd.index("--config-name")
        assert cmd[name_idx + 1] == "centroid.yaml"

        dir_idx = cmd.index("--config-dir")
        assert cmd[dir_idx + 1] == "/vast/project/configs"

    def test_labels_path_override(self):
        """Test labels_path creates Hydra override as list."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            labels_path="/vast/data/labels.slp",
        )

        cmd = builder.build_train_command(spec)

        # sleap-nn expects train_labels_path as a list
        assert "data_config.train_labels_path=[/vast/data/labels.slp]" in cmd

    def test_val_labels_path_override(self):
        """Test val_labels_path creates Hydra override."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            val_labels_path="/vast/data/val_labels.slp",
        )

        cmd = builder.build_train_command(spec)

        assert "data_config.val_labels_path=/vast/data/val_labels.slp" in cmd

    def test_max_epochs_override(self):
        """Test max_epochs creates Hydra override."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            max_epochs=100,
        )

        cmd = builder.build_train_command(spec)

        assert "trainer_config.max_epochs=100" in cmd

    def test_batch_size_applies_to_both_loaders(self):
        """Test batch_size applies to both train and val data loaders."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            batch_size=8,
        )

        cmd = builder.build_train_command(spec)

        assert "trainer_config.train_data_loader.batch_size=8" in cmd
        assert "trainer_config.val_data_loader.batch_size=8" in cmd

    def test_learning_rate_override(self):
        """Test learning_rate creates optimizer lr override."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            learning_rate=0.0001,
        )

        cmd = builder.build_train_command(spec)

        assert "trainer_config.optimizer.lr=0.0001" in cmd

    def test_run_name_override(self):
        """Test run_name creates Hydra override."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            run_name="experiment-1",
        )

        cmd = builder.build_train_command(spec)

        assert "trainer_config.run_name=experiment-1" in cmd

    def test_resume_checkpoint_override(self):
        """Test resume_ckpt_path creates Hydra override."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            resume_ckpt_path="/vast/models/checkpoint.ckpt",
        )

        cmd = builder.build_train_command(spec)

        assert "trainer_config.resume_ckpt_path=/vast/models/checkpoint.ckpt" in cmd

    def test_zmq_ports_default(self):
        """Test default ZMQ ports are included."""
        builder = CommandBuilder()
        spec = TrainJobSpec(config_path="/vast/config.yaml")

        cmd = builder.build_train_command(spec)

        # + prefix is required for Hydra to append keys not in schema
        assert (
            f"++trainer_config.zmq.controller_port={DEFAULT_ZMQ_PORTS['controller']}"
            in cmd
        )
        assert (
            f"++trainer_config.zmq.publish_port={DEFAULT_ZMQ_PORTS['publish']}" in cmd
        )

    def test_zmq_ports_custom(self):
        """Test custom ZMQ ports are used."""
        builder = CommandBuilder()
        spec = TrainJobSpec(config_path="/vast/config.yaml")

        cmd = builder.build_train_command(
            spec, zmq_ports={"controller": 8000, "publish": 8001}
        )

        # + prefix is required for Hydra to append keys not in schema
        assert "++trainer_config.zmq.controller_port=8000" in cmd
        assert "++trainer_config.zmq.publish_port=8001" in cmd

    def test_all_overrides(self):
        """Test command with all overrides."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/project/centroid.yaml",
            labels_path="/vast/data/labels.slp",
            val_labels_path="/vast/data/val.slp",
            max_epochs=100,
            batch_size=8,
            learning_rate=0.0001,
            run_name="exp1",
            resume_ckpt_path="/vast/models/ckpt.ckpt",
        )

        cmd = builder.build_train_command(spec)

        # Check all expected elements
        assert "sleap-nn" in cmd
        assert "train" in cmd
        assert "--config-name" in cmd
        assert "--config-dir" in cmd
        assert "data_config.train_labels_path=[/vast/data/labels.slp]" in cmd
        assert "data_config.val_labels_path=/vast/data/val.slp" in cmd
        assert "trainer_config.max_epochs=100" in cmd
        assert "trainer_config.train_data_loader.batch_size=8" in cmd
        assert "trainer_config.val_data_loader.batch_size=8" in cmd
        assert "trainer_config.optimizer.lr=0.0001" in cmd
        assert "trainer_config.run_name=exp1" in cmd
        assert "trainer_config.resume_ckpt_path=/vast/models/ckpt.ckpt" in cmd


class TestBuildTrainCommandVideoPathMap:
    """Tests for --video-path-map passthrough in train commands."""

    def test_no_path_mappings_no_video_path_map_args(self):
        """No path_mappings → no --video-path-map in command."""
        builder = CommandBuilder()
        spec = TrainJobSpec(config_path="/vast/config.yaml")

        cmd = builder.build_train_command(spec)

        assert "--video-path-map" not in cmd

    def test_empty_path_mappings_no_video_path_map_args(self):
        """Empty path_mappings dict → no --video-path-map in command."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            path_mappings={},
        )

        cmd = builder.build_train_command(spec)

        assert "--video-path-map" not in cmd

    def test_single_video_mapping_added(self):
        """Single video path mapping produces one --video-path-map OLD NEW pair."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            path_mappings={"/Volumes/data/vid.mp4": "/root/data/vid.mp4"},
        )

        cmd = builder.build_train_command(spec)

        assert "--video-path-map" in cmd
        idx = cmd.index("--video-path-map")
        assert cmd[idx + 1] == "/Volumes/data/vid.mp4"
        assert cmd[idx + 2] == "/root/data/vid.mp4"

    def test_multiple_video_mappings_all_added(self):
        """Multiple video path mappings all produce --video-path-map pairs."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            path_mappings={
                "/Volumes/data/vid1.mp4": "/root/data/vid1.mp4",
                "/Volumes/data/vid2.mp4": "/root/data/vid2.mp4",
            },
        )

        cmd = builder.build_train_command(spec)

        assert cmd.count("--video-path-map") == 2
        assert "/Volumes/data/vid1.mp4" in cmd
        assert "/root/data/vid1.mp4" in cmd
        assert "/Volumes/data/vid2.mp4" in cmd
        assert "/root/data/vid2.mp4" in cmd

    def test_slp_mapping_is_skipped(self):
        """The SLP file mapping (new_path == labels_path) is excluded from --video-path-map."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            labels_path="/root/data/labels.slp",
            path_mappings={
                "/Volumes/data/labels.slp": "/root/data/labels.slp",
                "/Volumes/data/vid.mp4": "/root/data/vid.mp4",
            },
        )

        cmd = builder.build_train_command(spec)

        # Only the video mapping should appear, not the SLP one
        assert cmd.count("--video-path-map") == 1
        idx = cmd.index("--video-path-map")
        assert cmd[idx + 1] == "/Volumes/data/vid.mp4"
        assert cmd[idx + 2] == "/root/data/vid.mp4"
        assert "/Volumes/data/labels.slp" not in cmd
        # labels_path appears only inside the Hydra override, not as a bare path-map arg
        assert not any(s == "/root/data/labels.slp" for s in cmd)

    def test_tif_sequence_mappings_added(self):
        """TIF image sequence paths are passed as --video-path-map (the main bug fix)."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            labels_path="/root/data/labels.slp",
            path_mappings={
                "/Volumes/data/labels.slp": "/root/data/labels.slp",
                "/Volumes/data/frames/001.tif": "/root/data/frames/001.tif",
                "/Volumes/data/frames/002.tif": "/root/data/frames/002.tif",
            },
        )

        cmd = builder.build_train_command(spec)

        assert cmd.count("--video-path-map") == 2
        assert "/Volumes/data/frames/001.tif" in cmd
        assert "/root/data/frames/001.tif" in cmd
        assert "/Volumes/data/frames/002.tif" in cmd
        assert "/root/data/frames/002.tif" in cmd

    def test_video_path_map_ordering(self):
        """--video-path-map pairs appear as consecutive OLD NEW triplets in the command."""
        builder = CommandBuilder()
        spec = TrainJobSpec(
            config_path="/vast/config.yaml",
            path_mappings={"/old/vid.mp4": "/new/vid.mp4"},
        )

        cmd = builder.build_train_command(spec)

        idx = cmd.index("--video-path-map")
        assert cmd[idx] == "--video-path-map"
        assert cmd[idx + 1] == "/old/vid.mp4"
        assert cmd[idx + 2] == "/new/vid.mp4"


class TestBuildTrackCommand:
    """Tests for building track commands."""

    def test_minimal_spec(self):
        """Test command with required fields only."""
        builder = CommandBuilder()
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=["/vast/models/centroid"],
        )

        cmd = builder.build_track_command(spec)

        assert cmd[0] == "sleap-nn"
        assert cmd[1] == "track"
        assert "--data_path" in cmd
        assert "/vast/data.slp" in cmd
        assert "--model_paths" in cmd
        assert "/vast/models/centroid" in cmd

    def test_multiple_model_paths(self):
        """Test command with multiple model paths."""
        builder = CommandBuilder()
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=[
                "/vast/models/centroid",
                "/vast/models/instance",
            ],
        )

        cmd = builder.build_track_command(spec)

        # Count occurrences of --model_paths
        model_path_count = cmd.count("--model_paths")
        assert model_path_count == 2
        assert "/vast/models/centroid" in cmd
        assert "/vast/models/instance" in cmd

    def test_output_path(self):
        """Test output path flag."""
        builder = CommandBuilder()
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=["/vast/models/model"],
            output_path="/vast/predictions.slp",
        )

        cmd = builder.build_track_command(spec)

        assert "-o" in cmd
        o_idx = cmd.index("-o")
        assert cmd[o_idx + 1] == "/vast/predictions.slp"

    def test_batch_size(self):
        """Test batch_size flag."""
        builder = CommandBuilder()
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=["/vast/models/model"],
            batch_size=16,
        )

        cmd = builder.build_track_command(spec)

        assert "--batch_size" in cmd
        bs_idx = cmd.index("--batch_size")
        assert cmd[bs_idx + 1] == "16"

    def test_peak_threshold(self):
        """Test peak_threshold flag."""
        builder = CommandBuilder()
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=["/vast/models/model"],
            peak_threshold=0.3,
        )

        cmd = builder.build_track_command(spec)

        assert "--peak_threshold" in cmd
        pt_idx = cmd.index("--peak_threshold")
        assert cmd[pt_idx + 1] == "0.3"

    def test_only_suggested_frames(self):
        """Test only_suggested_frames boolean flag."""
        builder = CommandBuilder()
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=["/vast/models/model"],
            only_suggested_frames=True,
        )

        cmd = builder.build_track_command(spec)

        assert "--only_suggested_frames" in cmd

    def test_only_suggested_frames_false(self):
        """Test only_suggested_frames=False is not included."""
        builder = CommandBuilder()
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=["/vast/models/model"],
            only_suggested_frames=False,
        )

        cmd = builder.build_track_command(spec)

        assert "--only_suggested_frames" not in cmd

    def test_frames_range(self):
        """Test frames range string."""
        builder = CommandBuilder()
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=["/vast/models/model"],
            frames="0-100,200-300",
        )

        cmd = builder.build_track_command(spec)

        assert "--frames" in cmd
        frames_idx = cmd.index("--frames")
        assert cmd[frames_idx + 1] == "0-100,200-300"

    def test_all_options(self):
        """Test command with all options."""
        builder = CommandBuilder()
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=["/vast/models/centroid", "/vast/models/instance"],
            output_path="/vast/output.slp",
            batch_size=8,
            peak_threshold=0.3,
            only_suggested_frames=True,
            frames="0-100",
        )

        cmd = builder.build_track_command(spec)

        assert "sleap-nn" in cmd
        assert "track" in cmd
        assert "--data_path" in cmd
        assert "/vast/data.slp" in cmd
        assert cmd.count("--model_paths") == 2
        assert "-o" in cmd
        assert "--batch_size" in cmd
        assert "--peak_threshold" in cmd
        assert "--only_suggested_frames" in cmd
        assert "--frames" in cmd


class TestBuildCommandGeneric:
    """Tests for generic build_command method."""

    def test_build_train_command(self):
        """Test generic build_command with TrainJobSpec."""
        builder = CommandBuilder()
        spec = TrainJobSpec(config_path="/vast/config.yaml")

        cmd = builder.build_command(spec)

        assert cmd[0] == "sleap-nn"
        assert cmd[1] == "train"

    def test_build_track_command(self):
        """Test generic build_command with TrackJobSpec."""
        builder = CommandBuilder()
        spec = TrackJobSpec(
            data_path="/vast/data.slp",
            model_paths=["/vast/models/model"],
        )

        cmd = builder.build_command(spec)

        assert cmd[0] == "sleap-nn"
        assert cmd[1] == "track"

    def test_build_command_with_zmq_ports(self):
        """Test generic build_command passes zmq_ports to train."""
        builder = CommandBuilder()
        spec = TrainJobSpec(config_path="/vast/config.yaml")

        cmd = builder.build_command(
            spec, zmq_ports={"controller": 5000, "publish": 5001}
        )

        # + prefix is required for Hydra to append keys not in schema
        assert "++trainer_config.zmq.controller_port=5000" in cmd
        assert "++trainer_config.zmq.publish_port=5001" in cmd

    def test_build_command_unknown_type(self):
        """Test generic build_command raises for unknown type."""
        builder = CommandBuilder()

        with pytest.raises(TypeError, match="Unknown job spec type"):
            builder.build_command("not a spec")


class TestDefaultZmqPorts:
    """Tests for default ZMQ port constants."""

    def test_default_ports_exist(self):
        """Test default ports are defined."""
        assert "controller" in DEFAULT_ZMQ_PORTS
        assert "publish" in DEFAULT_ZMQ_PORTS

    def test_default_ports_values(self):
        """Test default port values."""
        assert DEFAULT_ZMQ_PORTS["controller"] == 9000
        assert DEFAULT_ZMQ_PORTS["publish"] == 9001
