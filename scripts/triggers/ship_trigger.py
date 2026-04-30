"""Ship trigger. Detects when a commit looks like a shipped feature."""
from __future__ import annotations

import re
from typing import Any

SHIP_KEYWORDS = re.compile(
    r"\b(ship|shipped|release|releasing|deploy|deployed|launch|launched|"
    r"v\d+(\.\d+)*|done|complete|finish|merge|tagged|publish|announce)\b",
    re.IGNORECASE,
)


def detect(events: list[dict[str, Any]], state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if state is None:
        state = {}
    seen = set(state.get("ship_seen_shas", []))
    out: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("type") != "git_commit":
            continue
        sha = ev.get("sha", "")
        if sha in seen:
            continue
        msg = ev.get("message", "")
        files_changed = ev.get("files_changed", []) or []
        score = 0
        if SHIP_KEYWORDS.search(msg):
            score += 2
        if len(files_changed) >= 5:
            score += 1
        if any(f.lower().startswith("changelog") or "release" in f.lower() for f in files_changed):
            score += 2
        if score >= 2:
            out.append({
                "type": "ship",
                "context": f'commit {sha[:8]}: "{msg}"',
                "raw_signal": {
                    "sha": sha,
                    "message": msg,
                    "files_changed": files_changed[:10],
                    "diff_summary": ev.get("diff_summary", ""),
                    "repo": ev.get("repo"),
                },
            })
            seen.add(sha)
    state["ship_seen_shas"] = list(seen)[-200:]
    return out
