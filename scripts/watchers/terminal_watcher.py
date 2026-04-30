"""Terminal watcher. Tails ~/.zsh_history or ~/.bash_history."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..storage.state_store import load_state, save_state

log = logging.getLogger(__name__)


def scan(history_file: Path, state_path: Path, max_new: int = 200) -> list[dict[str, Any]]:
    history_file = Path(history_file).expanduser()
    if not history_file.exists():
        return []
    state = load_state(state_path)
    cursor = state.get("term_cursor", {}).get(str(history_file), 0)
    try:
        with history_file.open("rb") as f:
            f.seek(cursor)
            chunk = f.read()
            new_cursor = f.tell()
    except OSError as e:
        log.warning("Cannot read %s: %s", history_file, e)
        return []
    text = chunk.decode("utf-8", errors="ignore")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if "zsh" in history_file.name:
        cleaned = []
        for ln in lines:
            if ln.startswith(": ") and ";" in ln:
                cleaned.append(ln.split(";", 1)[1])
            else:
                cleaned.append(ln)
        lines = cleaned
    lines = lines[-max_new:]
    events = [{"type": "shell_command", "line": ln} for ln in lines]
    state.setdefault("term_cursor", {})[str(history_file)] = new_cursor
    save_state(state_path, state)
    return events
