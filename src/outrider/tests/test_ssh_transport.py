"""Tests for SSHTransport with file existence checking and progress callbacks"""

import pytest
import os
from unittest.mock import MagicMock, patch, call
from outrider.transport.ssh import SSHTransport
from outrider.transport.base import RemoteHost


class TestSSHTransportFileExists:
    """Test file_exists_remote method"""

    def test_file_exists_remote_true(self, mock_ssh_client):
        """Test file_exists_remote returns True when file exists"""
        client, sftp = mock_ssh_client
        sftp.stat.return_value = MagicMock()  # File exists

        transport = SSHTransport(password="test")
        transport.clients["example.com:22"] = client

        remote_host = RemoteHost(
            host="example.com",
            port=22,
            user="ubuntu",
            ssh_options={}
        )

        # Mock _get_client to return our mock client
        with patch.object(transport, "_get_client", return_value=client):
            result = transport.file_exists_remote(remote_host, "/tmp/images.tar")

        assert result is True
        sftp.stat.assert_called_once_with("/tmp/images.tar")
        sftp.close.assert_called_once()

    def test_file_exists_remote_false(self, mock_ssh_client):
        """Test file_exists_remote returns False when file doesn't exist"""
        client, sftp = mock_ssh_client
        sftp.stat.side_effect = IOError("File not found")

        transport = SSHTransport(password="test")
        transport.clients["example.com:22"] = client

        remote_host = RemoteHost(
            host="example.com",
            port=22,
            user="ubuntu",
            ssh_options={}
        )

        with patch.object(transport, "_get_client", return_value=client):
            result = transport.file_exists_remote(remote_host, "/tmp/images.tar")

        assert result is False
        sftp.close.assert_called_once()

    def test_file_exists_remote_exception(self, mock_ssh_client):
        """Test file_exists_remote handles exceptions gracefully"""
        client, sftp = mock_ssh_client
        client.open_sftp.side_effect = Exception("Connection failed")

        transport = SSHTransport(password="test")

        remote_host = RemoteHost(
            host="example.com",
            port=22,
            user="ubuntu",
            ssh_options={}
        )

        with patch.object(transport, "_get_client", return_value=client):
            result = transport.file_exists_remote(remote_host, "/tmp/images.tar")

        assert result is False


class TestSSHTransportTransferFile:
    """Test transfer_file method with skip_if_exists and progress callbacks"""

    def test_transfer_file_skip_if_exists_true_file_exists(self, mock_ssh_client, mock_tar_file):
        """Test transfer is skipped when file exists and skip_if_exists=True"""
        client, sftp = mock_ssh_client
        sftp.stat.return_value = MagicMock()  # File exists

        transport = SSHTransport(password="test")
        transport.clients["example.com:22"] = client

        remote_host = RemoteHost(
            host="example.com",
            port=22,
            user="ubuntu",
            ssh_options={}
        )

        with patch.object(transport, "file_exists_remote", return_value=True):
            result = transport.transfer_file(
                mock_tar_file,
                remote_host,
                "/tmp/images.tar",
                skip_if_exists=True
            )

        assert result is True
        # sftp.put should not be called since file exists
        sftp.put.assert_not_called()

    def test_transfer_file_skip_if_exists_false_file_exists(self, mock_ssh_client, mock_tar_file):
        """Test transfer happens when skip_if_exists=False even if file exists"""
        client, sftp = mock_ssh_client
        sftp.stat.return_value = MagicMock()

        transport = SSHTransport(password="test")
        transport.clients["example.com:22"] = client

        remote_host = RemoteHost(
            host="example.com",
            port=22,
            user="ubuntu",
            ssh_options={}
        )

        with patch.object(transport, "_get_client", return_value=client):
            result = transport.transfer_file(
                mock_tar_file,
                remote_host,
                "/tmp/images.tar",
                skip_if_exists=False
            )

        assert result is True
        # sftp.put should be called even though file exists
        sftp.put.assert_called_once()

    def test_transfer_file_with_progress_callback(self, mock_ssh_client, mock_tar_file):
        """Test transfer_file calls progress callback with correct arguments"""
        client, sftp = mock_ssh_client

        transport = SSHTransport(password="test")

        remote_host = RemoteHost(
            host="example.com",
            port=22,
            user="ubuntu",
            ssh_options={}
        )

        progress_callback = MagicMock()

        with patch.object(transport, "_get_client", return_value=client):
            with patch.object(transport, "file_exists_remote", return_value=False):
                result = transport.transfer_file(
                    mock_tar_file,
                    remote_host,
                    "/tmp/images.tar",
                    progress_callback=progress_callback,
                    skip_if_exists=False
                )

        assert result is True
        # Verify put was called with callback
        sftp.put.assert_called_once()
        call_args = sftp.put.call_args
        assert call_args[0][0] == mock_tar_file
        assert call_args[0][1] == "/tmp/images.tar"
        assert call_args[1]["callback"] == progress_callback

    def test_transfer_file_without_progress_callback(self, mock_ssh_client, mock_tar_file):
        """Test transfer_file works without progress callback"""
        client, sftp = mock_ssh_client

        transport = SSHTransport(password="test")

        remote_host = RemoteHost(
            host="example.com",
            port=22,
            user="ubuntu",
            ssh_options={}
        )

        with patch.object(transport, "_get_client", return_value=client):
            with patch.object(transport, "file_exists_remote", return_value=False):
                result = transport.transfer_file(
                    mock_tar_file,
                    remote_host,
                    "/tmp/images.tar",
                    progress_callback=None,
                    skip_if_exists=False
                )

        assert result is True
        # Verify put was called without callback keyword
        sftp.put.assert_called_once()
        call_args = sftp.put.call_args
        # Should be called with positional args only
        assert len(call_args[0]) == 2
        assert "callback" not in call_args[1]

    def test_transfer_file_creates_remote_directory(self, mock_ssh_client, mock_tar_file):
        """Test transfer_file creates remote directory if needed"""
        client, sftp = mock_ssh_client
        # stat raises IOError for missing directory
        sftp.stat.side_effect = [IOError("Not found"), None]

        transport = SSHTransport(password="test")

        remote_host = RemoteHost(
            host="example.com",
            port=22,
            user="ubuntu",
            ssh_options={}
        )

        with patch.object(transport, "_get_client", return_value=client):
            result = transport.transfer_file(
                mock_tar_file,
                remote_host,
                "/tmp/subdir/images.tar"
            )

        assert result is True
        sftp.makedirs.assert_called_once_with("/tmp/subdir")

    def test_transfer_file_error_handling(self, mock_ssh_client, mock_tar_file):
        """Test transfer_file handles errors gracefully"""
        client, sftp = mock_ssh_client
        sftp.put.side_effect = Exception("Transfer failed")

        transport = SSHTransport(password="test")

        remote_host = RemoteHost(
            host="example.com",
            port=22,
            user="ubuntu",
            ssh_options={}
        )

        with patch.object(transport, "_get_client", return_value=client):
            with patch.object(transport, "file_exists_remote", return_value=False):
                result = transport.transfer_file(
                    mock_tar_file,
                    remote_host,
                    "/tmp/images.tar"
                )

        assert result is False
