"""Idle trigger. Fires when no posts have been approved for N days."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage.history_store import last_approved_timestamp


def detect(history_path: Path, days_threshold: int = 3) -> list[dict[str, Any]]:
    last = last_approved_timestamp(history_path)
    if not last:
        return [{
            "type": "idle",
            "context": "no posts approved yet. consider drafting one.",
            "raw_signal": {"last_approved": None},
        }]
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return []
    now = datetime.now(timezone.utc)
    days = (now - last_dt).days
    if days < days_threshold:
        return []
    return [{
        "type": "idle",
        "context": f"last approved post was {days} days ago",
        "raw_signal": {"last_approved": last, "days": days},
    }]
