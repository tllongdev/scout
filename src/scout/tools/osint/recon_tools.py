"""Attack-surface recon via BBOT (recursive OSINT scanner).

BBOT is AGPL-3.0 - fine for this open-source POC, but note the copyleft/network
obligations if you embed Scout in a closed commercial service. Imported lazily.
"""

from __future__ import annotations

from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec


def _bbot(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        target = str(args.get("target", "")).strip()
        if not target:
            return "Error: 'target' (domain/IP) is required."
        preset = str(args.get("preset", "subdomain-enum")).strip() or "subdomain-enum"
        try:
            from bbot.scanner import Scanner

            scan = Scanner(target, presets=[preset])
            found: list[str] = []
            for event in scan.start():
                data = getattr(event, "data", None)
                etype = getattr(event, "type", "")
                if isinstance(data, str):
                    found.append(f"{etype}: {data}")
                    if etype in {"DNS_NAME", "IP_ADDRESS", "URL", "OPEN_TCP_PORT"}:
                        mission.upsert_entity(
                            Entity(name=data, type=etype.lower(), sources=["bbot"])
                        )
                if len(found) >= 200:
                    break
        except Exception as exc:  # noqa: BLE001
            return f"BBOT scan failed: {exc}"
        return "\n".join(found[:200])[:8000] or "No assets discovered."

    return [
        Tool(
            name="attack_surface_scan",
            description=(
                "Run a BBOT recon scan against a domain/IP to discover subdomains, "
                "hosts, open ports, and URLs. Records discovered assets as entities. "
                "Default preset: subdomain-enum. Scope to targets you're authorized "
                "to assess."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Domain or IP."},
                    "preset": {
                        "type": "string",
                        "description": "BBOT preset (e.g. subdomain-enum, web-basic).",
                    },
                },
                "required": ["target"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="bbot",
        name="BBOT",
        category="recon",
        summary="Recursive attack-surface recon: subdomains, ports, URLs.",
        builder=_bbot,
        import_check="bbot",
        sensitive=True,
        install_hint="pip install bbot (AGPL-3.0)",
        docs="https://github.com/blacklanternsecurity/bbot",
        keywords=("subdomain", "attack surface", "domain recon", "infrastructure",
                  "dns enumeration", "open ports", "hosts", "exposed services"),
    ),
]
