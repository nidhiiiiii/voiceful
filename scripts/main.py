"""Voiceful entry point. CLI for setup, profile build, polling, watching, drafting."""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

import click

from .config import Config, load_config, setup_logging, write_default_config
from .drafters import get_drafter
from .llm_client import make_client
from .storage import history_store, queue_store, state_store
from .triggers import idle_trigger, ship_trigger
from .voice.profile_builder import build_profile
from .voice.profile_loader import load_profile
from .voice.reinforcer import refine_profile
from .watchers import git_watcher, notes_watcher, terminal_watcher

log = logging.getLogger("voiceful")


def _load() -> tuple[Config, object, object]:
    setup_logging()
    cfg = load_config()
    profile = load_profile(cfg.voice_profile_path) if cfg.voice_profile_path.exists() else None
    llm = make_client(cfg)
    return cfg, profile, llm


def _draft_and_send(cfg: Config, profile, llm, platform: str, trigger_event: dict) -> str:
    drafter = get_drafter(platform, profile, llm)
    text = drafter.draft(trigger_event)
    draft = {
        "draft_id": str(uuid.uuid4()),
        "platform": platform,
        "text": text,
        "trigger": trigger_event.get("type"),
        "context": trigger_event.get("context", ""),
        "trigger_signal": trigger_event.get("raw_signal", {}),
    }
    from .channels.telegram import send_draft_for_approval
    try:
        send_draft_for_approval(cfg, draft)
        log.info("Sent draft %s to Telegram", draft["draft_id"])
    except Exception as e:
        log.error("Telegram send failed: %s. Draft queued only.", e)
    return text


@click.group()
def cli() -> None:
    """Voiceful CLI."""


@cli.command()
def setup() -> None:
    """Initialize storage dirs, config, and training folder."""
    setup_logging()
    cfg = load_config()
    cfg.home.mkdir(parents=True, exist_ok=True)
    cfg.training_dir.mkdir(parents=True, exist_ok=True)
    config_path = write_default_config()
    click.echo(f"Initialized at {cfg.home}")
    click.echo(f"Config: {config_path}")
    click.echo(f"Training dir: {cfg.training_dir}")
    click.echo("Drop your writing samples (.txt, .md, .json) into the training dir, then run `build-profile`.")


@cli.command("build-profile")
@click.option("--training-dir", type=click.Path(path_type=Path), default=None)
@click.option("--author-email", default=None, help="Filter git commits by this author email.")
def build_profile_cmd(training_dir: Path | None, author_email: str | None) -> None:
    """Build voice profile from training artifacts."""
    setup_logging()
    cfg = load_config()
    src = Path(training_dir) if training_dir else cfg.training_dir
    llm = make_client(cfg)
    profile = build_profile(src, cfg.voice_profile_path, llm, author_email=author_email)
    click.echo(f"Profile saved to {cfg.voice_profile_path}")
    click.echo(f"Sources: {profile['source_stats']}")
    click.echo(f"Voice: {profile['characteristics']['voice_attributes']}")


@cli.command("test-draft")
@click.argument("platform", type=click.Choice(["twitter", "linkedin", "medium", "devto", "hashnode"]))
@click.argument("topic", nargs=-1)
@click.option("--trigger", default="general")
def test_draft(platform: str, topic: tuple[str, ...], trigger: str) -> None:
    """Generate a one-off draft on the command line. Does not send to Telegram."""
    setup_logging()
    cfg = load_config()
    profile = load_profile(cfg.voice_profile_path)
    llm = make_client(cfg)
    drafter = get_drafter(platform, profile, llm)
    event = {"type": trigger, "context": " ".join(topic), "raw_signal": " ".join(topic)}
    text = drafter.draft(event)
    click.echo("--- DRAFT ---")
    click.echo(text)


@cli.command("compare")
@click.argument("topic", nargs=-1)
@click.option("--platform", default="twitter")
def compare(topic: tuple[str, ...], platform: str) -> None:
    """Side-by-side: Voiceful (with profile) vs vanilla (no profile)."""
    setup_logging()
    cfg = load_config()
    profile = load_profile(cfg.voice_profile_path)
    llm = make_client(cfg)
    topic_str = " ".join(topic)
    event = {"type": "asked", "context": topic_str, "raw_signal": topic_str}

    drafter = get_drafter(platform, profile, llm)
    voiceful = drafter.draft(event)

    generic_system = f"You are a social media writer. Write a {platform} post."
    generic = llm.complete(system=generic_system, user=f"Write a {platform} post about: {topic_str}", max_tokens=400)

    click.echo("=== VOICEFUL (your voice) ===")
    click.echo(voiceful)
    click.echo("\n=== GENERIC LLM ===")
    click.echo(generic)


@cli.command("poll-git")
def poll_git() -> None:
    """Poll repos for new commits and fire ship trigger. For cron."""
    cfg, profile, llm = _load()
    if not profile:
        click.echo("No voice profile. Run `build-profile` first.")
        return
    events = git_watcher.poll_repos(cfg.repos, cfg.state_path)
    if not events:
        log.info("No new commits.")
        return
    state = state_store.load_state(cfg.state_path)
    triggers = ship_trigger.detect(events, state)
    state_store.save_state(cfg.state_path, state)
    for t in triggers:
        for platform in ("twitter",):
            if cfg.raw["platforms"].get(platform, {}).get("enabled"):
                _draft_and_send(cfg, profile, llm, platform, t)


@cli.command("poll-terminal")
def poll_terminal() -> None:
    """Poll shell history for stuck signals."""
    from .triggers import stuck_trigger
    cfg, profile, llm = _load()
    if not profile:
        return
    events = terminal_watcher.scan(Path(cfg.raw["watchers"]["shell_history"]), cfg.state_path)
    state = state_store.load_state(cfg.state_path)
    triggers = stuck_trigger.detect(events, state)
    state_store.save_state(cfg.state_path, state)
    for t in triggers:
        _draft_and_send(cfg, profile, llm, "twitter", t)


@cli.command("poll-notes")
def poll_notes() -> None:
    """Scan notes dir for new entries."""
    from .triggers import insight_trigger
    cfg, profile, llm = _load()
    if not profile:
        return
    notes_dir = Path(cfg.raw["watchers"]["notes_dir"])
    events = notes_watcher.scan(notes_dir, cfg.state_path)
    state = state_store.load_state(cfg.state_path)
    triggers = insight_trigger.detect(events, state, min_words=cfg.raw["triggers"]["insight"]["min_word_count"])
    state_store.save_state(cfg.state_path, state)
    for t in triggers:
        _draft_and_send(cfg, profile, llm, "twitter", t)


@cli.command("check-idle")
def check_idle_cmd() -> None:
    """Check idle since last approved post."""
    cfg, profile, llm = _load()
    if not profile:
        return
    days = cfg.raw["triggers"]["idle"]["days_threshold"]
    triggers = idle_trigger.detect(cfg.history_path, days_threshold=days)
    for t in triggers:
        _draft_and_send(cfg, profile, llm, "twitter", t)


@cli.command()
@click.option("--interval", default=60, help="Seconds between polls.")
def watch(interval: int) -> None:
    """Long-lived daemon: poll git + notes + terminal periodically."""
    cfg, profile, llm = _load()
    if not profile:
        click.echo("No voice profile yet. Run `build-profile` first.")
        return
    log.info("Voiceful daemon started. Polling every %ds.", interval)
    while True:
        try:
            events = git_watcher.poll_repos(cfg.repos, cfg.state_path)
            state = state_store.load_state(cfg.state_path)
            for t in ship_trigger.detect(events, state):
                _draft_and_send(cfg, profile, llm, "twitter", t)
            state_store.save_state(cfg.state_path, state)
        except Exception as e:
            log.exception("Poll error: %s", e)
        time.sleep(interval)


@cli.command("run-bot")
def run_bot_cmd() -> None:
    """Run Telegram bot (long-poll). Handles approve/edit/reject/skip + /draft."""
    cfg, profile, llm = _load()
    if not profile:
        click.echo("No voice profile. Run `build-profile` first.")
        return
    from .channels.telegram import run_bot
    run_bot(cfg, profile, llm)


@cli.command()
def refine() -> None:
    """Refine voice profile from captured edits."""
    cfg, _, _ = _load()
    refine_profile(cfg.voice_profile_path, cfg.history_path)
    click.echo("Refined.")


if __name__ == "__main__":
    cli()
