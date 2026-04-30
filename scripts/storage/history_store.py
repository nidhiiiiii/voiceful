"""History store. Records every draft, edit, and approval action."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"drafts": []}
    with path.open() as f:
        return json.load(f)


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_draft(path: Path, entry: dict[str, Any]) -> None:
    data = _read(path)
    entry.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    data["drafts"].append(entry)
    _write(path, data)


def update_draft(path: Path, draft_id: str, fields: dict[str, Any]) -> None:
    data = _read(path)
    for d in data["drafts"]:
        if d.get("draft_id") == draft_id:
            d.update(fields)
            break
    _write(path, data)


def get_draft(path: Path, draft_id: str) -> dict[str, Any] | None:
    for d in _read(path)["drafts"]:
        if d.get("draft_id") == draft_id:
            return d
    return None


def all_drafts(path: Path) -> list[dict[str, Any]]:
    return _read(path)["drafts"]


def last_approved_timestamp(path: Path) -> str | None:
    data = _read(path)
    approved = [d for d in data["drafts"] if d.get("user_action") in ("approved", "edited_then_approved")]
    if not approved:
        return None
    return max(d.get("approved_at", d.get("created_at", "")) for d in approved)
