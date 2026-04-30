# CLAUDE.md

You are building **Voiceful** (working name, can change), an OpenClaw skill that lives in a builder's workspace, learns their authentic voice from real artifacts they have written, and proactively drafts social posts in their tone with their approval.

This file is the source of truth for what to build and what NOT to build. Read this entire file before writing any code. When in doubt, re-read this file.

## What this project IS

A proactive observational agent that:

1. Watches the user's workspace (git commits, code changes, notes files, terminal output)
2. Detects "post-worthy moments" via five trigger types (ship, stuck, insight, idle, asked)
3. Drafts platform-specific posts (Twitter, LinkedIn, Medium, dev.to, Hashnode) in the user's authentic voice
4. Pings the user on Telegram or Discord for approval
5. NEVER posts autonomously
6. Learns from every edit the user makes to refine the voice profile

## What this project IS NOT

- Not a generic AI ghostwriter. The voice profile is built from REAL user artifacts, not prompt descriptions.
- Not an auto-poster. Every post requires explicit human tap-approval.
- Not a SaaS. Everything runs locally inside OpenClaw. User data never leaves their machine.
- Not a content calendar tool. There is no scheduling UI. The agent surfaces moments as they happen.
- Not a follower-growth hack. The goal is reducing friction for builders who want to post but don't.

## The core differentiator (the moat)

Other tools generate posts from a generic LLM prompt. This tool generates posts from a deep voice profile built from the user's actual writing artifacts (past tweets, GitHub commits, README files, blog posts, notes). The voice profile is the moat. Spend disproportionate effort here.

If a generated post sounds like generic LLM output, the project has failed. Every test of "would the user actually post this without embarrassment?" must pass.

## Stack constraints

- **Language:** Python 3.11+
- **Framework:** OpenClaw skill format (SKILL.md + scripts/ + jobs.json)
- **Package manager:** uv
- **LLM:** Claude Sonnet 4.5 via Anthropic API for voice generation. Model string: `claude-sonnet-4-5-20250929`. Fallback to local model via Ollama if user prefers fully offline (stretch).
- **Storage:** JSON files in workspace at `~/.openclaw/voiceful/`. No database.
- **Channels:** Telegram (primary), Discord (alt). Use OpenClaw's existing channel integrations.
- **Triggers:** Cron jobs via OpenClaw's `jobs.json` for periodic checks. File watchers via Python `watchdog` library for real-time events.

## Hard rules

1. **Never post autonomously.** Every draft requires user approval via Telegram/Discord button tap.
2. **Never store credentials in plaintext.** Use OpenClaw's secrets mechanism or env vars.
3. **Never send user code or notes to third-party LLMs without explicit user setup.** The user must explicitly configure their Anthropic API key. Default behavior should fail loudly if no key is configured, not silently send data anywhere.
4. **Never invent facts about what the user did.** Drafts must be grounded in actual artifacts (commit messages, file contents, etc.). If the agent does not have enough signal, it should not draft, period.
5. **Always log what the agent saw and what it drafted.** The user must be able to audit every action.
6. **Always preserve the user's phrasing when they have written something themselves.** If the user wrote a note that says "this bug was annoying as hell", the draft should not sanitize that to "this issue presented some challenges".

## Voice authenticity rules

When generating any post, follow these rules in the voice profile system prompt:

1. Never use words from the user's "avoid list" (built from analyzing what they never write)
2. Match sentence rhythm from few-shot examples
3. Match casing conventions (do they capitalize sentence starts? do they use lowercase aesthetic?)
4. Match emoji usage exactly (most builders use zero or one emojis; never sprinkle them)
5. Match em-dash usage. Many real users never use em-dashes. If the user's training corpus has zero em-dashes, the output must have zero em-dashes.
6. Avoid phrases that signal AI: "delve into", "leverage", "in today's fast-paced world", "it's worth noting that", "navigate the complexities", "elevate", "unlock", "embark on a journey", "in conclusion", "moreover", "furthermore", "additionally" (unless user uses them).
7. Match formality level. If the user's tweets are casual lowercase, LinkedIn posts should still skew casual (not corporate).
8. Match hedging level. Some users hedge a lot ("I think", "maybe", "kinda"). Some never hedge. Match their exact rate.

## Architecture overview

```
~/.openclaw/skills/voiceful/
├── SKILL.md                    # OpenClaw skill manifest with YAML frontmatter
├── jobs.json                   # Cron schedule for periodic triggers
├── scripts/
│   ├── __init__.py
│   ├── main.py                 # Entry point invoked by OpenClaw
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── profile_builder.py  # Builds voice profile from artifacts
│   │   ├── profile_loader.py   # Loads + validates profile
│   │   └── reinforcer.py       # Updates profile based on user edits
│   ├── watchers/
│   │   ├── __init__.py
│   │   ├── git_watcher.py
│   │   ├── file_watcher.py
│   │   ├── notes_watcher.py
│   │   └── terminal_watcher.py
│   ├── triggers/
│   │   ├── __init__.py
│   │   ├── ship_trigger.py
│   │   ├── stuck_trigger.py
│   │   ├── insight_trigger.py
│   │   ├── idle_trigger.py
│   │   └── asked_trigger.py
│   ├── drafters/
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract drafter
│   │   ├── twitter.py
│   │   ├── linkedin.py
│   │   ├── medium.py
│   │   ├── devto.py
│   │   └── hashnode.py
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── telegram.py         # Sends drafts, receives approvals
│   │   └── discord.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── voice_store.py
│   │   ├── history_store.py
│   │   └── queue_store.py
│   └── config.py               # Loads ~/.openclaw/voiceful/config.yaml
├── references/
│   └── voice_profile_schema.md # Schema documentation for the voice profile JSON
└── tests/
    ├── test_voice_profile.py
    ├── test_drafters.py
    └── test_triggers.py
```

## Data formats

All data formats are documented in `references/voice_profile_schema.md`. The key formats are:

**voice_profile.json** — the user's voice fingerprint
**history.json** — every draft, every edit, every action
**queue.json** — pending drafts awaiting approval
**config.yaml** — user-tunable settings

## Build phases

Build in this order. Do not skip ahead. Each phase must work end-to-end before the next.

**Phase 1: Foundation.** OpenClaw skill scaffold, config loader, storage modules. Test with hardcoded data.

**Phase 2: Voice profile.** Profile builder that ingests artifacts (tweets, commits, README files), extracts characteristic features, stores as JSON. CLI command to build a profile from a folder of input files.

**Phase 3: One drafter end-to-end.** Twitter drafter only. Takes a "ship" event with a commit message, uses the voice profile, generates a draft. CLI command to test with sample input.

**Phase 4: One channel end-to-end.** Telegram bot. Receives draft from drafter, sends to user, captures approve/edit/reject response, logs to history.

**Phase 5: One trigger end-to-end.** Git watcher with ship trigger. Polls user's repos every N minutes (via jobs.json), detects new commits, fires ship trigger, calls Twitter drafter, sends to Telegram.

This is the full vertical slice. After Phase 5, the agent works end-to-end for one platform and one trigger type.

**Phase 6: Expand drafters.** LinkedIn, Medium, dev.to, Hashnode. Each gets its own tone-tuning prompts.

**Phase 7: Expand triggers.** File watcher, notes watcher, stuck trigger, insight trigger, idle trigger, asked trigger.

**Phase 8: Reinforcement loop.** When user edits a draft before approving, capture the diff. Periodically update voice profile based on accumulated edits.

**Phase 9: Discord channel.** Mirror the Telegram flow.

**Phase 10: Polish.** Better logging, better error handling, README, demo scripts.

## Definition of done for the hackathon demo

The demo must show all of these working live:

1. Agent is running as OpenClaw daemon
2. User makes a real git commit, agent detects it within 60 seconds, drafts a Twitter post in user's voice, sends to Telegram with approve/edit/reject buttons
3. User opens a code file with a long-stuck TODO, agent detects "stuck" pattern, suggests asking Twitter for help, drafts the question
4. User adds a new entry to their notes file, agent detects "insight", drafts a post preserving user's phrasing
5. Same insight gets formatted differently for Twitter (short), LinkedIn (longer), and dev.to (technical with code)
6. User edits a draft, taps approve, the edit is captured for the reinforcement loop
7. Side-by-side comparison: agent's draft vs ChatGPT's draft of the same input. Agent's must sound clearly more like the user.

## Things to NOT do

- Do not build a web dashboard. Telegram is the interface.
- Do not build a database layer. JSON files in workspace are sufficient.
- Do not build a fine-tuning pipeline. Prompt anchoring with few-shot is sufficient.
- Do not build follower-growth analytics. Out of scope.
- Do not build content scheduling. The agent surfaces in real time.
- Do not auto-post. Even with user permission. Even as a "convenience". Always require tap-approval.
- Do not use em-dashes anywhere in user-facing output. The user (Nidhi) considers em-dashes an AI tell.
- Do not write generic CRUD code without thinking about what the user actually needs.
- Do not hallucinate OpenClaw APIs. Reference `references/openclaw_apis.md` (you should create this and document the actual APIs you use, citing the docs).

## Testing approach

For each phase, write a test that runs the full vertical slice with a sample input and asserts the output. Tests should be runnable via `pytest` from the project root.

The most important test: the **voice authenticity test**. Given a user's training corpus, generate 10 sample posts from 10 different prompts. Manually review them. They must pass the "would Nidhi actually post this?" test. If 8/10 pass, ship it. If <8/10 pass, refine the voice profile prompt before moving on.

## Final note

The whole project lives or dies on the voice profile sounding authentic. If you find yourself spending more time on watchers and triggers than on the voice profile, you have your priorities wrong. Build the voice profile first, then build everything else around it.

The user is Nidhi. She is a software engineer in Bangalore who has shipped many hackathon projects. She has a strong personal voice in her writing. She does not use em-dashes. She is direct, technical, sometimes self-deprecating, often funny. The voice profile must capture that, not a generic "developer voice".
