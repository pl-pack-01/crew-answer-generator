"""Application configuration. Persists path settings to a JSON file."""

from __future__ import annotations

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_CONFIG_PATH = _PROJECT_ROOT / ".streamlit" / "app_config.json"

_DEFAULTS = {
    "data_dir": str(_PROJECT_ROOT / "data"),
    "db_filename": "crew.db",
    "upload_dirname": "uploads",
}

_config: dict | None = None


def _load() -> dict:
    global _config
    if _config is not None:
        return _config

    if _CONFIG_PATH.exists():
        try:
            _config = {**_DEFAULTS, **json.loads(_CONFIG_PATH.read_text())}
        except (json.JSONDecodeError, OSError):
            _config = dict(_DEFAULTS)
    else:
        _config = dict(_DEFAULTS)
    return _config


def get(key: str) -> str:
    return _load()[key]


def get_data_dir() -> Path:
    return Path(get("data_dir"))


def get_db_path() -> Path:
    return get_data_dir() / get("db_filename")


def get_upload_dir() -> Path:
    return get_data_dir() / get("upload_dirname")


def save(updates: dict) -> None:
    """Save configuration updates to disk."""
    global _config
    cfg = _load()
    cfg.update(updates)
    _config = cfg

    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def reload() -> dict:
    """Force reload from disk."""
    global _config
    _config = None
    return _load()
