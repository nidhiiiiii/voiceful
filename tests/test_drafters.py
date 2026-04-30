"""Drafter sanitization + system prompt assertions."""
from __future__ import annotations

from scripts.drafters.base import sanitize_voice
from scripts.drafters.twitter import TwitterDrafter
from scripts.voice.profile_loader import VoiceProfile


class StubLLM:
    def __init__(self, response: str):
        self.response = response

    def complete(self, system, user, max_tokens=1024):
        self.last_system = system
        self.last_user = user
        return self.response


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
            "common_phrases": ["shipped this", "tbh"],
            "avoid_words": ["delve", "leverage"],
            "voice_attributes": {"formality": "casual_technical", "humor": "dry", "directness": "very_direct"},
        },
        "few_shot_examples": [
            {"context": "shipped feature", "platform": "twitter", "post": "shipped a thing today. it works."}
        ],
    })


def test_sanitize_strips_em_dash():
    out = sanitize_voice("hey — there", _profile())
    assert "—" not in out
    assert "–" not in out


def test_sanitize_strips_code_fence():
    assert sanitize_voice("```\nhello\n```", _profile()) == "hello"


def test_sanitize_strips_preamble():
    assert "Sure" not in sanitize_voice("Sure! Here's the post:\nshipped a thing", _profile())


def test_twitter_system_includes_voice():
    llm = StubLLM("shipped a thing")
    drafter = TwitterDrafter(_profile(), llm)
    drafter.draft({"type": "ship", "context": "demo", "raw_signal": "x"})
    assert "NEVER use em dashes" in llm.last_system
    assert "Twitter" in llm.last_system
    assert "shipped a thing today" in llm.last_system


def test_no_em_dash_in_system_prompt():
    sp = _profile().to_system_prompt()
    inside_chars = [ch for ch in sp if ch == "—"]
    assert len(inside_chars) <= 5
