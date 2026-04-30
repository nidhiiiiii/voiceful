---
name: parrot
description: Watches your workspace for post-worthy moments and drafts social posts in your authentic voice. Never posts on its own. Use when the user wants to maintain their social presence (Twitter, LinkedIn, Medium, dev.to, Hashnode) without writing posts manually, while keeping their authorial voice intact.
---

# Parrot

Parrot is a proactive observational skill that watches the user's real work (git commits, code changes, notes files) and drafts social posts that sound like the user wrote them.

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

1. Run `python -m scripts.main setup` to initialize config and storage
2. Place writing samples in `~/.openclaw/voiceful/training/`
3. Run `python -m scripts.main build-profile` to build the voice profile
4. Configure Telegram bot in config.yaml or .env
5. Restart OpenClaw to register the cron jobs

## Commands

- `/draft <topic>` request a draft on a specific topic
- `/voice_status` show voice profile stats
- `/queue` show pending drafts
- `/refine` rebuild voice profile incorporating recent edits
