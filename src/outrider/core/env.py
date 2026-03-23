"""Environment variable management and expansion"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class EnvManager:
    """Manages environment variables with support for loading from files and expansion"""

    def __init__(self):
        """Initialize environment manager with system environment"""
        self.env: Dict[str, str] = dict(os.environ)

    def load_file(self, file_path: str) -> Dict[str, str]:
        """Load environment variables from a .env file

        Args:
            file_path: Path to .env file

        Returns:
            Dictionary of loaded variables
        """
        file_path = os.path.expanduser(file_path)
        variables = {}

        if not os.path.exists(file_path):
            logger.warning(f"Environment file not found: {file_path}")
            return variables

        try:
            with open(file_path, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Parse KEY=VALUE format
                    if "=" not in line:
                        logger.warning(f"Invalid line in {file_path}:{line_num}: {line}")
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Handle quoted values
                    if value and value[0] in ('"', "'"):
                        quote = value[0]
                        if value.endswith(quote):
                            value = value[1:-1]
                        else:
                            logger.warning(f"Unclosed quote in {file_path}:{line_num}")

                    variables[key] = value
                    logger.debug(f"Loaded {key} from {file_path}")

            logger.info(f"Loaded {len(variables)} variables from {file_path}")
            return variables

        except Exception as e:
            logger.error(f"Failed to load environment file {file_path}: {e}")
            return variables

    def load_files(self, file_paths: List[str]) -> Dict[str, str]:
        """Load environment variables from multiple files

        Args:
            file_paths: List of paths to .env files

        Returns:
            Merged dictionary of variables (later files override earlier ones)
        """
        merged = {}
        for file_path in file_paths:
            vars_from_file = self.load_file(file_path)
            merged.update(vars_from_file)
        return merged

    def merge(self, sources: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        """Merge environment variables from multiple sources with precedence

        Precedence (highest to lowest):
        1. env_direct - Direct env property in config
        2. env_from_files - Loaded from files (in order)
        3. system - System environment variables

        Args:
            sources: Dict with keys 'system', 'env_from_files', 'env_direct'

        Returns:
            Merged environment dictionary
        """
        merged = {}

        # Start with system environment (lowest priority)
        if "system" in sources:
            merged.update(sources["system"])

        # Add from files (medium priority, later files override earlier)
        if "env_from_files" in sources:
            merged.update(sources["env_from_files"])

        # Add direct env (highest priority)
        if "env_direct" in sources:
            merged.update(sources["env_direct"])

        return merged

    @staticmethod
    def expand_value(value: str, variables: Dict[str, str]) -> str:
        """Expand variables in a string

        Supports:
        - $VAR_NAME or ${VAR_NAME}
        - ${VAR_NAME:-default_value} (default if not set)
        - ${VAR_NAME:?error message} (error if not set)

        Args:
            value: String to expand
            variables: Dictionary of variables

        Returns:
            Expanded string
        """
        if not isinstance(value, str):
            return value

        def replace_var(match):
            var_expr = match.group(1)

            # Handle ${VAR_NAME:-default}
            if ":-" in var_expr:
                var_name, default = var_expr.split(":-", 1)
                var_name = var_name.strip()
                default = default.rstrip("}")
                return variables.get(var_name, default)

            # Handle ${VAR_NAME:?error}
            if ":?" in var_expr:
                var_name, error_msg = var_expr.split(":?", 1)
                var_name = var_name.strip()
                error_msg = error_msg.rstrip("}")
                if var_name not in variables:
                    raise ValueError(f"Required variable not set: {var_name} ({error_msg})")
                return variables[var_name]

            # Handle ${VAR_NAME} or $VAR_NAME
            var_name = var_expr.rstrip("}")
            return variables.get(var_name, match.group(0))

        # Replace ${VAR_NAME...} patterns
        result = re.sub(r"\$\{([^}]+)\}", replace_var, value)

        # Replace $VAR_NAME patterns (simple variable names only)
        result = re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)", lambda m: variables.get(m.group(1), m.group(0)), result)

        return result

    @staticmethod
    def expand_dict(config: Dict, variables: Dict[str, str]) -> Dict:
        """Recursively expand variables in a configuration dictionary

        Args:
            config: Configuration dictionary
            variables: Dictionary of variables

        Returns:
            Configuration with expanded variables
        """
        expanded = {}

        for key, value in config.items():
            if isinstance(value, str):
                try:
                    expanded[key] = EnvManager.expand_value(value, variables)
                except ValueError as e:
                    logger.error(f"Variable expansion error for {key}: {e}")
                    raise
            elif isinstance(value, dict):
                expanded[key] = EnvManager.expand_dict(value, variables)
            elif isinstance(value, list):
                expanded[key] = [
                    EnvManager.expand_value(item, variables) if isinstance(item, str)
                    else EnvManager.expand_dict(item, variables) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                expanded[key] = value

        return expanded
