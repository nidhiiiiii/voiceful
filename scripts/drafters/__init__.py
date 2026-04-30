"""Drafter registry."""
from .base import BaseDrafter
from .devto import DevtoDrafter
from .hashnode import HashnodeDrafter
from .linkedin import LinkedInDrafter
from .medium import MediumDrafter
from .twitter import TwitterDrafter

DRAFTERS: dict[str, type[BaseDrafter]] = {
    "twitter": TwitterDrafter,
    "linkedin": LinkedInDrafter,
    "medium": MediumDrafter,
    "devto": DevtoDrafter,
    "hashnode": HashnodeDrafter,
}


def get_drafter(platform: str, profile, llm) -> BaseDrafter:
    cls = DRAFTERS.get(platform)
    if not cls:
        raise ValueError(f"Unknown platform: {platform}. Known: {list(DRAFTERS)}")
    return cls(profile, llm)
