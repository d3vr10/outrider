"""Configuration management"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

import yaml

from outrider.transport.base import RemoteHost
from outrider.core.env import EnvManager

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for outrider"""

    def __init__(self, config_file: str, env_files: Optional[List[str]] = None):
        """Load configuration from YAML file

        Args:
            config_file: Path to configuration YAML file
            env_files: List of environment files to load
        """
        self.config_file = config_file
        self.data = {}
        self.env_manager = EnvManager()
        self.env_files = env_files or []

        # Load environment files if provided
        if self.env_files:
            env_from_files = self.env_manager.load_files(self.env_files)
            self.env_manager.env.update(env_from_files)

        self.load()

    def load(self) -> None:
        """Load configuration from file and apply environment variable expansion"""
        try:
            with open(self.config_file, "r") as f:
                self.data = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {self.config_file}")

            # Load environment variables from config if specified
            self._load_env_config()

            # Apply environment variable expansion
            self._apply_env_expansion()

        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_file}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse configuration file: {e}")
            raise

    def _load_env_config(self) -> None:
        """Load environment variables from env_from and env properties in config"""
        env_from_paths = self.data.get("env_from", [])
        if isinstance(env_from_paths, str):
            env_from_paths = [env_from_paths]

        # Load from files in env_from
        for file_path in env_from_paths:
            vars_from_file = self.env_manager.load_file(file_path)
            self.env_manager.env.update(vars_from_file)

        # Load direct env variables
        env_direct = self.data.get("env", {})
        if isinstance(env_direct, list):
            # Convert list format to dict
            env_dict = {}
            for item in env_direct:
                if "=" in item:
                    key, value = item.split("=", 1)
                    env_dict[key] = value
            env_direct = env_dict

        if env_direct:
            self.env_manager.env.update(env_direct)
            logger.info(f"Loaded {len(env_direct)} direct environment variables")

    def _apply_env_expansion(self) -> None:
        """Apply environment variable expansion to configuration"""
        try:
            self.data = self.env_manager.expand_dict(self.data, self.env_manager.env)
            logger.debug("Applied environment variable expansion to configuration")
        except ValueError as e:
            logger.error(f"Environment variable expansion failed: {e}")
            raise

    def _load_images_from_files(self) -> Set[str]:
        """Load images from files specified in images_from property

        Returns:
            Set of deduplicated image names
        """
        images_set: Set[str] = set()

        images_from_paths = self.data.get("images_from", [])
        if isinstance(images_from_paths, str):
            images_from_paths = [images_from_paths]

        for file_path in images_from_paths:
            expanded_path = os.path.expanduser(file_path)

            if not os.path.exists(expanded_path):
                logger.warning(f"Images file not found: {expanded_path}")
                continue

            try:
                with open(expanded_path, "r") as f:
                    # Read file and split by whitespace
                    content = f.read()
                    # Split by any whitespace (newlines, tabs, spaces)
                    raw_images = content.split()
                    images_set.update(raw_images)
                    logger.info(f"Loaded {len(raw_images)} images from {expanded_path}")

            except Exception as e:
                logger.error(f"Failed to load images from {expanded_path}: {e}")

        return images_set

    @property
    def images(self) -> List[str]:
        """Get list of images to pull (deduplicated from images and images_from)

        Returns:
            Deduplicated list of image names
        """
        images_set: Set[str] = set()

        # Load images from direct list
        direct_images = self.data.get("images", [])
        if isinstance(direct_images, str):
            direct_images = [direct_images]
        images_set.update(direct_images)

        # Load images from files
        images_from_files = self._load_images_from_files()
        images_set.update(images_from_files)

        if not images_set:
            logger.warning("No images specified in configuration")

        # Return as sorted list for reproducibility
        return sorted(list(images_set))

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

            # Determine user with precedence: per-target user > per-target ssh_options.user > global transport user > default
            user = target.get("user")
            if not user and "user" in ssh_options:
                user = ssh_options["user"]
            if not user:
                user = global_transport_options.get("user", "root")

            remote_host = RemoteHost(
                host=target["host"],
                user=user,
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
    def no_cache(self) -> bool:
        """Get no_cache flag (force re-upload)

        Returns:
            True if cache should be bypassed
        """
        return self.data.get("no_cache", False)

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
