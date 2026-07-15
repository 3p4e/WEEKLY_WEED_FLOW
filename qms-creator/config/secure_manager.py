"""
Secure Key Manager
Handles loading of API keys and secrets from .env files, local configuration files,
or environment variables. Prioritizes security by ensuring keys are never hardcoded or logged.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import dotenv_values, load_dotenv

logger = logging.getLogger("SecureManager")


class SecureKeyManager:
    def __init__(self, project_root: str, environment: Optional[str] = None):
        self.project_root = Path(project_root)
        self.environment = environment or os.environ.get("ENVIRONMENT", "development")
        self.secrets_path = self.project_root / "secrets.yaml"
        self._secrets: Dict[str, Any] = {}
        self._env_vars: Dict[str, str] = {}

        # Load in priority order
        self._load_env_files()
        self._load_secrets()

    def _load_env_files(self):
        """Load environment variables from .env files in priority order"""
        env_files = [
            self.project_root / ".env.example",  # Base defaults
            self.project_root / ".env",  # Shared local overrides
            self.project_root / f".env.{self.environment}",  # Environment-specific
        ]

        for env_file in env_files:
            if env_file.exists():
                try:
                    # Load dotenv file and merge with current environment
                    load_dotenv(env_file, override=True)
                    # Also store locally for reference
                    env_values = dotenv_values(env_file)
                    self._env_vars.update(env_values)
                    logger.info(f"Loaded environment from {env_file}")
                except Exception as e:
                    logger.error(f"Failed to load .env file {env_file}: {e}")

    def _load_secrets(self):
        """Load secrets from yaml file if it exists"""
        if self.secrets_path.exists():
            try:
                with open(self.secrets_path, "r", encoding="utf-8") as f:
                    self._secrets = yaml.safe_load(f) or {}
                # Ensure we don't log the actual keys
                logger.info(f"Loaded secrets from {self.secrets_path}")
            except Exception as e:
                logger.error(f"Failed to load secrets: {e}")
        else:
            logger.warning(
                f"No secrets file found at {self.secrets_path}. Using environment variables only."
            )

    def get_key(self, key_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret key.
        Priority:
        1. Environment Variable (Upper Case)
        2. secrets.yaml (Nested under 'keys' or top level)
        3. Default value
        """
        # 1. Environment Variable
        env_val = os.environ.get(key_name.upper())
        if env_val:
            return env_val

        # 2. secrets.yaml
        # Check deep structure if it exists, e.g. keys: { openai: ... }
        if self._secrets:
            # Try top level
            if key_name in self._secrets:
                return str(self._secrets[key_name])

            # Try under 'keys' section
            keys_section = self._secrets.get("keys", {})
            if isinstance(keys_section, dict) and key_name in keys_section:
                return str(keys_section[key_name])

        return default

    def set_environment_variables(self):
        """
        Inject known keys into environment variables so legacy libraries (like OpenAI client)
        can auto-discover them.
        """
        mapping = {
            "openai_api_key": "OPENAI_API_KEY",
            "anthropic_api_key": "ANTHROPIC_API_KEY",
            "ollama_url": "OLLAMA_URL",
        }

        for secret_name, env_name in mapping.items():
            val = self.get_key(secret_name)
            if val:
                os.environ[env_name] = val
                logger.debug(f"Set environment variable {env_name}")
