"""Tests for Config class with no_cache property"""

import pytest
import tempfile
import yaml
import os
from outrider.core.config import Config


class TestConfigNoCacheProperty:
    """Test Config.no_cache property"""

    def test_no_cache_default_false(self, temp_dir):
        """Test that no_cache defaults to False"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"]
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        assert config.no_cache is False

    def test_no_cache_true_in_config(self, temp_dir):
        """Test that no_cache can be set to True in config file"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "no_cache": True
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        assert config.no_cache is True

    def test_no_cache_false_in_config(self, temp_dir):
        """Test that no_cache can be explicitly set to False in config file"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "no_cache": False
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        assert config.no_cache is False

    def test_no_cache_is_boolean(self, temp_dir):
        """Test that no_cache property returns boolean type"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["ubuntu:22.04"],
            "no_cache": True
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        assert isinstance(config.no_cache, bool)
        assert config.no_cache is True

    def test_no_cache_with_environment_expansion(self, temp_dir):
        """Test no_cache property works with other config features"""
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "runtime": {"type": "docker"},
            "transport": {"type": "ssh", "options": {"password": "test"}},
            "targets": [{"host": "example.com"}],
            "images": ["$IMAGE_NAME:latest"],
            "no_cache": True,
            "env": {
                "IMAGE_NAME": "ubuntu"
            }
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        assert config.no_cache is True
        assert "ubuntu:latest" in config.images
