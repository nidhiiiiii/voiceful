"""Side-by-side demo: Voiceful (with profile) vs vanilla LLM. For the hackathon demo."""
from __future__ import annotations

import time

import click

from .config import load_config, setup_logging
from .drafters import get_drafter
from .llm_client import make_client
from .voice.profile_loader import load_profile

DEMO_CASES = [
    ("ship", "shipped voiceful, the agent watches your repo and drafts tweets in your voice"),
    ("stuck", "spent 90 min on what turned out to be a typo in a config file"),
    ("insight", "TIL git log has --since with relative dates like 2.weeks"),
]


@click.command()
@click.option("--platform", default="twitter", type=click.Choice(["twitter", "linkedin", "devto"]))
def main(platform: str) -> None:
    setup_logging()
    cfg = load_config()
    profile = load_profile(cfg.voice_profile_path)
    llm = make_client(cfg)
    drafter = get_drafter(platform, profile, llm)

    for trig, ctx in DEMO_CASES:
        click.echo("\n" + "=" * 70)
        click.echo(f"TRIGGER: {trig}")
        click.echo(f"CONTEXT: {ctx}")
        click.echo("-" * 70)

        voiceful = drafter.draft({"type": trig, "context": ctx, "raw_signal": ctx})
        click.echo("[VOICEFUL]")
        click.echo(voiceful)

        click.echo()

        generic = llm.complete(
            system=f"You are a social media writer. Write a {platform} post.",
            user=f"Write a {platform} post about: {ctx}",
            max_tokens=400,
        )
        click.echo("[GENERIC LLM]")
        click.echo(generic)
        time.sleep(8)  # stay under Groq free tier TPM


if __name__ == "__main__":
    main()
