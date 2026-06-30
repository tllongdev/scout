"""Global news and event monitoring via the GDELT Project.

GDELT indexes worldwide news in near-real-time. The DOC 2.0 API is free and
keyless, returning articles that match a query across thousands of outlets and
languages - good for surfacing recent coverage, events, and geopolitical
context for a person, org, place, or topic.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ...llm import Tool
from ...models import RawDocument
from ..registry import BuildContext, ToolSpec

_TIMEOUT = 30.0
_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def _gdelt(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' is required."
        params: dict[str, Any] = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": int(args.get("limit", 25)),
            "sort": str(args.get("sort", "datedesc")),
        }
        timespan = str(args.get("timespan", "")).strip()
        if timespan:
            params["timespan"] = timespan
        try:
            resp = httpx.get(
                _API, params=params, timeout=_TIMEOUT,
                headers={"User-Agent": "scout-osint/1.0"},
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
        except Exception as exc:  # noqa: BLE001
            return f"GDELT request failed: {exc}"

        if not articles:
            return f"No recent news found for '{query}'."

        trimmed = []
        for a in articles:
            trimmed.append({
                "title": a.get("title"),
                "url": a.get("url"),
                "domain": a.get("domain"),
                "seendate": a.get("seendate"),
                "country": a.get("sourcecountry"),
                "language": a.get("language"),
            })
            mission.raw_documents.append(
                RawDocument(url=a.get("url", ""), title=a.get("title", ""))
            )
        return json.dumps(trimmed, indent=2)[:8000]

    return [
        Tool(
            name="news_search",
            description=(
                "Search worldwide news in near-real-time via GDELT (thousands of "
                "outlets, many languages). Returns matching articles with title, "
                "URL, source domain, date, and country. Use to surface recent "
                "coverage and events for a person, org, place, or topic. Optional "
                "'timespan' like '7d' or '24h' narrows the window."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms (names, topics, places)."},
                    "timespan": {"type": "string", "description": "Optional window, e.g. 24h, 7d, 1m."},
                    "sort": {"type": "string", "description": "datedesc (default), dateasc, or hybridrel."},
                    "limit": {"type": "integer", "description": "Max articles (default 25)."},
                },
                "required": ["query"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="gdelt_news",
        name="GDELT News",
        category="news",
        summary="Near-real-time global news/event search across thousands of outlets.",
        builder=_gdelt,
        keyless=True,
        docs="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/",
        keywords=("news", "recent coverage", "media", "press", "headlines",
                  "current events", "geopolitical", "breaking", "reported"),
    ),
]
