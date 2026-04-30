"""Twitter / X drafter."""
from __future__ import annotations

from .base import BaseDrafter


class TwitterDrafter(BaseDrafter):
    platform = "twitter"

    def max_tokens(self) -> int:
        return 200

    def platform_constraints(self) -> str:
        return """
PLATFORM: Twitter / X
HARD CONSTRAINTS:
- Maximum 280 characters total. If the idea genuinely needs more, split into max 3 numbered tweets separated by a blank line and prefix "1/", "2/", etc.
- Hook in the first 7 words. No throat-clearing ("So,", "Recently,", "I've been thinking").
- No hashtags unless the writer's voice clearly uses them.
- Do NOT end with engagement bait ("what do you think?", "thoughts?", "drop a comment").
- Punchy. No flowery setups. No conclusions.
""".strip()
