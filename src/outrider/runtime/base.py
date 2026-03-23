"""Abstract base class for container runtimes"""

from abc import ABC, abstractmethod
from typing import List


class BaseRuntime(ABC):
    """Abstract base for container runtime implementations"""

    @abstractmethod
    def pull_image(self, image_name: str) -> bool:
        """Pull an image from registry

        Args:
            image_name: Full image reference (e.g., nginx:latest)

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def save_images(self, image_list: List[str], output_tar: str) -> bool:
        """Save images to a tar file

        Args:
            image_list: List of image names to save
            output_tar: Path to output tar file

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def load_images(self, tar_file: str) -> bool:
        """Load images from a tar file

        Args:
            tar_file: Path to tar file containing images

        Returns:
            True if successful, False otherwise
        """
        pass
