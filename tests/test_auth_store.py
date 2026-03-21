from __future__ import annotations

import os

from architec.auth.device import ensure_device
from architec.auth.lease import save_public_key
from architec.auth.store import auth_state_dir, load_session, save_session


def test_auth_session_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(tmp_path))

    save_session({"install_id": "install-demo", "refresh_token": "secret-token"})

    payload = load_session()

    assert payload["install_id"] == "install-demo"
    assert payload["refresh_token"] == "secret-token"


def test_auth_files_use_restricted_permissions_on_posix(monkeypatch, tmp_path):
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(tmp_path))

    save_session({"refresh_token": "secret-token"})
    ensure_device(install_id="install-demo", device_name="demo-device")
    save_public_key("-----BEGIN PUBLIC KEY-----\ndemo\n-----END PUBLIC KEY-----")

    auth_dir = auth_state_dir()
    if os.name == "posix":
        assert auth_dir.stat().st_mode & 0o777 == 0o700
        assert (auth_dir / "session.json").stat().st_mode & 0o777 == 0o600
        assert (auth_dir / "device.json").stat().st_mode & 0o777 == 0o600
        assert (auth_dir / "portal-public-key.pem").stat().st_mode & 0o777 == 0o600
