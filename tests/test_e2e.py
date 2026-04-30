"""End-to-end pipeline test with stubbed LLM and Telegram."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from scripts.config import Config
from scripts.drafters import get_drafter
from scripts.storage import history_store, queue_store
from scripts.triggers import ship_trigger
from scripts.voice.profile_loader import VoiceProfile


class StubLLM:
    def complete(self, system, user, max_tokens=1024):
        return "shipped a thing. it works. moving on."


def _profile():
    return VoiceProfile(raw={
        "version": "1.0",
        "characteristics": {
            "casing": {"sentence_start_lowercase_rate": 0.7},
            "punctuation": {"uses_em_dash": False, "uses_en_dash": False, "uses_semicolon": False,
                            "exclamation_rate_per_100_sentences": 1, "question_rate_per_100_sentences": 5},
            "emoji": {"uses_emoji": False, "common_emojis": [], "rate_per_post": 0.0},
            "hedging": {"rate": "low", "common_hedges": []},
            "sentence_length": {"median_words": 12, "p90_words": 28},
            "common_phrases": [], "avoid_words": [],
            "voice_attributes": {"formality": "casual_technical", "humor": "dry", "directness": "direct"},
        },
        "few_shot_examples": [],
    })


def test_full_pipeline(tmp_path: Path):
    cfg = Config(home=tmp_path, raw={
        "training_dir": str(tmp_path / "training"),
        "watchers": {"repos": [], "notes_dir": str(tmp_path), "shell_history": str(tmp_path / "h"), "workspace_dirs": []},
        "platforms": {"twitter": {"enabled": True}}, "channels": {"telegram": {"bot_token": "", "chat_id": ""}, "discord": {"enabled": False}},
        "triggers": {"insight": {"min_word_count": 50}, "idle": {"days_threshold": 3}, "ship": {"enabled": True}, "stuck": {"enabled": True}, "asked": {"enabled": True}},
        "llm": {"provider": "dummy", "api_key": ""},
        "user": {"name": "test"},
    })

    profile = _profile()
    llm = StubLLM()

    events = [{"type": "git_commit", "sha": "deadbeef", "message": "ship voice profile builder", "files_changed": ["a.py"]}]
    triggers = ship_trigger.detect(events, {})
    assert len(triggers) == 1

    drafter = get_drafter("twitter", profile, llm)
    text = drafter.draft(triggers[0])
    assert text
    assert "—" not in text

    draft_id = str(uuid.uuid4())
    draft = {"draft_id": draft_id, "platform": "twitter", "text": text, "trigger": "ship", "context": "x"}
    queue_store.enqueue(cfg.queue_path, draft)
    history_store.append_draft(cfg.history_path, {"draft_id": draft_id, "platform": "twitter", "draft_text": text, "user_action": "pending"})

    assert queue_store.get_pending(cfg.queue_path, draft_id) is not None

    history_store.update_draft(cfg.history_path, draft_id, {"user_action": "approved", "approved_at": "2026-04-30T10:00:00Z"})
    queue_store.dequeue(cfg.queue_path, draft_id)

    drafts = history_store.all_drafts(cfg.history_path)
    assert drafts[0]["user_action"] == "approved"
    assert queue_store.get_pending(cfg.queue_path, draft_id) is None
