"""File transfer and storage management for worker nodes.

This module handles file transfer via RTC data channels, file compression,
and filesystem browsing for SLEAP-RTC workers.
"""

import asyncio
import fnmatch
import logging
import os
import shutil
import time
from pathlib import Path
from typing import List, Optional

from aiortc import RTCDataChannel


class FileManager:
    """Manages file transfer, compression, and filesystem browsing for worker nodes.

    This class handles file transfer via RTC data channels, compression of
    training results, and browsing of configured mount points.

    Attributes:
        chunk_size: Size of chunks for file transfer (default 32KB).
        zipped_file: Path to most recently created zip file.
        save_dir: Local directory for saving files.
        output_dir: Output directory for job results.
        mounts: List of MountConfig objects for filesystem browsing.
        working_dir: Worker's current working directory.
    """

    # Constants for filesystem operations
    MAX_RESULTS = 20
    SEARCH_TIMEOUT = 10.0  # seconds
    MAX_SEARCH_DEPTH = 5
    MIN_PATTERN_CHARS = 3

    def __init__(
        self,
        chunk_size: int = 32 * 1024,
        mounts: list = None,
        working_dir: str = None,
    ):
        """Initialize file manager.

        Args:
            chunk_size: Size of chunks for file transfer (default 32KB).
            mounts: List of MountConfig objects for filesystem browsing.
            working_dir: Worker's current working directory.
        """
        self.chunk_size = chunk_size
        self.save_dir = "."
        self.zipped_file = ""
        self.output_dir = ""
        self.mounts: list = mounts or []
        self.working_dir: str = working_dir

    async def send_file(self, channel: RTCDataChannel, file_path: str, output_dir: str = ""):
        """Send a file to client via RTC data channel.

        Args:
            channel: RTC data channel for sending file.
            file_path: Path to file to send.
            output_dir: Output directory hint for client (where to save file).
        """
        if channel.readyState != "open":
            logging.error(f"Data channel not open: {channel.readyState}")
            return

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        # Send file metadata
        output_hint = output_dir or self.output_dir
        channel.send(f"FILE_META::{file_name}:{file_size}:{output_hint}")
        logging.info(f"Sending file: {file_name} ({file_size} bytes)")

        # Send file in chunks
        with open(file_path, "rb") as file:
            bytes_sent = 0
            while chunk := file.read(self.chunk_size):
                # Flow control: wait if buffer is too full
                while (
                    channel.bufferedAmount is not None
                    and channel.bufferedAmount > 16 * 1024 * 1024
                ):
                    await asyncio.sleep(0.1)

                channel.send(chunk)
                bytes_sent += len(chunk)

        # Signal end of file
        channel.send("END_OF_FILE")
        logging.info("File sent successfully")

    async def zip_results(self, file_name: str, dir_path: Optional[str] = None):
        """Zip directory contents into archive.

        Args:
            file_name: Name of the zip file to create (without .zip extension).
            dir_path: Path to directory to zip.

        Returns:
            Path to created zip file, or None if failed.
        """
        logging.info("Zipping results...")
        if not dir_path or not Path(dir_path).exists():
            logging.error(f"Directory does not exist: {dir_path}")
            return None

        try:
            shutil.make_archive(file_name, "zip", dir_path)
            self.zipped_file = f"{file_name}.zip"
            logging.info(f"Results zipped to {self.zipped_file}")
            return self.zipped_file
        except Exception as e:
            logging.error(f"Error zipping results: {e}")
            return None

    async def unzip_results(self, file_path: str):
        """Unzip archive to save directory.

        Args:
            file_path: Path to zip file to extract.

        Returns:
            Path to extracted directory, or None if failed.
        """
        logging.info("Unzipping results...")
        if not Path(file_path).exists():
            logging.error(f"File does not exist: {file_path}")
            return None

        try:
            shutil.unpack_archive(file_path, self.save_dir)
            logging.info(f"Results unzipped from {file_path} to {self.save_dir}")

            # Calculate unzipped directory path
            original_name = Path(file_path).stem  # Remove .zip extension
            unzipped_dir = f"{self.save_dir}/{original_name}"
            logging.info(f"Unzipped contents to {unzipped_dir}")
            return unzipped_dir
        except Exception as e:
            logging.error(f"Error unzipping results: {e}")
            return None

    # =========================================================================
    # Filesystem Browser Methods
    # =========================================================================

    def set_mounts(self, mounts: list) -> None:
        """Set the list of configured mount points.

        Args:
            mounts: List of MountConfig objects.
        """
        self.mounts = mounts or []

    def get_mounts(self) -> List[dict]:
        """Get list of available mount points.

        Returns:
            List of mount dictionaries with 'path' and 'label' fields.
        """
        return [{"path": mount.path, "label": mount.label} for mount in self.mounts]

    def get_worker_info(self, worker_id: str = None) -> dict:
        """Get worker information for browser status display.

        Args:
            worker_id: Optional worker identifier.

        Returns:
            Dictionary with worker_id, working_dir, and mounts.
        """
        return {
            "worker_id": worker_id or "unknown",
            "working_dir": self.working_dir or os.getcwd(),
            "mounts": self.get_mounts(),
        }

    def _is_path_allowed(self, path: Path) -> bool:
        """Check if a path is within an allowed mount.

        Args:
            path: Path to check.

        Returns:
            True if path is within a configured mount, False otherwise.
        """
        if not self.mounts:
            return False

        # Resolve the path to handle symlinks and .. segments
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

    def _is_wildcard_pattern(self, pattern: str) -> bool:
        """Check if pattern contains wildcard characters.

        Args:
            pattern: The pattern to check.

        Returns:
            True if pattern contains wildcards.
        """
        return any(c in pattern for c in "*?[")

    def _validate_pattern(self, pattern: str) -> tuple:
        """Validate a search pattern.

        Args:
            pattern: The pattern to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not pattern:
            return False, "Pattern cannot be empty"

        # Count non-wildcard characters
        non_wildcard = sum(1 for c in pattern if c not in "*?[]")
        if non_wildcard < self.MIN_PATTERN_CHARS:
            return False, f"Pattern must contain at least {self.MIN_PATTERN_CHARS} non-wildcard characters"

        return True, None

    def _match_filename(self, pattern: str, filename: str) -> dict:
        """Match a filename against a pattern.

        Args:
            pattern: Pattern to match (may contain wildcards).
            filename: Filename to check.

        Returns:
            Match result with 'matches' and 'match_type' fields.
        """
        # Case-insensitive matching
        pattern_lower = pattern.lower()
        filename_lower = filename.lower()

        # Exact match
        if filename_lower == pattern_lower:
            return {"matches": True, "match_type": "exact"}

        # Wildcard match using fnmatch
        if self._is_wildcard_pattern(pattern):
            if fnmatch.fnmatch(filename_lower, pattern_lower):
                return {"matches": True, "match_type": "wildcard"}

        # Filename contains pattern (substring match)
        if pattern_lower in filename_lower:
            return {"matches": True, "match_type": "substring"}

        return {"matches": False, "match_type": None}

    def resolve_path(
        self,
        pattern: str,
        file_size: int = None,
        max_depth: int = None,
        mount_label: str = None,
    ) -> dict:
        """Resolve a file pattern to matching files within mounts.

        Args:
            pattern: Filename or pattern to search for.
            file_size: Expected file size for ranking (optional).
            max_depth: Maximum directory depth to search.
            mount_label: Label of specific mount to search, or None/"all" for all mounts.

        Returns:
            Dictionary with candidates, truncated, timeout, and search_time_ms.
        """
        if max_depth is None:
            max_depth = self.MAX_SEARCH_DEPTH

        # Validate pattern if it contains wildcards
        if self._is_wildcard_pattern(pattern):
            is_valid, error = self._validate_pattern(pattern)
            if not is_valid:
                return {
                    "candidates": [],
                    "truncated": False,
                    "timeout": False,
                    "error": error,
                    "error_code": "PATTERN_TOO_BROAD",
                }

        start_time = time.time()
        candidates = []
        timed_out = False

        # Extract just the filename if a full path was provided
        search_name = Path(pattern).name

        # Filter mounts if mount_label specified
        mounts_to_search = self.mounts
        if mount_label and mount_label.lower() != "all":
            mounts_to_search = [m for m in self.mounts if m.label == mount_label]
            if not mounts_to_search:
                return {
                    "candidates": [],
                    "truncated": False,
                    "timeout": False,
                    "error": f"Mount '{mount_label}' not found",
                    "error_code": "MOUNT_NOT_FOUND",
                }

        for mount in mounts_to_search:
            if timed_out:
                break

            mount_path = Path(mount.path)
            if not mount_path.exists():
                continue

            # Scan the mount directory
            for match in self._scan_directory(
                mount_path,
                search_name,
                0,
                max_depth,
                file_size,
                start_time,
            ):
                if match is None:
                    # Timeout signal
                    timed_out = True
                    break

                candidates.append(match)

                # Early termination after MAX_RESULTS
                if len(candidates) >= self.MAX_RESULTS:
                    break

        # Sort candidates by score (descending)
        candidates.sort(key=lambda c: c.get("score", 0), reverse=True)

        # Truncate to MAX_RESULTS
        truncated = len(candidates) > self.MAX_RESULTS
        candidates = candidates[: self.MAX_RESULTS]

        search_time_ms = int((time.time() - start_time) * 1000)

        return {
            "candidates": candidates,
            "truncated": truncated,
            "timeout": timed_out,
            "search_time_ms": search_time_ms,
        }

    def _scan_directory(
        self,
        dir_path: Path,
        pattern: str,
        depth: int,
        max_depth: int,
        file_size: int,
        start_time: float,
    ):
        """Lazily scan a directory for matching files.

        Args:
            dir_path: Directory to scan.
            pattern: Pattern to match.
            depth: Current depth.
            max_depth: Maximum depth.
            file_size: Expected file size for scoring.
            start_time: Search start time for timeout.

        Yields:
            Match dictionaries, or None if timeout.
        """
        # Check timeout
        if time.time() - start_time > self.SEARCH_TIMEOUT:
            yield None
            return

        # Check depth limit
        if depth > max_depth:
            return

        try:
            entries = list(dir_path.iterdir())
        except (PermissionError, OSError):
            # Skip directories we can't read
            return

        for entry in entries:
            # Check timeout periodically
            if time.time() - start_time > self.SEARCH_TIMEOUT:
                yield None
                return

            try:
                if entry.is_file():
                    match_result = self._match_filename(pattern, entry.name)
                    if match_result["matches"]:
                        stat = entry.stat()
                        score = self._calculate_score(
                            match_result["match_type"],
                            stat.st_size,
                            file_size,
                            str(entry),
                        )
                        yield {
                            "path": str(entry),
                            "name": entry.name,
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                            "match_type": match_result["match_type"],
                            "score": score,
                        }

                elif entry.is_dir():
                    # Recursively scan subdirectories
                    for sub_match in self._scan_directory(
                        entry,
                        pattern,
                        depth + 1,
                        max_depth,
                        file_size,
                        start_time,
                    ):
                        yield sub_match

            except (PermissionError, OSError):
                # Skip files/directories we can't access
                continue

    def _calculate_score(
        self,
        match_type: str,
        actual_size: int,
        expected_size: int,
        path: str,
    ) -> float:
        """Calculate a ranking score for a match.

        Args:
            match_type: Type of match (exact, wildcard, substring).
            actual_size: Actual file size.
            expected_size: Expected file size from client.
            path: Full path for path token analysis.

        Returns:
            Score value (higher is better).
        """
        score = 0.0

        # Match type scoring (primary factor)
        if match_type == "exact":
            score += 100.0
        elif match_type == "wildcard":
            score += 50.0
        elif match_type == "substring":
            score += 25.0

        # Size match scoring (secondary factor)
        if expected_size and actual_size:
            if actual_size == expected_size:
                score += 20.0
            else:
                # Partial score for similar sizes (within 10%)
                size_diff = abs(actual_size - expected_size)
                if size_diff < expected_size * 0.1:
                    score += 10.0

        # Shorter paths get slight bonus (tertiary factor)
        path_depth = path.count(os.sep)
        score -= path_depth * 0.1

        return score

    def list_directory(self, path: str, offset: int = 0) -> dict:
        """List contents of a directory within allowed mounts.

        Args:
            path: Directory path to list.
            offset: Number of entries to skip (for pagination).

        Returns:
            Dictionary with path, entries, total_count, and has_more.
        """
        dir_path = Path(path)

        # Canonicalize path to prevent traversal attacks
        try:
            resolved_path = dir_path.resolve()
        except (OSError, ValueError) as e:
            return {
                "path": path,
                "entries": [],
                "total_count": 0,
                "has_more": False,
                "error": f"Invalid path: {e}",
                "error_code": "PATH_NOT_FOUND",
            }

        # Security check: path must be within allowed mounts
        if not self._is_path_allowed(resolved_path):
            return {
                "path": path,
                "entries": [],
                "total_count": 0,
                "has_more": False,
                "error": "Access denied: path is outside configured mounts",
                "error_code": "ACCESS_DENIED",
            }

        if not resolved_path.exists():
            return {
                "path": path,
                "entries": [],
                "total_count": 0,
                "has_more": False,
                "error": "Path does not exist",
                "error_code": "PATH_NOT_FOUND",
            }

        if not resolved_path.is_dir():
            return {
                "path": path,
                "entries": [],
                "total_count": 0,
                "has_more": False,
                "error": "Path is not a directory",
                "error_code": "PATH_NOT_FOUND",
            }

        try:
            all_entries = list(resolved_path.iterdir())
        except PermissionError:
            return {
                "path": path,
                "entries": [],
                "total_count": 0,
                "has_more": False,
                "error": "Permission denied",
                "error_code": "ACCESS_DENIED",
            }

        # Sort: directories first, then alphabetically
        all_entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))

        total_count = len(all_entries)

        # Apply offset and limit
        paginated = all_entries[offset : offset + self.MAX_RESULTS]

        entries = []
        for entry in paginated:
            try:
                stat = entry.stat()
                entries.append({
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": stat.st_size if entry.is_file() else 0,
                    "modified": stat.st_mtime,
                })
            except (PermissionError, OSError):
                # Skip entries we can't stat
                continue

        has_more = offset + len(entries) < total_count

        return {
            "path": str(resolved_path),
            "entries": entries,
            "total_count": total_count,
            "has_more": has_more,
        }
