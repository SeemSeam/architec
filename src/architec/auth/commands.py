from __future__ import annotations

import argparse
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .client import auth_base_url, build_browser_login_url, exchange_code, fetch_public_key, remote_status
from .device import ensure_device
from .guard import ArchitecAuthRequiredError, auth_enforced, require_authorized_session
from .lease import save_public_key
from .store import clear_session, load_session, save_session
from architec.version import current_cli_version


AUTH_COMMANDS = {"login", "logout", "status", "whoami", "devices"}


def _build_auth_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archi", description="Architec auth commands")
    subparsers = parser.add_subparsers(dest="auth_command", required=True)

    login = subparsers.add_parser("login", help="authenticate this local install")
    login.add_argument("--auth-code", default="", help="exchange a pre-issued auth code directly")
    login.add_argument("--device-name", default="", help="override device display name")
    login.add_argument("--install-id", default="", help="override local install id")
    login.add_argument("--listen-host", default="127.0.0.1", help="callback host")
    login.add_argument("--listen-port", default=46319, type=int, help="callback port")
    login.add_argument("--no-browser", action="store_true", help="print URL instead of opening a browser")
    login.add_argument("--timeout", default=180, type=int, help="callback wait timeout in seconds")

    subparsers.add_parser("logout", help="clear the local auth session")
    status = subparsers.add_parser("status", help="show local auth session status")
    status.add_argument("--json", action="store_true", help="print raw status JSON")
    whoami = subparsers.add_parser("whoami", help="show the current authenticated account")
    whoami.add_argument("--json", action="store_true", help="print raw account JSON")
    devices = subparsers.add_parser("devices", help="show devices known to the remote portal")
    devices.add_argument("--json", action="store_true", help="print raw devices JSON")
    return parser


class _CallbackServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int]):
        super().__init__(server_address, _CallbackHandler)
        self.code: str = ""
        self.state: str = ""
        self.error: str = ""
        self.event = threading.Event()


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        query = parse_qs(parsed.query)
        self.server.code = str((query.get("code") or [""])[0] or "").strip()
        self.server.state = str((query.get("state") or [""])[0] or "").strip()
        self.server.error = str((query.get("error") or [""])[0] or "").strip()
        if self.server.error == "access_denied":
            body = (
                "<html><body><h1>Architec login canceled</h1>"
                "<p>The browser denied the authorization request. You can return to the terminal.</p></body></html>"
            ).encode("utf-8")
        else:
            body = (
                "<html><body><h1>Architec login complete</h1>"
                "<p>You can return to the terminal.</p></body></html>"
            ).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.server.event.set()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        del format, args


def _recommended_upgrade_command(payload: dict[str, Any]) -> str:
    install_script_url = str(payload.get("latest_install_script_url", "") or "").strip()
    if install_script_url:
        return f"curl -fsSL {install_script_url} -o install_prod.sh && bash install_prod.sh"
    linux_url = str(payload.get("latest_linux_x64_url", "") or "").strip()
    if linux_url:
        return f"Download and install the latest Linux build: {linux_url}"
    release_url = str(payload.get("latest_release_url", "") or "").strip()
    if release_url:
        return f"Open the latest release: {release_url}"
    return ""


def _build_upgrade_payload(payload: dict[str, Any]) -> dict[str, Any]:
    required = bool(payload.get("upgrade_required"))
    command = _recommended_upgrade_command(payload) if required else ""
    result = {
        "required": required,
        "action": "upgrade_cli" if required else "",
        "current_version": str(payload.get("client_version", current_cli_version()) or "").strip(),
        "minimum_version": str(payload.get("cli_min_version", "") or "").strip(),
        "detail": str(payload.get("version_detail", "") or "").strip(),
        "release_url": str(payload.get("latest_release_url", "") or "").strip(),
        "linux_x64_url": str(payload.get("latest_linux_x64_url", "") or "").strip(),
        "install_script_url": str(payload.get("latest_install_script_url", "") or "").strip(),
        "command": command,
    }
    if not required:
        result["action"] = ""
        result["detail"] = ""
        result["command"] = ""
    return result


def _apply_upgrade_guidance(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in ("cli_min_version", "latest_release_url", "latest_linux_x64_url", "latest_install_script_url"):
        value = source.get(key)
        if value not in (None, ""):
            target[key] = value
    if bool(source.get("upgrade_required")):
        target["action_required"] = "upgrade_cli"
        target["upgrade_required"] = True
        if source.get("version_detail"):
            target["version_detail"] = source.get("version_detail")
        command = _recommended_upgrade_command(source)
        if command:
            target["recommended_upgrade_command"] = command
    elif "upgrade_required" in source:
        target["upgrade_required"] = bool(source.get("upgrade_required"))
    target["upgrade"] = _build_upgrade_payload(target)


def _listen_server(host: str, port: int) -> _CallbackServer:
    try:
        return _CallbackServer((host, port))
    except OSError:
        return _CallbackServer((host, 0))


def _print_login_payload(payload: dict[str, Any]) -> None:
    lease = payload.get("lease", {})
    print("Architec login OK")
    print(f"Portal: {auth_base_url()}")
    print(f"CLI version: {payload.get('client_version', current_cli_version())}")
    print(f"Install ID: {payload.get('install_id', '')}")
    print(f"Device: {payload.get('device_name', '')}")
    if str(payload.get("cli_min_version", "") or "").strip():
        print(f"Minimum supported CLI: {payload.get('cli_min_version', '')}")
    if isinstance(lease, dict):
        print(f"Email: {lease.get('email', '')}")
        print(f"Plan: {lease.get('plan', '')}")
        print(f"Lease expires: {lease.get('expires_at', '')}")


def _cmd_login(args: argparse.Namespace) -> int:
    device = ensure_device(install_id=str(args.install_id or ""), device_name=str(args.device_name or ""))
    install_id = str(device["install_id"])
    device_name = str(device["device_name"])
    client_version = current_cli_version()
    auth_code = str(args.auth_code or "").strip()
    if not auth_code:
        state = f"state-{int(time.time())}-{install_id[:6]}"
        server = _listen_server(str(args.listen_host or "127.0.0.1"), int(args.listen_port or 46319))
        host, port = server.server_address
        redirect_uri = f"http://{host}:{port}/callback"
        login_url = build_browser_login_url(
            state=state,
            install_id=install_id,
            device_name=device_name,
            redirect_uri=redirect_uri,
            app_version=client_version,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"Open this URL to authorize the CLI:\n{login_url}")
        if not bool(args.no_browser):
            webbrowser.open(login_url)
        if not server.event.wait(timeout=max(1, int(args.timeout or 180))):
            server.shutdown()
            raise ArchitecAuthRequiredError("Timed out waiting for browser callback.")
        server.shutdown()
        if server.state != state:
            raise ArchitecAuthRequiredError("Browser callback state mismatch.")
        if server.error:
            if server.error == "access_denied":
                raise ArchitecAuthRequiredError("Browser authorization was denied.")
            raise ArchitecAuthRequiredError(f"Browser authorization failed: {server.error}")
        auth_code = str(server.code or "").strip()
        if not auth_code:
            raise ArchitecAuthRequiredError("Browser callback did not include an auth code.")
    exchanged = exchange_code(code=auth_code, install_id=install_id, app_version=client_version)
    public_key = fetch_public_key()
    save_public_key(public_key)
    session = {
        "portal_url": auth_base_url(),
        "install_id": install_id,
        "device_name": device_name,
        "client_version": client_version,
        "refresh_token": exchanged.get("refresh_token", ""),
        "refresh_token_expires_at": exchanged.get("refresh_token_expires_at", ""),
        "public_key_url": exchanged.get("public_key_url", "/api/public-key"),
        "cli_min_version": exchanged.get("cli_min_version", ""),
        "latest_release_url": exchanged.get("latest_release_url", ""),
        "latest_linux_x64_url": exchanged.get("latest_linux_x64_url", ""),
        "latest_install_script_url": exchanged.get("latest_install_script_url", ""),
        "lease": exchanged.get("lease", {}),
    }
    save_session(session)
    _print_login_payload(session)
    return 0


def _cmd_logout(args: argparse.Namespace) -> int:
    del args
    clear_session()
    print("Architec auth session cleared")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    session = load_session()
    client_version = current_cli_version()
    if not auth_enforced():
        payload = {"auth_enforced": False, "message": "Auth disabled by ARCHITEC_DISABLE_AUTH", "client_version": client_version}
    elif not session:
        payload = {"authenticated": False, "message": "No local auth session. Run `archi login`.", "client_version": client_version}
    else:
        payload = {"authenticated": True, "client_version": client_version, **session}
        _apply_upgrade_guidance(payload, payload)
        try:
            payload["remote"] = remote_status(
                refresh_token=str(session.get("refresh_token", "") or ""),
                install_id=str(session.get("install_id", "") or ""),
                app_version=client_version,
            )
            remote = payload["remote"]
            if isinstance(remote, dict):
                _apply_upgrade_guidance(payload, remote)
        except Exception as exc:
            payload["remote_error"] = str(exc)
        try:
            require_authorized_session()
            payload["lease_valid"] = True
        except Exception as exc:
            payload["lease_valid"] = False
            payload["lease_error"] = str(exc)
    if "upgrade" not in payload:
        payload["upgrade"] = _build_upgrade_payload(payload)
    if bool(args.json):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Architec auth status")
        for key in (
            "authenticated",
            "auth_enforced",
            "message",
            "client_version",
            "cli_min_version",
            "action_required",
            "install_id",
            "device_name",
            "refresh_token_expires_at",
            "lease_valid",
            "lease_error",
            "remote_error",
            "latest_release_url",
            "latest_install_script_url",
            "recommended_upgrade_command",
        ):
            if key in payload:
                print(f"{key}: {payload[key]}")
        upgrade = payload.get("upgrade")
        if isinstance(upgrade, dict):
            for key in ("required", "minimum_version", "install_script_url", "command"):
                if key in upgrade:
                    print(f"upgrade_{key}: {upgrade[key]}")
        lease = payload.get("lease")
        if isinstance(lease, dict):
            print(f"email: {lease.get('email', '')}")
            print(f"plan: {lease.get('plan', '')}")
            print(f"lease_expires_at: {lease.get('expires_at', '')}")
        remote = payload.get("remote")
        if isinstance(remote, dict):
            for key in ("client_version", "cli_min_version", "upgrade_required", "version_detail"):
                if key in remote:
                    print(f"remote_{key}: {remote[key]}")
    return 0


def _current_remote_payload() -> dict[str, Any]:
    session = require_authorized_session()
    return remote_status(
        refresh_token=str(session.get("refresh_token", "") or ""),
        install_id=str(session.get("install_id", "") or ""),
        app_version=current_cli_version(),
    )


def _cmd_whoami(args: argparse.Namespace) -> int:
    payload = _current_remote_payload()
    account = {
        "client_version": payload.get("client_version", current_cli_version()),
        "cli_min_version": payload.get("cli_min_version", ""),
        "upgrade_required": payload.get("upgrade_required", False),
        "action_required": "upgrade_cli" if bool(payload.get("upgrade_required")) else "",
        "version_detail": payload.get("version_detail", ""),
        "latest_release_url": payload.get("latest_release_url", ""),
        "latest_install_script_url": payload.get("latest_install_script_url", ""),
        "recommended_upgrade_command": _recommended_upgrade_command(payload) if bool(payload.get("upgrade_required")) else "",
        "email": payload.get("email", ""),
        "plan": payload.get("plan", ""),
        "seat_limit": payload.get("seat_limit", ""),
        "license_active": payload.get("license_active", False),
        "install_id": payload.get("install_id", ""),
        "device_name": payload.get("device_name", ""),
        "device_revoked": payload.get("device_revoked", False),
    }
    account["upgrade"] = _build_upgrade_payload(account)
    if bool(args.json):
        print(json.dumps(account, ensure_ascii=False, indent=2))
    else:
        print("Architec account")
        for key, value in account.items():
            if key == "upgrade":
                continue
            print(f"{key}: {value}")
        upgrade = account.get("upgrade")
        if isinstance(upgrade, dict):
            for key in ("required", "minimum_version", "install_script_url", "command"):
                print(f"upgrade_{key}: {upgrade.get(key, '')}")
    return 0


def _cmd_devices(args: argparse.Namespace) -> int:
    payload = _current_remote_payload()
    devices = payload.get("devices", [])
    if bool(args.json):
        print(json.dumps(devices, ensure_ascii=False, indent=2))
    else:
        print("Architec devices")
        for item in devices:
            if not isinstance(item, dict):
                continue
            print(
                f"- {item.get('install_id', '')} | {item.get('device_name', '')} | "
                f"status={'revoked' if item.get('revoked_at') else 'active'} | "
                f"last_seen={item.get('last_seen_at', '')}"
            )
    return 0


def handle_auth_command(argv: list[str]) -> int | None:
    if not argv:
        return None
    if argv[0] not in AUTH_COMMANDS:
        return None
    parser = _build_auth_parser()
    args = parser.parse_args(argv)
    if args.auth_command == "login":
        return _cmd_login(args)
    if args.auth_command == "logout":
        return _cmd_logout(args)
    if args.auth_command == "status":
        return _cmd_status(args)
    if args.auth_command == "whoami":
        return _cmd_whoami(args)
    if args.auth_command == "devices":
        return _cmd_devices(args)
    return None
