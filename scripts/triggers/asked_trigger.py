"""Asked trigger. Direct user invocation via Telegram /draft <topic>."""
from __future__ import annotations

from typing import Any


def make_event(topic: str, platform: str = "twitter") -> dict[str, Any]:
    return {
        "type": "asked",
        "context": topic,
        "raw_signal": {"topic": topic, "platform": platform},
    }
