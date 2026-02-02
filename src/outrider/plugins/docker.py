"""Docker image loading plugin"""

import logging
from typing import Dict, Any

from outrider.transport.base import RemoteHost, BaseTransport

logger = logging.getLogger(__name__)


class DockerPlugin:
    """Plugin for importing images into Docker on remote systems"""

    def __init__(self, transport: BaseTransport):
        """Initialize Docker plugin

        Args:
            transport: Transport instance for executing commands
        """
        self.transport = transport

    def execute(self, remote_host: RemoteHost, tar_path: str, options: Dict[str, Any]) -> bool:
        """Execute Docker image loading

        Args:
            remote_host: Remote host configuration
            tar_path: Path to tar file on remote host
            options: Plugin options (docker_cmd, use_sudo, sudo_password, cleanup_tar)

        Returns:
            True if successful, False otherwise
        """
        if not self.validate_options(options):
            logger.error("Invalid Docker options")
            return False

        docker_cmd = options.get("docker_cmd", "docker")
        cleanup_tar = options.get("cleanup_tar", True)
        use_sudo = options.get("use_sudo", False)
        sudo_password = options.get("sudo_password")

        logger.info(f"Loading images into Docker on {remote_host.host}")

        # Command to load images using docker load
        cmd = f"{docker_cmd} load < {tar_path}"

        # Wrap with sudo if requested
        if use_sudo:
            if sudo_password:
                cmd = f"echo '{sudo_password}' | sudo -S -p '' {cmd}"
            else:
                cmd = f"sudo {cmd}"

        return_code, stdout, stderr = self.transport.execute_remote(remote_host, cmd)

        if return_code != 0:
            logger.error(f"Failed to load images: {stderr}")
            return False

        logger.info(f"Successfully loaded images into Docker on {remote_host.host}")

        # Log loaded images if available
        if stdout:
            logger.debug(f"Docker output: {stdout}")

        # Cleanup tar file if requested
        if cleanup_tar:
            cleanup_cmd = f"rm -f {tar_path}"
            # Apply sudo wrapping to cleanup command as well
            if use_sudo:
                if sudo_password:
                    cleanup_cmd = f"echo '{sudo_password}' | sudo -S -p '' {cleanup_cmd}"
                else:
                    cleanup_cmd = f"sudo {cleanup_cmd}"

            cleanup_return_code, _, cleanup_stderr = self.transport.execute_remote(remote_host, cleanup_cmd)
            if cleanup_return_code != 0:
                logger.warning(f"Failed to cleanup tar file on {remote_host.host}: {cleanup_stderr}")

        return True

    def validate_options(self, options: Dict[str, Any]) -> bool:
        """Validate Docker options

        Args:
            options: Options to validate

        Returns:
            True if options are valid
        """
        if not isinstance(options, dict):
            logger.error("Options must be a dictionary")
            return False

        # All options are optional, just validate types if provided
        if "docker_cmd" in options and not isinstance(options["docker_cmd"], str):
            logger.error("docker_cmd must be a string")
            return False

        if "cleanup_tar" in options and not isinstance(options["cleanup_tar"], bool):
            logger.error("cleanup_tar must be a boolean")
            return False

        if "use_sudo" in options and not isinstance(options["use_sudo"], bool):
            logger.error("use_sudo must be a boolean")
            return False

        if "sudo_password" in options and not isinstance(options["sudo_password"], str):
            logger.error("sudo_password must be a string")
            return False

        return True
