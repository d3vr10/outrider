"""K3s air-gap installation plugin"""

import logging
import os
from typing import Dict, Any

from outrider.transport.base import RemoteHost, BaseTransport

logger = logging.getLogger(__name__)


class K3sAirgapPlugin:
    """Plugin for importing images into K3s air-gap clusters"""

    def __init__(self, transport: BaseTransport):
        """Initialize K3s plugin

        Args:
            transport: Transport instance for executing commands
        """
        self.transport = transport

    def execute(self, remote_host: RemoteHost, tar_path: str, options: Dict[str, Any]) -> bool:
        """Execute K3s air-gap import

        Args:
            remote_host: Remote host configuration
            tar_path: Path to tar file on remote host
            options: Plugin options (e.g., k3s_path, containerd_path, use_sudo, sudo_password)

        Returns:
            True if successful, False otherwise
        """
        if not self.validate_options(options):
            logger.error("Invalid K3s options")
            return False

        k3s_path = options.get("k3s_path", "/usr/local/bin/k3s")
        containerd_path = options.get("containerd_path", "/run/k3s/containerd/containerd.sock")
        cleanup_tar = options.get("cleanup_tar", True)
        use_sudo = options.get("use_sudo", False)
        sudo_password = options.get("sudo_password")

        logger.info(f"Importing images to K3s on {remote_host.host}")

        # Command to load images using k3s ctr command
        # This works with k3s's bundled containerd
        cmd = f"CONTAINERD_ADDRESS={containerd_path} ctr -n k8s.io image import {tar_path}"

        # Wrap with sudo if requested
        if use_sudo:
            if sudo_password:
                cmd = f"echo '{sudo_password}' | sudo -S -p '' {cmd}"
            else:
                cmd = f"sudo {cmd}"

        return_code, stdout, stderr = self.transport.execute_remote(remote_host, cmd)

        if return_code != 0:
            logger.error(f"Failed to import images: {stderr}")
            return False

        logger.info(f"Successfully imported images to K3s on {remote_host.host}")

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
        """Validate K3s options

        Args:
            options: Options to validate

        Returns:
            True if options are valid
        """
        if not isinstance(options, dict):
            logger.error("Options must be a dictionary")
            return False

        # All options are optional, just validate types if provided
        if "k3s_path" in options and not isinstance(options["k3s_path"], str):
            logger.error("k3s_path must be a string")
            return False

        if "containerd_path" in options and not isinstance(options["containerd_path"], str):
            logger.error("containerd_path must be a string")
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
