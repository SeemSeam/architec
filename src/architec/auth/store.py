from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from architec.integration.resource_paths import user_config_dir
from architec.support.io_utils import read_json, write_json

_AUTH_DIR_MODE = 0o700
_AUTH_FILE_MODE = 0o600


def auth_state_dir() -> Path:
    return user_config_dir() / "auth"


def _apply_mode(path: Path, mode: int) -> None:
    if os.name != "posix":
        return
    try:
        path.chmod(mode)
    except OSError:
        return


def ensure_auth_state_dir() -> Path:
    path = auth_state_dir()
    path.mkdir(parents=True, exist_ok=True)
    _apply_mode(path, _AUTH_DIR_MODE)
    return path


def protect_auth_file(path: Path) -> Path:
    _apply_mode(path, _AUTH_FILE_MODE)
    return path


def session_file() -> Path:
    return ensure_auth_state_dir() / "session.json"


def public_key_file() -> Path:
    return ensure_auth_state_dir() / "portal-public-key.pem"


def auth_preferences_file() -> Path:
    return ensure_auth_state_dir() / "preferences.json"


def load_session() -> dict[str, Any]:
    ensure_auth_state_dir()
    payload = read_json(session_file(), {})
    return payload if isinstance(payload, dict) else {}


def save_session(payload: dict[str, Any]) -> None:
    path = session_file()
    write_json(path, payload)
    protect_auth_file(path)


def load_auth_preferences() -> dict[str, Any]:
    ensure_auth_state_dir()
    payload = read_json(auth_preferences_file(), {})
    return payload if isinstance(payload, dict) else {}


def save_auth_preferences(payload: dict[str, Any]) -> None:
    path = auth_preferences_file()
    write_json(path, payload)
    protect_auth_file(path)


def clear_session() -> None:
    path = session_file()
    if path.exists():
        path.unlink()
