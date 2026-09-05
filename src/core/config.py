"""Load provider configuration from the core package."""

import os
from pathlib import Path

import yaml


def load_config(path: Path | None = None) -> dict:
    config_path = path or Path(__file__).with_name("sync.yaml")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    for provider in config.get("providers", {}).values():
        env_name = provider.get("token_env")
        if not provider.get("token") and env_name:
            provider["token"] = os.getenv(env_name, "")
    return config
