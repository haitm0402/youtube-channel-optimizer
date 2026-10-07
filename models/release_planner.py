"""Release Planner domain models for multi-channel publishing schedules."""
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .session_metadata import parse_timestamp, utc_now, validate_session_id
from .validation import object_fields, required, strings


class ReleaseStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    HOLD = "HOLD"


def _uuid(value: str, name: str) -> str:
    try:
        validate_session_id(value)
    except ValueError as exc:
        raise ValueError(str(exc).replace("session_id", name)) from exc
    return value


def _optional(value: str | None, name: str) -> None:
    if value is not None:
        required(value, name)


def _date(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{name} must be canonical YYYY-MM-DD")
    return value


def _time(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be HH:MM")
    try:
        parsed = datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError(f"{name} must be 24-hour HH:MM") from exc
    if parsed.strftime("%H:%M") != value:
        raise ValueError(f"{name} must be canonical 24-hour HH:MM")
    return value


def _timezone(value: str) -> str:
    required(value, "timezone")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("timezone must be a valid IANA timezone, for example Asia/Ho_Chi_Minh") from exc
    return value


@dataclass(frozen=True)
class ReleaseChannel:
    name: str
    target_market: str | None = None
    timezone: str = "Asia/Ho_Chi_Minh"
    default_time: str = "20:00"
    release_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    notes: str | None = None
    archived: bool = False
    channel_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    updated_at: str | None = None

    def __post_init__(self) -> None:
        required(self.name, "channel name")
        _optional(self.target_market, "target_market")
        _timezone(self.timezone)
        _time(self.default_time, "default_time")
        _optional(self.notes, "notes")
        _uuid(self.channel_id, "channel_id")
        created = parse_timestamp(self.created_at, "created_at")
        if self.updated_at is None:
            object.__setattr__(self, "updated_at", self.created_at)
        if parse_timestamp(self.updated_at, "updated_at") < created:
            raise ValueError("updated_at must not precede created_at")
        if type(self.archived) is not bool:
            raise ValueError("archived must be a boolean")
        if not isinstance(self.release_days, list) or not self.release_days:
            raise ValueError("release_days must contain at least one weekday")
        if any(type(day) is not int or day < 0 or day > 6 for day in self.release_days):
            raise ValueError("release_days entries must be integers from 0 through 6")
        if len(set(self.release_days)) != len(self.release_days):
            raise ValueError("release_days must not contain duplicates")

    def to_dict(self) -> dict[str, Any]:
        replace(self)
        return {
            "channel_id": self.channel_id, "name": self.name,
            "target_market": self.target_market, "timezone": self.timezone,
            "default_time": self.default_time, "release_days": list(self.release_days),
            "notes": self.notes, "archived": self.archived,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReleaseChannel":
        fields = {
            "channel_id", "name", "target_market", "timezone", "default_time",
            "release_days", "notes", "archived", "created_at", "updated_at",
        }
        object_fields(data, fields, "ReleaseChannel")
        return cls(**data)


@dataclass(frozen=True)
class ReleaseItem:
    channel_id: str
    song_title: str
    publish_date: str
    publish_time: str
    timezone: str
    status: ReleaseStatus = ReleaseStatus.PLANNED
    video_title: str | None = None
    audio_ready: bool = False
    thumbnail_ready: bool = False
    video_ready: bool = False
    seo_ready: bool = False
    youtube_url: str | None = None
    notes: str | None = None
    archived: bool = False
    release_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    updated_at: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.channel_id, "channel_id")
        _uuid(self.release_id, "release_id")
        required(self.song_title, "song_title")
        _date(self.publish_date, "publish_date")
        _time(self.publish_time, "publish_time")
        _timezone(self.timezone)
        _optional(self.video_title, "video_title")
        _optional(self.youtube_url, "youtube_url")
        _optional(self.notes, "notes")
        try:
            object.__setattr__(self, "status", ReleaseStatus(self.status))
        except (TypeError, ValueError) as exc:
            raise ValueError("Unknown release status") from exc
        for name in ("audio_ready", "thumbnail_ready", "video_ready", "seo_ready", "archived"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        created = parse_timestamp(self.created_at, "created_at")
        if self.updated_at is None:
            object.__setattr__(self, "updated_at", self.created_at)
        if parse_timestamp(self.updated_at, "updated_at") < created:
            raise ValueError("updated_at must not precede created_at")

    @property
    def missing_assets(self) -> list[str]:
        return [
            label for ready, label in (
                (self.audio_ready, "AUDIO"), (self.thumbnail_ready, "THUMBNAIL"),
                (self.video_ready, "VIDEO"), (self.seo_ready, "SEO"),
            ) if not ready
        ]

    @property
    def readiness_label(self) -> str:
        if self.status == ReleaseStatus.PUBLISHED:
            return "PUBLISHED"
        if not self.missing_assets:
            return "READY"
        return "MISSING " + ", ".join(self.missing_assets)

    def to_dict(self) -> dict[str, Any]:
        replace(self)
        return {
            "release_id": self.release_id, "channel_id": self.channel_id,
            "song_title": self.song_title, "video_title": self.video_title,
            "publish_date": self.publish_date, "publish_time": self.publish_time,
            "timezone": self.timezone, "status": self.status.value,
            "audio_ready": self.audio_ready, "thumbnail_ready": self.thumbnail_ready,
            "video_ready": self.video_ready, "seo_ready": self.seo_ready,
            "youtube_url": self.youtube_url, "notes": self.notes,
            "archived": self.archived, "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReleaseItem":
        fields = {
            "release_id", "channel_id", "song_title", "video_title", "publish_date",
            "publish_time", "timezone", "status", "audio_ready", "thumbnail_ready",
            "video_ready", "seo_ready", "youtube_url", "notes", "archived",
            "created_at", "updated_at",
        }
        object_fields(data, fields, "ReleaseItem")
        return cls(**data)


@dataclass(frozen=True)
class ReleasePlan:
    channels: list[ReleaseChannel] = field(default_factory=list)
    releases: list[ReleaseItem] = field(default_factory=list)
    revision: int = 0
    created_at: str = field(default_factory=utc_now)
    updated_at: str | None = None

    def __post_init__(self) -> None:
        created = parse_timestamp(self.created_at, "created_at")
        if self.updated_at is None:
            object.__setattr__(self, "updated_at", self.created_at)
        if parse_timestamp(self.updated_at, "updated_at") < created:
            raise ValueError("updated_at must not precede created_at")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("revision must be a non-negative integer")
        if not isinstance(self.channels, list) or not all(isinstance(x, ReleaseChannel) for x in self.channels):
            raise ValueError("channels must contain ReleaseChannel entries")
        if not isinstance(self.releases, list) or not all(isinstance(x, ReleaseItem) for x in self.releases):
            raise ValueError("releases must contain ReleaseItem entries")
        channel_ids = [x.channel_id for x in self.channels]
        release_ids = [x.release_id for x in self.releases]
        if len(channel_ids) != len(set(channel_ids)):
            raise ValueError("channel IDs must be unique")
        if len(release_ids) != len(set(release_ids)):
            raise ValueError("release IDs must be unique")
        known = set(channel_ids)
        if any(item.channel_id not in known for item in self.releases):
            raise ValueError("Every release must reference an existing channel")

    def to_dict(self) -> dict[str, Any]:
        replace(self)
        return {
            "schema_version": 1,
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "channels": [item.to_dict() for item in self.channels],
            "releases": [item.to_dict() for item in self.releases],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReleasePlan":
        fields = {"schema_version", "revision", "created_at", "updated_at", "channels", "releases"}
        object_fields(data, fields, "ReleasePlan")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported release planner schema_version (expected 1)")
        if not isinstance(data["channels"], list) or not isinstance(data["releases"], list):
            raise ValueError("channels and releases must be arrays")
        return cls(
            channels=[ReleaseChannel.from_dict(item) for item in data["channels"]],
            releases=[ReleaseItem.from_dict(item) for item in data["releases"]],
            revision=data["revision"], created_at=data["created_at"], updated_at=data["updated_at"],
        )
