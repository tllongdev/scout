"""Dark-web search via Robin (LLM-driven .onion investigation).

Robin needs a running Tor service and its own LLM configured. It's exposed here
as a CLI wrapper; availability is gated on the `robin` binary being installed.
Sensitive: dark-web access carries obvious legal/ethical considerations.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Any

from ...llm import Tool
from ..registry import BuildContext, ToolSpec


def _robin(ctx: BuildContext) -> list[Tool]:
    def _handle(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' is required."
        model = os.getenv("ROBIN_MODEL", ctx.config.model)
        with tempfile.NamedTemporaryFile(
            "r", suffix=".md", delete=False
        ) as tmp:
            out_path = tmp.name
        try:
            proc = subprocess.run(
                ["robin", "cli", "-m", model, "-q", query, "-o", out_path],
                capture_output=True, text=True, timeout=1800,
            )
            try:
                with open(out_path) as fh:
                    report = fh.read()
            except OSError:
                report = ""
            return (report or proc.stdout or proc.stderr).strip()[:8000] or (
                "Robin returned no output (is Tor running?)."
            )
        except Exception as exc:  # noqa: BLE001
            return f"Robin failed: {exc}"
        finally:
            try:
                os.unlink(out_path)
            except OSError:
                pass

    return [
        Tool(
            name="darkweb_search",
            description=(
                "Search the dark web for a topic using Robin: queries ~15 .onion "
                "search engines, LLM-filters results, scrapes them, and returns a "
                "markdown intelligence summary. Requires Tor running."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to investigate."}
                },
                "required": ["query"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="robin",
        name="Robin",
        category="dark web",
        summary="LLM-driven dark-web search and reporting (needs Tor).",
        builder=_robin,
        binary_check="robin",
        sensitive=True,
        install_hint="pip install robin-osint (or clone apurvsinghgautam/robin) + run Tor",
        docs="https://github.com/apurvsinghgautam/robin",
        keywords=("dark web", "darkweb", "onion", "tor", "deep web",
                  "hidden service", "breach forum", "leak forum"),
    ),
]
