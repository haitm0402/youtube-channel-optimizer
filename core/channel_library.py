"""Project library derived from session records; no duplicate full-data index."""
from dataclasses import dataclass, replace
from .contracts import SessionStore
from models import WorkflowSession, WorkflowState
from models.session_metadata import next_timestamp


@dataclass(frozen=True)
class ChannelProjectSummary:
    session_id: str
    display_name: str
    competitor_url: str
    reference_artist: str | None
    target_market: str | None
    target_language: str | None
    selected_channel_name: str | None
    state: WorkflowState
    created_at: str
    updated_at: str

    @property
    def status(self) -> str:
        return {
            WorkflowState.WAITING_FOR_ANALYSIS: "WAITING FOR ANALYSIS",
            WorkflowState.WAITING_FOR_NAMES: "WAITING FOR NAMES",
            WorkflowState.WAITING_FOR_PACKAGE: "WAITING FOR PACKAGE",
            WorkflowState.COMPLETE: "COMPLETE",
        }.get(self.state, "IN PROGRESS")


class ChannelLibrary:
    def __init__(self, store: SessionStore):
        self.store = store

    def list_projects(self, *, archived: bool = False) -> list[ChannelProjectSummary]:
        return [ChannelProjectSummary(
            session.session_id, session.display_name, session.competitor.competitor_url,
            session.analysis.reference_artist if session.analysis is not None else None,
            session.competitor.target_market or (session.analysis.target_market if session.analysis is not None else None),
            session.competitor.target_language or (session.analysis.language if session.analysis is not None else None),
            session.selected_name, session.state, session.created_at, session.updated_at,
        ) for session in self.store.list_sessions(archived=archived)]

    def load_session(self, session_id: str) -> WorkflowSession:
        return self.store.load_session(session_id)

    def archive_session(self, session_id: str) -> WorkflowSession:
        session = self.store.load_session(session_id)
        if session.archived:
            return session
        archived = replace(session, archived=True, revision=session.revision + 1,
                           updated_at=next_timestamp(session.updated_at))
        self.store.save_session(archived, expected_revision=session.revision)
        return archived
