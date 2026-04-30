# OpenClaw integration

This skill follows the standard OpenClaw layout:

```
~/.openclaw/skills/voiceful/
├── SKILL.md      # YAML frontmatter manifest
├── jobs.json     # cron schedule
├── scripts/      # python entrypoints
└── references/
```

## Install as an OpenClaw skill

```
ln -s "$(pwd)" ~/.openclaw/skills/voiceful
```

Or copy the directory into `~/.openclaw/skills/voiceful/`.

OpenClaw discovers the skill by reading `SKILL.md` (top-level `name:` field) and registers cron from `jobs.json`.

## Standalone (no OpenClaw)

The skill also runs without OpenClaw. The `jobs.json` entries map 1:1 to crontab lines:

```
*/5 * * * *  cd /path/to/voiceful && .venv/bin/python -m scripts.main poll-git
*/15 * * * * cd /path/to/voiceful && .venv/bin/python -m scripts.main poll-terminal
0 */6 * * *  cd /path/to/voiceful && .venv/bin/python -m scripts.main check-idle
```

The Telegram bot runs as a long-lived process: `python -m scripts.main run-bot`.

## Notes

- This document is intentionally minimal. The skill works without any OpenClaw-specific imports because OpenClaw runs the commands in `jobs.json` as plain shell.
- If OpenClaw exposes a richer Python API in the future, integrate it inside `scripts/channels/` rather than scattering it across the codebase.
