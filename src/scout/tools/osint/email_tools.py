"""Email OSINT: holehe (where an email is registered) and theHarvester (harvest
emails/subdomains/names for a domain).

- ``holehe`` checks 120+ sites to see where an email address has an account,
  without alerting the target. Some modules (X/Twitter, Instagram) are degraded
  by anti-enumeration changes, but the rest of the catalog still works. Pip
  package exposing a ``holehe`` CLI.
- ``theHarvester`` gathers emails, names, and subdomains for a domain from
  search engines and public sources. Pip package exposing a ``theHarvester`` CLI.
"""

from __future__ import annotations

import subprocess
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec


def _holehe(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        email = str(args.get("email", "")).strip()
        if not email or "@" not in email:
            return "Error: a valid 'email' is required."
        try:
            proc = subprocess.run(
                ["holehe", email, "--only-used", "--no-color"],
                capture_output=True, text=True, timeout=300,
            )
            out = (proc.stdout or proc.stderr).strip()
        except Exception as exc:  # noqa: BLE001
            return f"holehe failed: {exc}"
        mission.upsert_entity(
            Entity(name=email, type="email", sources=["holehe"])
        )
        return out[:8000] or "No sites report this email as registered."

    return [
        Tool(
            name="email_registered_sites",
            description=(
                "Discover which of 120+ sites an email address is registered on, "
                "using holehe (silent - does not alert the target). Records the "
                "email as an entity. Note: X/Twitter and Instagram modules are "
                "currently degraded; other sites still work."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Email address to check."}
                },
                "required": ["email"],
            },
            handler=_handle,
        )
    ]


def _harvester(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        domain = str(args.get("domain", "")).strip().lower()
        if not domain:
            return "Error: 'domain' is required."
        sources = str(args.get("sources", "duckduckgo,bing,crtsh,otx")).strip()
        limit = int(args.get("limit", 200))
        try:
            proc = subprocess.run(
                ["theHarvester", "-d", domain, "-b", sources, "-l", str(limit)],
                capture_output=True, text=True, timeout=420,
            )
            out = (proc.stdout or proc.stderr).strip()
        except Exception as exc:  # noqa: BLE001
            return f"theHarvester failed: {exc}"
        mission.upsert_entity(
            Entity(name=domain, type="domain", sources=["theHarvester"])
        )
        return out[:8000] or "No data harvested."

    return [
        Tool(
            name="harvest_domain",
            description=(
                "Harvest emails, employee names, and subdomains for a domain from "
                "search engines and public sources using theHarvester. Records the "
                "domain as an entity. Use for org/company footprinting."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Target domain, e.g. example.com."},
                    "sources": {
                        "type": "string",
                        "description": "Comma-separated sources (default duckduckgo,bing,crtsh,otx).",
                    },
                    "limit": {"type": "integer", "description": "Max results (default 200)."},
                },
                "required": ["domain"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="holehe",
        name="holehe",
        category="email",
        summary="Check which of 120+ sites an email is registered on (silent).",
        builder=_holehe,
        binary_check="holehe",
        install_hint="pip install 'scout[email]' (or: pip install holehe)",
        docs="https://github.com/megadose/holehe",
        keywords=("email", "email address", "@", "registered", "account exists",
                  "where is this email", "breach", "signup"),
    ),
    ToolSpec(
        id="theharvester",
        name="theHarvester",
        category="email",
        summary="Harvest emails, names, and subdomains for a domain.",
        builder=_harvester,
        binary_check="theHarvester",
        install_hint="pip install 'scout[email]' (or: pip install theHarvester)",
        docs="https://github.com/laramies/theHarvester",
        keywords=("domain", "company", "organization", "corporate email",
                  "employee emails", "subdomain", "footprint", "email harvest"),
    ),
]
