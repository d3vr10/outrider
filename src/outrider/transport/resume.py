"""Resume-capable file transfer system with partial upload support"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ResumeManager:
    """Manages resumable file transfers with progress tracking"""

    def __init__(self, resume_dir: Optional[str] = None):
        """Initialize resume manager

        Args:
            resume_dir: Directory to store resume metadata (default: ~/.outrider/resume)
        """
        if resume_dir is None:
            resume_dir = os.path.expanduser("~/.outrider/resume")

        self.resume_dir = Path(resume_dir)
        self.resume_dir.mkdir(parents=True, exist_ok=True)

    def get_resume_key(self, local_path: str, remote_host: str, remote_path: str) -> str:
        """Generate unique key for a transfer

        Args:
            local_path: Local file path
            remote_host: Remote hostname
            remote_path: Remote file path

        Returns:
            Resume key string
        """
        key_data = f"{os.path.basename(local_path)}:{remote_host}:{remote_path}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def get_resume_file(self, resume_key: str) -> Path:
        """Get path to resume metadata file

        Args:
            resume_key: Resume key

        Returns:
            Path to resume file
        """
        return self.resume_dir / f"{resume_key}.json"

    def get_progress(self, local_path: str, remote_host: str, remote_path: str) -> Optional[Dict[str, Any]]:
        """Get transfer progress for a file

        Args:
            local_path: Local file path
            remote_host: Remote hostname
            remote_path: Remote file path

        Returns:
            Progress dictionary or None if no previous transfer
        """
        resume_key = self.get_resume_key(local_path, remote_host, remote_path)
        resume_file = self.get_resume_file(resume_key)

        if not resume_file.exists():
            return None

        try:
            with open(resume_file, "r") as f:
                progress = json.load(f)

            # Verify file hasn't changed
            file_size = os.path.getsize(local_path)
            if progress.get("file_size") != file_size:
                logger.warning(f"File size changed, cannot resume: {local_path}")
                self.clear_progress(local_path, remote_host, remote_path)
                return None

            # Check if local file was modified
            file_mtime = os.path.getmtime(local_path)
            if progress.get("local_mtime") != file_mtime:
                logger.warning(f"File modified since last transfer, cannot resume: {local_path}")
                self.clear_progress(local_path, remote_host, remote_path)
                return None

            return progress

        except Exception as e:
            logger.warning(f"Failed to read resume progress: {e}")
            return None

    def save_progress(self, local_path: str, remote_host: str, remote_path: str,
                     transferred_bytes: int, total_bytes: int) -> None:
        """Save transfer progress

        Args:
            local_path: Local file path
            remote_host: Remote hostname
            remote_path: Remote file path
            transferred_bytes: Bytes transferred so far
            total_bytes: Total file size
        """
        try:
            resume_key = self.get_resume_key(local_path, remote_host, remote_path)
            resume_file = self.get_resume_file(resume_key)

            progress = {
                "local_path": local_path,
                "remote_host": remote_host,
                "remote_path": remote_path,
                "transferred_bytes": transferred_bytes,
                "total_bytes": total_bytes,
                "file_size": os.path.getsize(local_path),
                "local_mtime": os.path.getmtime(local_path),
                "percentage": round((transferred_bytes / total_bytes * 100), 2) if total_bytes > 0 else 0,
            }

            with open(resume_file, "w") as f:
                json.dump(progress, f, indent=2)

            logger.debug(f"Saved resume progress: {transferred_bytes}/{total_bytes} bytes")

        except Exception as e:
            logger.warning(f"Failed to save resume progress: {e}")

    def clear_progress(self, local_path: str, remote_host: str, remote_path: str) -> None:
        """Clear resume progress for a transfer

        Args:
            local_path: Local file path
            remote_host: Remote hostname
            remote_path: Remote file path
        """
        try:
            resume_key = self.get_resume_key(local_path, remote_host, remote_path)
            resume_file = self.get_resume_file(resume_key)

            if resume_file.exists():
                resume_file.unlink()
                logger.debug(f"Cleared resume progress for {local_path}")

        except Exception as e:
            logger.warning(f"Failed to clear resume progress: {e}")

    def cleanup(self) -> None:
        """Clean up old resume files"""
        try:
            for resume_file in self.resume_dir.glob("*.json"):
                # Remove resume files older than 7 days
                file_age_seconds = os.time.time() - resume_file.stat().st_mtime
                if file_age_seconds > 7 * 24 * 3600:
                    resume_file.unlink()
                    logger.debug(f"Removed old resume file: {resume_file}")

        except Exception as e:
            logger.warning(f"Failed to cleanup resume files: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get resume statistics

        Returns:
            Dictionary with resume stats
        """
        files = list(self.resume_dir.glob("*.json"))
        return {
            "resume_dir": str(self.resume_dir),
            "pending_transfers": len(files),
            "files": [f.name for f in files]
        }
