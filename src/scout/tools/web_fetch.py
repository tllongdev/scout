"""Fetch a URL and extract clean, readable text.

Raw documents are recorded on the mission for provenance; the model receives a
trimmed version of the extracted text.
"""

from __future__ import annotations

from typing import Any

import httpx
import trafilatura
from bs4 import BeautifulSoup

from ..llm import Tool
from ..models import Mission, RawDocument

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 Scout/0.1"
    )
}
_MAX_CHARS = 8000


def web_fetch_tool(mission: Mission) -> Tool:
    def _fetch(args: dict[str, Any]) -> str:
        url = str(args.get("url", "")).strip()
        if not url:
            return "Error: 'url' is required."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            resp = httpx.get(
                url, headers=_HEADERS, follow_redirects=True, timeout=20.0
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return f"Fetch failed for {url}: {exc}"

        html = resp.text
        text = trafilatura.extract(html, include_comments=False) or ""
        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.string or "").strip() if soup.title else ""

        if not text:
            # Fallback: strip tags ourselves.
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = " ".join(soup.get_text(" ").split())

        mission.raw_documents.append(
            RawDocument(url=url, title=title, content=text)
        )

        body = text[:_MAX_CHARS]
        truncated = " [...truncated]" if len(text) > _MAX_CHARS else ""
        return f"TITLE: {title}\nURL: {url}\n\n{body}{truncated}"

    return Tool(
        name="web_fetch",
        description=(
            "Fetch a web page and return its readable text content. The full "
            "raw document is preserved for the report. Use after web_search to "
            "read promising sources in detail."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch.",
                }
            },
            "required": ["url"],
        },
        handler=_fetch,
    )
