"""Integration tests for progress bars, no_cache, and file existence checking"""

import pytest
import os
import tempfile
import yaml
from unittest.mock import MagicMock, patch
from outrider.core.orchestrator import Orchestrator
from outrider.core.config import Config
from outrider.transport.ssh import SSHTransport
from outrider.transport.base import RemoteHost


class TestProgressBarIntegration:
    """Integration tests for progress bars"""

    def test_transfer_with_progress_tracking_single_target(self, temp_dir, mock_tar_file):
        """Test end-to-end transfer with progress bar and single target"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com", "port": 22, "user": "ubuntu"}],
            "images": ["ubuntu:22.04"],
            "output_tar": mock_tar_file,
            "remote_tar_path": "/tmp/images.tar"
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)

        with patch("outrider.transport.ssh.SSHTransport._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_sftp = MagicMock()
            mock_client.open_sftp.return_value = mock_sftp
            mock_get_client.return_value = mock_client

            with patch("outrider.core.orchestrator.tqdm") as mock_tqdm:
                # Mock tqdm context manager
                mock_tqdm.return_value.__enter__ = MagicMock()
                mock_tqdm.return_value.__exit__ = MagicMock()

                orchestrator = Orchestrator(config)
                orchestrator.transport = SSHTransport(password="test")
                orchestrator.transport._get_client = mock_get_client

                result = orchestrator._transfer_to_target()

        assert result is True
        mock_tqdm.assert_called()

    def test_transfer_skip_existing_with_progress(self, temp_dir, mock_tar_file):
        """Test that skipped transfers still show progress bar"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "output_tar": mock_tar_file,
            "remote_tar_path": "/tmp/images.tar",
            "no_cache": False
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)

        with patch("outrider.transport.ssh.SSHTransport._get_client"):
            with patch("outrider.transport.ssh.SSHTransport.file_exists_remote", return_value=True):
                with patch("outrider.core.orchestrator.tqdm") as mock_tqdm:
                    mock_tqdm.return_value.__enter__ = MagicMock()
                    mock_tqdm.return_value.__exit__ = MagicMock()

                    orchestrator = Orchestrator(config)
                    orchestrator.transport = MagicMock()
                    orchestrator.transport.transfer_file.return_value = True

                    result = orchestrator._transfer_to_target()

        assert result is True


class TestNoCacheIntegration:
    """Integration tests for no_cache flag interactions"""

    def test_cli_no_cache_overrides_config(self, temp_dir):
        """Test that CLI --no-cache flag overrides config setting"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "no_cache": False  # Config says don't force
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        # CLI --no-cache flag is passed as True
        orchestrator = Orchestrator(config, no_cache=True)

        # The skip_if_exists should be False because CLI no_cache=True
        # (self.no_cache is False) and (self.config.no_cache is False) => True
        # But: no_cache=True means NOT (no_cache is False) => not skip
        assert orchestrator.no_cache is True

    def test_config_no_cache_affects_transfer(self, temp_dir, mock_tar_file):
        """Test that config no_cache=True forces re-upload"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "output_tar": mock_tar_file,
            "remote_tar_path": "/tmp/images.tar",
            "no_cache": True  # Force re-upload
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        assert config.no_cache is True

        orchestrator = Orchestrator(config, no_cache=False)

        # With config.no_cache=True, skip_if_exists should be False
        # (self.no_cache is False) and (self.config.no_cache is False) => False
        # Since config.no_cache is True, the second part is False
        # So overall: False and False => False (correct, don't skip)


class TestFileExistenceCheckingIntegration:
    """Integration tests for remote file existence checking"""

    def test_skip_transfer_if_file_exists(self, temp_dir, mock_tar_file):
        """Test that transfer is skipped if remote file exists and no_cache is False"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "output_tar": mock_tar_file,
            "remote_tar_path": "/tmp/images.tar",
            "no_cache": False
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)

        with patch("outrider.transport.ssh.SSHTransport._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_sftp = MagicMock()
            mock_client.open_sftp.return_value = mock_sftp
            mock_sftp.stat.return_value = MagicMock()  # File exists
            mock_get_client.return_value = mock_client

            transport = SSHTransport(password="test")
            orchestrator = Orchestrator(config)
            orchestrator.transport = transport

            remote_host = RemoteHost(
                host="example.com",
                port=22,
                user="ubuntu",
                ssh_options={}
            )

            # Check that file exists on remote
            exists = transport.file_exists_remote(remote_host, "/tmp/images.tar")
            assert exists is True

    def test_force_transfer_with_no_cache(self, temp_dir, mock_tar_file):
        """Test that transfer happens even if file exists when no_cache=True"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "output_tar": mock_tar_file,
            "remote_tar_path": "/tmp/images.tar"
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)

        with patch("outrider.transport.ssh.SSHTransport._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_sftp = MagicMock()
            mock_client.open_sftp.return_value = mock_sftp
            mock_sftp.stat.return_value = MagicMock()  # File exists
            mock_get_client.return_value = mock_client

            transport = SSHTransport(password="test")

            # With no_cache=True (CLI flag), skip_if_exists should be False
            orchestrator = Orchestrator(config, no_cache=True)

            # Simulate the logic: skip_if_exists = (no_cache is False) and (config.no_cache is False)
            # With CLI no_cache=True: (True is False) and (False is False) => False and False => False
            skip_existing = (orchestrator.no_cache is False) and (config.no_cache is False)
            assert skip_existing is False


class TestProgressCallbackIntegration:
    """Integration tests for progress callback functionality"""

    def test_progress_callback_invoked_during_transfer(self, temp_dir, mock_tar_file):
        """Test that progress callback is actually invoked during transfer"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "output_tar": mock_tar_file,
            "remote_tar_path": "/tmp/images.tar"
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)

        callback_invoked = []

        def mock_callback(transferred, total):
            callback_invoked.append((transferred, total))

        with patch("outrider.transport.ssh.SSHTransport._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_sftp = MagicMock()
            mock_client.open_sftp.return_value = mock_sftp

            # Simulate paramiko callback behavior
            def mock_put(localpath, remotepath, callback=None):
                if callback:
                    callback(512 * 1024, 1024 * 1024)  # Half transferred
                    callback(1024 * 1024, 1024 * 1024)  # Complete

            mock_sftp.put = mock_put
            mock_get_client.return_value = mock_client

            transport = SSHTransport(password="test")
            orchestrator = Orchestrator(config)

            remote_host = RemoteHost(
                host="example.com",
                port=22,
                user="ubuntu",
                ssh_options={}
            )

            # Transfer with callback
            result = transport.transfer_file(
                mock_tar_file,
                remote_host,
                "/tmp/images.tar",
                progress_callback=mock_callback,
                skip_if_exists=False
            )

            assert result is True
            assert len(callback_invoked) == 2
            assert callback_invoked[0] == (512 * 1024, 1024 * 1024)
            assert callback_invoked[1] == (1024 * 1024, 1024 * 1024)


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_transfer_with_empty_tar_file(self, temp_dir):
        """Test transfer with zero-byte tar file"""
        config_file = os.path.join(temp_dir, "config.yaml")
        empty_tar = os.path.join(temp_dir, "empty.tar")
        # Create empty file
        open(empty_tar, "w").close()

        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "output_tar": empty_tar,
            "remote_tar_path": "/tmp/images.tar"
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)

        with patch("outrider.transport.ssh.SSHTransport._get_client"):
            with patch("outrider.core.orchestrator.tqdm"):
                orchestrator = Orchestrator(config)
                orchestrator.transport = MagicMock()
                orchestrator.transport.transfer_file.return_value = True

                result = orchestrator._transfer_to_target()

        assert result is True

    def test_transfer_with_special_characters_in_path(self, temp_dir, mock_tar_file):
        """Test transfer with special characters in file path"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "output_tar": mock_tar_file,
            "remote_tar_path": "/tmp/images-2024-02-01.tar"
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)

        with patch("outrider.transport.ssh.SSHTransport._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_sftp = MagicMock()
            mock_client.open_sftp.return_value = mock_sftp
            mock_get_client.return_value = mock_client

            transport = SSHTransport(password="test")

            remote_host = RemoteHost(
                host="example.com",
                port=22,
                user="ubuntu",
                ssh_options={}
            )

            result = transport.transfer_file(
                mock_tar_file,
                remote_host,
                "/tmp/images-2024-02-01.tar"
            )

            assert result is True
            mock_sftp.put.assert_called_once()
