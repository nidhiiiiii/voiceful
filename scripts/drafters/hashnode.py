"""Hashnode drafter. Similar to dev.to with broader topical range."""
from __future__ import annotations

from .base import BaseDrafter


class HashnodeDrafter(BaseDrafter):
    platform = "hashnode"

    def max_tokens(self) -> int:
        return 2000

    def platform_constraints(self) -> str:
        return """
PLATFORM: Hashnode (developer audience, technical blog)
HARD CONSTRAINTS:
- 500-1500 words.
- Open with a concrete moment or observation, not a definition.
- Code in fenced blocks with language tags.
- Use ## headings, three max.
- Specific details over generalities.
- BANNED: "let's break it down", "happy coding", emoji decoration, hashtag sections.
""".strip()
