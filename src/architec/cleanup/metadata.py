from __future__ import annotations

from typing import Any


def cleanup_metadata_fields(item: dict[str, Any]) -> dict[str, Any]:
    owner = str(item.get("owner", "") or "").strip()
    ttl_days = item.get("ttl_days")
    expires_at = str(item.get("expires_at", "") or "").strip()
    expired = bool(item.get("expired", False))
    metadata: dict[str, Any] = {}
    if owner:
        metadata["owner"] = owner
    try:
        ttl_value = int(ttl_days)
    except Exception:
        ttl_value = 0
    if ttl_value > 0:
        metadata["ttl_days"] = ttl_value
    if expires_at:
        metadata["expires_at"] = expires_at
        metadata["expired"] = expired
    return metadata


def cleanup_metadata_text(item: dict[str, Any]) -> str:
    metadata = cleanup_metadata_fields(item)
    parts: list[str] = []
    owner = str(metadata.get("owner", "") or "").strip()
    if owner:
        parts.append(f"owner={owner}")
    ttl_days = int(metadata.get("ttl_days", 0) or 0)
    if ttl_days > 0:
        parts.append(f"ttl={ttl_days}d")
    expires_at = str(metadata.get("expires_at", "") or "").strip()
    if expires_at:
        parts.append(f"expires_at={expires_at}")
    if bool(metadata.get("expired", False)):
        parts.append("expired")
    return " | ".join(parts)


__all__ = [
    "cleanup_metadata_fields",
    "cleanup_metadata_text",
]
