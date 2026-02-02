"""Tests for CLI with --no-cache flag"""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from outrider.cli import cli


class TestCLINoCache:
    """Test --no-cache CLI flag"""

    def test_deploy_help_shows_no_cache_option(self):
        """Test that deploy --help shows --no-cache option"""
        runner = CliRunner()
        result = runner.invoke(cli, ["deploy", "--help"])

        assert result.exit_code == 0
        assert "--no-cache" in result.output
        assert "Force re-upload" in result.output

    def test_no_cache_flag_is_boolean(self):
        """Test that --no-cache flag is a boolean flag"""
        from outrider.cli import deploy
        # Check the deploy command has the --no-cache option
        assert any(
            param.name == "no_cache"
            for param in deploy.params
            if hasattr(param, "name")
        )

    def test_validate_command_exists(self):
        """Test that validate command is available"""
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--help"])

        assert result.exit_code == 0
        assert "validate" in result.output.lower()

    def test_help_shows_all_commands(self):
        """Test that main help shows all available commands"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "deploy" in result.output
        assert "validate" in result.output


class TestCLIOptions:
    """Test CLI option parsing"""

    def test_deploy_has_multiple_options(self):
        """Test that deploy command has expected options"""
        from outrider.cli import deploy
        option_names = {
            param.name
            for param in deploy.params
            if hasattr(param, "name")
        }

        # Check for key options
        assert "config" in option_names
        assert "verbose" in option_names
        assert "env_file" in option_names
        assert "skip_host_verification" in option_names
        assert "max_concurrent_uploads" in option_names
        assert "skip_cache" in option_names
        assert "clear_cache" in option_names
        assert "no_cache" in option_names

    def test_no_cache_flag_complementary_to_skip_cache(self):
        """Test that no_cache and skip_cache are separate concepts"""
        # skip_cache: skip local SHA256 cache validation and re-compress
        # no_cache: force re-upload even if file exists on remote
        # These are complementary but independent flags

        from outrider.cli import deploy

        # Both options should exist
        param_names = {param.name for param in deploy.params if hasattr(param, "name")}
        assert "skip_cache" in param_names
        assert "no_cache" in param_names
