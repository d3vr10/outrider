"""Docker container runtime implementation"""

import subprocess
import logging
from typing import List

from .base import BaseRuntime

logger = logging.getLogger(__name__)


class DockerRuntime(BaseRuntime):
    """Docker container runtime"""

    def __init__(self, docker_cmd: str = "docker"):
        """Initialize Docker runtime

        Args:
            docker_cmd: Docker command to use (default: 'docker')
        """
        self.docker_cmd = docker_cmd
        self._verify_docker()

    def _verify_docker(self) -> None:
        """Verify docker is available"""
        try:
            subprocess.run(
                [self.docker_cmd, "version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            logger.info("Docker runtime verified")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"Docker is not available or not working: {e}")
            raise RuntimeError(f"Docker runtime unavailable: {e}")

    def _image_exists_locally(self, image_name: str) -> bool:
        """Check if image already exists in local cache

        Args:
            image_name: Full image reference (e.g., nginx:latest)

        Returns:
            True if image exists locally, False otherwise
        """
        try:
            result = subprocess.run(
                [self.docker_cmd, "inspect", image_name],
                capture_output=True,
                check=False,
                timeout=5,
            )
            exists = result.returncode == 0
            if exists:
                logger.debug(f"Image already cached locally: {image_name}")
            return exists
        except Exception as e:
            logger.debug(f"Error checking if image exists: {e}")
            return False

    def pull_image(self, image_name: str) -> bool:
        """Pull an image from registry (or use local cache if available)

        Args:
            image_name: Full image reference (e.g., nginx:latest)

        Returns:
            True if successful, False otherwise
        """
        # Check if image already exists in local cache
        if self._image_exists_locally(image_name):
            logger.info(f"Using cached image: {image_name}")
            return True

        logger.info(f"Pulling image: {image_name}")
        try:
            result = subprocess.run(
                [self.docker_cmd, "pull", image_name],
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )
            if result.returncode == 0:
                logger.info(f"Successfully pulled: {image_name}")
                return True
            else:
                logger.error(f"Failed to pull {image_name}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error(f"Pull timeout for {image_name}")
            return False
        except Exception as e:
            logger.error(f"Error pulling {image_name}: {e}")
            return False

    def save_images(self, image_list: List[str], output_tar: str) -> bool:
        """Save images to a tar file

        Args:
            image_list: List of image names to save
            output_tar: Path to output tar file

        Returns:
            True if successful, False otherwise
        """
        if not image_list:
            logger.error("No images to save")
            return False

        logger.info(f"Saving {len(image_list)} image(s) to {output_tar}")

        cmd = [self.docker_cmd, "save", "-o", output_tar] + image_list

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )
            if result.returncode == 0:
                logger.info(f"Successfully saved images to {output_tar}")
                return True
            else:
                logger.error(f"Failed to save images: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("Save operation timeout")
            return False
        except Exception as e:
            logger.error(f"Error saving images: {e}")
            return False

    def load_images(self, tar_file: str) -> bool:
        """Load images from a tar file

        Args:
            tar_file: Path to tar file containing images

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Loading images from {tar_file}")

        try:
            with open(tar_file, "rb") as f:
                result = subprocess.run(
                    [self.docker_cmd, "load"],
                    stdin=f,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=600,
                )

            if result.returncode == 0:
                logger.info(f"Successfully loaded images from {tar_file}")
                return True
            else:
                logger.error(f"Failed to load images: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("Load operation timeout")
            return False
        except FileNotFoundError:
            logger.error(f"Tar file not found: {tar_file}")
            return False
        except Exception as e:
            logger.error(f"Error loading images: {e}")
            return False
