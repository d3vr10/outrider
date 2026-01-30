"""Configuration management"""

import logging
from typing import List, Dict, Any, Optional

import yaml

from outrider.transport.base import RemoteHost

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for outrider"""

    def __init__(self, config_file: str):
        """Load configuration from YAML file

        Args:
            config_file: Path to configuration YAML file
        """
        self.config_file = config_file
        self.data = {}
        self.load()

    def load(self) -> None:
        """Load configuration from file"""
        try:
            with open(self.config_file, "r") as f:
                self.data = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {self.config_file}")
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_file}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse configuration file: {e}")
            raise

    @property
    def images(self) -> List[str]:
        """Get list of images to pull

        Returns:
            List of image names
        """
        images = self.data.get("images", [])
        if not images:
            logger.warning("No images specified in configuration")
        return images

    @property
    def runtime_config(self) -> Dict[str, Any]:
        """Get runtime configuration

        Returns:
            Runtime config dict
        """
        return self.data.get("runtime", {"type": "docker"})

    @property
    def transport_config(self) -> Dict[str, Any]:
        """Get transport configuration

        Returns:
            Transport config dict
        """
        return self.data.get("transport", {"type": "ssh"})

    @property
    def targets(self) -> List[RemoteHost]:
        """Get list of remote targets

        Returns:
            List of RemoteHost instances
        """
        targets_data = self.data.get("targets", [])
        targets = []

        for target in targets_data:
            if "host" not in target:
                logger.warning("Target missing 'host' field, skipping")
                continue

            # Merge per-target transport options with ssh_options
            # This allows per-target overrides of global transport config
            ssh_options = {}
            global_transport_options = self.transport_config.get("options", {})
            per_target_transport_options = target.get("transport", {}).get("options", {})

            # Start with global transport options
            if "key_file" in global_transport_options:
                ssh_options["key_file"] = global_transport_options["key_file"]
            if "password" in global_transport_options:
                ssh_options["password"] = global_transport_options["password"]

            # Apply per-target transport options (override global)
            if "key_file" in per_target_transport_options:
                ssh_options["key_file"] = per_target_transport_options["key_file"]
            if "password" in per_target_transport_options:
                ssh_options["password"] = per_target_transport_options["password"]

            # Merge with explicit target ssh_options (highest precedence)
            target_ssh_options = target.get("ssh_options", {})
            if target_ssh_options:
                ssh_options.update(target_ssh_options)

            remote_host = RemoteHost(
                host=target["host"],
                user=target.get("user", "root"),
                port=target.get("port", 22),
                ssh_options=ssh_options,
                post_instructions=target.get("post_instructions", {}),
                transport_options=target.get("transport", {}),
            )
            targets.append(remote_host)

        return targets

    @property
    def post_instructions(self) -> Optional[Dict[str, Any]]:
        """Get post-instruction configuration

        Returns:
            Post-instruction config or None
        """
        return self.data.get("post_instructions")

    @property
    def output_tar(self) -> str:
        """Get output tar file path

        Returns:
            Output tar file path
        """
        return self.data.get("output_tar", "images.tar")

    @property
    def remote_tar_path(self) -> str:
        """Get remote tar file path

        Returns:
            Remote tar file path
        """
        return self.data.get("remote_tar_path", "/tmp/images.tar")

    def validate(self) -> bool:
        """Validate configuration

        Returns:
            True if configuration is valid
        """
        if not self.images:
            logger.error("No images specified")
            return False

        if not self.targets:
            logger.error("No targets specified")
            return False

        return True
