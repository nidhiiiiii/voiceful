"""Medium long-form drafter."""
from __future__ import annotations

from .base import BaseDrafter


class MediumDrafter(BaseDrafter):
    platform = "medium"

    def max_tokens(self) -> int:
        return 2000

    def platform_constraints(self) -> str:
        return """
PLATFORM: Medium (long-form essay)
HARD CONSTRAINTS:
- 500-1500 words.
- Open with a specific moment or scene, not a thesis statement.
- Use markdown headings (##) sparingly. Max 3 sections.
- Code blocks must use triple-backtick fenced blocks with the language tag.
- No SEO-bait subheaders.
- End with a single concrete takeaway, not a summary recap.
- BANNED phrases: "in this article we will", "let's dive in", "without further ado", "the bottom line".
""".strip()
