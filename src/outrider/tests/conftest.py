"""Pytest configuration and shared fixtures"""

import os
import tempfile
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_config_data():
    """Sample configuration data for testing"""
    return {
        "runtime": {
            "type": "docker",
            "options": {
                "cmd": "docker"
            }
        },
        "transport": {
            "type": "ssh",
            "options": {
                "key_file": None,
                "password": "test_password",
                "user": "testuser"
            }
        },
        "targets": [
            {
                "host": "192.168.1.100",
                "port": 22,
                "user": "ubuntu",
                "ssh_options": {
                    "user": "ubuntu"
                }
            }
        ],
        "images": [
            "ubuntu:22.04",
            "nginx:latest"
        ],
        "remote_tar_path": "/tmp/images.tar",
        "output_tar": "/tmp/output.tar",
        "no_cache": False
    }


@pytest.fixture
def sample_config_with_no_cache():
    """Sample configuration with no_cache enabled"""
    return {
        "runtime": {
            "type": "docker"
        },
        "transport": {
            "type": "ssh",
            "options": {
                "password": "test_password"
            }
        },
        "targets": [
            {
                "host": "192.168.1.100",
                "port": 22,
                "user": "ubuntu"
            }
        ],
        "images": ["ubuntu:22.04"],
        "remote_tar_path": "/tmp/images.tar",
        "output_tar": "/tmp/output.tar",
        "no_cache": True
    }


@pytest.fixture
def mock_ssh_client():
    """Mock SSH client for transport tests"""
    client = MagicMock()
    sftp = MagicMock()

    # Mock SFTP operations
    client.open_sftp.return_value = sftp
    sftp.stat.return_value = None
    sftp.put.return_value = None
    sftp.makedirs.return_value = None
    sftp.close.return_value = None

    return client, sftp


@pytest.fixture
def mock_tar_file(temp_dir):
    """Create a mock tar file for testing"""
    tar_path = os.path.join(temp_dir, "test.tar")
    # Create a 1MB test file
    with open(tar_path, "wb") as f:
        f.write(b"0" * (1024 * 1024))
    return tar_path


@pytest.fixture
def mock_docker_runtime():
    """Mock Docker runtime"""
    runtime = MagicMock()
    runtime.pull_image.return_value = True
    runtime.save_images.return_value = True
    return runtime


@pytest.fixture
def mock_ssh_transport():
    """Mock SSH transport"""
    transport = MagicMock()
    transport.transfer_file.return_value = True
    transport.file_exists_remote.return_value = False
    transport.close.return_value = None
    return transport


@pytest.fixture
def mock_config():
    """Mock Config object"""
    config = MagicMock()
    config.runtime_config = {
        "type": "docker",
        "options": {"cmd": "docker"}
    }
    config.transport_config = {
        "type": "ssh",
        "options": {}
    }
    config.images = ["ubuntu:22.04"]
    config.output_tar = "/tmp/test.tar"
    config.remote_tar_path = "/tmp/images.tar"
    config.targets = [MagicMock(host="192.168.1.100", port=22, user="ubuntu", ssh_options={})]
    config.post_instructions = None
    config.validate.return_value = True
    config.no_cache = False
    return config
