"""Stealth web fetching via Scrapling (anti-bot resistant).

Complements the basic web_fetch tool for sites behind Cloudflare/anti-bot
defenses. Imported lazily so Scrapling is an optional dependency.
"""

from __future__ import annotations

from typing import Any

from ...llm import Tool
from ...models import Mission, RawDocument
from ..registry import BuildContext, ToolSpec

_MAX_CHARS = 8000


def _scrapling(ctx: BuildContext) -> list[Tool]:
    mission: Mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        url = str(args.get("url", "")).strip()
        if not url:
            return "Error: 'url' is required."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            from scrapling.fetchers import StealthyFetcher

            page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
            text = page.get_all_text(ignore_tags=("script", "style"))
            title = page.css_first("title::text") or ""
        except Exception as exc:  # noqa: BLE001
            return f"Stealth fetch failed for {url}: {exc}"

        title = str(title).strip()
        mission.raw_documents.append(
            RawDocument(url=url, title=title, content=text)
        )
        body = text[:_MAX_CHARS]
        truncated = " [...truncated]" if len(text) > _MAX_CHARS else ""
        return f"TITLE: {title}\nURL: {url}\n\n{body}{truncated}"

    return [
        Tool(
            name="stealth_fetch",
            description=(
                "Fetch a page that blocks normal requests (Cloudflare/anti-bot) "
                "using Scrapling's stealthy browser fetcher. Slower than web_fetch "
                "- use only when web_fetch is blocked or returns no content."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch."}
                },
                "required": ["url"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="scrapling",
        name="Scrapling",
        category="web recon",
        summary="Anti-bot / stealth web scraping for protected pages.",
        builder=_scrapling,
        import_check="scrapling",
        install_hint="pip install 'scout[scraping]' (or: pip install scrapling)",
        docs="https://github.com/D4Vinci/Scrapling",
        keywords=("cloudflare", "anti-bot", "blocked", "bot protection",
                  "javascript-heavy", "captcha", "scrape protected"),
    ),
]
