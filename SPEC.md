# SPEC.md

Technical specification for Voiceful. Read CLAUDE.md first for project philosophy and constraints.

## 1. The voice profile

This is the most important module in the project. Get this right or nothing else matters.

### 1.1 Input artifacts

The user provides a folder containing their writing samples. Supported formats:

- `.txt` files containing past tweets (one per line, or one per file)
- `.md` files containing blog posts, README files, notes
- `.json` files exported from Twitter (Twitter's archive format)
- A pointer to a local Git repo (extract commit messages from the user's commits only)
- Plain text from LinkedIn (manual paste, since LinkedIn doesn't have clean export)

Default location: `~/.openclaw/voiceful/training/`

### 1.2 Profile schema

Stored at `~/.openclaw/voiceful/voice_profile.json`:

```json
{
  "version": "1.0",
  "built_at": "2026-04-30T10:00:00Z",
  "source_stats": {
    "tweet_count": 200,
    "commit_count": 450,
    "blog_post_count": 12,
    "readme_count": 8,
    "total_words": 18500
  },
  "characteristics": {
    "casing": {
      "sentence_start_lowercase_rate": 0.65,
      "all_caps_for_emphasis": false,
      "title_case_in_headers": false
    },
    "punctuation": {
      "uses_em_dash": false,
      "uses_en_dash": false,
      "uses_semicolon": true,
      "exclamation_rate_per_100_sentences": 3,
      "question_rate_per_100_sentences": 8
    },
    "emoji": {
      "uses_emoji": false,
      "common_emojis": [],
      "rate_per_post": 0.0
    },
    "hedging": {
      "rate": "low",
      "common_hedges": []
    },
    "common_phrases": ["shipped this", "tbh", "kinda", "the whole thing"],
    "avoid_words": ["delve", "leverage", "moreover", "furthermore", "elevate", "unlock", "navigate", "embark"],
    "sentence_length": {
      "median_words": 12,
      "p90_words": 28
    },
    "voice_attributes": {
      "formality": "casual_technical",
      "humor": "self_deprecating_dry",
      "directness": "very_direct",
      "first_person_rate": 0.8
    }
  },
  "few_shot_examples": [
    {
      "context": "shipped feature",
      "platform": "twitter",
      "post": "shipped a thing where the agent watches your repo and tells you when you should tweet about your work. testing it on myself and it called me out three times today."
    },
    {
      "context": "stuck on bug",
      "platform": "twitter",
      "post": "spent 90 min on what turned out to be a typo in a config file. genuinely impressed by how badly i can read sometimes."
    }
  ],
  "edit_history_summary": {
    "edits_captured": 24,
    "common_user_edits": ["shortens conclusions", "removes 'I think'", "adds 'tbh' to soften"]
  }
}
```

### 1.3 Profile builder algorithm

`scripts/voice/profile_builder.py` exposes:

```python
def build_profile(training_dir: Path, output_path: Path, llm_client) -> dict:
    """
    Build a voice profile from training artifacts.
    
    Steps:
    1. Load all artifacts from training_dir
    2. Compute statistical characteristics (casing, punctuation, emoji rates, sentence length)
    3. Extract avoid_words list (high-frequency LLM cliches NOT in user corpus)
    4. Use LLM to summarize voice_attributes (formality, humor, directness)
    5. Select 10-15 few_shot_examples that best represent the voice
    6. Save as JSON to output_path
    
    Returns the profile dict.
    """
```

The LLM call for voice_attributes uses this prompt structure:

```
You are analyzing a writer's voice. Given these 50 samples of their writing, describe their voice along these axes:
- formality (formal / professional / casual_technical / casual / very_informal)
- humor (none / dry / self_deprecating / playful / sarcastic / earnest)
- directness (very_indirect / indirect / balanced / direct / very_direct)
- first_person_rate (estimate 0.0 to 1.0, how often they use "I")

Also list 10 phrases or words this writer uses repeatedly that feel characteristic.
Also list 10 LLM-cliché words this writer NEVER uses.

Return as JSON.

Samples:
[paste 50 samples]
```

### 1.4 Profile loader

`scripts/voice/profile_loader.py` exposes:

```python
def load_profile(path: Path = None) -> VoiceProfile:
    """Load and validate the voice profile. Raises if missing or invalid."""

class VoiceProfile:
    def to_system_prompt(self) -> str:
        """Convert profile to a system prompt for the drafter LLM call."""
    
    def get_few_shots(self, platform: str, context: str, n: int = 5) -> list[dict]:
        """Get the n most relevant few-shot examples for this context and platform."""
```

The `to_system_prompt` method generates something like:

```
You write in a specific voice. Match it exactly.

Casing: lowercase sentence starts ~65% of the time. No title case in headers.

Punctuation: 
- NEVER use em dashes (—). 
- NEVER use en dashes (–). 
- Semicolons are okay but rare.
- ~3 exclamations per 100 sentences. Use sparingly.

Emoji: ZERO emojis. Do not add any.

Voice: casual_technical, self_deprecating_dry humor, very_direct.

Phrases this writer uses: "shipped this", "tbh", "kinda", "the whole thing"

Words this writer NEVER uses (do not use them): delve, leverage, moreover, furthermore, elevate, unlock, navigate, embark

Sentence length: median 12 words. Don't write long flowing paragraphs.

Match the voice in the few-shot examples below precisely.
```

## 2. The drafters

### 2.1 Base drafter

`scripts/drafters/base.py`:

```python
from abc import ABC, abstractmethod

class BaseDrafter(ABC):
    platform: str  # "twitter", "linkedin", etc.
    
    def __init__(self, profile: VoiceProfile, llm_client):
        self.profile = profile
        self.llm = llm_client
    
    @abstractmethod
    def platform_constraints(self) -> str:
        """Return platform-specific constraints (length, format, style)."""
    
    def draft(self, trigger_event: dict) -> str:
        """
        Generate a draft post.
        trigger_event has: type, raw_signal, context.
        Returns the post text.
        """
        system = self.profile.to_system_prompt() + "\n\n" + self.platform_constraints()
        few_shots = self.profile.get_few_shots(self.platform, trigger_event["type"], n=5)
        user_msg = self._build_user_message(trigger_event, few_shots)
        return self.llm.complete(system=system, user=user_msg)
    
    @abstractmethod
    def _build_user_message(self, event: dict, few_shots: list) -> str:
        """Build the user message for the LLM call."""
```

### 2.2 Twitter drafter

`scripts/drafters/twitter.py`:

```python
class TwitterDrafter(BaseDrafter):
    platform = "twitter"
    
    def platform_constraints(self) -> str:
        return """
        Platform: Twitter / X
        Constraints:
        - Maximum 280 characters per tweet
        - If the idea needs more, split into a thread (max 5 tweets)
        - Hook in the first 7 words. No throat-clearing.
        - No hashtags unless the user's training corpus shows they use them.
        - Don't end with engagement bait ("what do you think?")
        - Punchy. No flowery setups.
        """
```

### 2.3 LinkedIn drafter

```python
class LinkedInDrafter(BaseDrafter):
    platform = "linkedin"
    
    def platform_constraints(self) -> str:
        return """
        Platform: LinkedIn
        Constraints:
        - 100-300 words ideal
        - Open with a specific moment or observation, NOT a generic statement
        - First-person, not corporate-speak
        - One short paragraph per idea, lots of whitespace
        - End with a brief takeaway, not a question or call-to-action
        - NO buzzwords: synergy, leverage, ecosystem, journey, passionate, excited
        - NO emoji unless training corpus has them
        - NO line of single-word emphasis ("Resilience.\\n\\nGrit.\\n\\nFocus.")
        - NO "I'm thrilled to announce" or similar
        - Match the user's directness level. Don't soften their voice for "the platform".
        """
```

### 2.4 Medium / dev.to / Hashnode drafters

Long-form technical posts. 500-1500 words. Structure pulled from the actual artifact (commit, code change, notes). Code blocks preserved with proper fencing.

## 3. The watchers

### 3.1 Git watcher

`scripts/watchers/git_watcher.py`:

```python
def poll_repos(repos: list[Path], state_path: Path) -> list[dict]:
    """
    For each repo, check git log for commits newer than the last seen commit.
    Returns a list of new commit events.
    
    Event format:
    {
        "type": "git_commit",
        "repo": "/path/to/repo",
        "sha": "abc123",
        "message": "fix off-by-one in retry logic",
        "diff_summary": "5 files changed, 23 insertions, 8 deletions",
        "files_changed": ["retry.py", "tests/test_retry.py"],
        "timestamp": "2026-04-30T10:00:00Z"
    }
    
    Updates state_path with the latest seen commit per repo.
    """
```

Called from `jobs.json` cron every 5 minutes.

### 3.2 File watcher

`scripts/watchers/file_watcher.py`:

Uses `watchdog` library for real-time events. Watches workspace directories specified in config. Emits events when files are created, modified, or deleted. Filters by glob pattern (default: `*.py`, `*.md`, `*.txt`, `*.ipynb`).

### 3.3 Notes watcher

Specialized file watcher for the user's notes directory. Detects new entries (lines added to a daily note file, new files in a notes folder). Triggers insight detection when new content exceeds 50 words.

### 3.4 Terminal watcher

Reads `~/.bash_history` or `~/.zsh_history` periodically. Looks for repeated error commands, repeated test runs, repeated grep/search commands. Used for stuck detection.

## 4. The triggers

Each trigger module exposes `def detect(events: list[dict], state: dict) -> list[TriggerEvent]`.

### 4.1 Ship trigger

Fires when:
- A commit message contains keywords like "ship", "release", "deploy", "launch", "v1", "done"
- A commit changes >5 files (likely a feature)
- A PR is merged (if GitHub API is configured)
- A release tag is pushed

### 4.2 Stuck trigger

Fires when:
- Same error string appears in terminal 3+ times in last hour
- Same file edited 5+ times without commit in last 2 hours
- User runs same test command 3+ times

### 4.3 Insight trigger

Fires when:
- New entry in notes file >50 words
- Notes file contains keywords: "TIL", "learned", "interesting", "huh", "didn't know"
- New blog post draft detected

### 4.4 Idle trigger

Fires on heartbeat (every 6 hours):
- Check last_post_timestamp from history
- If >3 days since last post AND there are unposted recent events in the queue, surface them

### 4.5 Asked trigger

Direct user invocation via Telegram command: `/draft <topic>`

## 5. Channels

### 5.1 Telegram channel

`scripts/channels/telegram.py`:

```python
def send_draft_for_approval(draft: dict, bot_token: str, chat_id: str) -> None:
    """
    Sends draft to user with inline keyboard:
    [Approve] [Edit] [Reject] [Skip]
    
    draft format:
    {
        "platform": "twitter",
        "text": "...",
        "trigger": "ship",
        "context": "commit abc123: fix off-by-one in retry logic",
        "draft_id": "uuid"
    }
    """

def handle_approval_response(update: dict) -> None:
    """
    Handle inline keyboard callback.
    - Approve: copy text to clipboard, mark as approved, log to history
    - Edit: open conversation for user to send edited version, capture diff
    - Reject: log rejection with reason if provided
    - Skip: log as skipped (different signal from rejected)
    """
```

The Telegram message format:

```
🦞 Draft for Twitter

[the draft text]

Triggered by: shipped commit "fix off-by-one in retry logic"

[Approve] [Edit] [Reject] [Skip]
```

### 5.2 Discord channel

Mirror of Telegram, using discord.py. Implement after Telegram works.

## 6. Storage

All in `~/.openclaw/voiceful/`.

### 6.1 history.json

```json
{
  "drafts": [
    {
      "draft_id": "uuid",
      "created_at": "ts",
      "platform": "twitter",
      "trigger_type": "ship",
      "trigger_signal": {...},
      "draft_text": "...",
      "user_action": "edited_then_approved | approved | rejected | skipped",
      "user_edit_text": "...",
      "edit_diff": "...",
      "approved_at": "ts",
      "posted_at": "ts (or null if user didn't post)"
    }
  ]
}
```

### 6.2 queue.json

Active drafts awaiting user response. FIFO. Cleaned up after action.

### 6.3 voice_profile.json

See section 1.2.

### 6.4 config.yaml

```yaml
user:
  name: "Nidhi"
  
training_dir: "~/.openclaw/voiceful/training"

watchers:
  repos:
    - "~/code/voiceful"
    - "~/code/cipher"
  notes_dir: "~/notes"
  workspace_dirs:
    - "~/code"
  shell_history: "~/.zsh_history"

platforms:
  twitter:
    enabled: true
  linkedin:
    enabled: true
  medium:
    enabled: false
  devto:
    enabled: false
  hashnode:
    enabled: false

channels:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
  discord:
    enabled: false

triggers:
  ship:
    enabled: true
  stuck:
    enabled: true
    error_repeat_threshold: 3
    error_window_minutes: 60
  insight:
    enabled: true
    min_word_count: 50
  idle:
    enabled: true
    days_threshold: 3
  asked:
    enabled: true

llm:
  provider: "anthropic"
  model: "claude-sonnet-4-5-20250929"
  api_key: "${ANTHROPIC_API_KEY}"
  fallback_local: false
```

## 7. SKILL.md (OpenClaw manifest)

```markdown
---
name: voiceful
description: Watches your workspace for post-worthy moments and drafts social posts in your authentic voice. Never posts on its own. Use when the user wants to maintain their social presence (Twitter, LinkedIn, Medium, dev.to, Hashnode) without writing posts manually, while keeping their authorial voice intact.
---

# Voiceful

Voiceful is a proactive observational skill that watches the user's real work (git commits, code changes, notes files) and drafts social posts that sound like the user wrote them.

## When to use this skill

- User shipped a feature or made a meaningful commit
- User has been stuck on a problem and could benefit from asking their network
- User wrote something interesting in their notes
- User's social presence has been quiet for a few days
- User explicitly asks for a draft via `/draft <topic>`

## How it works

1. Watchers detect events in the user's workspace
2. Triggers classify events into post-worthy moments
3. Drafters generate platform-specific posts using the user's voice profile
4. Channel sends draft to user via Telegram with approve/edit/reject buttons
5. User approves; the post text is copied to clipboard for them to paste manually
6. The agent never posts directly to social platforms

## Setup

1. Run `python scripts/main.py setup` to initialize config and storage
2. Place writing samples in `~/.openclaw/voiceful/training/`
3. Run `python scripts/main.py build-profile` to build the voice profile
4. Configure Telegram bot in config.yaml
5. Restart OpenClaw to register the cron jobs

## Commands

- `/draft <topic>` — request a draft on a specific topic
- `/voice-status` — show voice profile stats
- `/queue` — show pending drafts
- `/refine` — rebuild voice profile incorporating recent edits
```

## 8. jobs.json (cron schedule)

```json
{
  "jobs": [
    {
      "name": "voiceful-git-poll",
      "schedule": "*/5 * * * *",
      "command": "python ~/.openclaw/skills/voiceful/scripts/main.py poll-git"
    },
    {
      "name": "voiceful-terminal-poll",
      "schedule": "*/15 * * * *",
      "command": "python ~/.openclaw/skills/voiceful/scripts/main.py poll-terminal"
    },
    {
      "name": "voiceful-idle-check",
      "schedule": "0 */6 * * *",
      "command": "python ~/.openclaw/skills/voiceful/scripts/main.py check-idle"
    }
  ]
}
```

(File watcher and notes watcher run as a long-lived process via `python scripts/main.py watch`, not as cron jobs.)

## 9. Testing

### 9.1 Voice authenticity test

The most important test. `tests/test_voice_authenticity.py`:

```python
def test_voice_authenticity():
    """
    Generate 10 sample posts from realistic trigger inputs.
    Save to tests/output/voice_samples.md for manual review.
    Assert that none contain words from avoid_words.
    Assert that none contain em-dashes or en-dashes.
    Assert that none contain emoji unless profile.uses_emoji is true.
    """
```

This test does not pass/fail on quality (LLM can't judge that reliably). It saves outputs for human review and asserts only the hard rules.

### 9.2 Drafter unit tests

For each drafter, test that:
- Output respects platform constraints (length, format)
- System prompt includes voice profile attributes
- Few-shot examples are included

### 9.3 Trigger unit tests

For each trigger, test with mock events that:
- It fires when conditions are met
- It does NOT fire when conditions are not met
- It deduplicates correctly (same commit doesn't fire twice)

### 9.4 End-to-end test

`tests/test_e2e.py`:

```python
def test_full_pipeline():
    """
    1. Build voice profile from sample training data
    2. Inject a fake git commit event
    3. Assert that ship trigger fires
    4. Assert that Twitter drafter generates a draft
    5. Assert that draft is queued for Telegram
    6. Mock Telegram approval response
    7. Assert that history records the approval
    """
```

## 10. Demo readiness checklist

Before demo day:

- [ ] Voice profile built from at least 200 real samples of Nidhi's writing
- [ ] Voice authenticity test passes 8/10 manual review
- [ ] Live demo: real git commit triggers Telegram draft within 60 seconds
- [ ] Live demo: stuck detection works on a scripted scenario
- [ ] Live demo: notes file insight detection works
- [ ] Live demo: same insight produces correctly-formatted post for Twitter, LinkedIn, dev.to
- [ ] Side-by-side ChatGPT vs Voiceful comparison ready
- [ ] Backup video of full demo recorded
- [ ] README.md with installation instructions
- [ ] All hard rules from CLAUDE.md verified
