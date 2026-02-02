"""Main orchestration logic"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from outrider.core.config import Config
from outrider.runtime.docker import DockerRuntime
from outrider.transport.ssh import SSHTransport
from outrider.plugins.k3s_airgap import K3sAirgapPlugin
from outrider.plugins.generic_ssh import GenericSSHPlugin
from outrider.plugins.docker import DockerPlugin

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates the image transfer workflow"""

    def __init__(self, config: Config, skip_host_verification: bool = False,
                 max_concurrent_uploads: int = 3):
        """Initialize orchestrator

        Args:
            config: Configuration instance
            skip_host_verification: Skip SSH host key verification (insecure)
            max_concurrent_uploads: Maximum number of concurrent uploads (1-10)
        """
        self.config = config
        self.runtime = None
        self.transport = None
        self.skip_host_verification = skip_host_verification
        self.max_concurrent_uploads = max_concurrent_uploads

    def _init_runtime(self) -> bool:
        """Initialize container runtime

        Returns:
            True if successful, False otherwise
        """
        runtime_config = self.config.runtime_config
        runtime_type = runtime_config.get("type", "docker")

        try:
            if runtime_type == "docker":
                docker_cmd = runtime_config.get("options", {}).get("cmd", "docker")
                self.runtime = DockerRuntime(docker_cmd=docker_cmd)
                logger.info("Initialized Docker runtime")
            else:
                logger.error(f"Unsupported runtime type: {runtime_type}")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to initialize runtime: {e}")
            return False

    def _init_transport(self) -> bool:
        """Initialize transport protocol

        Returns:
            True if successful, False otherwise
        """
        transport_config = self.config.transport_config
        transport_type = transport_config.get("type", "ssh")

        try:
            if transport_type == "ssh":
                options = transport_config.get("options", {})
                key_file = options.get("key_file")
                password = options.get("password")
                ssh_config = options.get("ssh_config")

                self.transport = SSHTransport(
                    key_file=key_file,
                    password=password,
                    ssh_config=ssh_config,
                    skip_host_verification=self.skip_host_verification
                )
                logger.info("Initialized SSH transport")
            else:
                logger.error(f"Unsupported transport type: {transport_type}")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to initialize transport: {e}")
            return False

    def _pull_images(self) -> bool:
        """Pull images from registry

        Returns:
            True if all images pulled successfully
        """
        logger.info(f"Pulling {len(self.config.images)} image(s)")

        all_success = True
        for image in self.config.images:
            if not self.runtime.pull_image(image):
                all_success = False
                logger.error(f"Failed to pull {image}")

        return all_success

    def _compress_images(self) -> bool:
        """Compress images to tar file

        Returns:
            True if successful, False otherwise
        """
        output_tar = self.config.output_tar

        # Clean up existing tar file
        if os.path.exists(output_tar):
            os.remove(output_tar)
            logger.debug(f"Removed existing tar file: {output_tar}")

        logger.info(f"Compressing {len(self.config.images)} image(s) to {output_tar}")

        if not self.runtime.save_images(self.config.images, output_tar):
            logger.error("Failed to compress images")
            return False

        if not os.path.exists(output_tar):
            logger.error(f"Tar file not created: {output_tar}")
            return False

        tar_size_mb = os.path.getsize(output_tar) / (1024 * 1024)
        logger.info(f"Successfully created tar file: {output_tar} ({tar_size_mb:.2f} MB)")

        return True

    def _transfer_to_target(self) -> bool:
        """Transfer tar file to all targets (concurrent)

        Returns:
            True if all transfers successful
        """
        local_tar = self.config.output_tar
        remote_tar = self.config.remote_tar_path

        if not os.path.exists(local_tar):
            logger.error(f"Local tar file not found: {local_tar}")
            return False

        targets = self.config.targets

        # If only 1 target, skip thread pool overhead
        if len(targets) == 1:
            target = targets[0]
            logger.info(f"Transferring to {target.user}@{target.host}:{target.port}")
            success = self.transport.transfer_file(local_tar, target, remote_tar)
            if success:
                logger.info(f"Successfully transferred to {target.host}")
            else:
                logger.error(f"Failed to transfer to {target.host}")
            return success

        # Concurrent transfers for multiple targets
        logger.info(f"Transferring to {len(targets)} target(s) with max {self.max_concurrent_uploads} concurrent uploads")

        def transfer_worker(target):
            """Worker function for threaded transfer"""
            logger.info(f"Transferring to {target.user}@{target.host}:{target.port}")
            try:
                success = self.transport.transfer_file(local_tar, target, remote_tar)
                if success:
                    logger.info(f"Successfully transferred to {target.host}")
                else:
                    logger.error(f"Failed to transfer to {target.host}")
                return (target.host, success)
            except Exception as e:
                logger.error(f"Exception transferring to {target.host}: {e}")
                return (target.host, False)

        all_success = True
        with ThreadPoolExecutor(max_workers=self.max_concurrent_uploads) as executor:
            # Submit all transfer tasks
            future_to_target = {
                executor.submit(transfer_worker, target): target
                for target in targets
            }

            # Wait for completion and collect results
            for future in as_completed(future_to_target):
                target = future_to_target[future]
                try:
                    host, success = future.result()
                    if not success:
                        all_success = False
                except Exception as e:
                    logger.error(f"Unexpected error for {target.host}: {e}")
                    all_success = False

        return all_success

    def _merge_post_instructions(self, global_config: dict, target_config: dict) -> tuple:
        """Merge global and per-target post-instructions with per-target precedence

        Args:
            global_config: Global post-instructions config
            target_config: Per-target post-instructions config

        Returns:
            Tuple of (plugin_type, merged_options)
        """
        # Use per-target plugin type if specified, otherwise use global
        plugin_type = target_config.get("plugin") or global_config.get("plugin")

        # Merge options: global options + per-target options (per-target overrides)
        merged_options = {}
        if global_config.get("options"):
            merged_options.update(global_config["options"])
        if target_config.get("options"):
            merged_options.update(target_config["options"])

        return plugin_type, merged_options

    def _execute_post_instruction_single(self, target, plugin_type: str, remote_tar: str, options: dict) -> bool:
        """Execute post-instruction on a single target

        Args:
            target: Remote host target
            plugin_type: Type of plugin to execute
            remote_tar: Remote tar file path
            options: Plugin options

        Returns:
            True if successful
        """
        logger.info(f"Executing post-instructions on {target.host} with plugin: {plugin_type}")
        try:
            if plugin_type == "k3s_airgap":
                plugin = K3sAirgapPlugin(self.transport)
            elif plugin_type == "generic_ssh":
                plugin = GenericSSHPlugin(self.transport)
            elif plugin_type == "docker":
                plugin = DockerPlugin(self.transport)
            else:
                logger.error(f"Unknown plugin type: {plugin_type}")
                return False

            success = plugin.execute(target, remote_tar, options)
            if success:
                logger.info(f"Post-instructions completed on {target.host}")
            else:
                logger.error(f"Post-instruction failed on {target.host}")
            return success
        except Exception as e:
            logger.error(f"Error executing post-instructions on {target.host}: {e}")
            return False

    def _execute_post_instructions(self) -> bool:
        """Execute post-instructions on all targets (concurrent)

        Returns:
            True if all executions successful or no post-instructions
        """
        global_post_config = self.config.post_instructions
        targets = self.config.targets
        remote_tar = self.config.remote_tar_path

        # Check if any post-instructions are configured (global or per-target)
        has_post_instructions = bool(global_post_config)
        if not has_post_instructions:
            for target in targets:
                if target.post_instructions:
                    has_post_instructions = True
                    break

        if not has_post_instructions:
            logger.info("No post-instructions configured")
            return True

        # Single target optimization
        if len(targets) == 1:
            target = targets[0]
            plugin_type, options = self._merge_post_instructions(
                global_post_config or {}, target.post_instructions
            )
            if not plugin_type:
                logger.warning("Post-instructions configured but no plugin specified")
                return True
            return self._execute_post_instruction_single(target, plugin_type, remote_tar, options)

        # Concurrent execution for multiple targets
        logger.info(f"Executing post-instructions on {len(targets)} target(s) with max {self.max_concurrent_uploads} concurrent operations")

        def post_instruction_worker(target):
            """Worker function for threaded post-instruction execution"""
            try:
                # Merge global and per-target post-instructions
                plugin_type, options = self._merge_post_instructions(
                    global_post_config or {}, target.post_instructions
                )

                if not plugin_type:
                    logger.debug(f"No post-instructions for {target.host}, skipping")
                    return (target.host, True)

                logger.info(f"Executing post-instructions on {target.host} with plugin: {plugin_type}")

                if plugin_type == "k3s_airgap":
                    plugin = K3sAirgapPlugin(self.transport)
                elif plugin_type == "generic_ssh":
                    plugin = GenericSSHPlugin(self.transport)
                elif plugin_type == "docker":
                    plugin = DockerPlugin(self.transport)
                else:
                    logger.error(f"Unknown plugin type: {plugin_type}")
                    return (target.host, False)

                success = plugin.execute(target, remote_tar, options)
                if success:
                    logger.info(f"Post-instructions completed on {target.host}")
                else:
                    logger.error(f"Post-instruction failed on {target.host}")
                return (target.host, success)
            except Exception as e:
                logger.error(f"Error executing post-instructions on {target.host}: {e}")
                return (target.host, False)

        all_success = True
        with ThreadPoolExecutor(max_workers=self.max_concurrent_uploads) as executor:
            future_to_target = {
                executor.submit(post_instruction_worker, target): target
                for target in targets
            }

            for future in as_completed(future_to_target):
                target = future_to_target[future]
                try:
                    host, success = future.result()
                    if not success:
                        all_success = False
                except Exception as e:
                    logger.error(f"Unexpected error for {target.host}: {e}")
                    all_success = False

        return all_success

    def run(self) -> bool:
        """Execute the complete workflow

        Returns:
            True if workflow completed successfully
        """
        logger.info("=" * 60)
        logger.info("Starting Outrider workflow")
        logger.info("=" * 60)

        # Validate configuration
        if not self.config.validate():
            logger.error("Configuration validation failed")
            return False

        # Initialize runtime and transport
        if not self._init_runtime():
            return False

        if not self._init_transport():
            return False

        # Execute workflow steps
        try:
            if not self._pull_images():
                logger.error("Image pull failed")
                return False

            if not self._compress_images():
                logger.error("Image compression failed")
                return False

            if not self._transfer_to_target():
                logger.error("File transfer failed")
                return False

            if not self._execute_post_instructions():
                logger.error("Post-instructions failed")
                return False

            logger.info("=" * 60)
            logger.info("Workflow completed successfully!")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"Workflow failed with exception: {e}")
            return False

        finally:
            # Cleanup
            self.transport.close()
