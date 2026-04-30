"""Voice authenticity hard-rules test. Saves outputs to tests/output/ for human review."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

OUTPUT = Path("tests/output")


@pytest.mark.skipif(os.environ.get("VOICEFUL_RUN_LIVE_TESTS") != "1",
                    reason="Set VOICEFUL_RUN_LIVE_TESTS=1 to run authenticity test against real LLM.")
def test_voice_authenticity_hard_rules():
    from scripts.config import load_config
    from scripts.drafters import get_drafter
    from scripts.llm_client import make_client
    from scripts.voice.profile_loader import load_profile

    cfg = load_config()
    profile = load_profile(cfg.voice_profile_path)
    llm = make_client(cfg)

    prompts = [
        ("ship", "shipped voiceful, the agent watches your repo and drafts tweets in your voice"),
        ("stuck", "spent 90 min on what turned out to be a typo in a config file"),
        ("insight", "TIL git log has --since with relative dates like 2.weeks"),
        ("opinion", "the moat for ai tools is context, not the model"),
        ("ship", "deleted 800 lines of dead code today"),
        ("stuck", "test passes locally fails in CI for the third time today"),
        ("insight", "telegram inline keyboards eat callbacks if your handler raises"),
        ("opinion", "your CI pipeline is not the bottleneck, your code review is"),
        ("ship", "got the voice profile builder to work, batched 50 samples per call"),
        ("observation", "ten people asked me today if voiceful uses an LLM. the answer is yes but it's not the point"),
    ]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out_lines = ["# Voice authenticity samples\n", f"Profile built: {profile.raw.get('built_at')}\n"]
    avoid = profile.characteristics.get("avoid_words", [])

    for trig, ctx in prompts:
        drafter = get_drafter("twitter", profile, llm)
        text = drafter.draft({"type": trig, "context": ctx, "raw_signal": ctx})
        out_lines.append(f"\n## [{trig}] {ctx}\n\n{text}\n")
        assert "—" not in text, f"em-dash leaked: {text!r}"
        assert "–" not in text, f"en-dash leaked: {text!r}"
        for w in avoid:
            assert w.lower() not in text.lower(), f"avoid word {w!r} leaked: {text!r}"

    (OUTPUT / "voice_samples.md").write_text("\n".join(out_lines))
