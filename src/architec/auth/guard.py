from __future__ import annotations

import os

from .client import fetch_public_key, refresh_lease
from .lease import is_expired, needs_refresh, save_public_key, verify_signature
from .store import load_session, save_session
from architec.version import current_cli_version


class ArchitecAuthRequiredError(RuntimeError):
    """Raised when a protected command is executed without valid auth."""


def auth_enforced() -> bool:
    disabled = str(os.environ.get("ARCHITEC_DISABLE_AUTH", "") or "").strip().lower()
    return disabled not in {"1", "true", "yes", "on"}


def _validate_session_shape(session: dict) -> None:
    refresh_token = str(session.get("refresh_token", "") or "").strip()
    install_id = str(session.get("install_id", "") or "").strip()
    lease = session.get("lease")
    if not refresh_token or not install_id or not isinstance(lease, dict):
        raise ArchitecAuthRequiredError("Architec auth session is missing. Run `archi login`.")


def require_authorized_session() -> dict:
    if not auth_enforced():
        return {}
    session = load_session()
    _validate_session_shape(session)
    session["client_version"] = current_cli_version()
    lease = dict(session.get("lease") or {})
    if not str(lease.get("signature", "") or "").strip():
        raise ArchitecAuthRequiredError("Architec auth lease signature missing. Run `archi login`.")
    try:
        if not verify_signature(lease):
            save_public_key(fetch_public_key())
    except Exception:
        save_public_key(fetch_public_key())
    expires_at = str(lease.get("expires_at", "") or "").strip()
    if not expires_at:
        raise ArchitecAuthRequiredError("Architec auth lease is missing expiry. Run `archi login` again.")
    if not verify_signature(lease):
        raise ArchitecAuthRequiredError("Architec auth lease signature is invalid. Run `archi login` again.")
    if needs_refresh(expires_at):
        refreshed = refresh_lease(
            refresh_token=str(session["refresh_token"]),
            install_id=str(session["install_id"]),
            app_version=current_cli_version(),
        )
        refreshed_lease = refreshed.get("lease")
        if not isinstance(refreshed_lease, dict) or not verify_signature(refreshed_lease):
            raise ArchitecAuthRequiredError("Architec auth refresh returned an invalid lease.")
        session["lease"] = refreshed_lease
        for key in ("cli_min_version", "latest_release_url", "latest_linux_x64_url", "latest_install_script_url"):
            if key in refreshed:
                session[key] = refreshed.get(key, "")
        save_session(session)
        lease = refreshed_lease
        expires_at = str(lease.get("expires_at", "") or "").strip()
    if is_expired(expires_at):
        raise ArchitecAuthRequiredError("Architec auth lease expired. Run `archi login`.")
    return session
