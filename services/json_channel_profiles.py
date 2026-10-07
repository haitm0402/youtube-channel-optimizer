"""Strict local JSON storage for reusable Channel DNA profiles."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile

from core.errors import ChannelProfileConflictError, ChannelProfileStoreError
from models.channel_dna import ChannelDNAProfile
from models.session_metadata import parse_timestamp, validate_session_id


@contextmanager
def _profile_lock(path: Path):
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
            raise ChannelProfileConflictError("Channel profile is busy in another process; retry after it finishes") from exc
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


def _load_profile_text(raw: str) -> ChannelDNAProfile:
    def no_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate key: {key}")
            value[key] = item
        return value

    def no_constants(value):
        raise ValueError(f"invalid JSON constant: {value}")

    try:
        data = json.loads(raw, object_pairs_hook=no_duplicates, parse_constant=no_constants)
        return ChannelDNAProfile.from_dict(data)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        raise ChannelProfileStoreError(f"Corrupt or incompatible channel profile: {exc}") from exc


class JsonChannelProfileStore:
    def __init__(self, data_dir: Path | str):
        self.directory = Path(data_dir).resolve() / "channel_profiles"

    def _path(self, profile_id: str) -> Path:
        try:
            validate_session_id(profile_id)
        except ValueError as exc:
            raise ChannelProfileStoreError(str(exc).replace("session_id", "profile_id")) from exc
        return self.directory / f"{profile_id}.json"

    def load_profile(self, profile_id: str) -> ChannelDNAProfile:
        path = self._path(profile_id)
        try:
            profile = _load_profile_text(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ChannelProfileStoreError(f"Channel profile not found: {profile_id}") from exc
        except (OSError, UnicodeError) as exc:
            raise ChannelProfileStoreError(f"Cannot read channel profile: {profile_id}") from exc
        if profile.profile_id != profile_id:
            raise ChannelProfileStoreError(f"Channel profile ID does not match filename: {profile_id}")
        return profile

    def save_profile(self, profile: ChannelDNAProfile, *, expected_revision: int | None = None) -> None:
        if not isinstance(profile, ChannelDNAProfile):
            raise ChannelProfileStoreError("Expected a ChannelDNAProfile")
        try:
            validated = ChannelDNAProfile.from_dict(profile.to_dict())
            payload = json.dumps(validated.to_dict(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        except (TypeError, ValueError, KeyError) as exc:
            raise ChannelProfileStoreError(f"Channel profile validation failed: {exc}") from exc
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 0):
            raise ChannelProfileStoreError("expected_revision must be a non-negative integer or None")
        path = self._path(profile.profile_id)
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with _profile_lock(path.with_suffix(".lock")):
                if expected_revision is None:
                    if path.exists():
                        raise ChannelProfileConflictError("Channel profile already exists; load it before saving")
                    if profile.revision != 0:
                        raise ChannelProfileStoreError("New channel profiles must have revision 0")
                else:
                    existing = self.load_profile(profile.profile_id)
                    if existing.revision != expected_revision:
                        raise ChannelProfileConflictError("Channel profile changed in another process; reload before saving")
                    if profile.revision != expected_revision + 1:
                        raise ChannelProfileStoreError("Updated revision must increase by exactly 1")
                    if profile.created_at != existing.created_at:
                        raise ChannelProfileStoreError("created_at cannot change")
                    if parse_timestamp(profile.updated_at, "updated_at") < parse_timestamp(existing.updated_at, "updated_at"):
                        raise ChannelProfileStoreError("updated_at cannot move backwards")
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.directory,
                    prefix=f".{profile.profile_id}-", suffix=".tmp", delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
                temporary = None
        except (ChannelProfileConflictError, ChannelProfileStoreError):
            raise
        except OSError as exc:
            raise ChannelProfileStoreError(f"Cannot save channel profile: {profile.profile_id}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def list_profiles(self, *, archived: bool = False) -> list[ChannelDNAProfile]:
        if type(archived) is not bool:
            raise ChannelProfileStoreError("archived filter must be a boolean")
        if not self.directory.exists():
            return []
        try:
            paths = sorted(path for path in self.directory.iterdir() if path.suffix == ".json")
        except OSError as exc:
            raise ChannelProfileStoreError("Cannot list channel profiles") from exc
        profiles = [self.load_profile(path.stem) for path in paths]
        return sorted(
            (profile for profile in profiles if profile.archived == archived),
            key=lambda profile: (parse_timestamp(profile.updated_at, "updated_at"), profile.profile_id),
            reverse=True,
        )
