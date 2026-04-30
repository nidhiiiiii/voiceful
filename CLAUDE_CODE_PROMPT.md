# Claude Code Prompt

This is the single prompt to paste into Claude Code (in your terminal, with Claude Code installed) to build the entire Voiceful project.

Before you paste, make sure:

1. You are in an empty directory where you want the project to live
2. You have copied `CLAUDE.md` and `SPEC.md` into that directory
3. You have an Anthropic API key ready (export it as `ANTHROPIC_API_KEY` env var when you run things, but don't paste it into Claude Code)

## The prompt

Copy everything below this line and paste it into Claude Code as your first message:

---

I have placed `CLAUDE.md` and `SPEC.md` in this directory. Read both of them carefully, in full, before doing anything else. They are the source of truth for what to build.

After reading them:

1. Do not ask me to confirm the plan. Just start building.
2. Build the project in the phase order specified in CLAUDE.md (Phase 1 through Phase 10).
3. After each phase, run any tests you wrote for that phase. If tests fail, fix them before moving on.
4. Use Python 3.11+, uv for package management, and the OpenClaw skill format described in SPEC.md.
5. Create a `pyproject.toml` with proper dependencies. Pin versions.
6. Create a `README.md` with setup instructions.
7. Create a `.env.example` with the env vars users need to set.
8. Add a `.gitignore` that excludes the typical Python noise plus `~/.openclaw/voiceful/` data directories and any `.env` files.
9. Use type hints everywhere. Use dataclasses or pydantic for structured data.
10. Write meaningful logging using Python's stdlib `logging` module. Default level INFO, debug level available via env var.
11. For the LLM client, build a thin abstraction that wraps the Anthropic SDK. Do not call the SDK directly from drafters; call it through the abstraction. This makes future swap to local Ollama easier.
12. For the voice profile builder, the LLM call to extract voice attributes should be one call per batch of 50 samples, then merge results. Don't put 500 samples in one prompt.
13. For the few-shot example selection, use simple keyword matching on context for now. Don't build a vector store. We can iterate later.
14. For the Telegram bot, use python-telegram-bot v20+ with async handlers. Inline keyboards for approve/edit/reject/skip.
15. For the file watcher, use the `watchdog` library. Not custom polling.
16. For the git watcher, use `pygit2` or shell out to `git log --since=<last_seen>`.
17. After each phase, give me a brief summary of what's done and what's next. Do not summarize verbosely. One paragraph per phase.

Hard constraints I want you to internalize from CLAUDE.md:

- The voice profile is the moat. Spend disproportionate effort on it. Phase 2 is the most important phase. If Phase 2 produces drafts that sound generic, stop and refine before moving on.
- Never write em-dashes (—) or en-dashes (–) in any user-facing output, even in your own README and demo files. The user considers em-dashes an AI tell.
- Never auto-post. Every post requires user tap-approval.
- Everything stays local. The only external service we call is the Anthropic API for generation.
- The user's data (code, notes, terminal output) never gets sent to any LLM unless the user has explicitly configured an API key, and even then, only the minimum necessary context for generation.

After Phase 5 (the first end-to-end vertical slice), pause and tell me clearly what's working and what isn't. I'll review and we'll continue from there.

Now begin. Read CLAUDE.md and SPEC.md first, then start with Phase 1.

---

End of prompt. Paste the entire block above into Claude Code (start at "I have placed..." and end at "...start with Phase 1.").

## Tips for working with Claude Code on this

1. **Don't interrupt early.** Let it finish at least Phase 5 before reviewing. The early phases set up scaffolding that pays off later.

2. **Watch for em-dashes in its output.** Claude Code might still slip and use em-dashes. If you see one in any generated file, ask it to grep for em-dashes and replace them.

3. **The voice profile test is critical.** When Claude Code finishes Phase 2, manually test the profile builder with your own real writing samples (your tweets, your README files, your blog drafts). Read the generated outputs. If they don't sound like you, the project will fail. Iterate on the profile builder prompt until they do.

4. **Don't let it skip the side-by-side comparison demo.** Phase 10 should include a script that takes one input and shows the Voiceful output next to a generic ChatGPT output. This is your demo's killer moment.

5. **For Telegram setup**, you'll need to:
   - Create a bot via @BotFather on Telegram, get the bot token
   - Send a message to your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to get your chat_id
   - Put both in your `.env` file

6. **For Anthropic API**, you'll need an API key from https://console.anthropic.com. The model `claude-sonnet-4-5-20250929` is a good default.

7. **Test with your real artifacts ASAP.** The sooner you give the profile builder real writing samples from yourself, the faster you'll know if the voice authenticity is working. Don't wait until Phase 10 to find out the voice sounds generic.
