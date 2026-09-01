"""Configuration loading for the AI Content Automation System.

Precedence (lowest to highest):
  1. config/config.yaml  (project defaults committed to git)
  2. config/.env          (local secrets / overrides, gitignored)
  3. process environment variables

Environment variable names are derived from config keys in SCREAMING_SNAKE
form using the full dotted path, e.g. ``pipeline.script_provider`` maps to
``PIPELINE_SCRIPT_PROVIDER``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"
ENV_FILE = PROJECT_ROOT / "config" / ".env"

_CACHE: dict[str, Any] | None = None
_CACHE_PATH: Path | None = None


def _load_env_files() -> None:
    for candidate in (ENV_FILE, PROJECT_ROOT / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)


def _env_name(path: tuple[str, ...]) -> str:
    return "_".join(path).upper()


def _apply_env_overrides(node: dict[str, Any], path: tuple[str, ...] = ()) -> None:
    for key, value in list(node.items()):
        child_path = path + (key,)
        if isinstance(value, dict):
            _apply_env_overrides(value, child_path)
            continue
        override = os.environ.get(_env_name(child_path))
        if override is None:
            continue
        if isinstance(value, bool):
            node[key] = override.strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(value, int):
            node[key] = int(override)
        elif isinstance(value, float):
            node[key] = float(override)
        else:
            node[key] = override


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load the effective configuration as a nested dict."""
    global _CACHE, _CACHE_PATH
    _load_env_files()
    cfg_file = path or CONFIG_FILE
    if cfg_file.exists():
        with open(cfg_file, encoding="utf-8") as fh:
            defaults = yaml.safe_load(fh) or {}
    else:
        logger.warning("Config file not found at %s; using defaults.", cfg_file)
        defaults = {}
    _apply_env_overrides(defaults)
    _CACHE = defaults
    _CACHE_PATH = cfg_file
    return defaults


def get_config(path: Path | None = None) -> dict[str, Any]:
    """Return the effective configuration (cached per source file).

    An explicit ``path`` reloads only when it differs from the cached source.
    """
    global _CACHE
    if path is not None and (
        _CACHE is None or _CACHE_PATH is None or _CACHE_PATH.resolve() != path.resolve()
    ):
        return load_config(path)
    if _CACHE is None:
        return load_config()
    return _CACHE


def reload_config() -> dict[str, Any]:
    """Clear the cached configuration and reload it (used in tests)."""
    return load_config()