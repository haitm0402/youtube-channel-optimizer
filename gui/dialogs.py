"""Friendly error messages; exception details go only to an optional logger."""
from core.errors import (MalformedResponseError, ResponseValidationError, SessionConflictError, ChannelProfileConflictError)


def error_message(error: Exception) -> str:
    if isinstance(error, MalformedResponseError):
        return "Invalid JSON. Paste one JSON object without Markdown fences."
    if isinstance(error, SessionConflictError):
        return "Session changed or is busy in another process. Reload the project before continuing."
    if isinstance(error, ChannelProfileConflictError):
        return "Channel profile changed or is busy in another process. Reopen it before saving."
    if isinstance(error, ResponseValidationError):
        return str(error).removeprefix("AI response schema validation failed: ")
    if isinstance(error, (ValueError, OSError)):
        return str(error) or "The operation could not be completed."
    from core.errors import ApplicationError
    if isinstance(error, ApplicationError):
        return str(error)
    return "The operation could not be completed. Reload the project and try again."
