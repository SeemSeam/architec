from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from architec.version import current_cli_version


DEFAULT_AUTH_BASE_URL = "https://www.architec.top"


class ArchitecAuthClientError(RuntimeError):
    """Raised when the auth portal rejects or cannot fulfill a request."""


def auth_base_url() -> str:
    return str(os.environ.get("ARCHITEC_AUTH_BASE_URL", DEFAULT_AUTH_BASE_URL) or DEFAULT_AUTH_BASE_URL).strip().rstrip("/")


def auth_api_base_url() -> str:
    override = str(os.environ.get("ARCHITEC_AUTH_API_BASE_URL", "") or "").strip().rstrip("/")
    return override or auth_base_url()


def build_browser_login_url(
    *,
    state: str,
    install_id: str,
    device_name: str,
    redirect_uri: str,
    app_version: str | None = None,
) -> str:
    params = urlencode(
        {
            "state": state,
            "install_id": install_id,
            "device_name": device_name,
            "redirect_uri": redirect_uri,
            "app_version": str(app_version or current_cli_version()).strip(),
        }
    )
    return f"{auth_base_url()}/cli/login?{params}"


def _render_portal_error(*, detail: str, payload: dict[str, Any] | None = None) -> str:
    message = str(detail or "Auth portal rejected the request.").strip()
    if not isinstance(payload, dict):
        return message
    latest_install_script = str(payload.get("latest_install_script_url", "") or "").strip()
    latest_linux = str(payload.get("latest_linux_x64_url", "") or "").strip()
    latest_release = str(payload.get("latest_release_url", "") or "").strip()
    if bool(payload.get("upgrade_required")):
        if latest_install_script:
            return (
                f"{message} Run: curl -fsSL {latest_install_script} -o install_prod.sh && "
                "bash install_prod.sh"
            )
        if latest_linux:
            return f"{message} Download the current Linux build: {latest_linux}"
        if latest_release:
            return f"{message} Open the latest release: {latest_release}"
    return message


def _json_request(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=15.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.reason
        error_payload: dict[str, Any] | None = None
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            if isinstance(error_payload, dict):
                detail = error_payload.get("detail", detail)
        except Exception:
            pass
        rendered = _render_portal_error(detail=str(detail), payload=error_payload)
        raise ArchitecAuthClientError(f"Auth portal rejected the request: {rendered}") from exc
    except URLError as exc:
        raise ArchitecAuthClientError(f"Cannot reach auth portal at {auth_base_url()}: {exc.reason}") from exc


def exchange_code(*, code: str, install_id: str, app_version: str | None = None) -> dict[str, Any]:
    return _json_request(
        f"{auth_api_base_url()}/api/cli/login/exchange",
        {"code": code, "install_id": install_id, "app_version": str(app_version or current_cli_version()).strip()},
    )


def refresh_lease(*, refresh_token: str, install_id: str, app_version: str | None = None) -> dict[str, Any]:
    return _json_request(
        f"{auth_api_base_url()}/api/cli/lease/refresh",
        {
            "refresh_token": refresh_token,
            "install_id": install_id,
            "app_version": str(app_version or current_cli_version()).strip(),
        },
    )


def remote_status(*, refresh_token: str, install_id: str, app_version: str | None = None) -> dict[str, Any]:
    params = urlencode(
        {
            "refresh_token": refresh_token,
            "install_id": install_id,
            "app_version": str(app_version or current_cli_version()).strip(),
        }
    )
    try:
        with urlopen(f"{auth_api_base_url()}/api/cli/status?{params}", timeout=15.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.reason
        error_payload: dict[str, Any] | None = None
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            if isinstance(error_payload, dict):
                detail = error_payload.get("detail", detail)
        except Exception:
            pass
        rendered = _render_portal_error(detail=str(detail), payload=error_payload)
        raise ArchitecAuthClientError(f"Auth portal rejected the request: {rendered}") from exc
    except URLError as exc:
        raise ArchitecAuthClientError(f"Cannot reach auth portal at {auth_api_base_url()}: {exc.reason}") from exc


def fetch_public_key() -> str:
    try:
        with urlopen(f"{auth_api_base_url()}/api/public-key", timeout=15.0) as response:
            return response.read().decode("utf-8")
    except URLError as exc:
        raise ArchitecAuthClientError(f"Cannot reach auth portal at {auth_api_base_url()}: {exc.reason}") from exc
