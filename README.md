# Voiceful

Proactive observational agent that watches your workspace, detects post-worthy moments (ship / stuck / insight / idle / asked), and drafts platform-specific social posts in your authentic voice. Sends drafts to Telegram with approve / edit / reject buttons.

**Never auto-posts.** Every post requires your explicit tap-approval.

## What's in the box

- Voice profile builder. Ingests your tweets, READMEs, blog posts, commit messages. Computes statistical features (casing, punctuation, emoji, sentence length) plus LLM-extracted voice attributes (formality, humor, directness). Picks 12 representative few-shot examples.
- Drafters for Twitter, LinkedIn, Medium, dev.to, Hashnode. Each enforces platform-specific length and structure rules. All sanitize em-dashes and AI cliches before output.
- Watchers for git commits, files, notes, and shell history.
- Triggers: ship, stuck, insight, idle, asked.
- Telegram channel with inline approve / edit / reject / skip buttons. Edits are captured for the reinforcement loop.
- Reinforcement loop: every approved edit feeds back into the profile.
- Standalone CLI; can be installed as an OpenClaw skill.

## Setup

### 0. Prereqs

Python 3.11+ and pip. No need to install any local LLM. The default LLM provider is **Groq** (free tier, very fast Llama 3.1).

Get a Groq key (30 sec, free): https://console.groq.com/keys

Get a Telegram bot:
1. Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, follow prompts, copy the token.
2. Send a message to your new bot.
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and find your `chat.id`.

### 1. Install

```bash
cd /path/to/voiceful
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:
```
VOICEFUL_LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Initialize storage:
```bash
python -m scripts.main setup
```

This creates `~/.openclaw/voiceful/` with `config.yaml`, `training/`, and empty stores.

### 3. Train your voice profile

Drop writing samples into `~/.openclaw/voiceful/training/`:
- `*.txt` files of tweets (one per line)
- `*.md` blog posts, READMEs, notes
- `*.json` Twitter archive exports
- a `repos/` subfolder containing local git repos to harvest commits from

Or, for a quick demo, copy the seed samples shipped in this repo:
```bash
cp training_seed/* ~/.openclaw/voiceful/training/
```

Build the profile:
```bash
python -m scripts.main build-profile
```

Inspect `~/.openclaw/voiceful/voice_profile.json`. If the voice attributes feel wrong, drop more samples and rebuild.

### 4. Test a draft

```bash
python -m scripts.main test-draft twitter "shipped voiceful, the agent that watches your repo"
```

Side-by-side comparison vs a generic LLM:
```bash
python -m scripts.main compare "shipped voiceful, the agent that watches your repo"
```

Or run the full 3-case demo:
```bash
python -m scripts.demo
```

### 5. Wire up the watchers

Add the repos you want watched to `~/.openclaw/voiceful/config.yaml`:
```yaml
watchers:
  repos:
    - "~/code/voiceful"
    - "~/code/your-other-repo"
  notes_dir: "~/notes"
```

### 6. Run the daemon

Two processes:

**Telegram bot** (long-poll, handles approvals + `/draft <topic>` commands):
```bash
python -m scripts.main run-bot
```

**Watcher loop** (polls git every 60s for commits):
```bash
python -m scripts.main watch
```

Or wire it into cron from `jobs.json`:
```
*/5 * * * * cd /path/to/voiceful && .venv/bin/python -m scripts.main poll-git
*/15 * * * * cd /path/to/voiceful && .venv/bin/python -m scripts.main poll-terminal
0 */6 * * * cd /path/to/voiceful && .venv/bin/python -m scripts.main check-idle
```

### 7. Demo flow

1. `python -m scripts.main run-bot` in one terminal
2. `python -m scripts.main watch` in another
3. Make a real commit: `git commit -m "ship voiceful demo"`
4. Within 60 seconds, your Telegram bot pings you with a draft tweet, in your voice, with approve/edit/reject buttons.
5. Tap approve. Text is copied to your clipboard. Paste into Twitter manually.

## OpenClaw integration

This project is structured as an OpenClaw skill (`SKILL.md`, `jobs.json`, `scripts/`).

To install:
```bash
ln -s "$(pwd)" ~/.openclaw/skills/voiceful
```

OpenClaw discovers the skill from `SKILL.md` and registers cron from `jobs.json`. The Telegram bot still runs as a separate long-lived process: `python -m scripts.main run-bot`.

If OpenClaw is not available on your machine, the skill works standalone using its own cron + the daemon command above.

## LLM providers

The default provider is Groq for demo speed. You can swap any time via `.env`:

| Provider | Env var | Notes |
|---|---|---|
| `groq` | `GROQ_API_KEY` | Default. Free tier. Qwen 3 32B (Apache 2.0). |
| `huggingface` | `HF_TOKEN` | Free tier. Slower cold start. |
| `openrouter` | `OPENROUTER_API_KEY` | Wide model selection. Pay per call. |
| `together` | `TOGETHER_API_KEY` | Paid. Llama / Mixtral. |
| `anthropic` | `ANTHROPIC_API_KEY` | Closed source. Optional. |
| `dummy` | none | Offline stub for tests. |

All open-source providers above are HTTP APIs. No local model install required.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The voice authenticity test (`test_voice_authenticity.py`) is gated behind `VOICEFUL_RUN_LIVE_TESTS=1` because it hits the LLM. It asserts hard rules (no em-dashes, no avoid-words) and writes outputs to `tests/output/voice_samples.md` for manual review.

## Hard rules

These are enforced in code, not just prompts:

1. **Never auto-posts.** No code path posts to a social platform. The Telegram approve button copies text to your clipboard. You paste it.
2. **Never sends your data anywhere without consent.** The only network call is to the LLM provider you configured. No telemetry.
3. **Never uses em-dashes or en-dashes** in any user-facing output. Sanitized post-LLM.
4. **Never invents facts.** Drafts are grounded in actual trigger context (commit message, note text, etc).

## Project layout

```
voiceful/
├── SKILL.md
├── jobs.json
├── pyproject.toml
├── scripts/
│   ├── main.py             # CLI
│   ├── config.py
│   ├── llm_client.py       # Groq, HF, OpenRouter, Together, Anthropic
│   ├── voice/              # profile builder, loader, reinforcer
│   ├── drafters/           # twitter, linkedin, medium, devto, hashnode
│   ├── watchers/           # git, file, notes, terminal
│   ├── triggers/           # ship, stuck, insight, idle, asked
│   ├── channels/           # telegram
│   └── storage/            # voice, history, queue, state
├── references/
│   ├── voice_profile_schema.md
│   └── openclaw_apis.md
├── tests/
│   ├── test_voice_profile.py
│   ├── test_drafters.py
│   ├── test_triggers.py
│   ├── test_e2e.py
│   └── test_voice_authenticity.py
└── training_seed/          # sample writing for first-build demo
```

## License

MIT.
