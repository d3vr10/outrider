"""Abstract base class for post-instruction plugins"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from outrider.transport.base import RemoteHost


class BasePlugin(ABC):
    """Abstract base for post-instruction plugins"""

    @abstractmethod
    def execute(self, remote_host: RemoteHost, tar_path: str, options: Dict[str, Any]) -> bool:
        """Execute post-instruction on remote host

        Args:
            remote_host: Remote host configuration
            tar_path: Path to tar file on remote host
            options: Plugin-specific options

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def validate_options(self, options: Dict[str, Any]) -> bool:
        """Validate plugin options

        Args:
            options: Options to validate

        Returns:
            True if options are valid, False otherwise
        """
        pass
