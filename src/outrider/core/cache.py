"""Caching system for tar files with SHA256 integrity checks"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages tar file cache with SHA256 integrity verification"""

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize cache manager

        Args:
            cache_dir: Directory to store cache metadata (default: ~/.outrider/cache)
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.outrider/cache")

        self.cache_dir = Path(cache_dir)
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = {}

        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load existing metadata
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load metadata from cache file"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    self.metadata = json.load(f)
                logger.debug(f"Loaded cache metadata from {self.metadata_file}")
            except Exception as e:
                logger.warning(f"Failed to load cache metadata: {e}, starting fresh")
                self.metadata = {}

    def _save_metadata(self) -> None:
        """Save metadata to cache file"""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2)
            logger.debug(f"Saved cache metadata to {self.metadata_file}")
        except Exception as e:
            logger.error(f"Failed to save cache metadata: {e}")

    @staticmethod
    def _compute_sha256(file_path: str, chunk_size: int = 8192) -> str:
        """Compute SHA256 hash of a file

        Args:
            file_path: Path to file
            chunk_size: Chunk size for reading (default: 8KB)

        Returns:
            SHA256 hash as hex string
        """
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to compute SHA256 for {file_path}: {e}")
            raise

    def get_cache_key(self, images: list, output_path: str) -> str:
        """Generate cache key from images and output path

        Args:
            images: List of image names
            output_path: Output tar file path

        Returns:
            Cache key string
        """
        # Create a stable hash from sorted images and output path
        key_data = json.dumps({
            "images": sorted(images),
            "output_path": os.path.basename(output_path)
        }, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def is_valid(self, file_path: str, images: list) -> bool:
        """Check if cached tar file is valid

        Args:
            file_path: Path to tar file
            images: List of images that should be in tar

        Returns:
            True if file exists and SHA256 matches recorded value
        """
        if not os.path.exists(file_path):
            logger.debug(f"Cache file not found: {file_path}")
            return False

        cache_key = self.get_cache_key(images, file_path)

        if cache_key not in self.metadata:
            logger.debug(f"No cache entry for {file_path}")
            return False

        cached_info = self.metadata[cache_key]
        expected_sha256 = cached_info.get("sha256")
        expected_mtime = cached_info.get("mtime")

        if not expected_sha256:
            logger.debug(f"No SHA256 in cache for {file_path}")
            return False

        # Check file modification time first (faster)
        try:
            current_mtime = os.path.getmtime(file_path)
            if current_mtime != expected_mtime:
                logger.debug(f"File modified since cache: {file_path}")
                return False
        except OSError:
            logger.warning(f"Failed to get mtime for {file_path}")
            return False

        # Verify SHA256
        try:
            current_sha256 = self._compute_sha256(file_path)
            if current_sha256 != expected_sha256:
                logger.warning(f"SHA256 mismatch for {file_path}")
                return False

            logger.info(f"Cache valid for {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to verify cache: {e}")
            return False

    def update(self, file_path: str, images: list) -> None:
        """Update cache entry for a file

        Args:
            file_path: Path to tar file
            images: List of images in tar
        """
        try:
            cache_key = self.get_cache_key(images, file_path)
            sha256 = self._compute_sha256(file_path)
            mtime = os.path.getmtime(file_path)
            file_size = os.path.getsize(file_path)

            self.metadata[cache_key] = {
                "file_path": file_path,
                "sha256": sha256,
                "mtime": mtime,
                "file_size": file_size,
                "images": sorted(images),
                "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip()
            }

            self._save_metadata()
            logger.info(f"Updated cache for {file_path} (SHA256: {sha256[:16]}...)")

        except Exception as e:
            logger.error(f"Failed to update cache: {e}")

    def clear(self, file_path: Optional[str] = None) -> None:
        """Clear cache entry or entire cache

        Args:
            file_path: If specified, only clear this file's cache; otherwise clear all
        """
        if file_path is None:
            self.metadata.clear()
            self._save_metadata()
            logger.info("Cleared entire cache")
        else:
            # Remove entries related to this file
            keys_to_remove = [
                k for k, v in self.metadata.items()
                if v.get("file_path") == file_path
            ]
            for k in keys_to_remove:
                del self.metadata[k]
            self._save_metadata()
            logger.info(f"Cleared cache for {file_path}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        total_size = sum(
            v.get("file_size", 0) for v in self.metadata.values()
        )
        return {
            "cache_dir": str(self.cache_dir),
            "num_entries": len(self.metadata),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "entries": self.metadata
        }
