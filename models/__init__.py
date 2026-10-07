"""Domain data contracts and strict AI response factories."""
from .channel import (
    AvatarConcept, BannerConcept, ChannelNameResult, ChannelPackage, ChannelProfile,
    CompetitorAnalysis, CompetitorInput, NameCandidate, NameCategory, TargetAudience,
)

from .manual import ChannelPackageV1, WorkflowSession, WorkflowState
from .release_planner import ReleaseChannel, ReleaseItem, ReleasePlan, ReleaseStatus

__all__ = [
    "ChannelPackageV1", "WorkflowSession", "WorkflowState",
    "ReleaseChannel", "ReleaseItem", "ReleasePlan", "ReleaseStatus",
    "AvatarConcept", "BannerConcept", "ChannelNameResult", "ChannelPackage", "ChannelProfile",
    "CompetitorAnalysis", "CompetitorInput", "NameCandidate", "NameCategory", "TargetAudience",
]
