"""Configuration persistence for Shellshuck."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from shellshuck.models import AppConfig

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "shellshuck"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"


class ConfigManager:
    """Loads and saves AppConfig to a JSON file."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or DEFAULT_CONFIG_FILE

    def load(self) -> AppConfig:
        """Load config from disk. Returns default config if file doesn't exist."""
        if not self.config_path.exists():
            logger.info("No config file found at %s, using defaults", self.config_path)
            return AppConfig()

        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            return AppConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.error("Failed to parse config at %s: %s", self.config_path, e)
            raise

    def save(self, config: AppConfig) -> None:
        """Save config to disk, creating parent directories as needed."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(config.to_dict(), indent=2)
        self.config_path.write_text(data + "\n", encoding="utf-8")
        logger.info("Config saved to %s", self.config_path)
