"""Abstract base class for transport protocols"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple


class RemoteHost:
    """Represents a remote host configuration"""

    def __init__(self, host: str, user: str, port: int = 22, ssh_options: Optional[dict] = None,
                 post_instructions: Optional[dict] = None, transport_options: Optional[dict] = None):
        """Initialize remote host

        Args:
            host: Hostname or IP address (can be SSH config alias)
            user: Username for authentication
            port: SSH port (default: 22)
            ssh_options: Optional per-target SSH options (key_file, password, etc.)
            post_instructions: Optional per-target post-instructions config (plugin, options)
            transport_options: Optional per-target transport options (overrides global config)
        """
        self.host = host
        self.user = user
        self.port = port
        self.ssh_options = ssh_options or {}
        self.post_instructions = post_instructions or {}
        self.transport_options = transport_options or {}


class BaseTransport(ABC):
    """Abstract base for transport protocol implementations"""

    @abstractmethod
    def transfer_file(self, local_path: str, remote_host: RemoteHost, remote_path: str) -> bool:
        """Transfer a file to a remote host

        Args:
            local_path: Path to local file
            remote_host: Remote host configuration
            remote_path: Path on remote host

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def execute_remote(self, remote_host: RemoteHost, command: str) -> Tuple[int, str, str]:
        """Execute a command on remote host

        Args:
            remote_host: Remote host configuration
            command: Command to execute

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close transport connections"""
        pass
