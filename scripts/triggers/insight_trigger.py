"""Insight trigger. Fires on substantial new entries in notes files."""
from __future__ import annotations

import re
from typing import Any

INSIGHT_KEYWORDS = re.compile(r"(?i)\b(TIL|today i learned|learned that|huh|didn't know|interesting|realized)\b")


def detect(events: list[dict[str, Any]], state: dict[str, Any] | None = None, min_words: int = 50) -> list[dict[str, Any]]:
    if state is None:
        state = {}
    out: list[dict[str, Any]] = []
    seen = set(state.get("insight_seen", []))

    for ev in events:
        if ev.get("type") != "note_change":
            continue
        text = ev.get("new_text", "")
        word_count = len(text.split())
        if word_count < min_words and not INSIGHT_KEYWORDS.search(text):
            continue
        sig = f"{ev.get('path','')}:{hash(text) & 0xffffff}"
        if sig in seen:
            continue
        out.append({
            "type": "insight",
            "context": f"new note in {ev.get('path','')}: {text[:200]}",
            "raw_signal": {"path": ev.get("path"), "text": text, "word_count": word_count},
        })
        seen.add(sig)

    state["insight_seen"] = list(seen)[-200:]
    return out
