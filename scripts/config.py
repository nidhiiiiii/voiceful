"""Config loader. Reads ~/.openclaw/voiceful/config.yaml and env vars."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv(override=True)

DEFAULT_HOME = Path(os.path.expanduser(os.environ.get("VOICEFUL_HOME", "~/.openclaw/voiceful")))
ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        def repl(m: re.Match) -> str:
            return os.environ.get(m.group(1), "")
        return ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


DEFAULT_CONFIG: dict[str, Any] = {
    "user": {"name": "Nidhi"},
    "training_dir": str(DEFAULT_HOME / "training"),
    "watchers": {
        "repos": [],
        "notes_dir": "~/notes",
        "workspace_dirs": ["~/code"],
        "shell_history": "~/.zsh_history",
    },
    "platforms": {
        "twitter": {"enabled": True},
        "linkedin": {"enabled": True},
        "medium": {"enabled": False},
        "devto": {"enabled": False},
        "hashnode": {"enabled": False},
    },
    "channels": {
        "telegram": {
            "enabled": True,
            "bot_token": "${TELEGRAM_BOT_TOKEN}",
            "chat_id": "${TELEGRAM_CHAT_ID}",
        },
        "discord": {"enabled": False},
    },
    "triggers": {
        "ship": {"enabled": True},
        "stuck": {"enabled": True, "error_repeat_threshold": 3, "error_window_minutes": 60},
        "insight": {"enabled": True, "min_word_count": 50},
        "idle": {"enabled": True, "days_threshold": 3},
        "asked": {"enabled": True},
    },
    "llm": {
        "provider": "groq",
        "groq_api_key": "${GROQ_API_KEY}",
        "groq_model": "qwen/qwen3-32b",
        "hf_token": "${HF_TOKEN}",
        "hf_model": "mistralai/Mistral-7B-Instruct-v0.3",
        "openrouter_api_key": "${OPENROUTER_API_KEY}",
        "openrouter_model": "meta-llama/llama-3.1-8b-instruct",
        "together_api_key": "${TOGETHER_API_KEY}",
        "together_model": "meta-llama/Llama-3.1-8B-Instruct-Turbo",
        "model": "claude-sonnet-4-5-20250929",
        "api_key": "${ANTHROPIC_API_KEY}",
    },
}


@dataclass
class Config:
    home: Path
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def training_dir(self) -> Path:
        return Path(os.path.expanduser(self.raw["training_dir"]))

    @property
    def voice_profile_path(self) -> Path:
        return self.home / "voice_profile.json"

    @property
    def history_path(self) -> Path:
        return self.home / "history.json"

    @property
    def queue_path(self) -> Path:
        return self.home / "queue.json"

    @property
    def state_path(self) -> Path:
        return self.home / "state.json"

    @property
    def llm_model(self) -> str:
        return self.raw["llm"]["model"]

    @property
    def llm_api_key(self) -> str:
        return self.raw["llm"]["api_key"] or os.environ.get("ANTHROPIC_API_KEY", "")

    @property
    def telegram_token(self) -> str:
        return self.raw["channels"]["telegram"]["bot_token"] or os.environ.get("TELEGRAM_BOT_TOKEN", "")

    @property
    def telegram_chat_id(self) -> str:
        return self.raw["channels"]["telegram"]["chat_id"] or os.environ.get("TELEGRAM_CHAT_ID", "")

    @property
    def repos(self) -> list[Path]:
        return [Path(os.path.expanduser(r)) for r in self.raw["watchers"]["repos"]]


def _merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Path | None = None) -> Config:
    home = DEFAULT_HOME
    home.mkdir(parents=True, exist_ok=True)
    config_path = path or (home / "config.yaml")
    raw: dict[str, Any] = dict(DEFAULT_CONFIG)
    if config_path.exists():
        with config_path.open() as f:
            user_raw = yaml.safe_load(f) or {}
        raw = _merge(raw, user_raw)
    raw = _expand(raw)
    return Config(home=home, raw=raw)


def write_default_config(path: Path | None = None) -> Path:
    home = DEFAULT_HOME
    home.mkdir(parents=True, exist_ok=True)
    config_path = path or (home / "config.yaml")
    if not config_path.exists():
        with config_path.open("w") as f:
            yaml.safe_dump(DEFAULT_CONFIG, f, sort_keys=False)
    return config_path


def setup_logging() -> None:
    level = os.environ.get("VOICEFUL_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Avoid leaking secrets via verbose HTTP logs (e.g., Telegram bot token in URL).
    logging.getLogger("httpx").setLevel(logging.WARNING)
