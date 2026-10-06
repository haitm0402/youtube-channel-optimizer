"""Application errors callers can handle without inspecting provider output."""


class ApplicationError(Exception):
    """Base for errors exposed by the AI pipeline."""


class PromptError(ApplicationError):
    """A template cannot be loaded or rendered."""


class ProviderError(ApplicationError):
    """A text provider could not complete the request."""


class MalformedResponseError(ApplicationError):
    """Provider output is not strict JSON."""


class ResponseValidationError(ApplicationError):
    """JSON does not satisfy the requested domain schema."""
