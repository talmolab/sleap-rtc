"""Job execution orchestration for training and inference workflows.

This module handles execution of SLEAP training and inference jobs, including
script parsing, process management, log streaming, and progress reporting.
"""

import asyncio
import logging
import os
import re
import shutil
import stat
import time
from pathlib import Path
from typing import TYPE_CHECKING

from aiortc import RTCDataChannel

if TYPE_CHECKING:
    from sleap_rtc.worker.capabilities import WorkerCapabilities

# Set chunk separator for log streaming
SEP = re.compile(rb"[\r\n]")


class JobExecutor:
    """Executes training and inference jobs with progress monitoring.

    This class orchestrates the execution of SLEAP training and inference
    workflows, handling script parsing, process execution, log streaming,
    and integration with progress reporting systems.

    Attributes:
        worker: Reference to parent RTCWorkerClient for accessing shared state.
        capabilities: WorkerCapabilities instance for job compatibility.
        unzipped_dir: Working directory for current job.
        output_dir: Output directory for job results.
        package_type: Type of package ("train" or "track").
    """

    def __init__(
        self,
        worker,
        capabilities: "WorkerCapabilities",
    ):
        """Initialize job executor.

        Args:
            worker: Parent RTCWorkerClient instance.
            capabilities: WorkerCapabilities for job compatibility checking.
        """
        self.worker = worker
        self.capabilities = capabilities

        # Job execution state
        self.unzipped_dir = ""
        self.output_dir = ""
        self.package_type = "train"  # Default to training

    def parse_training_script(self, train_script_path: str):
        """Parse train-script.sh and extract sleap-nn train commands.

        Args:
            train_script_path: Path to train-script.sh

        Returns:
            List of config names for training jobs.
        """
        jobs = []
        # Updated pattern to match 'sleap-nn train' and extract --config-name
        # Example: sleap-nn train --config-name centroid.yaml...
        pattern = re.compile(r"^\s*sleap-(?:nn\s+)?train\s+.*--config-name\s+(\S+)")

        with open(train_script_path, "r") as f:
            for line in f:
                match = pattern.match(line)
                if match:
                    config_name = match.group(1)
                    # For sleap-nn, we don't need separate labels file
                    jobs.append(config_name)
        return jobs

    def parse_track_script(self, track_script_path: str):
        """Parse track-script.sh and extract sleap-nn track commands.

        Args:
            track_script_path: Path to track-script.sh

        Returns:
            List of command argument lists.
        """
        commands = []
        pattern = re.compile(r"^\s*sleap-nn\s+track\s+(.+)")

        with open(track_script_path, "r") as f:
            script_content = f.read()

        # Handle multi-line commands with backslashes
        script_content = script_content.replace("\\\n", " ")

        for line in script_content.split("\n"):
            match = pattern.match(line)
            if match:
                # Split arguments while preserving quoted strings
                args_str = match.group(1)
                # Simple split (for more complex parsing, use shlex.split)
                args = ["sleap-nn", "track"] + args_str.split()
                commands.append(args)

        return commands

    async def run_all_training_jobs(
        self, channel: RTCDataChannel, train_script_path: str
    ):
        """Execute training jobs with progress updates.

        Args:
            channel: RTC data channel for sending logs
            train_script_path: Path to training script
        """
        training_jobs = self.parse_training_script(train_script_path)

        # Get job ID and client ID from worker's current_job if available
        job_id = (
            self.worker.current_job.get("job_id") if self.worker.current_job else None
        )
        client_id = (
            self.worker.current_job.get("client_id")
            if self.worker.current_job
            else None
        )

        try:
            for config_name in training_jobs:
                job_name = Path(config_name).stem

                # Send RTC msg over channel to indicate job start.
                logging.info(
                    f"Starting training job: {job_name} with config: {config_name}"
                )
                channel.send(f"TRAIN_JOB_START::{job_name}")

                # Send starting status via peer message
                if job_id and client_id:
                    await self._send_peer_message(
                        client_id,
                        {
                            "app_message_type": "job_status",
                            "job_id": job_id,
                            "status": "starting",
                            "progress": 0.0,
                            "message": f"Initializing training: {job_name}",
                        },
                    )

                # Use sleap-nn train command for newer SLEAP versions
                # Run directly in the extracted directory with config-dir from training script
                cmd = [
                    "sleap-nn",
                    "train",
                    "--config-name",
                    config_name,
                    "--config-dir",
                    ".",
                    "trainer_config.ckpt_dir=models",
                    f"trainer_config.run_name={job_name}",
                    "trainer_config.zmq.controller_port=9000",
                    "trainer_config.zmq.publish_port=9001",
                    # macOS compatibility: disable multiprocessing
                    "trainer_config.train_data_loader.num_workers=0",
                    "trainer_config.val_data_loader.num_workers=0",
                ]
                logging.info(f"[RUNNING] {' '.join(cmd)} (cwd={self.unzipped_dir})")

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=self.unzipped_dir,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )

                assert process.stdout is not None
                logging.info(f"Process started with PID: {process.pid}")

                async def stream_logs(
                    emit_on_cr=True, read_size=512, max_flush=64 * 1024
                ):
                    buf = b""
                    try:
                        while True:
                            chunk = await process.stdout.read(read_size)
                            if not chunk:
                                # process ended; flush any remaining text
                                if buf:
                                    channel.send(buf.decode(errors="replace") + "\n")
                                break

                            buf += chunk

                            while True:
                                m = SEP.search(buf)
                                if not m:
                                    # If tqdm keeps extending one long line, flush
                                    if len(buf) > max_flush:
                                        text = buf.decode(errors="replace")
                                        if emit_on_cr and text:
                                            channel.send("\r" + text)
                                        buf = b""
                                    break

                                sep = buf[m.start() : m.end()]
                                payload = buf[: m.start()]
                                buf = buf[m.end() :]

                                text = payload.decode(errors="replace")
                                if not text:
                                    continue

                                if sep == b"\n":
                                    channel.send(text + "\n")
                                else:  # sep == b'\r'
                                    if emit_on_cr:
                                        channel.send("\r" + text)

                    except Exception as e:
                        logging.exception("stream_logs failed: %s", e)
                        try:
                            channel.send(f"[log-stream error] {e}\n")
                        except Exception:
                            pass

                # Track start time for duration calculation
                start_time = time.time()

                await stream_logs()
                logging.info("Waiting for process to complete...")
                await process.wait()
                logging.info(
                    f"Process completed with return code: {process.returncode}"
                )

                # Calculate training duration
                training_duration = (time.time() - start_time) / 60

                if process.returncode == 0:
                    logging.info(f"[DONE] Job {job_name} completed successfully.")
                    if channel.readyState == "open":
                        channel.send(f"TRAIN_JOB_END::{job_name}")

                    # Send completion status via peer message
                    if job_id and client_id:
                        await self._send_peer_message(
                            client_id,
                            {
                                "app_message_type": "job_status",
                                "job_id": job_id,
                                "status": "running",
                                "progress": 1.0,
                                "message": f"Training completed: {job_name}",
                            },
                        )
                else:
                    logging.warning(
                        f"[FAILED] Job {job_name} exited with code {process.returncode}."
                    )
                    if channel.readyState == "open":
                        channel.send(
                            f"TRAIN_JOB_ERROR::{job_name}::{process.returncode}"
                        )

                    # Send failure status via peer message
                    if job_id and client_id:
                        await self._send_peer_message(
                            client_id,
                            {
                                "app_message_type": "job_failed",
                                "job_id": job_id,
                                "status": "failed",
                                "error": {
                                    "code": "TRAINING_FAILED",
                                    "message": f"Training job {job_name} failed with exit code {process.returncode}",
                                    "recoverable": False,
                                },
                            },
                        )

            # All jobs completed - send final completion message
            channel.send("TRAINING_JOBS_DONE")

            # Send job completion message via peer message
            if job_id and client_id:
                await self._send_peer_message(
                    client_id,
                    {
                        "app_message_type": "job_complete",
                        "job_id": job_id,
                        "status": "completed",
                        "result": {
                            "training_duration_minutes": training_duration,
                            "total_jobs": len(training_jobs),
                        },
                        "transfer_method": "webrtc_datachannel",
                        "ready_for_download": True,
                    },
                )

        except Exception as e:
            # Handle any unexpected errors during training
            logging.error(f"Error during training execution: {e}")
            if job_id and client_id:
                await self._send_peer_message(
                    client_id,
                    {
                        "app_message_type": "job_failed",
                        "job_id": job_id,
                        "status": "failed",
                        "error": {
                            "code": "EXECUTION_ERROR",
                            "message": str(e),
                            "recoverable": False,
                        },
                    },
                )
            raise

        finally:
            # Update status back to available when done
            if self.worker.current_job:
                await self.worker.update_status("available")
                self.worker.current_job = None

    async def run_track_workflow(self, channel: RTCDataChannel, track_script_path: str):
        """Execute inference workflow on received track package.

        Args:
            channel: RTC data channel for sending progress
            track_script_path: Path to track-script.sh
        """
        # Get job ID and client ID from worker's current_job if available
        job_id = (
            self.worker.current_job.get("job_id") if self.worker.current_job else None
        )
        client_id = (
            self.worker.current_job.get("client_id")
            if self.worker.current_job
            else None
        )

        try:
            if not Path(track_script_path).exists():
                logging.error("No track-script.sh found in package")
                channel.send("INFERENCE_ERROR::No track script found")

                # Send error via peer message
                if job_id and client_id:
                    await self._send_peer_message(
                        client_id,
                        {
                            "app_message_type": "job_failed",
                            "job_id": job_id,
                            "status": "failed",
                            "error": {
                                "code": "TRACK_SCRIPT_NOT_FOUND",
                                "message": "No track script found in package",
                                "recoverable": False,
                            },
                        },
                    )
                return

            logging.info("Starting inference workflow...")
            channel.send("INFERENCE_START")

            # Send starting status via peer message
            if job_id and client_id:
                await self._send_peer_message(
                    client_id,
                    {
                        "app_message_type": "job_status",
                        "job_id": job_id,
                        "status": "starting",
                        "progress": 0.0,
                        "message": "Initializing inference",
                    },
                )

            # Make script executable
            os.chmod(
                track_script_path, os.stat(track_script_path).st_mode | stat.S_IEXEC
            )

            # Parse and run track commands
            track_commands = self.parse_track_script(track_script_path)
            start_time = time.time()

            for cmd_args in track_commands:
                job_name = "inference"
                channel.send(f"INFERENCE_JOB_START::{job_name}")

                # Run sleap-nn track
                process = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=self.unzipped_dir,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )

                # Stream logs
                async for line in process.stdout:
                    decoded_line = line.decode().rstrip()
                    if channel.readyState == "open":
                        try:
                            channel.send(f"TRACK_LOG:{decoded_line}")
                        except Exception as e:
                            logging.error(f"Failed to send track log: {e}")

                await process.wait()

                if process.returncode == 0:
                    logging.info("Inference completed successfully")
                    channel.send(f"INFERENCE_JOB_END::{job_name}")
                else:
                    logging.error(f"Inference failed with code {process.returncode}")
                    channel.send(
                        f"INFERENCE_JOB_ERROR::{job_name}::{process.returncode}"
                    )

                    # Send failure via peer message
                    if job_id and client_id:
                        await self._send_peer_message(
                            client_id,
                            {
                                "app_message_type": "job_failed",
                                "job_id": job_id,
                                "status": "failed",
                                "error": {
                                    "code": "INFERENCE_FAILED",
                                    "message": f"Inference failed with exit code {process.returncode}",
                                    "recoverable": False,
                                },
                            },
                        )
                    return

            # Find and send predictions file
            predictions_files = list(Path(self.unzipped_dir).glob("*.predictions.slp"))

            if predictions_files:
                predictions_path = predictions_files[0]

                # Send predictions back to client via RTC
                logging.info(f"Sending predictions via RTC: {predictions_path}")
                await self.worker.send_file(channel, str(predictions_path))

                # Send completion via peer message
                if job_id and client_id:
                    predictions_size_mb = predictions_path.stat().st_size / (
                        1024 * 1024
                    )
                    await self._send_peer_message(
                        client_id,
                        {
                            "app_message_type": "job_complete",
                            "job_id": job_id,
                            "status": "completed",
                            "result": {
                                "predictions_size_mb": predictions_size_mb,
                                "inference_duration_seconds": int(
                                    (time.time() - start_time)
                                ),
                                "predictions_file": predictions_path.name,
                            },
                            "transfer_method": "webrtc_datachannel",
                            "ready_for_download": True,
                        },
                    )
            else:
                logging.warning("No predictions file found")

                # Send warning via peer message
                if job_id and client_id:
                    await self._send_peer_message(
                        client_id,
                        {
                            "app_message_type": "job_complete",
                            "job_id": job_id,
                            "status": "completed",
                            "result": {
                                "inference_duration_seconds": int(
                                    (time.time() - start_time)
                                ),
                                "warning": "No predictions file generated",
                            },
                            "transfer_method": "webrtc_datachannel",
                            "ready_for_download": False,
                        },
                    )

            channel.send("INFERENCE_JOBS_DONE")

        except Exception as e:
            # Handle any unexpected errors during inference
            logging.error(f"Error during inference execution: {e}")
            if job_id and client_id:
                await self._send_peer_message(
                    client_id,
                    {
                        "app_message_type": "job_failed",
                        "job_id": job_id,
                        "status": "failed",
                        "error": {
                            "code": "EXECUTION_ERROR",
                            "message": str(e),
                            "recoverable": False,
                        },
                    },
                )
            raise

        finally:
            # Update status back to available when done
            if self.worker.current_job:
                await self.worker.update_status("available")
                self.worker.current_job = None

    async def _send_peer_message(self, to_peer_id: str, payload: dict):
        """Send peer message via worker's websocket.

        Args:
            to_peer_id: Target peer ID
            payload: Message payload
        """
        # Delegate to worker's peer messaging
        await self.worker._send_peer_message(to_peer_id, payload)

    async def execute_from_spec(
        self,
        channel,
        cmd: list,
        job_id: str,
        job_type: str = "train",
        working_dir: str = None,
    ):
        """Execute a job from a pre-built command list (structured job submission).

        This method executes a sleap-nn command that was built by CommandBuilder
        from a validated job specification. It reuses the log streaming logic
        and sends JOB_PROGRESS, JOB_COMPLETE, or JOB_FAILED messages.

        Args:
            channel: RTC data channel for sending logs and status
            cmd: Command list to execute (e.g., ["sleap-nn", "train", ...])
            job_id: Unique job identifier
            job_type: Type of job ("train" or "track")
            working_dir: Working directory for execution (defaults to current dir)
        """
        from sleap_rtc.protocol import (
            MSG_JOB_PROGRESS,
            MSG_JOB_COMPLETE,
            MSG_JOB_FAILED,
            MSG_SEPARATOR,
        )

        working_dir = working_dir or os.getcwd()
        start_time = time.time()

        logging.info(f"[JOB {job_id}] Starting {job_type} job")
        logging.info(f"[JOB {job_id}] Command: {' '.join(cmd)}")
        logging.info(f"[JOB {job_id}] Working directory: {working_dir}")

        try:
            # Start the process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=working_dir,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )

            logging.info(f"[JOB {job_id}] Process started with PID: {process.pid}")

            # Stream logs with progress extraction
            async def stream_logs_with_progress():
                """Stream logs and extract progress information."""
                buf = b""
                epoch_pattern = re.compile(r"Epoch\s+(\d+)")
                loss_pattern = re.compile(r"loss[:\s]+([0-9.]+)")
                val_loss_pattern = re.compile(r"val_loss[:\s]+([0-9.]+)")

                current_epoch = 0
                current_loss = None
                current_val_loss = None

                try:
                    while True:
                        chunk = await process.stdout.read(512)
                        if not chunk:
                            # Process ended; flush remaining text
                            if buf:
                                line = buf.decode(errors="replace")
                                logging.info(f"[JOB {job_id}] {line}")
                                if channel.readyState == "open":
                                    channel.send(line + "\n")
                            break

                        buf += chunk

                        while True:
                            match = SEP.search(buf)
                            if not match:
                                # Flush long lines
                                if len(buf) > 64 * 1024:
                                    text = buf.decode(errors="replace")
                                    if channel.readyState == "open":
                                        channel.send("\r" + text)
                                    buf = b""
                                break

                            sep = buf[match.start():match.end()]
                            payload = buf[:match.start()]
                            buf = buf[match.end():]

                            text = payload.decode(errors="replace")
                            if not text:
                                continue

                            # Log and send log line to client
                            logging.info(f"[JOB {job_id}] {text}")
                            if sep == b"\n":
                                if channel.readyState == "open":
                                    channel.send(text + "\n")
                            else:  # \r for progress bars
                                if channel.readyState == "open":
                                    channel.send("\r" + text)

                            # Extract progress info for training jobs
                            if job_type == "train":
                                epoch_match = epoch_pattern.search(text)
                                if epoch_match:
                                    current_epoch = int(epoch_match.group(1))

                                loss_match = loss_pattern.search(text)
                                if loss_match:
                                    current_loss = float(loss_match.group(1))

                                val_loss_match = val_loss_pattern.search(text)
                                if val_loss_match:
                                    current_val_loss = float(val_loss_match.group(1))

                                # Send progress update if we have epoch info
                                if current_epoch > 0:
                                    progress_data = {
                                        "epoch": current_epoch,
                                    }
                                    if current_loss is not None:
                                        progress_data["loss"] = current_loss
                                    if current_val_loss is not None:
                                        progress_data["val_loss"] = current_val_loss

                                    if channel.readyState == "open":
                                        import json
                                        progress_msg = f"{MSG_JOB_PROGRESS}{MSG_SEPARATOR}{json.dumps(progress_data)}"
                                        channel.send(progress_msg)

                except Exception as e:
                    logging.exception(f"[JOB {job_id}] Log streaming error: {e}")
                    if channel.readyState == "open":
                        channel.send(f"[log-stream error] {e}\n")

            await stream_logs_with_progress()
            await process.wait()

            duration_seconds = int(time.time() - start_time)
            logging.info(
                f"[JOB {job_id}] Process completed with return code: {process.returncode}"
            )

            if process.returncode == 0:
                # Job completed successfully
                import json
                result_data = {
                    "job_id": job_id,
                    "job_type": job_type,
                    "duration_seconds": duration_seconds,
                    "success": True,
                }
                if channel.readyState == "open":
                    channel.send(f"{MSG_JOB_COMPLETE}{MSG_SEPARATOR}{json.dumps(result_data)}")
                logging.info(f"[JOB {job_id}] Job completed successfully")
            else:
                # Job failed
                import json
                error_data = {
                    "job_id": job_id,
                    "job_type": job_type,
                    "exit_code": process.returncode,
                    "duration_seconds": duration_seconds,
                    "message": f"Process exited with code {process.returncode}",
                }
                if channel.readyState == "open":
                    channel.send(f"{MSG_JOB_FAILED}{MSG_SEPARATOR}{json.dumps(error_data)}")
                logging.error(f"[JOB {job_id}] Job failed with exit code {process.returncode}")

        except Exception as e:
            # Unexpected error
            import json
            logging.error(f"[JOB {job_id}] Execution error: {e}")
            error_data = {
                "job_id": job_id,
                "job_type": job_type,
                "message": str(e),
            }
            if channel.readyState == "open":
                channel.send(f"{MSG_JOB_FAILED}{MSG_SEPARATOR}{json.dumps(error_data)}")
