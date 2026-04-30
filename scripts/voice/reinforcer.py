"""Reinforcement: capture user edits and update profile periodically."""
from __future__ import annotations

import logging
from difflib import unified_diff
from pathlib import Path
from typing import Any

from ..storage.history_store import all_drafts
from ..storage.voice_store import load_profile_dict, save_profile

log = logging.getLogger(__name__)


def diff_text(original: str, edited: str) -> str:
    return "\n".join(unified_diff(original.splitlines(), edited.splitlines(), lineterm=""))


def summarize_edits(history_path: Path) -> dict[str, Any]:
    edits = []
    for d in all_drafts(history_path):
        if d.get("user_action") == "edited_then_approved" and d.get("user_edit_text"):
            edits.append({
                "original": d.get("draft_text", ""),
                "edited": d.get("user_edit_text", ""),
            })
    common = []
    for e in edits[-30:]:
        if len(e["edited"]) < len(e["original"]) - 20:
            common.append("shortens output")
        if "i think" in e["original"].lower() and "i think" not in e["edited"].lower():
            common.append("removes 'I think'")
        if "tbh" in e["edited"].lower() and "tbh" not in e["original"].lower():
            common.append("adds 'tbh'")
    return {
        "edits_captured": len(edits),
        "common_user_edits": list(dict.fromkeys(common))[:10],
    }


def refine_profile(profile_path: Path, history_path: Path) -> dict:
    profile = load_profile_dict(profile_path)
    profile["edit_history_summary"] = summarize_edits(history_path)
    save_profile(profile_path, profile)
    log.info("Refined profile with %d edits", profile["edit_history_summary"]["edits_captured"])
    return profile
