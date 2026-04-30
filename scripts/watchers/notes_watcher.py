"""Notes watcher. Tracks word-count delta on note files."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..storage.state_store import load_state, save_state

log = logging.getLogger(__name__)


def scan(notes_dir: Path, state_path: Path) -> list[dict[str, Any]]:
    notes_dir = Path(notes_dir).expanduser()
    if not notes_dir.exists():
        return []
    state = load_state(state_path)
    notes_state = state.setdefault("notes", {})
    events: list[dict[str, Any]] = []
    for path in notes_dir.rglob("*"):
        if path.is_dir() or path.name.startswith(".") or path.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        prev_len = notes_state.get(str(path), 0)
        cur_len = len(text)
        if cur_len > prev_len + 200:
            new_text = text[prev_len:]
            events.append({"type": "note_change", "path": str(path), "new_text": new_text})
        notes_state[str(path)] = cur_len
    state["notes"] = notes_state
    save_state(state_path, state)
    return events
