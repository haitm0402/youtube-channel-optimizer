"""Local strict JSON sessions with atomic replacement and optimistic concurrency."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from core.errors import SessionConflictError, SessionStoreError
from core.responses import parse_response
from core.errors import MalformedResponseError, ResponseValidationError
from models import WorkflowSession
from models.session_metadata import parse_timestamp, validate_session_id


@contextmanager
def _file_lock(path: Path):
    # Persistent lock files avoid the inode race caused by deleting lock files.
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SessionConflictError("Session is busy in another process; retry after it finishes") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class JsonSessionStore:
    def __init__(self, data_dir: Path | str):
        self.directory = Path(data_dir).resolve() / "sessions"

    def _path(self, session_id: str) -> Path:
        try:
            validate_session_id(session_id)
        except ValueError as exc:
            raise SessionStoreError(str(exc)) from exc
        return self.directory / f"{session_id}.json"

    def load_session(self, session_id: str) -> WorkflowSession:
        path = self._path(session_id)
        try:
            session = parse_response(path.read_text(encoding="utf-8"), WorkflowSession.from_dict)
        except FileNotFoundError as exc:
            raise SessionStoreError(f"Session not found: {session_id}") from exc
        except (OSError, UnicodeError) as exc:
            raise SessionStoreError(f"Cannot read session: {session_id}") from exc
        except (MalformedResponseError, ResponseValidationError) as exc:
            raise SessionStoreError(f"Corrupt or incompatible session {session_id}: {exc}") from exc
        if session.session_id != session_id:
            raise SessionStoreError(f"Session ID does not match filename: {session_id}")
        return session

    def save_session(self, session: WorkflowSession, *, expected_revision: int | None = None) -> None:
        if not isinstance(session, WorkflowSession):
            raise SessionStoreError("Expected a WorkflowSession")
        try:
            validated = WorkflowSession.from_dict(session.to_dict())
            payload = json.dumps(validated.to_dict(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        except (ValueError, TypeError, KeyError) as exc:
            raise SessionStoreError(f"Session validation failed: {exc}") from exc
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 0):
            raise SessionStoreError("expected_revision must be a non-negative integer or None")
        path = self._path(session.session_id)
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with _file_lock(path.with_suffix(".lock")):
                if expected_revision is None:
                    if path.exists():
                        raise SessionConflictError("Session already exists; load it before saving")
                    if session.revision != 0:
                        raise SessionStoreError("New sessions must have revision 0")
                else:
                    existing = self.load_session(session.session_id)
                    if existing.revision != expected_revision:
                        raise SessionConflictError("Session changed in another process; reload before saving")
                    if session.revision != expected_revision + 1:
                        raise SessionStoreError("Updated revision must increase by exactly 1")
                    if session.created_at != existing.created_at:
                        raise SessionStoreError("created_at cannot change")
                    if parse_timestamp(session.updated_at, "updated_at") < parse_timestamp(existing.updated_at, "updated_at"):
                        raise SessionStoreError("updated_at cannot move backwards")
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                                 prefix=f".{session.session_id}-", suffix=".tmp", delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                # The file is closed before replace, including on Windows.
                os.replace(temporary, path)
                temporary = None
        except OSError as exc:
            raise SessionStoreError(f"Cannot save session: {session.session_id}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def list_sessions(self, *, archived: bool = False) -> list[WorkflowSession]:
        if type(archived) is not bool:
            raise SessionStoreError("archived filter must be a boolean")
        if not self.directory.exists():
            return []
        try:
            paths = sorted(path for path in self.directory.iterdir() if path.suffix == ".json")
        except OSError as exc:
            raise SessionStoreError("Cannot list local sessions") from exc
        sessions = [self.load_session(path.stem) for path in paths]
        return sorted((session for session in sessions if session.archived == archived),
                      key=lambda session: (parse_timestamp(session.updated_at, "updated_at"), session.session_id), reverse=True)
