"""Tests for voice profile statistical analyzer."""
from __future__ import annotations

from pathlib import Path

from scripts.voice.artifacts import Sample, load_training_dir
from scripts.voice.stats import compute_stats


def test_stats_basic():
    samples = [
        Sample("shipped a thing today.", "tweet", "x"),
        Sample("spent 3 hours on a typo.", "tweet", "x"),
        Sample("the bug was in the test.", "tweet", "x"),
    ]
    stats = compute_stats(samples)
    assert stats["source_stats"]["tweet_count"] == 3
    assert stats["characteristics"]["punctuation"]["uses_em_dash"] is False
    assert stats["characteristics"]["emoji"]["uses_emoji"] is False


def test_em_dash_detected():
    samples = [Sample("this — that", "tweet", "x")]
    stats = compute_stats(samples)
    assert stats["characteristics"]["punctuation"]["uses_em_dash"] is True


def test_emoji_detected():
    samples = [Sample("shipped 🚀", "tweet", "x")]
    stats = compute_stats(samples)
    assert stats["characteristics"]["emoji"]["uses_emoji"] is True


def test_load_training_dir(tmp_path: Path):
    (tmp_path / "tweets.txt").write_text("one tweet here\nanother one here\n")
    (tmp_path / "post.md").write_text("# title\n\na blog post body that is longer than a tweet by far.\n")
    samples = load_training_dir(tmp_path)
    assert len(samples) >= 2
    assert any(s.source == "tweet" for s in samples)
