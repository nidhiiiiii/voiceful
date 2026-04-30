"""Git watcher. Polls repos for new commits since last seen sha."""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage.state_store import load_state, save_state

log = logging.getLogger(__name__)


def _git(repo: Path, *args: str) -> str:
    cmd = ["git", "-C", str(repo), *args]
    try:
        return subprocess.check_output(cmd, text=True, errors="ignore").strip()
    except subprocess.CalledProcessError as e:
        log.warning("git %s failed in %s: %s", args, repo, e)
        return ""


def _author_email(repo: Path) -> str:
    return _git(repo, "config", "user.email")


def _new_commits(repo: Path, since_sha: str | None) -> list[dict[str, Any]]:
    if since_sha:
        rng = f"{since_sha}..HEAD"
        out = _git(repo, "log", rng, "--pretty=%H%x09%ae%x09%aI%x09%s%x1e", "-n50")
    else:
        out = _git(repo, "log", "--pretty=%H%x09%ae%x09%aI%x09%s%x1e", "-n5")
    if not out:
        return []
    own = _author_email(repo)
    commits = []
    for entry in out.split("\x1e"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\t")
        if len(parts) < 4:
            continue
        sha, email, ts, subject = parts
        if own and email and email != own:
            continue
        diff_stat = _git(repo, "show", "--stat", "--format=", sha)
        files = _git(repo, "show", "--name-only", "--format=", sha).splitlines()
        commits.append({
            "type": "git_commit",
            "repo": str(repo),
            "sha": sha,
            "message": subject,
            "diff_summary": diff_stat.splitlines()[-1] if diff_stat else "",
            "files_changed": [f for f in files if f.strip()][:20],
            "timestamp": ts,
            "author_email": email,
        })
    return list(reversed(commits))


def poll_repos(repos: list[Path], state_path: Path) -> list[dict[str, Any]]:
    state = load_state(state_path)
    git_state = state.setdefault("git", {})
    events: list[dict[str, Any]] = []
    for repo in repos:
        if not repo.exists() or not (repo / ".git").exists():
            log.warning("Skipping %s (not a git repo)", repo)
            continue
        last = git_state.get(str(repo))
        new = _new_commits(repo, last)
        if new:
            log.info("Found %d new commits in %s", len(new), repo)
            events.extend(new)
            git_state[str(repo)] = new[-1]["sha"]
        else:
            head = _git(repo, "rev-parse", "HEAD")
            if head and not last:
                git_state[str(repo)] = head
    state["git"] = git_state
    state["last_poll"] = datetime.now(timezone.utc).isoformat()
    save_state(state_path, state)
    return events
