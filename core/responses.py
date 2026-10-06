"""Strict JSON decoding followed by a typed domain factory, without repair."""
from collections.abc import Callable
import json
from typing import TypeVar
from .errors import MalformedResponseError, ResponseValidationError

T = TypeVar("T")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Non-finite JSON number")


def parse_response(response: str, factory: Callable[[dict], T]) -> T:
    if not isinstance(response, str):
        raise MalformedResponseError("AI response must be JSON text")
    try:
        data = json.loads(response, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, RecursionError) as exc:
        raise MalformedResponseError("AI response is malformed JSON; expected one JSON object without markdown") from exc
    if not isinstance(data, dict):
        raise ResponseValidationError("AI response must be a JSON object")
    try:
        return factory(data)
    except (ValueError, TypeError, KeyError) as exc:
        raise ResponseValidationError(f"AI response schema validation failed: {exc}") from exc
