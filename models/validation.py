"""Strict boundary validation shared by AI response schemas."""
from typing import Any


def required(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def strings(values: list[str], name: str, *, nonempty: bool = False) -> None:
    if not isinstance(values, list):
        raise ValueError(f"{name} must be a list of strings")
    if nonempty and not values:
        raise ValueError(f"{name} must contain at least one entry")
    for index, value in enumerate(values):
        required(value, f"{name}[{index}]")


def object_fields(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    missing = fields - value.keys()
    extra = value.keys() - fields
    if missing:
        raise ValueError(f"{name}: missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"{name}: unknown fields: {', '.join(sorted(extra))}")
    return value
