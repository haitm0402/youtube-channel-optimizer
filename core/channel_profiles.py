"""Channel Profile Manager: reusable channel DNA independent from optimization sessions."""
from dataclasses import dataclass, replace
import json
from pathlib import Path

from models.channel_dna import ChannelDNAProfile, EDITABLE_PROFILE_FIELDS
from models.manual import WorkflowSession
from models.session_metadata import next_timestamp
from services.json_channel_profiles import JsonChannelProfileStore
from utils.manual_export import channel_folder_name


@dataclass(frozen=True)
class ChannelProfileSummary:
    profile_id: str
    channel_name: str
    target_artist: str | None
    target_market: str | None
    target_language: str | None
    genre: str | None
    upload_time: str | None
    updated_at: str
    archived: bool


class ChannelProfileManager:
    def __init__(self, store: JsonChannelProfileStore, exports_dir: Path | str):
        self.store = store
        self.exports_dir = Path(exports_dir).resolve()

    def list_profiles(self, *, archived: bool = False) -> list[ChannelProfileSummary]:
        return [
            ChannelProfileSummary(
                profile.profile_id, profile.channel_name, profile.target_artist,
                profile.target_market, profile.target_language, profile.genre,
                profile.upload_time, profile.updated_at, profile.archived,
            )
            for profile in self.store.list_profiles(archived=archived)
        ]

    def load_profile(self, profile_id: str) -> ChannelDNAProfile:
        return self.store.load_profile(profile_id)

    def create_profile(self, **values) -> ChannelDNAProfile:
        unknown = set(values) - EDITABLE_PROFILE_FIELDS
        if unknown:
            raise ValueError(f"Unknown channel profile fields: {', '.join(sorted(unknown))}")
        profile = ChannelDNAProfile(**values)
        self.store.save_profile(profile)
        return profile

    def update_profile(self, profile_id: str, **changes) -> ChannelDNAProfile:
        unknown = set(changes) - EDITABLE_PROFILE_FIELDS
        if unknown:
            raise ValueError(f"Unknown channel profile fields: {', '.join(sorted(unknown))}")
        current = self.store.load_profile(profile_id)
        if current.archived:
            raise ValueError("Archived channel profiles are read-only; restore the profile before editing")
        candidate = replace(
            current, **changes, revision=current.revision + 1,
            updated_at=next_timestamp(current.updated_at),
        )
        self.store.save_profile(candidate, expected_revision=current.revision)
        return candidate

    def create_from_session(self, session: WorkflowSession) -> ChannelDNAProfile:
        for archived in (False, True):
            for existing in self.store.list_profiles(archived=archived):
                if existing.source_session_id == session.session_id:
                    return existing
        profile = ChannelDNAProfile.from_completed_session(session)
        self.store.save_profile(profile)
        return profile

    def archive_profile(self, profile_id: str) -> ChannelDNAProfile:
        current = self.store.load_profile(profile_id)
        if current.archived:
            return current
        candidate = replace(
            current, archived=True, revision=current.revision + 1,
            updated_at=next_timestamp(current.updated_at),
        )
        self.store.save_profile(candidate, expected_revision=current.revision)
        return candidate

    def restore_profile(self, profile_id: str) -> ChannelDNAProfile:
        current = self.store.load_profile(profile_id)
        if not current.archived:
            return current
        candidate = replace(
            current, archived=False, revision=current.revision + 1,
            updated_at=next_timestamp(current.updated_at),
        )
        self.store.save_profile(candidate, expected_revision=current.revision)
        return candidate

    def export_profile(self, profile_id: str) -> Path:
        profile = self.store.load_profile(profile_id)
        destination_dir = self.exports_dir / "channel_profiles"
        destination_dir.mkdir(parents=True, exist_ok=True)
        base = channel_folder_name(profile.channel_name)
        payload = json.dumps(profile.to_prompt_dict(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        for suffix in range(1000):
            name = f"{base}.json" if suffix == 0 else f"{base}-{suffix}.json"
            destination = destination_dir / name
            try:
                with destination.open("x", encoding="utf-8") as handle:
                    handle.write(payload)
                return destination
            except FileExistsError:
                continue
            except Exception:
                destination.unlink(missing_ok=True)
                raise
        raise FileExistsError("Cannot allocate a fresh channel profile export")
