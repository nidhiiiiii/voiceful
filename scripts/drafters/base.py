"""Abstract drafter. Sanitizes output to enforce hard rules (no em-dashes, etc)."""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from ..llm_client import LLMClient
from ..voice.profile_loader import VoiceProfile

log = logging.getLogger(__name__)

EM_DASH = "—"
EN_DASH = "–"


def sanitize_voice(text: str, profile: VoiceProfile) -> str:
    """Strip hard-banned characters and trim wrapper noise."""
    out = text.strip()
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL | re.IGNORECASE).strip()
    out = re.sub(r"<think>.*$", "", out, flags=re.DOTALL | re.IGNORECASE).strip()
    out = re.sub(r"^```(?:\w+)?\s*", "", out)
    out = re.sub(r"\s*```$", "", out)
    out = re.sub(r"^(here(?:'s| is)|sure|okay|certainly)[^\n]*[:\n]", "", out, flags=re.I).strip()
    out = re.sub(r'^"(.*)"$', r"\1", out, flags=re.S)
    out = out.replace(EM_DASH, ", ").replace(EN_DASH, "-")
    out = re.sub(r"\s+,", ",", out)
    return out.strip()


class BaseDrafter(ABC):
    platform: str = "generic"

    def __init__(self, profile: VoiceProfile, llm: LLMClient):
        self.profile = profile
        self.llm = llm

    @abstractmethod
    def platform_constraints(self) -> str: ...

    def max_tokens(self) -> int:
        return 400

    def draft(self, trigger_event: dict[str, Any]) -> str:
        system = self.profile.to_system_prompt() + "\n\n" + self.platform_constraints()
        few_shots = self.profile.get_few_shots(self.platform, trigger_event.get("type", "general"), n=5)
        user_msg = self._build_user_message(trigger_event, few_shots)
        log.debug("Drafter %s system_chars=%d user_chars=%d", self.platform, len(system), len(user_msg))
        raw = self.llm.complete(system=system, user=user_msg, max_tokens=self.max_tokens())
        out = sanitize_voice(raw, self.profile)
        if out:
            return out

        # Providers sometimes return empty content (or content fully stripped by sanitizer).
        # Retry once with an explicit minimum-output requirement, then fall back to a safe
        # "need more context" message (still grounded, no invented facts).
        retry_user = user_msg + "\n\nIMPORTANT: Output at least one sentence. If you cannot, ask for more context in one sentence."
        raw2 = self.llm.complete(system=system, user=retry_user, max_tokens=self.max_tokens())
        out2 = sanitize_voice(raw2, self.profile)
        if out2:
            return out2
        log.warning("Empty draft after retry. trigger_type=%s platform=%s", trigger_event.get("type"), self.platform)
        return "need a bit more context to draft this. send 1-2 specifics and i’ll rewrite."

    def _build_user_message(self, event: dict[str, Any], few_shots: list[dict[str, Any]]) -> str:
        shots_block = ""
        for ex in few_shots:
            shots_block += f"\n--- example post (do not copy verbatim, match the style) ---\n{ex.get('post','')}\n"
        return f"""Trigger type: {event.get('type','general')}
Context: {event.get('context','')}
Raw signal: {event.get('raw_signal','')}

{shots_block}

Write ONE post for {self.platform} grounded ONLY in the context above. If the context is thin, write tighter. Do NOT invent details. Output the post text only. No preamble, no quotes, no commentary, no markdown fences."""
