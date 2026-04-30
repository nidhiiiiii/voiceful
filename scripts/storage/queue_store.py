"""Queue store. Pending drafts awaiting user approval."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"pending": []}
    with path.open() as f:
        return json.load(f)


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def enqueue(path: Path, draft: dict[str, Any]) -> None:
    data = _read(path)
    data["pending"].append(draft)
    _write(path, data)


def dequeue(path: Path, draft_id: str) -> dict[str, Any] | None:
    data = _read(path)
    found = None
    remaining = []
    for d in data["pending"]:
        if d.get("draft_id") == draft_id and found is None:
            found = d
        else:
            remaining.append(d)
    data["pending"] = remaining
    _write(path, data)
    return found


def list_pending(path: Path) -> list[dict[str, Any]]:
    return _read(path)["pending"]


def get_pending(path: Path, draft_id: str) -> dict[str, Any] | None:
    for d in list_pending(path):
        if d.get("draft_id") == draft_id:
            return d
    return None
