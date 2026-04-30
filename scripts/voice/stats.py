"""Statistical analysis of writing samples. No LLM."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .artifacts import Sample

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F9FF]"
)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
HEDGES = ["i think", "kinda", "sort of", "maybe", "i guess", "probably", "i feel like", "tbh"]
LLM_CLICHES = [
    "delve", "leverage", "moreover", "furthermore", "additionally", "elevate",
    "unlock", "navigate", "embark", "in conclusion", "it's worth noting",
    "in today's", "fast-paced", "synergy", "ecosystem", "passionate", "thrilled",
    "excited to announce", "game-changer", "robust", "seamless", "cutting-edge",
    "harness", "empower", "pivotal", "paradigm",
]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def compute_stats(samples: list[Sample]) -> dict[str, Any]:
    if not samples:
        return {}

    all_text = "\n".join(s.text for s in samples)
    sentences = []
    for s in samples:
        sentences.extend(_sentences(s.text))

    sentence_starts = [s for s in sentences if s and s[0].isalpha()]
    lower_starts = sum(1 for s in sentence_starts if s[0].islower())
    lower_rate = lower_starts / len(sentence_starts) if sentence_starts else 0.0

    em_dash_count = all_text.count("—")
    en_dash_count = all_text.count("–")
    semicolon_count = all_text.count(";")
    excl_count = all_text.count("!")
    q_count = all_text.count("?")
    n_sent = max(1, len(sentences))

    emojis = EMOJI_RE.findall(all_text)
    emoji_counter = Counter(emojis)

    hedges_lower = all_text.lower()
    hedge_hits = {h: hedges_lower.count(h) for h in HEDGES}
    hedge_total = sum(hedge_hits.values())
    n_words = len(_words(all_text)) or 1
    hedge_rate = hedge_total / n_words

    if hedge_rate > 0.01:
        hedge_level = "high"
    elif hedge_rate > 0.003:
        hedge_level = "medium"
    else:
        hedge_level = "low"

    sentence_lengths = sorted(len(s.split()) for s in sentences if s)
    median_words = sentence_lengths[len(sentence_lengths) // 2] if sentence_lengths else 0
    p90_words = sentence_lengths[int(len(sentence_lengths) * 0.9)] if sentence_lengths else 0

    fp_count = len(re.findall(r"\b[Ii]\b", all_text))
    first_person_rate = min(1.0, fp_count / max(1, len(sentences)))

    avoid = [w for w in LLM_CLICHES if w not in hedges_lower]

    counts = {
        "tweet_count": sum(1 for s in samples if s.source == "tweet"),
        "commit_count": sum(1 for s in samples if s.source == "commit"),
        "blog_post_count": sum(1 for s in samples if s.source == "blog"),
        "readme_count": sum(1 for s in samples if s.source == "readme"),
        "notes_count": sum(1 for s in samples if s.source == "notes"),
        "total_words": sum(len(s.text.split()) for s in samples),
    }

    return {
        "source_stats": counts,
        "characteristics": {
            "casing": {
                "sentence_start_lowercase_rate": round(lower_rate, 3),
                "all_caps_for_emphasis": False,
                "title_case_in_headers": False,
            },
            "punctuation": {
                "uses_em_dash": em_dash_count > 0,
                "uses_en_dash": en_dash_count > 0,
                "uses_semicolon": semicolon_count > 0,
                "exclamation_rate_per_100_sentences": round(100 * excl_count / n_sent, 1),
                "question_rate_per_100_sentences": round(100 * q_count / n_sent, 1),
            },
            "emoji": {
                "uses_emoji": len(emojis) > 0,
                "common_emojis": [e for e, _ in emoji_counter.most_common(5)],
                "rate_per_post": round(len(emojis) / max(1, len(samples)), 3),
            },
            "hedging": {
                "rate": hedge_level,
                "common_hedges": [h for h, c in hedge_hits.items() if c > 0],
            },
            "sentence_length": {
                "median_words": median_words,
                "p90_words": p90_words,
            },
            "first_person_rate": round(first_person_rate, 2),
            "avoid_words_seed": avoid,
        },
    }
