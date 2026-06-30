"""Reddit OSINT via the public archive APIs (no Reddit credentials needed).

PullPush and Arctic Shift mirror Reddit content - including removed/deleted
posts - and are directly callable over HTTP, which is a far better agent fit
than the GUI-only Reddit OSINT dashboards.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec

_TIMEOUT = 25.0


def _reddit(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _history(args: dict[str, Any]) -> str:
        author = str(args.get("author", "")).strip().lstrip("u/")
        if not author:
            return "Error: 'author' (Reddit username) is required."
        kind = str(args.get("kind", "comment")).strip()
        if kind not in {"comment", "submission"}:
            kind = "comment"
        try:
            resp = httpx.get(
                f"https://api.pullpush.io/reddit/search/{kind}/",
                params={"author": author, "size": int(args.get("limit", 25))},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception as exc:  # noqa: BLE001
            return f"PullPush request failed: {exc}"

        if data:
            subs = sorted({d.get("subreddit", "") for d in data if d.get("subreddit")})
            mission.upsert_entity(
                Entity(
                    name=f"u/{author}",
                    type="reddit_user",
                    attributes={"active_subreddits": ", ".join(subs[:20])},
                    sources=[f"https://reddit.com/user/{author}"],
                )
            )
        trimmed = [
            {
                "subreddit": d.get("subreddit"),
                "created_utc": d.get("created_utc"),
                "body": (d.get("body") or d.get("title") or "")[:500],
                "score": d.get("score"),
                "permalink": d.get("permalink"),
            }
            for d in data
        ]
        return json.dumps(trimmed, indent=2)[:8000] or "No content found."

    def _search(args: dict[str, Any]) -> str:
        q = str(args.get("query", "")).strip()
        if not q:
            return "Error: 'query' is required."
        params: dict[str, Any] = {"q": q, "size": int(args.get("limit", 25))}
        if args.get("subreddit"):
            params["subreddit"] = str(args["subreddit"]).strip()
        try:
            resp = httpx.get(
                "https://api.pullpush.io/reddit/search/submission/",
                params=params,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception as exc:  # noqa: BLE001
            return f"PullPush search failed: {exc}"
        trimmed = [
            {
                "subreddit": d.get("subreddit"),
                "author": d.get("author"),
                "title": d.get("title"),
                "created_utc": d.get("created_utc"),
                "permalink": d.get("permalink"),
            }
            for d in data
        ]
        return json.dumps(trimmed, indent=2)[:8000] or "No results."

    return [
        Tool(
            name="reddit_user_history",
            description=(
                "Fetch a Reddit user's comment or submission history (incl. removed "
                "content) via the PullPush archive. Records the user as an entity "
                "with their active subreddits. No Reddit login required."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "author": {"type": "string", "description": "Reddit username."},
                    "kind": {"type": "string", "description": "comment | submission"},
                    "limit": {"type": "integer", "description": "Max items (default 25)."},
                },
                "required": ["author"],
            },
            handler=_history,
        ),
        Tool(
            name="reddit_search",
            description=(
                "Search Reddit submissions by keyword (optionally within a "
                "subreddit) via the PullPush archive. No Reddit login required."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms."},
                    "subreddit": {"type": "string", "description": "Optional subreddit."},
                    "limit": {"type": "integer", "description": "Max results (default 25)."},
                },
                "required": ["query"],
            },
            handler=_search,
        ),
    ]


SPECS = [
    ToolSpec(
        id="reddit",
        name="Reddit OSINT (PullPush)",
        category="social",
        summary="Reddit user history + search, including removed content; no login.",
        builder=_reddit,
        keyless=True,
        docs="https://pullpush.io",
    ),
]
