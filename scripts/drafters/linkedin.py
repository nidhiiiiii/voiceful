"""LinkedIn drafter."""
from __future__ import annotations

from .base import BaseDrafter


class LinkedInDrafter(BaseDrafter):
    platform = "linkedin"

    def max_tokens(self) -> int:
        return 600

    def platform_constraints(self) -> str:
        return """
PLATFORM: LinkedIn
HARD CONSTRAINTS:
- 100-300 words ideal. Hard cap 350.
- Open with a SPECIFIC moment or observation, not a generic statement. No "In today's world".
- First-person, not corporate-speak.
- Short paragraphs. Whitespace between them. Max 3 sentences per paragraph.
- End with a brief takeaway, NOT a question or call-to-action.
- BANNED words: synergy, leverage, ecosystem, journey, passionate, excited, thrilled, robust, seamless, empower, navigate.
- BANNED openers: "I'm thrilled to announce", "I'm excited to share".
- NO emoji unless the writer's training corpus uses them.
- NO single-word emphasis lines ("Resilience.\\n\\nGrit.\\n\\nFocus."). Outright forbidden.
- Match the writer's directness. Don't soften their voice for "the platform".
""".strip()
