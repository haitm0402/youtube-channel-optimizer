"""Persistent channel DNA used by downstream music-production workflows."""
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import uuid4

from .manual import WorkflowSession, WorkflowState
from .session_metadata import parse_timestamp, utc_now, validate_session_id
from .validation import object_fields, required, strings


EDITABLE_PROFILE_FIELDS = {
    "channel_name", "target_artist", "target_market", "target_language",
    "channel_positioning", "channel_description", "slogan", "music_niche",
    "genre", "subgenre", "vocal_direction", "flow_direction", "lyric_rules",
    "suno_style_rules", "visual_identity", "thumbnail_rules", "banner_direction",
    "seo_topics", "channel_keywords", "video_keywords", "default_tags",
    "default_hashtags", "title_templates", "upload_time", "competitor_urls", "notes",
}

_OPTIONAL_TEXT_FIELDS = {
    "target_artist", "target_market", "target_language", "channel_positioning",
    "channel_description", "slogan", "music_niche", "genre", "subgenre",
    "vocal_direction", "flow_direction", "lyric_rules", "suno_style_rules",
    "visual_identity", "thumbnail_rules", "banner_direction", "upload_time", "notes",
}

_LIST_FIELDS = {
    "seo_topics", "channel_keywords", "video_keywords", "default_tags",
    "default_hashtags", "title_templates", "competitor_urls",
}


def _optional_text(value: str | None, name: str) -> None:
    if value is not None:
        required(value, name)


@dataclass(frozen=True)
class ChannelDNAProfile:
    """Reusable per-channel settings; independent from one optimization session."""

    channel_name: str
    target_artist: str | None = None
    target_market: str | None = None
    target_language: str | None = None
    channel_positioning: str | None = None
    channel_description: str | None = None
    slogan: str | None = None
    music_niche: str | None = None
    genre: str | None = None
    subgenre: str | None = None
    vocal_direction: str | None = None
    flow_direction: str | None = None
    lyric_rules: str | None = None
    suno_style_rules: str | None = None
    visual_identity: str | None = None
    thumbnail_rules: str | None = None
    banner_direction: str | None = None
    seo_topics: list[str] = field(default_factory=list)
    channel_keywords: list[str] = field(default_factory=list)
    video_keywords: list[str] = field(default_factory=list)
    default_tags: list[str] = field(default_factory=list)
    default_hashtags: list[str] = field(default_factory=list)
    title_templates: list[str] = field(default_factory=list)
    upload_time: str | None = None
    competitor_urls: list[str] = field(default_factory=list)
    notes: str | None = None
    source_session_id: str | None = None
    profile_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    updated_at: str | None = None
    archived: bool = False
    revision: int = 0

    def __post_init__(self) -> None:
        required(self.channel_name, "channel_name")
        validate_session_id(self.profile_id)
        if self.source_session_id is not None:
            validate_session_id(self.source_session_id)
        created = parse_timestamp(self.created_at, "created_at")
        if self.updated_at is None:
            object.__setattr__(self, "updated_at", self.created_at)
        if parse_timestamp(self.updated_at, "updated_at") < created:
            raise ValueError("updated_at must not precede created_at")
        if type(self.archived) is not bool:
            raise ValueError("archived must be a boolean")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("revision must be a non-negative integer")
        for name in sorted(_OPTIONAL_TEXT_FIELDS):
            _optional_text(getattr(self, name), name)
        for name in sorted(_LIST_FIELDS):
            strings(getattr(self, name), name)

    def to_dict(self) -> dict[str, Any]:
        replace(self)  # Revalidate mutable nested lists.
        data = {name: getattr(self, name) for name in sorted(EDITABLE_PROFILE_FIELDS)}
        data.update({
            "schema_version": 1,
            "profile_id": self.profile_id,
            "source_session_id": self.source_session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived": self.archived,
            "revision": self.revision,
        })
        return data

    def to_prompt_dict(self) -> dict[str, Any]:
        """Portable semantic payload for future Song Factory/ChatGPT workflows."""
        replace(self)
        result = {"profile_type": "channel_dna_v1", "schema_version": 1}
        for name in (
            "channel_name", "target_artist", "target_market", "target_language",
            "channel_positioning", "channel_description", "slogan", "music_niche",
            "genre", "subgenre", "vocal_direction", "flow_direction", "lyric_rules",
            "suno_style_rules", "visual_identity", "thumbnail_rules", "banner_direction",
            "seo_topics", "channel_keywords", "video_keywords", "default_tags",
            "default_hashtags", "title_templates", "upload_time", "competitor_urls", "notes",
        ):
            value = getattr(self, name)
            result[name] = list(value) if isinstance(value, list) else value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelDNAProfile":
        fields = set(EDITABLE_PROFILE_FIELDS) | {
            "schema_version", "profile_id", "source_session_id", "created_at",
            "updated_at", "archived", "revision",
        }
        object_fields(data, fields, "ChannelDNAProfile")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported channel profile schema_version (expected 1)")
        kwargs = {name: data[name] for name in EDITABLE_PROFILE_FIELDS}
        kwargs.update({
            "profile_id": data["profile_id"],
            "source_session_id": data["source_session_id"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "archived": data["archived"],
            "revision": data["revision"],
        })
        return cls(**kwargs)

    @classmethod
    def from_completed_session(cls, session: WorkflowSession) -> "ChannelDNAProfile":
        if not isinstance(session, WorkflowSession) or session.state != WorkflowState.COMPLETE:
            raise ValueError("A COMPLETE workflow session is required")
        analysis, package = session.analysis, session.package
        return cls(
            channel_name=session.selected_name,
            target_artist=session.competitor.target_artist,
            target_market=session.competitor.target_market or analysis.target_market,
            target_language=session.competitor.target_language or analysis.language,
            channel_positioning=package.channel_positioning,
            channel_description=package.channel_description,
            slogan=package.slogan,
            music_niche=analysis.music_niche,
            genre=analysis.genre,
            subgenre=analysis.subgenre,
            lyric_rules=f"Tone of voice: {analysis.tone_of_voice}",
            visual_identity=analysis.visual_identity,
            thumbnail_rules=package.thumbnail_direction,
            banner_direction=package.banner_direction,
            seo_topics=list(analysis.seo_topics),
            channel_keywords=list(package.channel_keywords),
            video_keywords=list(package.video_core_keywords),
            default_tags=list(package.video_tags),
            default_hashtags=list(package.hashtags),
            title_templates=list(package.title_templates),
            competitor_urls=[session.competitor.competitor_url],
            source_session_id=session.session_id,
        )
