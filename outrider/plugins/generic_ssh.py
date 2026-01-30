"""Generic SSH command execution plugin"""

import logging
from typing import Dict, Any

from outrider.transport.base import RemoteHost, BaseTransport

logger = logging.getLogger(__name__)


class GenericSSHPlugin:
    """Plugin for executing arbitrary SSH commands"""

    def __init__(self, transport: BaseTransport):
        """Initialize Generic SSH plugin

        Args:
            transport: Transport instance for executing commands
        """
        self.transport = transport

    def execute(self, remote_host: RemoteHost, tar_path: str, options: Dict[str, Any]) -> bool:
        """Execute custom SSH command

        Args:
            remote_host: Remote host configuration
            tar_path: Path to tar file on remote host (available as {tar_path} in command)
            options: Plugin options with 'command' key and optional 'use_sudo', 'sudo_password'

        Returns:
            True if successful, False otherwise
        """
        if not self.validate_options(options):
            logger.error("Invalid GenericSSH options")
            return False

        # Support {tar_path} placeholder in command
        command = options.get("command", "").format(tar_path=tar_path)
        use_sudo = options.get("use_sudo", False)
        sudo_password = options.get("sudo_password")

        if not command:
            logger.error("No command specified")
            return False

        # Wrap with sudo if requested
        if use_sudo:
            if sudo_password:
                command = f"echo '{sudo_password}' | sudo -S -p '' {command}"
            else:
                command = f"sudo {command}"

        logger.info(f"Executing on {remote_host.host}: {command}")

        return_code, stdout, stderr = self.transport.execute_remote(remote_host, command)

        if return_code != 0:
            logger.error(f"Command failed with code {return_code}: {stderr}")
            if stdout:
                logger.debug(f"stdout: {stdout}")
            return False

        logger.info(f"Command executed successfully on {remote_host.host}")
        if stdout:
            logger.debug(f"Output: {stdout}")

        return True

    def validate_options(self, options: Dict[str, Any]) -> bool:
        """Validate GenericSSH options

        Args:
            options: Options to validate

        Returns:
            True if options are valid
        """
        if not isinstance(options, dict):
            logger.error("Options must be a dictionary")
            return False

        if "command" not in options:
            logger.error("'command' is required in options")
            return False

        if not isinstance(options["command"], str):
            logger.error("'command' must be a string")
            return False

        if "use_sudo" in options and not isinstance(options["use_sudo"], bool):
            logger.error("use_sudo must be a boolean")
            return False

        if "sudo_password" in options and not isinstance(options["sudo_password"], str):
            logger.error("sudo_password must be a string")
            return False

        return True
