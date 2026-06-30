"""Sanctions / PEP screening via OpenSanctions.

OpenSanctions aggregates global sanctions lists (incl. the US OFAC SDN),
politically-exposed-person (PEP) records, and watchlists. The hosted API
requires a key (free for journalists, NGOs, and academic research; metered for
commercial use), so this tool is gated on OPENSANCTIONS_API_KEY. For unmetered
use, self-host the open-source `yente` server and point SCOUT_OPENSANCTIONS_URL
at it.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec

_TIMEOUT = 25.0


def _opensanctions(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission
    base = os.getenv("SCOUT_OPENSANCTIONS_URL", "https://api.opensanctions.org").rstrip("/")
    key = os.environ["OPENSANCTIONS_API_KEY"]

    def _handle(args: dict[str, Any]) -> str:
        name = str(args.get("name", "")).strip()
        if not name:
            return "Error: 'name' is required (person, org, vessel, or aircraft)."
        schema = str(args.get("schema", "")).strip()
        params: dict[str, Any] = {"q": name, "limit": int(args.get("limit", 8))}
        if schema:
            params["schema"] = schema
        try:
            resp = httpx.get(
                f"{base}/search/default",
                params=params,
                headers={"Authorization": f"ApiKey {key}"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception as exc:  # noqa: BLE001
            return f"OpenSanctions request failed: {exc}"

        if not results:
            return f"No sanctions/PEP matches for '{name}'."

        trimmed = []
        for r in results:
            props = r.get("properties", {})
            trimmed.append({
                "name": r.get("caption"),
                "type": r.get("schema"),
                "score": round(float(r.get("score", 0)), 3),
                "topics": props.get("topics"),
                "countries": props.get("country"),
                "datasets": r.get("datasets"),
            })
        top = trimmed[0]
        mission.upsert_entity(
            Entity(
                name=top["name"] or name,
                type="sanctioned_entity",
                attributes={
                    "match_topics": ", ".join(top.get("topics") or []),
                    "datasets": ", ".join(top.get("datasets") or []),
                },
                sources=["opensanctions"],
            )
        )
        return json.dumps(trimmed, indent=2)[:8000]

    return [
        Tool(
            name="sanctions_screen",
            description=(
                "Screen a person, organization, vessel, or aircraft against global "
                "sanctions lists (incl. US OFAC SDN), PEP records, and watchlists "
                "via OpenSanctions. Returns ranked matches with their topics "
                "(sanction/pep/crime), countries, and source datasets. Records the "
                "top match as an entity. Use for due-diligence and entity vetting."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name to screen."},
                    "schema": {
                        "type": "string",
                        "description": "Optional type filter: Person, Organization, Vessel, Airplane.",
                    },
                    "limit": {"type": "integer", "description": "Max matches (default 8)."},
                },
                "required": ["name"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="opensanctions",
        name="OpenSanctions",
        category="sanctions",
        summary="Screen names against sanctions, PEP, and watchlist data (OFAC SDN+).",
        builder=_opensanctions,
        env_keys=("OPENSANCTIONS_API_KEY",),
        install_hint=(
            "get a free key (journalists/NGOs/academics) at opensanctions.org/api "
            "and set OPENSANCTIONS_API_KEY, or self-host yente and set "
            "SCOUT_OPENSANCTIONS_URL"
        ),
        docs="https://www.opensanctions.org/docs/api/",
        keywords=("sanction", "sanctions", "ofac", "sdn", "pep",
                  "politically exposed", "watchlist", "due diligence",
                  "embargo", "sanctioned"),
    ),
]
