"""Ports for future adapters. Core never imports a provider SDK."""
from typing import Protocol, runtime_checkable
from models import CompetitorInput, WorkflowSession


@runtime_checkable
class TextGenerator(Protocol):
    def generate(self, *, prompt: str) -> str:
        """Generate text through a replaceable provider adapter."""
        ...


class CompetitorSource(Protocol):
    def fetch(self, url: str) -> CompetitorInput:
        """Obtain competitor data through a future source adapter."""
        ...


@runtime_checkable
class SessionStore(Protocol):
    def save_session(self, session: WorkflowSession, *, expected_revision: int | None = None) -> None:
        """Create if expected_revision is None; otherwise compare-and-save atomically."""
        ...

    def load_session(self, session_id: str) -> WorkflowSession:
        ...

    def list_sessions(self, *, archived: bool = False) -> list[WorkflowSession]:
        ...
