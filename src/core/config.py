"""Load and persist provider settings without exposing credentials."""

from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import tempfile
from typing import Any

import yaml


BUNDLED_CONFIG = Path(__file__).with_name("sync.yaml")
CONFIG_PATH_ENV = "SMMD_CONFIG"
PROVIDER_FIELDS = {
    "github": ("api_url", "GITHUB_API_URL"),
    "gitee": ("api_url", "GITEE_API_URL"),
    "youtrack": ("url", "YOUTRACK_URL"),
}


def _read_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError(f"configuration must be a YAML object: {path}")
    if not isinstance(value.get("providers", {}), dict):
        raise ValueError("configuration providers must be an object")
    return value


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _environment_bool(value: str, name: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


class ConfigStore:
    """YAML-backed settings with process-environment overrides at read time."""

    def __init__(self, path: Path | str | None = None):
        configured = path if path is not None else os.getenv(CONFIG_PATH_ENV)
        self.path = Path(configured).expanduser() if configured else None

    def _stored(self) -> dict[str, Any]:
        base = _read_yaml(BUNDLED_CONFIG)
        if self.path and self.path.exists():
            return _merge(base, _read_yaml(self.path))
        return base

    def load(self) -> dict[str, Any]:
        config = self._stored()
        providers = config.setdefault("providers", {})
        for name, (url_key, url_env) in PROVIDER_FIELDS.items():
            provider = providers.setdefault(name, {})
            prefix = name.upper()
            enabled_env = f"{prefix}_ENABLED"
            if enabled_env in os.environ:
                provider["enabled"] = _environment_bool(
                    os.environ[enabled_env], enabled_env
                )
            if url_env in os.environ:
                provider[url_key] = os.environ[url_env]
            token_env = provider.get("token_env") or f"{prefix}_TOKEN"
            if token_env in os.environ:
                provider["token"] = os.environ[token_env]
            elif not provider.get("token"):
                provider["token"] = ""
        return config

    def public(self) -> dict[str, Any]:
        effective = self.load()
        stored = self._stored()
        result: dict[str, Any] = {
            "persistent": self.path is not None,
            "providers": {},
        }
        for name, (url_key, url_env) in PROVIDER_FIELDS.items():
            provider = effective.get("providers", {}).get(name, {})
            stored_provider = stored.get("providers", {}).get(name, {})
            token_env = provider.get("token_env") or f"{name.upper()}_TOKEN"
            result["providers"][name] = {
                "enabled": bool(provider.get("enabled", False)),
                "url": provider.get(url_key, ""),
                "token_configured": bool(provider.get("token")),
                "token_source": (
                    "environment"
                    if token_env in os.environ
                    else ("yaml" if stored_provider.get("token") else None)
                ),
                "environment_overrides": [
                    key
                    for key in (f"{name.upper()}_ENABLED", url_env, token_env)
                    if key in os.environ
                ],
            }
        return result

    def update(self, providers: dict[str, Any]) -> dict[str, Any]:
        if self.path is None:
            raise ValueError(f"persistent configuration requires {CONFIG_PATH_ENV}")
        if not isinstance(providers, dict):
            raise ValueError("providers must be an object")
        stored = self._stored()
        settings = stored.setdefault("providers", {})
        for name, values in providers.items():
            if name not in PROVIDER_FIELDS:
                raise ValueError(f"unsupported provider: {name}")
            if not isinstance(values, dict):
                raise ValueError(f"provider settings must be an object: {name}")
            unknown = set(values) - {"enabled", "url", "token", "clear_token"}
            if unknown:
                raise ValueError(
                    f"unsupported provider setting: {name}.{sorted(unknown)[0]}"
                )
            provider = settings.setdefault(name, {})
            url_key, _ = PROVIDER_FIELDS[name]
            if "enabled" in values:
                if not isinstance(values["enabled"], bool):
                    raise ValueError(f"{name}.enabled must be boolean")
                provider["enabled"] = values["enabled"]
            if "url" in values:
                url = values["url"]
                if not isinstance(url, str) or not url.strip():
                    raise ValueError(f"{name}.url must be non-empty text")
                provider[url_key] = url.strip().rstrip("/")
            if values.get("clear_token"):
                provider.pop("token", None)
            elif "token" in values:
                if not isinstance(values["token"], str):
                    raise ValueError(f"{name}.token must be text")
                if values["token"]:
                    provider["token"] = values["token"]
        self._write(stored)
        return self.public()

    def _write(self, value: dict[str, Any]) -> None:
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                yaml.safe_dump(value, stream, allow_unicode=True, sort_keys=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    return ConfigStore(path).load()
