"""Web search tool backed by DuckDuckGo (no API key required)."""

from __future__ import annotations

import json
from typing import Any

from ddgs import DDGS

from ..llm import Tool


def _search(args: dict[str, Any]) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return "Error: 'query' is required."
    max_results = int(args.get("max_results", 8))
    max_results = max(1, min(max_results, 20))

    try:
        with DDGS() as ddgs:
            hits = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:  # noqa: BLE001
        return f"Search failed: {exc}"

    if not hits:
        return f"No results for {query!r}."

    results = [
        {
            "title": h.get("title", ""),
            "url": h.get("href", "") or h.get("url", ""),
            "snippet": h.get("body", ""),
        }
        for h in hits
    ]
    return json.dumps(results, indent=2)


def web_search_tool() -> Tool:
    return Tool(
        name="web_search",
        description=(
            "Search the public web for pages relevant to a query. Returns a list "
            "of titles, URLs, and snippets. Use this to discover sources, then "
            "use web_fetch to read the most promising ones."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "How many results to return (1-20, default 8).",
                },
            },
            "required": ["query"],
        },
        handler=_search,
    )
