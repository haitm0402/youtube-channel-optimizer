"""Domain data contracts and strict AI response factories."""
from .channel import (
    AvatarConcept, BannerConcept, ChannelNameResult, ChannelPackage, ChannelProfile,
    CompetitorAnalysis, CompetitorInput, NameCandidate, NameCategory, TargetAudience,
)

from .manual import ChannelPackageV1, WorkflowSession, WorkflowState

__all__ = [
    "ChannelPackageV1", "WorkflowSession", "WorkflowState",
    "AvatarConcept", "BannerConcept", "ChannelNameResult", "ChannelPackage", "ChannelProfile",
    "CompetitorAnalysis", "CompetitorInput", "NameCandidate", "NameCategory", "TargetAudience",
]
