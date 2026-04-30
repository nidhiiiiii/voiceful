"""Telegram channel. Sends drafts, captures approve/edit/reject/skip via inline keyboard.

Two modes:
1. send_draft_for_approval(): one-shot send, returns immediately. Used by triggers.
2. run_bot(): long-lived poller that handles user responses + /draft commands.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ..config import Config
from ..storage import history_store, queue_store

log = logging.getLogger(__name__)

EDIT_PROMPT_KEY = "awaiting_edit_for_draft_id"


def _build_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Approve", callback_data=f"approve:{draft_id}"),
        InlineKeyboardButton("Edit", callback_data=f"edit:{draft_id}"),
        InlineKeyboardButton("Reject", callback_data=f"reject:{draft_id}"),
        InlineKeyboardButton("Skip", callback_data=f"skip:{draft_id}"),
    ]])


def _format_message(draft: dict[str, Any]) -> str:
    platform = draft.get("platform", "?")
    text = draft.get("text", "")
    trigger = draft.get("trigger", "")
    context = draft.get("context", "")
    return (
        f"*Draft for {platform}*\n\n"
        f"{text}\n\n"
        f"_Triggered by: {trigger} \\| {context}_"
    )


def _escape_md(text: str) -> str:
    text = text.replace("\\", "\\\\")
    for ch in "_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, "\\" + ch)
    return text


async def _send_draft(app: Application, chat_id: str, draft: dict[str, Any]) -> int:
    platform = _escape_md(draft.get("platform", "?"))
    text = _escape_md(draft.get("text", ""))
    trigger = _escape_md(draft.get("trigger", ""))
    context = _escape_md(draft.get("context", ""))
    msg = (
        f"*Draft for {platform}*\n\n{text}\n\n_Triggered by: {trigger} \\| {context}_"
    )
    sent = await app.bot.send_message(
        chat_id=chat_id,
        text=msg,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=_build_keyboard(draft["draft_id"]),
    )
    return sent.message_id


def send_draft_for_approval(config: Config, draft: dict[str, Any]) -> None:
    """Synchronous one-shot send. Adds draft to queue + history, sends Telegram message."""
    queue_store.enqueue(config.queue_path, draft)
    history_store.append_draft(config.history_path, {
        "draft_id": draft["draft_id"],
        "platform": draft.get("platform"),
        "trigger_type": draft.get("trigger"),
        "trigger_signal": draft.get("trigger_signal", {}),
        "context": draft.get("context"),
        "draft_text": draft.get("text"),
        "user_action": "pending",
    })
    if not config.telegram_token or not config.telegram_chat_id:
        log.warning("Telegram not configured. Draft %s queued only.", draft["draft_id"])
        return
    app = Application.builder().token(config.telegram_token).build()
    asyncio.run(_send_only(app, config.telegram_chat_id, draft))


async def _send_only(app: Application, chat_id: str, draft: dict[str, Any]) -> None:
    async with app:
        await _send_draft(app, chat_id, draft)


async def _on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    query = update.callback_query
    await query.answer()
    action, draft_id = query.data.split(":", 1)
    draft = queue_store.get_pending(cfg.queue_path, draft_id)
    if not draft:
        await query.edit_message_text(query.message.text + "\n\n[expired]")
        return

    now = datetime.now(timezone.utc).isoformat()

    if action == "approve":
        try:
            import pyperclip
            pyperclip.copy(draft.get("text", ""))
            clipboard_note = " (copied to clipboard)"
        except Exception:
            clipboard_note = ""
        history_store.update_draft(cfg.history_path, draft_id, {
            "user_action": "approved",
            "approved_at": now,
        })
        queue_store.dequeue(cfg.queue_path, draft_id)
        await query.edit_message_text(query.message.text + f"\n\n[APPROVED{clipboard_note}]")
        return

    if action == "reject":
        history_store.update_draft(cfg.history_path, draft_id, {
            "user_action": "rejected",
            "approved_at": now,
        })
        queue_store.dequeue(cfg.queue_path, draft_id)
        await query.edit_message_text(query.message.text + "\n\n[REJECTED]")
        return

    if action == "skip":
        history_store.update_draft(cfg.history_path, draft_id, {
            "user_action": "skipped",
            "approved_at": now,
        })
        queue_store.dequeue(cfg.queue_path, draft_id)
        await query.edit_message_text(query.message.text + "\n\n[SKIPPED]")
        return

    if action == "edit":
        context.user_data[EDIT_PROMPT_KEY] = draft_id
        await query.message.reply_text(
            f"Send your edited version of the draft for {draft.get('platform')}. "
            f"I'll capture the diff and mark it as edited+approved."
        )
        return


async def _on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    draft_id = context.user_data.pop(EDIT_PROMPT_KEY, None)
    if not draft_id:
        return
    edited = update.message.text.strip()
    draft = queue_store.get_pending(cfg.queue_path, draft_id)
    if not draft:
        await update.message.reply_text("Draft expired.")
        return
    now = datetime.now(timezone.utc).isoformat()
    history_store.update_draft(cfg.history_path, draft_id, {
        "user_action": "edited_then_approved",
        "user_edit_text": edited,
        "approved_at": now,
    })
    queue_store.dequeue(cfg.queue_path, draft_id)
    try:
        import pyperclip
        pyperclip.copy(edited)
        note = " (copied to clipboard)"
    except Exception:
        note = ""
    await update.message.reply_text(f"Captured edit and marked approved.{note}")


async def _cmd_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    profile = context.application.bot_data["profile"]
    llm = context.application.bot_data["llm"]
    from ..drafters import get_drafter

    topic = " ".join(context.args).strip() or "general update"
    drafter = get_drafter("twitter", profile, llm)
    text = drafter.draft({
        "type": "asked",
        "context": topic,
        "raw_signal": topic,
    })
    import uuid
    draft = {
        "draft_id": str(uuid.uuid4()),
        "platform": "twitter",
        "text": text,
        "trigger": "asked",
        "context": topic,
    }
    queue_store.enqueue(cfg.queue_path, draft)
    history_store.append_draft(cfg.history_path, {
        "draft_id": draft["draft_id"],
        "platform": "twitter",
        "trigger_type": "asked",
        "context": topic,
        "draft_text": text,
        "user_action": "pending",
    })
    await _send_draft(context.application, str(update.effective_chat.id), draft)


async def _cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    pending = queue_store.list_pending(cfg.queue_path)
    if not pending:
        await update.message.reply_text("Queue empty.")
        return
    lines = [f"Pending: {len(pending)}"]
    for d in pending[:10]:
        lines.append(f"- {d.get('platform')}: {d.get('text','')[:80]}")
    await update.message.reply_text("\n".join(lines))


async def _cmd_voice_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = context.application.bot_data.get("profile")
    if not profile:
        await update.message.reply_text("No voice profile loaded.")
        return
    raw = profile.raw
    stats = raw.get("source_stats", {})
    va = raw.get("characteristics", {}).get("voice_attributes", {})
    msg = (
        f"Voice profile v{raw.get('version','?')}\n"
        f"Built: {raw.get('built_at','?')}\n"
        f"Sources: {stats}\n"
        f"Voice: {va}"
    )
    await update.message.reply_text(msg)


async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Voiceful is online.\n"
        "Commands:\n"
        "/draft <topic> draft a tweet on a topic\n"
        "/queue show pending drafts\n"
        "/voice_status show voice profile stats"
    )


def build_app(cfg: Config, profile=None, llm=None) -> Application:
    app = Application.builder().token(cfg.telegram_token).build()
    app.bot_data["cfg"] = cfg
    app.bot_data["profile"] = profile
    app.bot_data["llm"] = llm
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("draft", _cmd_draft))
    app.add_handler(CommandHandler("queue", _cmd_queue))
    app.add_handler(CommandHandler("voice_status", _cmd_voice_status))
    app.add_handler(CallbackQueryHandler(_on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))
    return app


def run_bot(cfg: Config, profile, llm) -> None:
    if not cfg.telegram_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set.")
    app = build_app(cfg, profile=profile, llm=llm)
    log.info("Telegram bot starting (long-poll).")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
