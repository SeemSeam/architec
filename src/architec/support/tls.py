from __future__ import annotations

import os
import ssl
from pathlib import Path

import certifi


def _env_override_present() -> bool:
    return bool(str(os.environ.get("SSL_CERT_FILE", "") or "").strip()) or bool(
        str(os.environ.get("SSL_CERT_DIR", "") or "").strip()
    )


def _default_verify_paths_usable() -> bool:
    paths = ssl.get_default_verify_paths()
    cafile = str(getattr(paths, "cafile", "") or "").strip()
    capath = str(getattr(paths, "capath", "") or "").strip()
    if cafile and Path(cafile).is_file():
        return True
    if capath and Path(capath).is_dir():
        return True
    return False


def _certifi_cafile() -> str:
    cafile = str(certifi.where() or "").strip()
    if cafile and Path(cafile).is_file():
        return cafile
    return ""


def ensure_default_ca_bundle_env() -> str:
    if _env_override_present():
        return str(os.environ.get("SSL_CERT_FILE", "") or "").strip()
    if _default_verify_paths_usable():
        return ""
    cafile = _certifi_cafile()
    if cafile:
        os.environ["SSL_CERT_FILE"] = cafile
    return cafile
