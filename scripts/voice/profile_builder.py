"""Voice profile builder. Statistical features + batched LLM extraction + few-shot selection."""
from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..llm_client import LLMClient
from ..storage.voice_store import save_profile
from .artifacts import Sample, load_training_dir
from .stats import LLM_CLICHES, compute_stats

log = logging.getLogger(__name__)

VOICE_EXTRACTION_SYSTEM = """You analyze a writer's voice from their authentic samples.
You return strict JSON. No prose, no commentary, no markdown fences.
You never invent traits not visible in the samples.
You never use em-dashes (—) or en-dashes (–) anywhere in your output."""

VOICE_EXTRACTION_USER_TEMPLATE = """Analyze the writing samples below.

Return JSON with EXACTLY these keys:
{{
  "formality": one of ["formal", "professional", "casual_technical", "casual", "very_informal"],
  "humor": one of ["none", "dry", "self_deprecating", "playful", "sarcastic", "earnest"],
  "directness": one of ["very_indirect", "indirect", "balanced", "direct", "very_direct"],
  "first_person_rate": float 0.0-1.0,
  "characteristic_phrases": [up to 10 short phrases this writer actually uses repeatedly],
  "avoid_words": [up to 10 LLM-cliche words this writer NEVER uses but a generic LLM would],
  "tone_summary": one sentence describing the voice
}}

Samples (one per line, separated by ---):

{samples}
"""

FEW_SHOT_SELECT_SYSTEM = """You select few-shot examples that best represent a writer's voice
across different post contexts. You return strict JSON only. No commentary."""

FEW_SHOT_SELECT_USER_TEMPLATE = """From these samples, pick {n} that best represent the writer's
voice across diverse contexts (shipping, stuck on bug, insight learned, observation, opinion).

For each chosen sample, output:
{{
  "context": one of ["shipped feature", "stuck on bug", "insight learned", "observation", "opinion", "general"],
  "platform": "twitter" if <= 280 chars else "linkedin",
  "post": the exact sample text, unmodified
}}

Return JSON array.

Samples (numbered):
{samples}
"""

BATCH_SIZE = 50
MAX_BATCHES = 6


def _batch(samples: list[Sample], size: int) -> list[list[Sample]]:
    return [samples[i:i + size] for i in range(0, len(samples), size)]


def _extract_json(text: str) -> Any:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        raise


def _merge_attributes(results: list[dict]) -> dict:
    if not results:
        return {}
    from collections import Counter

    def mode(key: str) -> str:
        c = Counter(r.get(key, "") for r in results if r.get(key))
        return c.most_common(1)[0][0] if c else ""

    phrases = Counter()
    avoids = Counter()
    for r in results:
        for p in r.get("characteristic_phrases", []) or []:
            phrases[p.lower().strip()] += 1
        for w in r.get("avoid_words", []) or []:
            avoids[w.lower().strip()] += 1
    fp_rates = [r.get("first_person_rate") for r in results if isinstance(r.get("first_person_rate"), (int, float))]
    summary = next((r.get("tone_summary") for r in results if r.get("tone_summary")), "")
    return {
        "formality": mode("formality"),
        "humor": mode("humor"),
        "directness": mode("directness"),
        "first_person_rate": round(sum(fp_rates) / len(fp_rates), 2) if fp_rates else 0.5,
        "characteristic_phrases": [p for p, _ in phrases.most_common(15)],
        "avoid_words": [w for w, _ in avoids.most_common(15)],
        "tone_summary": summary,
    }


def _select_few_shots_heuristic(samples: list[Sample], n: int = 12) -> list[dict]:
    """Cheap fallback: pick diverse samples by length and source."""
    by_source: dict[str, list[Sample]] = {}
    for s in samples:
        by_source.setdefault(s.source, []).append(s)
    picks: list[Sample] = []
    rng = random.Random(0)
    for src in ["tweet", "commit", "notes", "blog", "readme"]:
        bucket = by_source.get(src, [])
        rng.shuffle(bucket)
        picks.extend(bucket[:max(1, n // 5)])
    picks = picks[:n]
    out = []
    for s in picks:
        platform = "twitter" if len(s.text) <= 280 else "linkedin"
        context = {
            "commit": "shipped feature",
            "tweet": "general",
            "notes": "insight learned",
            "blog": "observation",
            "readme": "observation",
        }.get(s.source, "general")
        out.append({"context": context, "platform": platform, "post": s.text})
    return out


def _select_few_shots_llm(samples: list[Sample], llm: LLMClient, n: int = 12) -> list[dict]:
    pool = samples[:60]
    numbered = "\n".join(f"{i+1}. {s.text}" for i, s in enumerate(pool))
    user = FEW_SHOT_SELECT_USER_TEMPLATE.format(n=n, samples=numbered)
    try:
        raw = llm.complete(system=FEW_SHOT_SELECT_SYSTEM, user=user, max_tokens=2048)
        data = _extract_json(raw)
        if isinstance(data, list):
            return data[:n]
    except Exception as e:
        log.warning("LLM few-shot select failed, using heuristic: %s", e)
    return _select_few_shots_heuristic(samples, n)


def _extract_voice_attributes(samples: list[Sample], llm: LLMClient) -> dict:
    batches = _batch(samples, BATCH_SIZE)[:MAX_BATCHES]
    results = []
    for i, batch in enumerate(batches):
        joined = "\n---\n".join(s.text for s in batch)
        if len(joined) > 18000:
            joined = joined[:18000]
        user = VOICE_EXTRACTION_USER_TEMPLATE.format(samples=joined)
        try:
            raw = llm.complete(system=VOICE_EXTRACTION_SYSTEM, user=user, max_tokens=1024)
            data = _extract_json(raw)
            if isinstance(data, dict):
                results.append(data)
                log.info("Extracted voice from batch %d/%d", i + 1, len(batches))
        except Exception as e:
            log.warning("Voice extraction batch %d failed: %s", i, e)
    return _merge_attributes(results)


def build_profile(
    training_dir: Path,
    output_path: Path,
    llm: LLMClient,
    author_email: str | None = None,
) -> dict:
    samples = load_training_dir(training_dir, author_email=author_email)
    if not samples:
        raise RuntimeError(
            f"No training samples found in {training_dir}. "
            "Add .txt/.md/.json files or a repos/ subfolder."
        )

    stats = compute_stats(samples)
    attrs = _extract_voice_attributes(samples, llm)

    seed_avoid = stats["characteristics"].pop("avoid_words_seed", LLM_CLICHES)
    avoid_words = list(dict.fromkeys((attrs.get("avoid_words") or []) + seed_avoid))[:20]

    few_shots = _select_few_shots_llm(samples, llm, n=12)

    profile: dict[str, Any] = {
        "version": "1.0",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source_stats": stats["source_stats"],
        "characteristics": {
            **stats["characteristics"],
            "common_phrases": attrs.get("characteristic_phrases", []),
            "avoid_words": avoid_words,
            "voice_attributes": {
                "formality": attrs.get("formality", "casual_technical"),
                "humor": attrs.get("humor", "dry"),
                "directness": attrs.get("directness", "direct"),
                "first_person_rate": attrs.get("first_person_rate", 0.5),
                "tone_summary": attrs.get("tone_summary", ""),
            },
        },
        "few_shot_examples": few_shots,
        "edit_history_summary": {
            "edits_captured": 0,
            "common_user_edits": [],
        },
    }

    save_profile(output_path, profile)
    log.info("Saved voice profile to %s", output_path)
    return profile
