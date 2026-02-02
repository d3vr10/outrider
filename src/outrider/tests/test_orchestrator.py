"""Tests for Orchestrator with progress bars and no_cache logic"""

import pytest
import os
from unittest.mock import MagicMock, patch, call
from outrider.core.orchestrator import Orchestrator
from outrider.transport.base import RemoteHost


class TestOrchestratorInit:
    """Test Orchestrator initialization with no_cache parameter"""

    def test_orchestrator_init_no_cache_default_false(self, mock_config):
        """Test that no_cache defaults to False in Orchestrator"""
        orchestrator = Orchestrator(mock_config)
        assert orchestrator.no_cache is False

    def test_orchestrator_init_no_cache_true(self, mock_config):
        """Test that no_cache can be set to True"""
        orchestrator = Orchestrator(mock_config, no_cache=True)
        assert orchestrator.no_cache is True

    def test_orchestrator_init_no_cache_with_other_params(self, mock_config):
        """Test no_cache with other parameters"""
        orchestrator = Orchestrator(
            mock_config,
            skip_host_verification=True,
            max_concurrent_uploads=4,
            skip_cache=True,
            clear_cache=True,
            no_cache=True
        )
        assert orchestrator.no_cache is True
        assert orchestrator.skip_host_verification is True
        assert orchestrator.max_concurrent_uploads == 4
        assert orchestrator.skip_cache is True
        assert orchestrator.clear_cache is True


class TestOrchestratorTransferWithNoCacheLogic:
    """Test transfer logic with no_cache flag"""

    def test_transfer_skip_existing_when_no_cache_false(self, mock_config, mock_tar_file, mock_ssh_transport):
        """Test that skip_if_exists=True when both no_cache and config.no_cache are False"""
        mock_config.output_tar = mock_tar_file
        mock_config.no_cache = False

        orchestrator = Orchestrator(mock_config, no_cache=False)
        orchestrator.transport = mock_ssh_transport
        orchestrator.runtime = MagicMock()

        with patch("outrider.core.orchestrator.tqdm"):
            result = orchestrator._transfer_to_target()

        # Verify skip_if_exists was True (config and CLI both allow skipping)
        assert mock_ssh_transport.transfer_file.called
        call_args = mock_ssh_transport.transfer_file.call_args
        assert call_args[1]["skip_if_exists"] is True

    def test_transfer_no_skip_when_cli_no_cache_true(self, mock_config, mock_tar_file, mock_ssh_transport):
        """Test that skip_if_exists=False when CLI --no-cache is True"""
        mock_config.output_tar = mock_tar_file
        mock_config.no_cache = False

        orchestrator = Orchestrator(mock_config, no_cache=True)
        orchestrator.transport = mock_ssh_transport
        orchestrator.runtime = MagicMock()

        with patch("outrider.core.orchestrator.tqdm"):
            result = orchestrator._transfer_to_target()

        # Verify skip_if_exists was False (CLI flag overrides)
        assert mock_ssh_transport.transfer_file.called
        call_args = mock_ssh_transport.transfer_file.call_args
        assert call_args[1]["skip_if_exists"] is False

    def test_transfer_no_skip_when_config_no_cache_true(self, mock_config, mock_tar_file, mock_ssh_transport):
        """Test that skip_if_exists=False when config has no_cache=True"""
        mock_config.output_tar = mock_tar_file
        mock_config.no_cache = True

        orchestrator = Orchestrator(mock_config, no_cache=False)
        orchestrator.transport = mock_ssh_transport
        orchestrator.runtime = MagicMock()

        with patch("outrider.core.orchestrator.tqdm"):
            result = orchestrator._transfer_to_target()

        # Verify skip_if_exists was False (config no_cache is True)
        assert mock_ssh_transport.transfer_file.called
        call_args = mock_ssh_transport.transfer_file.call_args
        assert call_args[1]["skip_if_exists"] is False

    def test_transfer_no_skip_when_both_no_cache_true(self, mock_config, mock_tar_file, mock_ssh_transport):
        """Test that skip_if_exists=False when both CLI and config have no_cache=True"""
        mock_config.output_tar = mock_tar_file
        mock_config.no_cache = True

        orchestrator = Orchestrator(mock_config, no_cache=True)
        orchestrator.transport = mock_ssh_transport
        orchestrator.runtime = MagicMock()

        with patch("outrider.core.orchestrator.tqdm"):
            result = orchestrator._transfer_to_target()

        # Verify skip_if_exists was False (both are True)
        assert mock_ssh_transport.transfer_file.called
        call_args = mock_ssh_transport.transfer_file.call_args
        assert call_args[1]["skip_if_exists"] is False


class TestOrchestratorProgressBars:
    """Test progress bar integration in Orchestrator"""

    @patch("outrider.core.orchestrator.tqdm")
    def test_compress_images_shows_progress(self, mock_tqdm, mock_config):
        """Test that _compress_images shows progress bar"""
        mock_config.images = ["ubuntu:22.04", "nginx:latest"]

        orchestrator = Orchestrator(mock_config)
        orchestrator.runtime = MagicMock()
        orchestrator.runtime.save_images.return_value = True

        # Create a mock tar file
        with patch("os.path.exists") as mock_exists:
            with patch("os.path.getsize", return_value=1024 * 1024):  # 1MB
                with patch("os.remove"):  # Mock removal to avoid file errors
                    mock_exists.return_value = True  # File exists after save_images
                    result = orchestrator._compress_images()

        # Verify tqdm was called with correct parameters
        mock_tqdm.assert_called_once_with(total=100, desc="Compressing images", unit="%")
        assert result is True

    @patch("outrider.core.orchestrator.tqdm")
    def test_transfer_to_target_single_target_shows_progress(self, mock_tqdm, mock_config, mock_tar_file, mock_ssh_transport):
        """Test that _transfer_to_target shows progress bar for single target"""
        mock_config.output_tar = mock_tar_file
        mock_config.no_cache = False

        orchestrator = Orchestrator(mock_config)
        orchestrator.transport = mock_ssh_transport
        orchestrator.runtime = MagicMock()

        with patch("os.path.exists", return_value=True):
            with patch("os.path.getsize", return_value=1024 * 1024):  # 1MB
                result = orchestrator._transfer_to_target()

        # Verify tqdm was called with file size
        mock_tqdm.assert_called()
        call_args = mock_tqdm.call_args_list[0]
        assert call_args[1]["total"] == 1024 * 1024
        assert "Upload to" in call_args[1]["desc"]

    @patch("outrider.core.orchestrator.tqdm")
    def test_transfer_to_target_multiple_targets_shows_progress(self, mock_tqdm, mock_config, mock_tar_file, mock_ssh_transport):
        """Test that _transfer_to_target shows progress bars for multiple targets"""
        mock_config.output_tar = mock_tar_file
        mock_config.no_cache = False
        # Add second target
        target2 = MagicMock(host="192.168.1.101", port=22, user="ubuntu", ssh_options={})
        mock_config.targets = [mock_config.targets[0], target2]

        orchestrator = Orchestrator(mock_config, max_concurrent_uploads=2)
        orchestrator.transport = mock_ssh_transport
        orchestrator.runtime = MagicMock()

        with patch("os.path.exists", return_value=True):
            with patch("os.path.getsize", return_value=1024 * 1024):  # 1MB
                result = orchestrator._transfer_to_target()

        # Verify tqdm was called for each target
        assert mock_tqdm.call_count >= 2

    @patch("outrider.core.orchestrator.tqdm")
    def test_progress_callback_updates_progress(self, mock_tqdm, mock_config, mock_tar_file, mock_ssh_transport):
        """Test that progress callback is passed to transfer_file"""
        mock_config.output_tar = mock_tar_file
        mock_config.no_cache = False

        orchestrator = Orchestrator(mock_config)
        orchestrator.transport = mock_ssh_transport
        orchestrator.runtime = MagicMock()

        # Capture the progress callback
        progress_callback_arg = None
        def capture_callback(*args, **kwargs):
            nonlocal progress_callback_arg
            if "progress_callback" in kwargs:
                progress_callback_arg = kwargs["progress_callback"]
            return True

        mock_ssh_transport.transfer_file.side_effect = capture_callback

        with patch("os.path.exists", return_value=True):
            with patch("os.path.getsize", return_value=1024 * 1024):  # 1MB
                result = orchestrator._transfer_to_target()

        # Verify progress callback was passed
        assert progress_callback_arg is not None
        assert callable(progress_callback_arg)


class TestOrchestratorErrorHandling:
    """Test error handling in transfer operations"""

    def test_transfer_to_target_missing_local_file(self, mock_config):
        """Test error when local tar file doesn't exist"""
        orchestrator = Orchestrator(mock_config)
        orchestrator.transport = MagicMock()

        with patch("os.path.exists", return_value=False):
            result = orchestrator._transfer_to_target()

        assert result is False

    def test_transfer_to_target_transfer_failure(self, mock_config, mock_tar_file, mock_ssh_transport):
        """Test handling of transfer failure"""
        mock_config.output_tar = mock_tar_file
        mock_ssh_transport.transfer_file.return_value = False

        orchestrator = Orchestrator(mock_config)
        orchestrator.transport = mock_ssh_transport
        orchestrator.runtime = MagicMock()

        with patch("os.path.exists", return_value=True):
            with patch("os.path.getsize", return_value=1024 * 1024):
                with patch("outrider.core.orchestrator.tqdm"):
                    result = orchestrator._transfer_to_target()

        assert result is False
