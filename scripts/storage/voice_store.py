"""Voice profile JSON storage."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_profile(path: Path, profile: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


def load_profile_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Voice profile not found at {path}. Run `python -m scripts.main build-profile` first."
        )
    with path.open() as f:
        return json.load(f)
