"""Text-only V1 package and state contracts, separate from legacy image packages."""
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any
from .channel import ChannelNameResult, CompetitorAnalysis, CompetitorInput
from .validation import object_fields, required, strings

PACKAGE_V1_TEXT_FIELDS = {
    "channel_positioning", "channel_description", "thumbnail_direction", "banner_direction", "slogan",
}
PACKAGE_V1_LIST_FIELDS = {
    "channel_keywords", "video_core_keywords", "video_tags", "hashtags", "title_templates",
}


@dataclass(frozen=True)
class ChannelPackageV1:
    channel_positioning: str
    channel_description: str
    channel_keywords: list[str]
    video_core_keywords: list[str]
    video_tags: list[str]
    hashtags: list[str]
    title_templates: list[str]
    thumbnail_direction: str
    banner_direction: str
    slogan: str

    def __post_init__(self) -> None:
        for name in sorted(PACKAGE_V1_TEXT_FIELDS):
            required(getattr(self, name), name)
        for name in sorted(PACKAGE_V1_LIST_FIELDS):
            strings(getattr(self, name), name, nonempty=True)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelPackageV1":
        object_fields(data, PACKAGE_V1_TEXT_FIELDS | PACKAGE_V1_LIST_FIELDS, "ChannelPackageV1")
        return cls(**data)


class WorkflowState(str, Enum):
    INPUT = "INPUT"
    WAITING_FOR_ANALYSIS = "WAITING_FOR_ANALYSIS"
    ANALYSIS_READY = "ANALYSIS_READY"
    WAITING_FOR_NAMES = "WAITING_FOR_NAMES"
    NAMES_READY = "NAMES_READY"
    NAME_SELECTED = "NAME_SELECTED"
    WAITING_FOR_PACKAGE = "WAITING_FOR_PACKAGE"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class WorkflowSession:
    competitor: CompetitorInput
    state: WorkflowState = WorkflowState.INPUT
    analysis: CompetitorAnalysis | None = None
    names: ChannelNameResult | None = None
    selected_name: str | None = None
    package: ChannelPackageV1 | None = None
    pending_prompt: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.competitor, CompetitorInput):
            raise ValueError("competitor must be a CompetitorInput")
        try:
            object.__setattr__(self, "state", WorkflowState(self.state))
        except (TypeError, ValueError) as exc:
            raise ValueError("Unknown workflow state") from exc
        states = list(WorkflowState)
        index = states.index(self.state)
        for name, kind, required_at in (
            ("analysis", CompetitorAnalysis, 2), ("names", ChannelNameResult, 4),
            ("selected_name", str, 5), ("package", ChannelPackageV1, 7),
        ):
            value = getattr(self, name)
            if index >= required_at and not isinstance(value, kind):
                raise ValueError(f"{name} is required in state {self.state.value}")
            if index < required_at and value is not None:
                raise ValueError(f"{name} is not allowed in state {self.state.value}")
        if self.analysis is not None:
            CompetitorAnalysis.from_ai_dict(self.analysis.to_ai_dict())
        if self.names is not None:
            ChannelNameResult.from_ai_dict(self.names.to_ai_dict())
        if self.selected_name is not None:
            required(self.selected_name, "selected_name")
            if self.selected_name not in [item.name for item in self.names.names]:
                raise ValueError("selected_name must exactly match a suggested name")
        if self.package is not None:
            ChannelPackageV1.from_dict(self.package.to_dict())
        waiting = self.state in {WorkflowState.WAITING_FOR_ANALYSIS, WorkflowState.WAITING_FOR_NAMES,
                                 WorkflowState.WAITING_FOR_PACKAGE}
        if waiting:
            required(self.pending_prompt, "pending_prompt")
        elif self.pending_prompt is not None:
            raise ValueError("pending_prompt is only allowed while waiting for a response")

    def to_profile_dict(self) -> dict[str, Any]:
        """Export V1 workflow shape; distinct from the legacy ChannelProfile contract."""
        if self.state != WorkflowState.COMPLETE:
            raise ValueError("Only a COMPLETE workflow can be exported")
        # Revalidate before export because frozen dataclasses still contain mutable lists.
        WorkflowSession(self.competitor, self.state, self.analysis, self.names,
                        self.selected_name, self.package, self.pending_prompt)
        return {"profile_type": "manual_text_v1", "schema_version": 1,
                "competitor": self.competitor.to_prompt_dict(),
                "analysis": self.analysis.to_ai_dict(), "names": self.names.to_ai_dict(),
                "selected_name": self.selected_name, "package": self.package.to_dict()}
