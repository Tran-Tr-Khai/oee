from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PACKAGE_ROOT.parent
PROJECT_ROOT = SRC_ROOT.parent

DEFAULT_CONFIG = PROJECT_ROOT / "config.yaml"
DEFAULT_STATE = PROJECT_ROOT / "state.json"
DEFAULT_LOG = PROJECT_ROOT / "logs" / "download.log"


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not isinstance(config.get("rules"), dict):
        raise ValueError("config.yaml must have a 'rules' section.")

    return config


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logging.warning("state.json is invalid. Use empty state.")
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def resolve_output_root(project_root: Path, config: dict[str, Any]) -> Path:
    output_root = Path(config.get("output_root", "data/raw"))
    if output_root.is_absolute():
        return output_root
    return project_root / output_root
