"""Account/identity OSINT: username enumeration and Google account footprinting."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec


def _tookie(ctx: BuildContext) -> list[Tool]:
    repo = os.environ["SCOUT_TOOKIE_PATH"]
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        username = str(args.get("username", "")).strip()
        if not username:
            return "Error: 'username' is required."
        script = os.path.join(repo, "brib.py")
        if not os.path.exists(script):
            return f"tookie-osint not found at {script}."
        try:
            proc = subprocess.run(
                ["python3", "brib.py", "-u", username],
                capture_output=True, text=True, timeout=300, cwd=repo,
            )
            out = (proc.stdout or proc.stderr).strip()
        except Exception as exc:  # noqa: BLE001
            return f"tookie-osint failed: {exc}"
        mission.upsert_entity(
            Entity(name=username, type="username", sources=["tookie-osint"])
        )
        return out[:8000] or "No accounts found."

    return [
        Tool(
            name="username_search",
            description=(
                "Enumerate online accounts for a username across many sites using "
                "tookie-osint. Records the username as an entity. Returns the list "
                "of discovered profiles."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username to hunt."}
                },
                "required": ["username"],
            },
            handler=_handle,
        )
    ]


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
        id="tookie",
        name="tookie-osint",
        category="accounts",
        summary="Username -> accounts enumeration across many sites.",
        builder=_tookie,
        env_keys=("SCOUT_TOOKIE_PATH",),
        install_hint="clone Alfredredbird/tookie-osint and set SCOUT_TOOKIE_PATH",
        docs="https://github.com/Alfredredbird/tookie-osint",
        keywords=("username", "handle", "alias", "screen name", "profile",
                  "social media account", "online accounts"),
    ),
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
