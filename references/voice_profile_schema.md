# voice_profile.json schema

Stored at `~/.openclaw/voiceful/voice_profile.json`.

```jsonc
{
  "version": "1.0",
  "built_at": "ISO-8601 timestamp",
  "source_stats": {
    "tweet_count": int,
    "commit_count": int,
    "blog_post_count": int,
    "readme_count": int,
    "notes_count": int,
    "total_words": int
  },
  "characteristics": {
    "casing": {
      "sentence_start_lowercase_rate": 0.0-1.0,
      "all_caps_for_emphasis": bool,
      "title_case_in_headers": bool
    },
    "punctuation": {
      "uses_em_dash": bool,
      "uses_en_dash": bool,
      "uses_semicolon": bool,
      "exclamation_rate_per_100_sentences": float,
      "question_rate_per_100_sentences": float
    },
    "emoji": {
      "uses_emoji": bool,
      "common_emojis": [str],
      "rate_per_post": float
    },
    "hedging": {
      "rate": "low" | "medium" | "high",
      "common_hedges": [str]
    },
    "sentence_length": {
      "median_words": int,
      "p90_words": int
    },
    "first_person_rate": 0.0-1.0,
    "common_phrases": [str],
    "avoid_words": [str],
    "voice_attributes": {
      "formality": "formal" | "professional" | "casual_technical" | "casual" | "very_informal",
      "humor": "none" | "dry" | "self_deprecating" | "playful" | "sarcastic" | "earnest",
      "directness": "very_indirect" | "indirect" | "balanced" | "direct" | "very_direct",
      "first_person_rate": 0.0-1.0,
      "tone_summary": "one sentence"
    }
  },
  "few_shot_examples": [
    {
      "context": "shipped feature" | "stuck on bug" | "insight learned" | "observation" | "opinion" | "general",
      "platform": "twitter" | "linkedin",
      "post": "the exact text"
    }
  ],
  "edit_history_summary": {
    "edits_captured": int,
    "common_user_edits": [str]
  }
}
```

`profile_builder.py` populates this via:
1. Statistical pass over all samples (no LLM): casing, punctuation, emoji, sentence length, hedging.
2. Batched LLM extraction (50 samples per batch, max 6 batches): formality, humor, directness, characteristic phrases, avoid words.
3. Few-shot selection (LLM, with heuristic fallback): pick 12 representative samples across contexts.

`profile_loader.VoiceProfile.to_system_prompt()` serializes this to the system prompt the drafters use.
