from __future__ import annotations

import os
import requests

TELEGRAM_API = "https://api.telegram.org"


def telegram_ready() -> bool:
    return bool(
        os.environ.get("TELEGRAM_BOT_TOKEN")
        and os.environ.get("TELEGRAM_CHAT_ID")
    )


def get_updates(offset: int = 0, timeout: int = 30) -> list[dict]:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.get(
        f"{TELEGRAM_API}/bot{token}/getUpdates",
        params={"offset": offset, "timeout": timeout, "allowed_updates": '["message","callback_query"]'},
        timeout=timeout + 5,
    )
    r.raise_for_status()
    return r.json().get("result", [])


def reply(chat_id: int | str, text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    for chunk in _split(text, 4096):
        requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=15,
        ).raise_for_status()


def send_message(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    # Telegram messages are limited to 4096 chars; split if needed
    chunks = _split(text, 4096)
    for chunk in chunks:
        r = requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        r.raise_for_status()


def reply_with_buttons(
    chat_id: int | str, text: str, buttons: list[list[dict]]
) -> int | None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": {"inline_keyboard": buttons},
        },
        timeout=15,
    )
    if not r.ok:
        return None
    return r.json().get("result", {}).get("message_id")


def edit_message_buttons(
    chat_id: int | str, message_id: int, buttons: list[list[dict]]
) -> bool:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.post(
        f"{TELEGRAM_API}/bot{token}/editMessageReplyMarkup",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": {"inline_keyboard": buttons},
        },
        timeout=15,
    )
    return r.ok


def answer_callback_query(callback_query_id: str, text: str | None = None) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    payload: dict = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    requests.post(
        f"{TELEGRAM_API}/bot{token}/answerCallbackQuery",
        json=payload,
        timeout=15,
    )


def _split(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
