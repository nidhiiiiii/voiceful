"""dev.to drafter. Technical, code-forward."""
from __future__ import annotations

from .base import BaseDrafter


class DevtoDrafter(BaseDrafter):
    platform = "devto"

    def max_tokens(self) -> int:
        return 2000

    def platform_constraints(self) -> str:
        return """
PLATFORM: dev.to (developer audience, technical)
HARD CONSTRAINTS:
- 400-1200 words.
- Open with the concrete problem or symptom, not background.
- Show actual code in fenced blocks with language tags.
- Cover: what broke, why it broke, how it was fixed.
- Use ## headings for sections (Problem, Cause, Fix). Three sections max.
- Be specific. File paths, function names, real error messages welcome.
- BANNED: "happy coding!", "I hope this helps", emoji decoration.
""".strip()
