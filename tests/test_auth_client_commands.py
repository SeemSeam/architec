from __future__ import annotations

import base64
import json
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from architec.auth import client, commands, guard


def test_build_browser_login_url_includes_local_cli_version(monkeypatch):
    monkeypatch.setattr(client, "current_cli_version", lambda: "0.1.0")

    url = client.build_browser_login_url(
        state="demo-state",
        install_id="install-demo",
        device_name="Demo Device",
        redirect_uri="http://127.0.0.1:46319/callback",
    )

    assert "app_version=0.1.0" in url
    assert "install_id=install-demo" in url


def test_exchange_code_surfaces_upgrade_download_url(monkeypatch):
    def fake_urlopen(req, timeout=15.0):
        del timeout
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["app_version"] == "0.0.9"
        raise HTTPError(
            req.full_url,
            426,
            "Upgrade Required",
            hdrs=None,
            fp=BytesIO(
                json.dumps(
                    {
                        "detail": "CLI 0.0.9 is below minimum supported version 0.1.0. Upgrade required.",
                        "upgrade_required": True,
                        "cli_min_version": "0.1.0",
                        "client_version": "0.0.9",
                        "latest_install_script_url": "https://example.com/install_prod.sh",
                        "latest_linux_x64_url": "https://example.com/archi-linux-x86_64.tar.gz",
                    }
                ).encode("utf-8")
            ),
        )

    monkeypatch.setattr(client, "urlopen", fake_urlopen)

    with pytest.raises(client.ArchitecAuthClientError) as exc:
        client.exchange_code(code="issued-code", install_id="install-demo", app_version="0.0.9")

    message = str(exc.value)
    assert "Upgrade required" in message
    assert "https://example.com/install_prod.sh" in message
    assert "bash install_prod.sh" in message


def test_cmd_login_saves_version_gate_metadata(monkeypatch, capsys):
    saved_session: dict[str, object] = {}

    monkeypatch.setattr(commands, "current_cli_version", lambda: "0.1.0")
    monkeypatch.setattr(commands.time, "time", lambda: 1234567890)
    monkeypatch.setattr(
        commands,
        "ensure_device",
        lambda *, install_id, device_name: {
            "install_id": install_id or "install-demo",
            "device_name": device_name or "Demo Device",
        },
    )

    def fake_exchange_code(*, code, install_id, app_version):
        assert code == "issued-code"
        assert install_id == "install-demo"
        assert app_version == "0.1.0"
        return {
            "refresh_token": "refresh-token",
            "refresh_token_expires_at": "2099-01-01T00:00:00+00:00",
            "public_key_url": "/api/cli/public-key",
            "cli_min_version": "0.1.0",
            "latest_release_url": "https://example.com/releases/latest",
            "latest_linux_x64_url": "https://example.com/archi-linux-x86_64.tar.gz",
            "latest_install_script_url": "https://example.com/install_prod.sh",
            "lease": {
                "email": "demo@example.com",
                "plan": "standard",
                "expires_at": "2099-01-02T00:00:00+00:00",
                "signature": "signed-lease",
            },
        }

    monkeypatch.setattr(commands, "exchange_code", fake_exchange_code)
    monkeypatch.setattr(commands, "fetch_public_key", lambda: "-----BEGIN PUBLIC KEY-----\ndemo\n-----END PUBLIC KEY-----")
    monkeypatch.setattr(commands, "save_public_key", lambda pem: pem)
    monkeypatch.setattr(commands, "save_session", lambda payload: saved_session.update(payload))
    args = SimpleNamespace(
        auth_code="issued-code",
        device_name="",
        install_id="",
        listen_host="127.0.0.1",
        listen_port=46319,
        no_browser=True,
        timeout=30,
    )

    assert commands._cmd_login(args) == 0

    assert saved_session["client_version"] == "0.1.0"
    assert saved_session["cli_min_version"] == "0.1.0"
    assert saved_session["latest_release_url"] == "https://example.com/releases/latest"
    assert saved_session["latest_linux_x64_url"] == "https://example.com/archi-linux-x86_64.tar.gz"
    assert saved_session["latest_install_script_url"] == "https://example.com/install_prod.sh"

    out = capsys.readouterr().out
    assert "CLI version: 0.1.0" in out
    assert "Minimum supported CLI: 0.1.0" in out


def test_cmd_login_waits_for_browser_callback_without_manual_code_prompt(monkeypatch, capsys):
    saved_session: dict[str, object] = {}
    opened_urls: list[str] = []
    observed_exchange: dict[str, str] = {}

    monkeypatch.setattr(commands, "current_cli_version", lambda: "0.1.0")
    monkeypatch.setattr(commands.time, "time", lambda: 1234567890)
    monkeypatch.setattr(
        commands,
        "ensure_device",
        lambda *, install_id, device_name: {
            "install_id": install_id or "install-demo",
            "device_name": device_name or "Demo Device",
        },
    )
    class FakeEvent:
        def wait(self, timeout):
            assert timeout == 30
            return True

    class FakeServer:
        def __init__(self):
            self.server_address = ("127.0.0.1", 46319)
            self.event = FakeEvent()
            self.code = "issued-code"
            self.state = "state-1234567890-instal"
            self.error = ""
            self.shutdown_called = False

        def serve_forever(self):
            return None

        def shutdown(self):
            self.shutdown_called = True

    fake_server = FakeServer()

    class FakeThread:
        def __init__(self, *, target, daemon):
            self.target = target
            self.daemon = daemon
            self.started = False

        def start(self):
            self.started = True

    monkeypatch.setattr(commands, "_listen_server", lambda host, port: fake_server)
    monkeypatch.setattr(commands, "build_browser_login_url", lambda **kwargs: opened_urls.append(kwargs["redirect_uri"]) or "https://www.architec.top/cli/login?demo")
    monkeypatch.setattr(commands.threading, "Thread", FakeThread)
    monkeypatch.setattr(commands.webbrowser, "open", lambda url: opened_urls.append(url) or True)
    monkeypatch.setattr(
        commands,
        "exchange_code",
        lambda *, code, install_id, app_version: observed_exchange.update(
            {"code": code, "install_id": install_id, "app_version": app_version}
        ) or {
            "refresh_token": "refresh-token",
            "refresh_token_expires_at": "2099-01-01T00:00:00+00:00",
            "public_key_url": "/api/cli/public-key",
            "cli_min_version": "0.1.0",
            "latest_release_url": "https://example.com/releases/latest",
            "latest_linux_x64_url": "https://example.com/archi-linux-x86_64.tar.gz",
            "latest_install_script_url": "https://example.com/install_prod.sh",
            "lease": {
                "email": "demo@example.com",
                "plan": "standard",
                "expires_at": "2099-01-02T00:00:00+00:00",
                "signature": "signed-lease",
            },
        },
    )
    monkeypatch.setattr(commands, "fetch_public_key", lambda: "pem")
    monkeypatch.setattr(commands, "save_public_key", lambda pem: pem)
    monkeypatch.setattr(commands, "save_session", lambda payload: saved_session.update(payload))

    args = SimpleNamespace(
        auth_code="",
        device_name="",
        install_id="",
        listen_host="127.0.0.1",
        listen_port=46319,
        no_browser=True,
        timeout=30,
    )

    assert commands._cmd_login(args) == 0
    assert saved_session["install_id"] == "install-demo"
    assert observed_exchange == {
        "code": "issued-code",
        "install_id": "install-demo",
        "app_version": "0.1.0",
    }
    assert fake_server.shutdown_called is True
    assert "http://127.0.0.1:46319/callback" in opened_urls
    out = capsys.readouterr().out
    assert "Architec login OK" in out
    assert "Install ID: install-demo" in out
    assert "Device: Demo Device" in out


def test_cmd_login_accepts_self_contained_activation_code(monkeypatch, capsys):
    saved_session: dict[str, object] = {}
    saved_public_key: list[str] = []

    monkeypatch.setattr(commands, "current_cli_version", lambda: "0.1.0")
    monkeypatch.setattr(
        commands,
        "ensure_device",
        lambda *, install_id, device_name: {
            "install_id": install_id or "install-demo",
            "device_name": device_name or "Demo Device",
        },
    )
    monkeypatch.setattr(commands, "trusted_public_key_pem", lambda: "-----BEGIN PUBLIC KEY-----\ndemo\n-----END PUBLIC KEY-----")
    monkeypatch.setattr(commands, "save_public_key", lambda pem: saved_public_key.append(pem))
    monkeypatch.setattr(commands, "save_session", lambda payload: saved_session.update(payload))
    monkeypatch.setattr(
        commands,
        "verify_signature",
        lambda payload: str(payload.get("signature", "") or "") in {"bundle-signature", "lease-signature"},
    )

    payload = {
        "kind": "architec-offline-activation",
        "version": 1,
        "activation_expires_at": "2099-01-01T00:00:00+00:00",
        "install_id": "install-demo",
        "device_name": "Demo Device",
        "refresh_token": "refresh-token",
        "refresh_token_expires_at": "2099-02-01T00:00:00+00:00",
        "public_key_url": "/api/cli/public-key",
        "cli_min_version": "0.1.0",
        "client_version": "0.1.0",
        "latest_release_url": "https://example.com/releases/latest",
        "latest_linux_x64_url": "https://example.com/archi-linux-x86_64.tar.gz",
        "latest_install_script_url": "https://example.com/install_prod.sh",
        "lease": {
            "email": "demo@example.com",
            "plan": "standard",
            "expires_at": "2099-01-02T00:00:00+00:00",
            "signature": "lease-signature",
        },
        "signature": "bundle-signature",
    }
    auth_code = "archi_act_" + base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")

    args = SimpleNamespace(
        auth_code=auth_code,
        device_name="",
        install_id="",
        listen_host="127.0.0.1",
        listen_port=46319,
        no_browser=True,
        timeout=30,
    )

    assert commands._cmd_login(args) == 0
    assert saved_session["refresh_token"] == "refresh-token"
    assert saved_session["install_id"] == "install-demo"
    assert saved_public_key == ["-----BEGIN PUBLIC KEY-----\ndemo\n-----END PUBLIC KEY-----"]

    out = capsys.readouterr().out
    assert "Architec login OK" in out
    assert "Email: demo@example.com" in out


def test_cmd_login_raises_when_browser_callback_times_out(monkeypatch):
    monkeypatch.setattr(commands, "current_cli_version", lambda: "0.1.0")
    monkeypatch.setattr(
        commands,
        "ensure_device",
        lambda *, install_id, device_name: {
            "install_id": install_id or "install-demo",
            "device_name": device_name or "Demo Device",
        },
    )

    class FakeEvent:
        def wait(self, timeout):
            assert timeout == 5
            return False

    class FakeServer:
        def __init__(self):
            self.server_address = ("127.0.0.1", 46319)
            self.event = FakeEvent()
            self.code = ""
            self.state = ""
            self.error = ""
            self.shutdown_called = False

        def serve_forever(self):
            return None

        def shutdown(self):
            self.shutdown_called = True

    fake_server = FakeServer()

    class FakeThread:
        def __init__(self, *, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            return None

    monkeypatch.setattr(commands, "_listen_server", lambda host, port: fake_server)
    monkeypatch.setattr(commands, "build_browser_login_url", lambda **kwargs: "https://www.architec.top/cli/login?demo")
    monkeypatch.setattr(commands.threading, "Thread", FakeThread)
    monkeypatch.setattr(commands.webbrowser, "open", lambda url: True)

    args = SimpleNamespace(
        auth_code="",
        device_name="",
        install_id="",
        listen_host="127.0.0.1",
        listen_port=46319,
        no_browser=False,
        timeout=5,
    )

    with pytest.raises(commands.ArchitecAuthRequiredError, match="Timed out waiting for browser callback. Run `archi login` again."):
        commands._cmd_login(args)

    assert fake_server.shutdown_called is True


def test_require_authorized_session_refresh_passes_cli_version(monkeypatch):
    saved_session: dict[str, object] = {}

    monkeypatch.setattr(guard, "auth_enforced", lambda: True)
    monkeypatch.setattr(
        guard,
        "load_session",
        lambda: {
            "refresh_token": "refresh-token",
            "install_id": "install-demo",
            "lease": {"signature": "signed", "expires_at": "2000-01-01T00:00:00+00:00"},
        },
    )
    monkeypatch.setattr(guard, "current_cli_version", lambda: "0.1.0")
    monkeypatch.setattr(guard, "verify_signature", lambda payload: True)
    monkeypatch.setattr(guard, "needs_refresh", lambda value: True)
    monkeypatch.setattr(guard, "is_expired", lambda value: False)
    monkeypatch.setattr(guard, "fetch_public_key", lambda: "pem")
    monkeypatch.setattr(guard, "save_public_key", lambda pem: pem)

    def fake_refresh_lease(*, refresh_token, install_id, app_version):
        assert refresh_token == "refresh-token"
        assert install_id == "install-demo"
        assert app_version == "0.1.0"
        return {
            "cli_min_version": "0.1.0",
            "latest_release_url": "https://example.com/releases/latest",
            "latest_linux_x64_url": "https://example.com/archi-linux-x86_64.tar.gz",
            "latest_install_script_url": "https://example.com/install_prod.sh",
            "lease": {
                "signature": "refreshed-signature",
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
        }

    monkeypatch.setattr(guard, "refresh_lease", fake_refresh_lease)
    monkeypatch.setattr(guard, "save_session", lambda payload: saved_session.update(payload))

    session = guard.require_authorized_session()

    assert session["client_version"] == "0.1.0"
    assert session["cli_min_version"] == "0.1.0"
    assert session["latest_release_url"] == "https://example.com/releases/latest"
    assert session["latest_install_script_url"] == "https://example.com/install_prod.sh"
    assert saved_session["lease"]["signature"] == "refreshed-signature"


def test_cmd_whoami_uses_current_cli_version_for_remote_status(monkeypatch, capsys):
    monkeypatch.setattr(commands, "current_cli_version", lambda: "0.1.0")
    monkeypatch.setattr(commands, "require_authorized_session", lambda: {"refresh_token": "token", "install_id": "install-demo"})

    def fake_remote_status(*, refresh_token, install_id, app_version):
        assert refresh_token == "token"
        assert install_id == "install-demo"
        assert app_version == "0.1.0"
        return {
            "client_version": "0.1.0",
            "cli_min_version": "0.2.0",
            "upgrade_required": True,
            "version_detail": "CLI 0.1.0 is below minimum supported version 0.2.0. Upgrade required.",
            "latest_release_url": "https://example.com/releases/latest",
            "latest_install_script_url": "https://example.com/install_prod.sh",
            "email": "demo@example.com",
            "plan": "standard",
            "seat_limit": 3,
            "license_active": True,
            "install_id": "install-demo",
            "device_name": "Demo Device",
            "device_revoked": False,
        }

    monkeypatch.setattr(commands, "remote_status", fake_remote_status)

    assert commands._cmd_whoami(SimpleNamespace(json=False)) == 0

    out = capsys.readouterr().out
    assert "client_version: 0.1.0" in out
    assert "cli_min_version: 0.2.0" in out
    assert "action_required: upgrade_cli" in out
    assert "recommended_upgrade_command: curl -fsSL https://example.com/install_prod.sh -o install_prod.sh && bash install_prod.sh" in out
    assert "upgrade_required: True" in out
    assert "upgrade_minimum_version: 0.2.0" in out
    assert "upgrade_install_script_url: https://example.com/install_prod.sh" in out
    assert "email: demo@example.com" in out


def test_cmd_status_surfaces_upgrade_guidance_in_json(monkeypatch, capsys):
    monkeypatch.setattr(commands, "current_cli_version", lambda: "0.1.0")
    monkeypatch.setattr(
        commands,
        "load_session",
        lambda: {
            "refresh_token": "token",
            "install_id": "install-demo",
            "device_name": "Demo Device",
            "latest_release_url": "https://example.com/releases/latest",
        },
    )
    monkeypatch.setattr(commands, "auth_enforced", lambda: True)
    monkeypatch.setattr(
        commands,
        "remote_status",
        lambda *, refresh_token, install_id, app_version: {
            "client_version": app_version,
            "cli_min_version": "0.2.0",
            "upgrade_required": True,
            "version_detail": "CLI 0.1.0 is below minimum supported version 0.2.0. Upgrade required.",
            "latest_release_url": "https://example.com/releases/latest",
            "latest_install_script_url": "https://example.com/install_prod.sh",
        },
    )
    monkeypatch.setattr(commands, "require_authorized_session", lambda: {"ok": True})

    assert commands._cmd_status(SimpleNamespace(json=True)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["action_required"] == "upgrade_cli"
    assert payload["cli_min_version"] == "0.2.0"
    assert payload["latest_install_script_url"] == "https://example.com/install_prod.sh"
    assert payload["recommended_upgrade_command"] == "curl -fsSL https://example.com/install_prod.sh -o install_prod.sh && bash install_prod.sh"
    assert payload["upgrade"] == {
        "required": True,
        "action": "upgrade_cli",
        "current_version": "0.1.0",
        "minimum_version": "0.2.0",
        "detail": "CLI 0.1.0 is below minimum supported version 0.2.0. Upgrade required.",
        "release_url": "https://example.com/releases/latest",
        "linux_x64_url": "",
        "install_script_url": "https://example.com/install_prod.sh",
        "command": "curl -fsSL https://example.com/install_prod.sh -o install_prod.sh && bash install_prod.sh",
    }


def test_cmd_status_json_includes_empty_upgrade_object_when_no_upgrade_needed(monkeypatch, capsys):
    monkeypatch.setattr(commands, "current_cli_version", lambda: "0.2.0")
    monkeypatch.setattr(commands, "auth_enforced", lambda: False)

    assert commands._cmd_status(SimpleNamespace(json=True)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["client_version"] == "0.2.0"
    assert payload["upgrade"] == {
        "required": False,
        "action": "",
        "current_version": "0.2.0",
        "minimum_version": "",
        "detail": "",
        "release_url": "",
        "linux_x64_url": "",
        "install_script_url": "",
        "command": "",
    }
