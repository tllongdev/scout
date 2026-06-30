"""Phone-number OSINT via PhoneInfoga.

PhoneInfoga validates and footprints phone numbers: country, carrier, line type,
local/international formatting, and search dorks for further lookup. It is a Go
binary with both a CLI and a ``serve`` REST API; we invoke the CLI here so no
server or API key is needed for the core scan.
"""

from __future__ import annotations

import subprocess
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec


def _phoneinfoga(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        number = str(args.get("number", "")).strip()
        if not number:
            return "Error: 'number' is required (E.164 form recommended, e.g. +14155552671)."
        try:
            proc = subprocess.run(
                ["phoneinfoga", "scan", "-n", number],
                capture_output=True, text=True, timeout=180,
            )
            out = (proc.stdout or proc.stderr).strip()
        except Exception as exc:  # noqa: BLE001
            return f"PhoneInfoga failed: {exc}"
        mission.upsert_entity(
            Entity(name=number, type="phone", sources=["phoneinfoga"])
        )
        return out[:8000] or "No data returned for this number."

    return [
        Tool(
            name="phone_osint",
            description=(
                "Footprint a phone number with PhoneInfoga: validates it and "
                "returns country, carrier, line type, formatting, and search dorks "
                "for deeper lookup. Records the number as an entity. Best with the "
                "number in E.164 form (e.g. +14155552671)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "number": {"type": "string", "description": "Phone number, ideally E.164."}
                },
                "required": ["number"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="phoneinfoga",
        name="PhoneInfoga",
        category="phone",
        summary="Phone-number validation and footprinting (country/carrier/dorks).",
        builder=_phoneinfoga,
        binary_check="phoneinfoga",
        install_hint=(
            "install the PhoneInfoga binary on PATH "
            "(see github.com/sundowndev/phoneinfoga releases)"
        ),
        docs="https://github.com/sundowndev/phoneinfoga",
        keywords=("phone", "phone number", "telephone", "mobile number",
                  "cell number", "msisdn", "caller", "carrier"),
    ),
]
