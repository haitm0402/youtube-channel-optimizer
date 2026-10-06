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


class WorkflowStateError(ApplicationError):
    """An action is unavailable in the current manual workflow state."""


class SessionStoreError(ApplicationError):
    """Local session data cannot be read or saved safely."""


class SessionConflictError(SessionStoreError):
    """Another process saved or locked this session; reload before retrying."""
