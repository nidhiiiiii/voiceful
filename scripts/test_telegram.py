"""One-shot Telegram smoke test. `python -m scripts.test_telegram`"""
from __future__ import annotations

import uuid

from .channels.telegram import send_draft_for_approval
from .config import load_config, setup_logging


def main() -> None:
    setup_logging()
    cfg = load_config()
    if not cfg.telegram_token or not cfg.telegram_chat_id:
        print("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.")
        return
    draft = {
        "draft_id": str(uuid.uuid4()),
        "platform": "twitter",
        "text": "smoke test from voiceful. tap any button to verify the round-trip works.",
        "trigger": "test",
        "context": "smoke test",
    }
    send_draft_for_approval(cfg, draft)
    print(f"Sent test draft {draft['draft_id']} to chat {cfg.telegram_chat_id}.")
    print("Check your Telegram. Then run `python -m scripts.main run-bot` to handle button taps.")


if __name__ == "__main__":
    main()
