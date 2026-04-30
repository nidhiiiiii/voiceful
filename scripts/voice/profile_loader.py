"""Voice profile loader. Builds the system prompt that goes to the drafter LLM."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..storage.voice_store import load_profile_dict


@dataclass
class VoiceProfile:
    raw: dict[str, Any]

    @property
    def characteristics(self) -> dict[str, Any]:
        return self.raw.get("characteristics", {})

    @property
    def few_shots(self) -> list[dict[str, Any]]:
        return self.raw.get("few_shot_examples", [])

    def to_system_prompt(self) -> str:
        c = self.characteristics
        casing = c.get("casing", {})
        punct = c.get("punctuation", {})
        emoji = c.get("emoji", {})
        hedging = c.get("hedging", {})
        sl = c.get("sentence_length", {})
        va = c.get("voice_attributes", {})

        lower_rate = casing.get("sentence_start_lowercase_rate", 0)
        if lower_rate > 0.5:
            casing_line = f"Lowercase sentence starts ~{int(lower_rate * 100)}% of the time. Don't capitalize sentence starts."
        elif lower_rate > 0.15:
            casing_line = f"Mixed casing. ~{int(lower_rate * 100)}% of sentences start lowercase."
        else:
            casing_line = "Capitalize sentence starts as normal."

        emoji_line = (
            f"Emoji rate {emoji.get('rate_per_post', 0)} per post. Common: {' '.join(emoji.get('common_emojis', []))}"
            if emoji.get("uses_emoji")
            else "ZERO emojis. Do not add any."
        )

        phrases = c.get("common_phrases", [])
        avoid = c.get("avoid_words", [])

        few_shot_block = ""
        for ex in self.few_shots[:8]:
            few_shot_block += f"\n[{ex.get('context','general')} / {ex.get('platform','twitter')}]\n{ex.get('post','')}\n"

        return f"""You write in a specific writer's voice. Match it exactly. The writer will reject anything that sounds generic.

CASING: {casing_line}

PUNCTUATION:
- NEVER use em dashes (—). Not even one. This is a hard rule.
- NEVER use en dashes (–). Use commas, periods, or parentheses instead.
- {'Semicolons are fine but rare.' if punct.get('uses_semicolon') else 'Avoid semicolons.'}
- ~{punct.get('exclamation_rate_per_100_sentences', 0)} exclamations per 100 sentences. Use sparingly.
- ~{punct.get('question_rate_per_100_sentences', 0)} questions per 100 sentences.

EMOJI: {emoji_line}

VOICE: formality={va.get('formality','casual_technical')}, humor={va.get('humor','dry')}, directness={va.get('directness','direct')}.
{va.get('tone_summary', '').strip()}

HEDGING: {hedging.get('rate', 'low')}. Common hedges actually used: {', '.join(hedging.get('common_hedges', [])) or 'none'}. Do not invent new hedges.

PHRASES THE WRITER USES (use sparingly, in context, never all in one post): {', '.join(phrases) or 'none specified'}

WORDS THE WRITER NEVER USES (do not use): {', '.join(avoid) or 'none'}

SENTENCE LENGTH: median {sl.get('median_words', 12)} words. p90 {sl.get('p90_words', 28)} words. Don't write long flowing sentences.

ANTI-AI RULES:
- Never write: "delve", "leverage", "moreover", "furthermore", "additionally", "elevate", "unlock", "embark", "navigate the complexities", "in conclusion", "in today's fast-paced", "it's worth noting that", "I'm thrilled to announce".
- No three-word emphasis lines (e.g. "Resilience.\\n\\nGrit.\\n\\nFocus.")
- No engagement bait ("what do you think?", "thoughts?", "drop a comment").
- No hashtag spam. Only use hashtags if the few-shot examples contain them.
- Never invent facts about the user. If the trigger context lacks signal, write tighter / shorter, do not pad.

EXAMPLES OF THIS WRITER'S ACTUAL VOICE:
{few_shot_block}
""".strip()

    def get_few_shots(self, platform: str, context: str, n: int = 5) -> list[dict[str, Any]]:
        scored = []
        for ex in self.few_shots:
            score = 0
            if ex.get("platform") == platform:
                score += 2
            if ex.get("context") == context:
                score += 3
            if any(k in (ex.get("context","")+" "+ex.get("post","")).lower() for k in context.lower().split()):
                score += 1
            scored.append((score, ex))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ex for _, ex in scored[:n]]


def load_profile(path: Path) -> VoiceProfile:
    return VoiceProfile(raw=load_profile_dict(path))
