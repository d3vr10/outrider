"""SSH/SCP transport implementation"""

import logging
import os
import threading
from typing import Tuple, Optional, Dict, Any

import paramiko
from paramiko import SSHClient, AutoAddPolicy, WarningPolicy, RSAKey

from .base import BaseTransport, RemoteHost

logger = logging.getLogger(__name__)


class SSHTransport(BaseTransport):
    """SSH/SCP transport protocol"""

    def __init__(self, key_file: Optional[str] = None, password: Optional[str] = None,
                 ssh_config: Optional[str] = None, skip_host_verification: bool = False):
        """Initialize SSH transport

        Args:
            key_file: Path to SSH private key (default: ~/.ssh/id_rsa)
            password: SSH password (used if key_file not available)
            ssh_config: Path to SSH config file (auto-detected if None)
            skip_host_verification: Skip SSH host key verification (insecure, for testing only)
        """
        # Expand ~ in paths
        if key_file:
            self.key_file = os.path.expanduser(key_file)
        else:
            self.key_file = os.path.expanduser("~/.ssh/id_rsa")
        self.password = password
        self.clients = {}  # Cache for SSH clients
        self.clients_lock = threading.Lock()  # Protect client cache for concurrent access
        self.ssh_config_parser = None
        self.skip_host_verification = skip_host_verification
        if skip_host_verification:
            logger.warning("SSH host key verification is DISABLED - only use for testing!")
        self._load_ssh_config(ssh_config)

    def _load_ssh_config(self, ssh_config_path: Optional[str] = None) -> None:
        """Load SSH config file with auto-detection

        Args:
            ssh_config_path: Path to SSH config file (None = auto-detect ~/.ssh/config)
        """
        if ssh_config_path is None:
            ssh_config_path = os.path.expanduser("~/.ssh/config")
        else:
            ssh_config_path = os.path.expanduser(ssh_config_path)

        if os.path.exists(ssh_config_path):
            try:
                self.ssh_config_parser = paramiko.SSHConfig.from_path(ssh_config_path)
                logger.info(f"Loaded SSH config from {ssh_config_path}")
            except Exception as e:
                logger.warning(f"Failed to load SSH config from {ssh_config_path}: {e}")
                self.ssh_config_parser = None
        else:
            logger.debug(f"SSH config not found at {ssh_config_path}")
            self.ssh_config_parser = None

    def _merge_ssh_config(self, remote_host: RemoteHost) -> Dict[str, Any]:
        """Merge SSH config with precedence: per-target > global > SSH config > defaults

        Args:
            remote_host: Remote host configuration

        Returns:
            Merged connection parameters for paramiko SSHClient.connect()
        """
        config = {}

        # Start with SSH config file (lowest precedence)
        if self.ssh_config_parser:
            ssh_config = self.ssh_config_parser.lookup(remote_host.host)
            config['hostname'] = ssh_config.get('hostname', remote_host.host)
            config['port'] = ssh_config.get('port', 22)
            config['username'] = ssh_config.get('user', remote_host.user)

            # Handle identity files
            identity_files = ssh_config.get('identityfile', [])
            if identity_files:
                config['key_filename'] = identity_files

            # Handle ProxyJump/ProxyCommand
            if 'proxyjump' in ssh_config:
                proxy_host = ssh_config['proxyjump']
                proxy_cmd = f"ssh -W %h:%p {proxy_host}"
                config['sock'] = paramiko.ProxyCommand(proxy_cmd)
            elif 'proxycommand' in ssh_config:
                config['sock'] = paramiko.ProxyCommand(ssh_config['proxycommand'])
        else:
            # No SSH config - use RemoteHost values as base
            config['hostname'] = remote_host.host
            config['port'] = remote_host.port
            config['username'] = remote_host.user

        # Apply global transport options (medium precedence)
        if self.key_file and not config.get('key_filename'):
            config['key_filename'] = self.key_file
        if self.password:
            config['password'] = self.password

        # Apply per-target ssh_options (highest precedence)
        if remote_host.ssh_options:
            if 'key_file' in remote_host.ssh_options:
                config['key_filename'] = os.path.expanduser(remote_host.ssh_options['key_file'])
            if 'password' in remote_host.ssh_options:
                config['password'] = remote_host.ssh_options['password']
            if 'port' in remote_host.ssh_options:
                config['port'] = remote_host.ssh_options['port']
            if 'user' in remote_host.ssh_options:
                config['username'] = remote_host.ssh_options['user']

        config.setdefault('timeout', 10)
        return config

    def _get_client(self, remote_host: RemoteHost) -> SSHClient:
        """Get or create SSH client for host

        Args:
            remote_host: Remote host configuration

        Returns:
            SSH client instance
        """
        # Merge all config sources
        connect_config = self._merge_ssh_config(remote_host)

        # Use resolved hostname for caching
        host_key = f"{connect_config['hostname']}:{connect_config['port']}"

        with self.clients_lock:
            if host_key not in self.clients:
                client = SSHClient()

                # Choose host key policy
                if self.skip_host_verification:
                    client.set_missing_host_key_policy(WarningPolicy())
                else:
                    client.set_missing_host_key_policy(AutoAddPolicy())

                try:
                    logger.debug(f"Connecting to {remote_host.host} (resolved: {connect_config['hostname']})")
                    client.connect(**connect_config)

                    self.clients[host_key] = client
                    logger.info(f"Connected to {remote_host.host}")
                except Exception as e:
                    logger.error(f"Failed to connect to {remote_host.host}: {e}")
                    raise

            return self.clients[host_key]

    def transfer_file(self, local_path: str, remote_host: RemoteHost, remote_path: str) -> bool:
        """Transfer a file to a remote host via SCP

        Args:
            local_path: Path to local file
            remote_host: Remote host configuration
            remote_path: Path on remote host

        Returns:
            True if successful, False otherwise
        """
        try:
            client = self._get_client(remote_host)
            sftp = client.open_sftp()

            logger.info(f"Transferring {local_path} to {remote_host.host}:{remote_path}")

            # Create remote directory if needed
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                try:
                    sftp.stat(remote_dir)
                except IOError:
                    logger.debug(f"Creating remote directory: {remote_dir}")
                    sftp.makedirs(remote_dir)

            sftp.put(local_path, remote_path)
            sftp.close()

            logger.info(f"Successfully transferred {local_path} to {remote_host.host}")
            return True

        except Exception as e:
            logger.error(f"Failed to transfer file: {e}")
            return False

    def execute_remote(self, remote_host: RemoteHost, command: str) -> Tuple[int, str, str]:
        """Execute a command on remote host

        Args:
            remote_host: Remote host configuration
            command: Command to execute

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            client = self._get_client(remote_host)

            logger.debug(f"Executing on {remote_host.host}: {command}")

            stdin, stdout, stderr = client.exec_command(command, timeout=300)
            return_code = stdout.channel.recv_exit_status()

            stdout_str = stdout.read().decode("utf-8", errors="replace")
            stderr_str = stderr.read().decode("utf-8", errors="replace")

            logger.debug(f"Command completed with return code: {return_code}")

            return return_code, stdout_str, stderr_str

        except Exception as e:
            logger.error(f"Failed to execute remote command: {e}")
            return 1, "", str(e)

    def close(self) -> None:
        """Close all SSH connections"""
        with self.clients_lock:
            for client in self.clients.values():
                try:
                    client.close()
                except Exception as e:
                    logger.warning(f"Error closing SSH connection: {e}")

            self.clients.clear()
        logger.info("Closed SSH connections")
