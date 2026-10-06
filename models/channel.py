"""Validated input, intermediate results, and versioned export contracts."""
from dataclasses import asdict, dataclass, field
from typing import Any
from enum import Enum
import math
import re
from .validation import required as _required, strings as _strings, object_fields
from urllib.parse import urlsplit



@dataclass(frozen=True)
class TargetAudience:
    artist: str | None = None
    market: str | None = None
    language: str | None = None

    def __post_init__(self) -> None:
        for name in ("artist", "market", "language"):
            value = getattr(self, name)
            if value is not None:
                _required(value, name)


@dataclass(frozen=True, init=False)
class CompetitorInput:
    # Legacy fields preserve positional constructors and existing profile JSON.
    url: str
    avatar_reference: str | None
    description: str
    target: TargetAudience

    def __init__(self, url: str | None = None, avatar_reference: str | None = None,
                 description: str | None = None, target: TargetAudience | None = None, *,
                 competitor_url: str | None = None, competitor_description: str | None = None,
                 target_artist: str | None = None, target_market: str | None = None,
                 target_language: str | None = None):
        if url is not None and competitor_url is not None and url != competitor_url:
            raise ValueError("url and competitor_url conflict")
        if description is not None and competitor_description is not None and description != competitor_description:
            raise ValueError("description and competitor_description conflict")
        if target is not None and not isinstance(target, TargetAudience):
            raise ValueError("target must be a TargetAudience")
        audience = target if target is not None else TargetAudience()
        for name, value in (("artist", target_artist), ("market", target_market), ("language", target_language)):
            if value is not None and getattr(audience, name) is not None and value != getattr(audience, name):
                raise ValueError(f"target_{name} conflicts with target.{name}")
        audience = TargetAudience(
            target_artist if target_artist is not None else audience.artist,
            target_market if target_market is not None else audience.market,
            target_language if target_language is not None else audience.language,
        )
        object.__setattr__(self, "url", competitor_url if competitor_url is not None else url)
        object.__setattr__(self, "description", competitor_description if competitor_description is not None else description)
        object.__setattr__(self, "avatar_reference", avatar_reference)
        object.__setattr__(self, "target", audience)
        self.__post_init__()

    def __post_init__(self) -> None:
        _required(self.url, "competitor_url")
        if any(character.isspace() or ord(character) < 32 for character in self.url):
            raise ValueError("url must not contain whitespace or control characters")
        try:
            parsed = urlsplit(self.url)
            valid_port = parsed.port in (None, 443)
        except ValueError as exc:
            raise ValueError("url must be a valid HTTPS YouTube channel reference") from exc
        channel_path = re.fullmatch(
            r"/(?:@[^/]+|(?:channel|c|user)/[^/]+)(?:/(?:featured|videos|shorts|streams|playlists|community|about|releases))?",
            parsed.path.rstrip("/"),
        )
        if (parsed.scheme != "https" or parsed.hostname not in
                {"youtube.com", "www.youtube.com", "m.youtube.com"}
                or not channel_path or not valid_port or parsed.username is not None or parsed.password is not None):
            raise ValueError("url must be an HTTPS YouTube channel reference (@handle, channel, c, or user)")
        if self.avatar_reference is not None:
            _required(self.avatar_reference, "avatar_reference")
        _required(self.description, "competitor_description")

    @property
    def competitor_url(self) -> str:
        return self.url

    @property
    def competitor_description(self) -> str:
        return self.description

    @property
    def target_artist(self) -> str | None:
        return self.target.artist

    @property
    def target_market(self) -> str | None:
        return self.target.market

    @property
    def target_language(self) -> str | None:
        return self.target.language

    def to_prompt_dict(self) -> dict[str, Any]:
        """Active V1 text input; legacy avatar metadata is never used."""
        return {"competitor_url": self.competitor_url,
                "competitor_description": self.competitor_description,
                "target_artist": self.target_artist, "target_market": self.target_market,
                "target_language": self.target_language}

    @classmethod
    def from_v1_dict(cls, data: dict[str, Any]) -> "CompetitorInput":
        if not isinstance(data, dict):
            raise ValueError("Competitor input must be a JSON object")
        mandatory = {"competitor_url", "competitor_description"}
        optional = {"target_artist", "target_market", "target_language"}
        object_fields(data, mandatory | (data.keys() & optional), "Competitor input")
        return cls(**data)


@dataclass(frozen=True)
class CompetitorAnalysis:
    summary: str
    positioning: str
    # Preserve Phase 1 constructor order and audience alias.
    audience: str | None = None
    strengths: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    reference_artist: str | None = None
    music_niche: str | None = None
    genre: str | None = None
    subgenre: str | None = None
    target_market: str | None = None
    language: str | None = None
    target_audience: str | None = None
    visual_identity: str | None = None
    tone_of_voice: str | None = None
    seo_topics: list[str] = field(default_factory=list)
    branding_characteristics: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in ("summary", "positioning"):
            _required(getattr(self, name), name)
        if self.audience is not None and self.target_audience is not None and self.audience != self.target_audience:
            raise ValueError("audience and target_audience conflict")
        audience = self.target_audience if self.target_audience is not None else self.audience
        _required(audience, "target_audience")
        object.__setattr__(self, "audience", audience)
        object.__setattr__(self, "target_audience", audience)
        for name in ("reference_artist", "music_niche", "genre", "subgenre", "target_market",
                     "language", "visual_identity", "tone_of_voice"):
            if getattr(self, name) is not None:
                _required(getattr(self, name), name)
        for name in ("strengths", "opportunities", "seo_topics", "branding_characteristics"):
            _strings(getattr(self, name), name)

    @classmethod
    def from_ai_dict(cls, data: dict[str, Any]) -> "CompetitorAnalysis":
        object_fields(data, ANALYSIS_FIELDS, "CompetitorAnalysis")
        for name in sorted(ANALYSIS_TEXT_FIELDS):
            _required(data[name], name)
        for name in sorted(ANALYSIS_LIST_FIELDS):
            _strings(data[name], name, nonempty=True)
        # reference_artist may explicitly be null when not supplied/known.
        return cls(**data)

    def to_ai_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in sorted(ANALYSIS_FIELDS)}


ANALYSIS_TEXT_FIELDS = {"summary", "positioning", "music_niche", "genre", "subgenre",
                        "target_market", "language", "target_audience", "visual_identity", "tone_of_voice"}
ANALYSIS_LIST_FIELDS = {"seo_topics", "branding_characteristics", "strengths", "opportunities"}
ANALYSIS_FIELDS = ANALYSIS_TEXT_FIELDS | ANALYSIS_LIST_FIELDS | {"reference_artist"}


class NameCategory(str, Enum):
    POSITIONING = "positioning"
    BRAND = "brand"
    MEMORABLE = "memorable"


@dataclass(frozen=True)
class NameCandidate:
    name: str
    rationale: str | None = None
    category: NameCategory | None = None
    short_reason: str | None = None
    score: float | None = None

    def __post_init__(self) -> None:
        _required(self.name, "name")
        if self.rationale is not None and self.short_reason is not None and self.rationale != self.short_reason:
            raise ValueError("rationale and short_reason conflict")
        reason = self.short_reason if self.short_reason is not None else self.rationale
        _required(reason, "short_reason")
        object.__setattr__(self, "rationale", reason)
        object.__setattr__(self, "short_reason", reason)
        if self.category is not None:
            try:
                object.__setattr__(self, "category", NameCategory(self.category))
            except (TypeError, ValueError) as exc:
                raise ValueError("category must be positioning, brand, or memorable") from exc
        if self.score is not None:
            if type(self.score) not in (int, float) or not 0 <= self.score <= 10 or not math.isfinite(self.score):
                raise ValueError("score must be a finite number between 0 and 10")

    @classmethod
    def from_ai_dict(cls, data: dict[str, Any]) -> "NameCandidate":
        object_fields(data, {"name", "category", "short_reason", "score"}, "NameCandidate")
        if data["category"] is None or data["score"] is None:
            raise ValueError("category and score are required")
        return cls(**data)


@dataclass(frozen=True)
class ChannelNameResult:
    names: list[NameCandidate]
    best_recommendation: str

    def __post_init__(self) -> None:
        if not isinstance(self.names, list) or len(self.names) != 12:
            raise ValueError("names must contain exactly 12 suggestions")
        if not all(isinstance(item, NameCandidate) and item.category is not None and item.score is not None
                   for item in self.names):
            raise ValueError("every suggestion must have a valid category and score")
        for category in NameCategory:
            if sum(item.category == category for item in self.names) != 4:
                raise ValueError(f"names must contain exactly 4 {category.value} suggestions")
        normalized = [item.name.strip().casefold() for item in self.names]
        if len(set(normalized)) != 12:
            raise ValueError("names must be unique (ignoring case and surrounding whitespace)")
        _required(self.best_recommendation, "best_recommendation")
        if self.best_recommendation not in [item.name for item in self.names]:
            raise ValueError("best_recommendation must exactly match a suggested name")

    @classmethod
    def from_ai_dict(cls, data: dict[str, Any]) -> "ChannelNameResult":
        object_fields(data, {"names", "best_recommendation"}, "ChannelNameResult")
        if not isinstance(data["names"], list):
            raise ValueError("names must be an array")
        return cls([NameCandidate.from_ai_dict(item) for item in data["names"]], data["best_recommendation"])

    def to_ai_dict(self) -> dict[str, Any]:
        return {"names": [{"name": item.name, "category": item.category.value if item.category is not None else None,
                           "short_reason": item.short_reason, "score": item.score} for item in self.names],
                "best_recommendation": self.best_recommendation}


@dataclass(frozen=True)
class AvatarConcept:
    concept: str
    prompt: str | None = None
    composition: str | None = None
    colors: list[str] = field(default_factory=list)
    lighting: str | None = None
    background: str | None = None
    main_subject: str | None = None
    image_prompt: str | None = None

    def __post_init__(self) -> None:
        _required(self.concept, "concept")
        if self.prompt is not None and self.image_prompt is not None and self.prompt != self.image_prompt:
            raise ValueError("prompt and image_prompt conflict")
        prompt = self.image_prompt if self.image_prompt is not None else self.prompt
        _required(prompt, "image_prompt")
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(self, "image_prompt", prompt)
        for name in ("composition", "lighting", "background", "main_subject"):
            if getattr(self, name) is not None:
                _required(getattr(self, name), name)
        _strings(self.colors, "colors")

    @classmethod
    def from_ai_dict(cls, data: dict[str, Any]) -> "AvatarConcept":
        object_fields(data, AVATAR_FIELDS, "AvatarConcept")
        for name in sorted(AVATAR_FIELDS - {"colors"}):
            _required(data[name], f"avatar.{name}")
        _strings(data["colors"], "avatar.colors", nonempty=True)
        return cls(**data)


AVATAR_FIELDS = {"concept", "composition", "colors", "lighting", "background", "main_subject", "image_prompt"}


@dataclass(frozen=True)
class BannerConcept:
    concept: str
    layout: str
    background: str
    typography_direction: str
    main_visual: str
    image_prompt: str

    def __post_init__(self) -> None:
        for name in sorted(BANNER_FIELDS):
            _required(getattr(self, name), f"banner.{name}")

    @classmethod
    def from_ai_dict(cls, data: dict[str, Any]) -> "BannerConcept":
        object_fields(data, BANNER_FIELDS, "BannerConcept")
        return cls(**data)


BANNER_FIELDS = {"concept", "layout", "background", "typography_direction", "main_visual", "image_prompt"}
PACKAGE_LIST_FIELDS = {"channel_keywords", "video_core_keywords", "video_tags", "hashtags", "title_templates"}
PACKAGE_FIELDS = PACKAGE_LIST_FIELDS | {"channel_positioning", "avatar_concepts", "banner",
                                       "channel_description", "thumbnail_visual_guide", "slogan"}


@dataclass(frozen=True)
class ChannelPackage:
    # Preserve the Phase 1 constructor and JSON field names as aliases.
    positioning: str
    avatar_concepts: list[AvatarConcept]
    banner_concept: str
    banner_prompt: str
    description: str
    channel_keywords: list[str]
    video_core_keywords: list[str]
    video_tags: list[str]
    hashtags: list[str]
    title_templates: list[str]
    thumbnail_visual_guide: str
    banner: BannerConcept | None = None
    slogan: str | None = None

    @property
    def channel_positioning(self) -> str:
        return self.positioning

    @property
    def channel_description(self) -> str:
        return self.description

    def __post_init__(self) -> None:
        for name in ("positioning", "banner_concept", "banner_prompt", "description", "thumbnail_visual_guide"):
            _required(getattr(self, name), name)
        if (not isinstance(self.avatar_concepts, list) or len(self.avatar_concepts) != 4
                or not all(isinstance(item, AvatarConcept) for item in self.avatar_concepts)):
            raise ValueError("avatar_concepts must contain exactly four AvatarConcept objects")
        for name in sorted(PACKAGE_LIST_FIELDS):
            _strings(getattr(self, name), name, nonempty=True)
        if self.banner is not None:
            if not isinstance(self.banner, BannerConcept):
                raise ValueError("banner must be a BannerConcept")
            if self.banner_concept != self.banner.concept or self.banner_prompt != self.banner.image_prompt:
                raise ValueError("banner conflicts with legacy banner fields")
        if self.slogan is not None:
            _required(self.slogan, "slogan")

    @classmethod
    def from_ai_dict(cls, data: dict[str, Any]) -> "ChannelPackage":
        object_fields(data, PACKAGE_FIELDS, "ChannelPackage")
        for name in ("channel_positioning", "channel_description", "thumbnail_visual_guide", "slogan"):
            _required(data[name], name)
        if not isinstance(data["avatar_concepts"], list):
            raise ValueError("avatar_concepts must be an array")
        banner = BannerConcept.from_ai_dict(data["banner"])
        return cls(positioning=data["channel_positioning"],
                   avatar_concepts=[AvatarConcept.from_ai_dict(item) for item in data["avatar_concepts"]],
                   banner_concept=banner.concept, banner_prompt=banner.image_prompt, banner=banner,
                   description=data["channel_description"], slogan=data["slogan"],
                   thumbnail_visual_guide=data["thumbnail_visual_guide"],
                   **{name: data[name] for name in PACKAGE_LIST_FIELDS})

    def to_ai_dict(self) -> dict[str, Any]:
        return {"channel_positioning": self.channel_positioning,
                "channel_description": self.channel_description,
                "avatar_concepts": [{name: getattr(item, name) for name in sorted(AVATAR_FIELDS)}
                                    for item in self.avatar_concepts],
                "banner": asdict(self.banner) if self.banner is not None else None,
                "slogan": self.slogan, "thumbnail_visual_guide": self.thumbnail_visual_guide,
                **{name: getattr(self, name) for name in sorted(PACKAGE_LIST_FIELDS)}}


@dataclass(frozen=True)
class ChannelProfile:
    competitor: CompetitorInput
    analysis: CompetitorAnalysis
    selected_name: str
    package: ChannelPackage
    schema_version: int = 1

    def __post_init__(self) -> None:
        _required(self.selected_name, "selected_name")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported channel profile schema version")
        for name, kind in (("competitor", CompetitorInput), ("analysis", CompetitorAnalysis),
                           ("package", ChannelPackage)):
            if not isinstance(getattr(self, name), kind):
                raise ValueError(f"{name} must be a {kind.__name__}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelProfile":
        """Reconstruct nested contracts and validate a persisted profile."""
        competitor = dict(data["competitor"])
        competitor["target"] = TargetAudience(**competitor.get("target", {}))
        package = dict(data["package"])
        package["avatar_concepts"] = [AvatarConcept(**item) for item in package["avatar_concepts"]]
        if package.get("banner") is not None:
            package["banner"] = BannerConcept(**package["banner"])
        return cls(competitor=CompetitorInput(**competitor),
                   analysis=CompetitorAnalysis(**data["analysis"]),
                   selected_name=data["selected_name"], package=ChannelPackage(**package),
                   schema_version=data["schema_version"])
