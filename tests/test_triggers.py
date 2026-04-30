"""Trigger detection tests."""
from __future__ import annotations

from scripts.triggers import insight_trigger, ship_trigger, stuck_trigger


def test_ship_fires_on_keyword():
    events = [{"type": "git_commit", "sha": "abc1", "message": "ship voice profile builder", "files_changed": ["a.py"]}]
    out = ship_trigger.detect(events, {})
    assert len(out) == 1
    assert out[0]["type"] == "ship"


def test_ship_fires_on_many_files():
    events = [{"type": "git_commit", "sha": "abc2", "message": "wip stuff", "files_changed": ["a","b","c","d","e","f","CHANGELOG.md"]}]
    out = ship_trigger.detect(events, {})
    assert len(out) == 1


def test_ship_dedupes():
    events = [{"type": "git_commit", "sha": "same", "message": "ship", "files_changed": []}]
    state: dict = {}
    ship_trigger.detect(events, state)
    out = ship_trigger.detect(events, state)
    assert out == []


def test_stuck_fires_on_repeated_errors():
    events = [{"type": "shell_command", "line": "TypeError: wat"} for _ in range(3)]
    out = stuck_trigger.detect(events, {}, threshold=3)
    assert len(out) == 1


def test_stuck_no_fire_below_threshold():
    events = [{"type": "shell_command", "line": "Error: nope"} for _ in range(2)]
    out = stuck_trigger.detect(events, {}, threshold=3)
    assert out == []


def test_insight_fires_on_long_note():
    text = " ".join(["word"] * 60)
    events = [{"type": "note_change", "path": "n.md", "new_text": text}]
    out = insight_trigger.detect(events, {}, min_words=50)
    assert len(out) == 1


def test_insight_fires_on_TIL_keyword():
    events = [{"type": "note_change", "path": "n.md", "new_text": "TIL git log has --since"}]
    out = insight_trigger.detect(events, {}, min_words=50)
    assert len(out) == 1
