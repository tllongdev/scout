"""Account/identity OSINT: Google account footprinting.

Username enumeration lives in ``username_tools`` (maigret, Blackbird).
"""

from __future__ import annotations

import subprocess
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec


def _ghunt(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        email = str(args.get("email", "")).strip()
        if not email:
            return "Error: 'email' is required."
        try:
            proc = subprocess.run(
                ["ghunt", "email", email],
                capture_output=True, text=True, timeout=180,
            )
            out = (proc.stdout or proc.stderr).strip()
        except Exception as exc:  # noqa: BLE001
            return f"GHunt failed (is it authenticated with `ghunt login`?): {exc}"
        mission.upsert_entity(
            Entity(name=email, type="email", sources=["ghunt"])
        )
        return out[:8000] or "No Google account data returned."

    return [
        Tool(
            name="google_account_osint",
            description=(
                "Footprint a Google account from an email via GHunt: owner name, "
                "Gaia ID, profile photo, active Google services, Maps reviews, "
                "public Drive files. Requires GHunt to be authenticated."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Target Gmail/Google email."}
                },
                "required": ["email"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="ghunt",
        name="GHunt",
        category="accounts",
        summary="Google account footprinting from an email address.",
        builder=_ghunt,
        binary_check="ghunt",
        install_hint="pip install ghunt && ghunt login",
        docs="https://github.com/mxrch/GHunt",
        keywords=("gmail", "google account", "@gmail", "email address",
                  "google profile", "gaia id"),
    ),
]
