from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .store import protect_auth_file, public_key_file


DEFAULT_AUTH_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA6gXuA7nAVituR/dy4vGHjoBOm8Cb+jwIxDwzDf0TRoA=
-----END PUBLIC KEY-----"""


def save_public_key(pem_text: str) -> Path:
    path = public_key_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pem_text or "").strip() + "\n", encoding="utf-8")
    return protect_auth_file(path)


def trusted_public_key_pem() -> str:
    override = str(os.environ.get("ARCHITEC_AUTH_PUBLIC_KEY_PEM", "") or "").strip()
    if override:
        return override
    path = public_key_file()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return DEFAULT_AUTH_PUBLIC_KEY_PEM


def load_public_key() -> Ed25519PublicKey:
    pem = trusted_public_key_pem().encode("utf-8")
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise RuntimeError("Unsupported portal public key type")
    return key


def parse_iso(value: str) -> datetime:
    normalized = str(value or "").strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_expired(value: str) -> bool:
    return parse_iso(value) <= utc_now()


def needs_refresh(value: str, *, within_seconds: int = 300) -> bool:
    return parse_iso(value) <= utc_now() + timedelta(seconds=max(0, int(within_seconds)))


def verify_signature(payload: dict[str, Any]) -> bool:
    signature = str(payload.get("signature", "") or "").strip()
    if not signature:
        return False
    body = {key: value for key, value in payload.items() if key != "signature"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    padded = signature + "=" * (-len(signature) % 4)
    try:
        signature_bytes = base64.urlsafe_b64decode(padded.encode("utf-8"))
        load_public_key().verify(signature_bytes, blob)
    except Exception:
        return False
    return True
