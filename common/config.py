"""Load config.yaml once and give every module the same settings."""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict:
    """Read config.yaml (or another file) and apply optional overrides."""
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    return _merge(cfg, overrides or {})


def resolve(path: str | Path) -> Path:
    """Turn a path from config.yaml (relative to the project root) into an absolute path."""
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p
