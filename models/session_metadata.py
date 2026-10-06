"""Portable UUID and UTC timestamp validation for local session records."""
from datetime import datetime, timezone, timedelta
from uuid import UUID


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def validate_session_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("session_id must be a canonical UUID string")
    try:
        canonical = str(UUID(value))
    except ValueError as exc:
        raise ValueError("session_id must be a canonical UUID string") from exc
    if value != canonical:
        raise ValueError("session_id must be a canonical UUID string")
    return value


def parse_timestamp(value: str, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO 8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO 8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an ISO 8601 UTC timestamp")
    return parsed


def next_timestamp(previous: str) -> str:
    return max(datetime.now(timezone.utc), parse_timestamp(previous, "updated_at")).isoformat(timespec="microseconds")
