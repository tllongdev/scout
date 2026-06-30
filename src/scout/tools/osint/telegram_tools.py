"""Telegram OSINT via public channel web previews.

Public Telegram channels expose a read-only web preview at ``t.me/s/<channel>``
that lists recent posts without any login or API key. This tool fetches and
parses that preview so agents can read a channel's recent messages and activity.
Only public channels are accessible; private channels return nothing.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec

_TIMEOUT = 25.0


def _telegram(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        channel = str(args.get("channel", "")).strip().lstrip("@").rstrip("/")
        channel = channel.replace("https://t.me/", "").replace("t.me/", "").replace("s/", "")
        if not channel:
            return "Error: 'channel' is required (public channel handle)."
        limit = int(args.get("limit", 20))
        try:
            resp = httpx.get(
                f"https://t.me/s/{channel}",
                timeout=_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (scout-osint)"},
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return f"Telegram fetch failed for @{channel}: {exc}"

        soup = BeautifulSoup(resp.text, "html.parser")
        posts: list[dict[str, Any]] = []
        for msg in soup.select(".tgme_widget_message")[-limit:]:
            text_el = msg.select_one(".tgme_widget_message_text")
            time_el = msg.select_one("time")
            views_el = msg.select_one(".tgme_widget_message_views")
            posts.append({
                "text": (text_el.get_text(" ", strip=True) if text_el else "")[:600],
                "datetime": time_el.get("datetime") if time_el else None,
                "views": views_el.get_text(strip=True) if views_el else None,
            })

        if not posts:
            title = soup.select_one(".tgme_page_title")
            if title is None:
                return f"No public preview for '{channel}' (private or nonexistent)."
            return f"Channel '{channel}' exists but no posts were parseable."

        mission.upsert_entity(
            Entity(
                name=f"@{channel}",
                type="telegram_channel",
                sources=[f"https://t.me/s/{channel}"],
            )
        )
        return json.dumps(posts, indent=2)[:8000]

    return [
        Tool(
            name="telegram_channel",
            description=(
                "Read recent posts from a PUBLIC Telegram channel via its web "
                "preview (no login/API key). Returns message text, timestamps, and "
                "view counts, and records the channel as an entity. Private "
                "channels are not accessible."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Public channel handle (e.g. durov)."},
                    "limit": {"type": "integer", "description": "Max recent posts (default 20)."},
                },
                "required": ["channel"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="telegram",
        name="Telegram OSINT",
        category="social",
        summary="Read public Telegram channel posts via web preview; no login.",
        builder=_telegram,
        keyless=True,
        docs="https://t.me",
        keywords=("telegram", "tg channel", "t.me", "telegram channel",
                  "telegram group"),
    ),
]
