"""Command building from validated job specifications.

This module converts job specifications into sleap-nn CLI commands,
handling config path splitting, Hydra overrides, and optional flags.
"""

from pathlib import Path
from typing import Dict, List, Optional

from sleap_rtc.jobs.spec import TrainJobSpec, TrackJobSpec


# Default ZMQ ports for progress reporting
DEFAULT_ZMQ_PORTS = {
    "controller": 9000,
    "publish": 9001,
}


class CommandBuilder:
    """Builds sleap-nn commands from validated job specifications.

    This class converts TrainJobSpec and TrackJobSpec into command lists
    that can be executed via subprocess. Commands are built as lists of
    strings (not shell strings) for secure execution.
    """

    def build_train_command(
        self,
        spec: TrainJobSpec,
        zmq_ports: Optional[Dict[str, int]] = None,
        config_index: int = 0,
    ) -> List[str]:
        """Build sleap-nn train command from job spec.

        Args:
            spec: Validated TrainJobSpec
            zmq_ports: Optional dict with 'controller' and 'publish' ports
                      for ZMQ progress reporting
            config_index: Index of config to use when spec has multiple configs

        Returns:
            Command as list of strings

        Example:
            >>> builder = CommandBuilder()
            >>> spec = TrainJobSpec(config_paths=["/vast/project/centroid.yaml"])
            >>> cmd = builder.build_train_command(spec)
            >>> # ['sleap-nn', 'train', '--config-name', 'centroid.yaml', ...]
        """
        cmd = ["sleap-nn", "train"]

        # Config path - split into name and directory
        config_path = Path(spec.config_paths[config_index])
        cmd.extend(["--config-name", config_path.name])
        cmd.extend(["--config-dir", str(config_path.parent)])

        # Data path overrides (Hydra syntax)
        # sleap-nn expects train_labels_path as a list
        if spec.labels_path:
            cmd.append(f"data_config.train_labels_path=[{spec.labels_path}]")

        if spec.val_labels_path:
            cmd.append(f"data_config.val_labels_path={spec.val_labels_path}")

        # Training hyperparameter overrides
        if spec.max_epochs is not None:
            cmd.append(f"trainer_config.max_epochs={spec.max_epochs}")

        if spec.batch_size is not None:
            # Apply to both train and val data loaders
            cmd.append(
                f"trainer_config.train_data_loader.batch_size={spec.batch_size}"
            )
            cmd.append(f"trainer_config.val_data_loader.batch_size={spec.batch_size}")

        if spec.learning_rate is not None:
            cmd.append(f"trainer_config.optimizer.lr={spec.learning_rate}")

        if spec.run_name:
            cmd.append(f"trainer_config.run_name={spec.run_name}")

        if spec.resume_ckpt_path:
            cmd.append(f"trainer_config.resume_ckpt_path={spec.resume_ckpt_path}")

        # ZMQ ports for progress reporting
        # Use + prefix to append new keys (zmq is not in sleap-nn's default config schema)
        ports = zmq_ports or DEFAULT_ZMQ_PORTS
        cmd.append(f"+trainer_config.zmq.controller_port={ports.get('controller', 9000)}")
        cmd.append(f"+trainer_config.zmq.publish_port={ports.get('publish', 9001)}")

        return cmd

    def build_train_commands(
        self,
        spec: TrainJobSpec,
        zmq_ports: Optional[Dict[str, int]] = None,
    ) -> List[List[str]]:
        """Build sleap-nn train commands for all configs in spec.

        For multi-model training (e.g., top-down with centroid + centered_instance),
        this returns a list of commands to be executed sequentially.

        Args:
            spec: Validated TrainJobSpec with one or more configs
            zmq_ports: Optional dict with 'controller' and 'publish' ports

        Returns:
            List of commands, each as a list of strings
        """
        commands = []
        for i in range(len(spec.config_paths)):
            commands.append(self.build_train_command(spec, zmq_ports, config_index=i))
        return commands

    def build_track_command(self, spec: TrackJobSpec) -> List[str]:
        """Build sleap-nn track command from job spec.

        Args:
            spec: Validated TrackJobSpec

        Returns:
            Command as list of strings

        Example:
            >>> builder = CommandBuilder()
            >>> spec = TrackJobSpec(
            ...     data_path="/vast/data.slp",
            ...     model_paths=["/vast/models/centroid"],
            ... )
            >>> cmd = builder.build_track_command(spec)
            >>> # ['sleap-nn', 'track', '--data_path', '/vast/data.slp', ...]
        """
        cmd = ["sleap-nn", "track"]

        # Required arguments
        cmd.extend(["--data_path", spec.data_path])

        # Model paths (can be multiple)
        for model_path in spec.model_paths:
            cmd.extend(["--model_paths", model_path])

        # Optional arguments
        if spec.output_path:
            cmd.extend(["-o", spec.output_path])

        if spec.batch_size is not None:
            cmd.extend(["--batch_size", str(spec.batch_size)])

        if spec.peak_threshold is not None:
            cmd.extend(["--peak_threshold", str(spec.peak_threshold)])

        if spec.only_suggested_frames:
            cmd.append("--only_suggested_frames")

        if spec.frames:
            cmd.extend(["--frames", spec.frames])

        return cmd

    def build_command(
        self,
        spec,
        zmq_ports: Optional[Dict[str, int]] = None,
    ) -> List[str]:
        """Build command from any job spec type.

        Args:
            spec: TrainJobSpec or TrackJobSpec
            zmq_ports: Optional ZMQ ports (only used for train)

        Returns:
            Command as list of strings

        Raises:
            TypeError: If spec is not a recognized job spec type
        """
        if isinstance(spec, TrainJobSpec):
            return self.build_train_command(spec, zmq_ports)
        elif isinstance(spec, TrackJobSpec):
            return self.build_track_command(spec)
        else:
            raise TypeError(f"Unknown job spec type: {type(spec).__name__}")
