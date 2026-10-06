"""Validated input, intermediate results, and versioned export contracts."""
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlsplit


def _required(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _strings(values: list[str], name: str) -> None:
    if not isinstance(values, list):
        raise ValueError(f"{name} must be a list")
    for value in values:
        _required(value, name)


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


@dataclass(frozen=True)
class CompetitorInput:
    url: str
    avatar_reference: str
    description: str
    target: TargetAudience = field(default_factory=TargetAudience)

    def __post_init__(self) -> None:
        _required(self.url, "url")
        parsed = urlsplit(self.url)
        if (parsed.scheme != "https" or parsed.hostname not in
                {"youtube.com", "www.youtube.com", "m.youtube.com"}
                or not parsed.path.strip("/") or parsed.username or parsed.password):
            raise ValueError("url must be an HTTPS YouTube channel reference")
        _required(self.avatar_reference, "avatar_reference")
        _required(self.description, "description")
        if not isinstance(self.target, TargetAudience):
            raise ValueError("target must be a TargetAudience")


@dataclass(frozen=True)
class CompetitorAnalysis:
    summary: str
    positioning: str
    audience: str
    strengths: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in ("summary", "positioning", "audience"):
            _required(getattr(self, name), name)
        for name in ("strengths", "opportunities"):
            _strings(getattr(self, name), name)


@dataclass(frozen=True)
class NameCandidate:
    name: str
    rationale: str

    def __post_init__(self) -> None:
        _required(self.name, "name")
        _required(self.rationale, "rationale")


@dataclass(frozen=True)
class AvatarConcept:
    concept: str
    prompt: str

    def __post_init__(self) -> None:
        _required(self.concept, "concept")
        _required(self.prompt, "prompt")


@dataclass(frozen=True)
class ChannelPackage:
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

    def __post_init__(self) -> None:
        for name in ("positioning", "banner_concept", "banner_prompt", "description",
                     "thumbnail_visual_guide"):
            _required(getattr(self, name), name)
        if (not isinstance(self.avatar_concepts, list) or len(self.avatar_concepts) != 4
                or not all(isinstance(item, AvatarConcept) for item in self.avatar_concepts)):
            raise ValueError("avatar_concepts must contain exactly four AvatarConcept objects")
        for name in ("channel_keywords", "video_core_keywords", "video_tags", "hashtags", "title_templates"):
            values = getattr(self, name)
            _strings(values, name)
            if not values:
                raise ValueError(f"{name} must contain at least one entry")


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
        return cls(competitor=CompetitorInput(**competitor),
                   analysis=CompetitorAnalysis(**data["analysis"]),
                   selected_name=data["selected_name"], package=ChannelPackage(**package),
                   schema_version=data["schema_version"])
