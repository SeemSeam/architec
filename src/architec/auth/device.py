from __future__ import annotations

import socket
import uuid
from pathlib import Path

from architec.support.io_utils import read_json, write_json
from .store import ensure_auth_state_dir, protect_auth_file


def auth_state_dir() -> Path:
    return ensure_auth_state_dir()


def device_file() -> Path:
    return auth_state_dir() / "device.json"


def load_device() -> dict[str, str]:
    return read_json(device_file(), {})


def ensure_device(*, install_id: str = "", device_name: str = "") -> dict[str, str]:
    current = load_device()
    current_install_id = str(current.get("install_id", "") or "").strip()
    current_device_name = str(current.get("device_name", "") or "").strip()
    resolved_install_id = str(install_id or current_install_id or f"install-{uuid.uuid4().hex[:16]}").strip()
    resolved_device_name = str(device_name or current_device_name or socket.gethostname() or "Architec Device").strip()
    payload = {
        "install_id": resolved_install_id,
        "device_name": resolved_device_name,
    }
    path = device_file()
    write_json(path, payload)
    protect_auth_file(path)
    return payload
