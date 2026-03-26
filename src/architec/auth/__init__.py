__all__ = [
    "auto_login",
    "handle_auth_command",
    "require_authorized_session",
]


def __getattr__(name: str):
    if name == "auto_login":
        from .commands import auto_login

        return auto_login
    if name == "handle_auth_command":
        from .commands import handle_auth_command

        return handle_auth_command
    if name == "require_authorized_session":
        from .guard import require_authorized_session

        return require_authorized_session
    raise AttributeError(f"module 'architec.auth' has no attribute {name!r}")
