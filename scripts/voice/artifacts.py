"""Load training artifacts from a directory. Each sample = a chunk of user writing."""
from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class Sample:
    text: str
    source: str  # "tweet", "commit", "readme", "blog", "notes", "linkedin"
    origin: str  # file path or repo

    def word_count(self) -> int:
        return len(self.text.split())


def _split_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def load_txt(path: Path) -> list[Sample]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    lines = _split_lines(text)
    avg_len = sum(len(ln) for ln in lines) / max(1, len(lines))
    if len(lines) >= 2 and avg_len < 280:
        return [Sample(ln, "tweet", str(path)) for ln in lines]
    return [Sample(text, "blog", str(path))]


def load_md(path: Path) -> list[Sample]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    name = path.name.lower()
    source = "readme" if "readme" in name else "blog" if "blog" in name or "post" in name else "notes"
    return [Sample(text, source, str(path))]


def load_twitter_json(path: Path) -> list[Sample]:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if raw.startswith("window."):
            raw = raw.split("=", 1)[1].strip().rstrip(";")
        data = json.loads(raw)
    except Exception as e:
        log.warning("Failed to parse %s as twitter json: %s", path, e)
        return []
    samples: list[Sample] = []
    items = data if isinstance(data, list) else [data]
    for item in items:
        tweet = item.get("tweet", item) if isinstance(item, dict) else None
        if not isinstance(tweet, dict):
            continue
        text = tweet.get("full_text") or tweet.get("text") or ""
        if not text or text.startswith("RT @"):
            continue
        text = re.sub(r"https?://\S+", "", text).strip()
        if text:
            samples.append(Sample(text, "tweet", str(path)))
    return samples


def load_git_repo(repo: Path, author_email: str | None = None, limit: int = 500) -> list[Sample]:
    if not (repo / ".git").exists() and not repo.is_dir():
        return []
    cmd = ["git", "-C", str(repo), "log", f"--pretty=%H%x09%ae%x09%s%x09%b%x1e", f"-n{limit}"]
    try:
        out = subprocess.check_output(cmd, text=True, errors="ignore")
    except subprocess.CalledProcessError as e:
        log.warning("git log failed for %s: %s", repo, e)
        return []
    samples: list[Sample] = []
    for entry in out.split("\x1e"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\t")
        if len(parts) < 3:
            continue
        sha, email, subject = parts[0], parts[1], parts[2]
        body = parts[3] if len(parts) > 3 else ""
        if author_email and email != author_email:
            continue
        msg = subject + (("\n\n" + body) if body.strip() else "")
        samples.append(Sample(msg, "commit", f"{repo}:{sha[:8]}"))
    return samples


def load_training_dir(training_dir: Path, author_email: str | None = None) -> list[Sample]:
    if not training_dir.exists():
        log.warning("Training dir %s does not exist.", training_dir)
        return []
    samples: list[Sample] = []
    for path in sorted(training_dir.rglob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        try:
            if suffix == ".txt":
                samples.extend(load_txt(path))
            elif suffix in (".md", ".markdown"):
                samples.extend(load_md(path))
            elif suffix == ".json":
                samples.extend(load_twitter_json(path))
        except Exception as e:
            log.warning("Failed to load %s: %s", path, e)
    repos_dir = training_dir / "repos"
    if repos_dir.exists():
        for repo in repos_dir.iterdir():
            if repo.is_dir():
                samples.extend(load_git_repo(repo, author_email=author_email))
    log.info("Loaded %d samples from %s", len(samples), training_dir)
    return samples
