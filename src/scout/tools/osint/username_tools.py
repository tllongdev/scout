"""Username enumeration: maigret (deep dossier) and Blackbird (fast/WhatsMyName).

Two complementary tools - run either or both, since each catches accounts the
other misses:

- ``maigret`` checks 3,000+ sites and parses profile pages to extract metadata
  and linked identifiers (recursive identity graph). Slower, deeper. Installed
  as a pip package, so it is importable and exposes a ``maigret`` CLI.
- ``Blackbird`` is a fast async checker backed by the WhatsMyName database
  (600+ sites), covers username *and* email, and has a low false-positive rate.
  It is run from a cloned repo, so we invoke it by path.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec


def _maigret(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        username = str(args.get("username", "")).strip().lstrip("@")
        if not username:
            return "Error: 'username' is required."
        top = int(args.get("top_sites", 150))
        try:
            proc = subprocess.run(
                [
                    "maigret", username,
                    "--top-sites", str(top),
                    "--timeout", "20",
                    "--no-recursion",
                    "--no-progressbar",
                ],
                capture_output=True, text=True, timeout=420,
            )
            out = (proc.stdout or proc.stderr).strip()
        except Exception as exc:  # noqa: BLE001
            return f"maigret failed: {exc}"
        mission.upsert_entity(
            Entity(name=username, type="username", sources=["maigret"])
        )
        return out[:8000] or "No accounts found."

    return [
        Tool(
            name="maigret_username",
            description=(
                "Build a deep dossier on a username with maigret: checks thousands "
                "of sites, parses profile pages for names/links/IDs, and surfaces "
                "linked identities. Records the username as an entity. Slower but "
                "the most thorough username tool - use when depth matters."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username/handle to hunt."},
                    "top_sites": {
                        "type": "integer",
                        "description": "How many top sites to check (default 150).",
                    },
                },
                "required": ["username"],
            },
            handler=_handle,
        )
    ]


def _blackbird(ctx: BuildContext) -> list[Tool]:
    repo = os.environ["SCOUT_BLACKBIRD_PATH"]
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        username = str(args.get("username", "")).strip().lstrip("@")
        email = str(args.get("email", "")).strip()
        if not username and not email:
            return "Error: provide 'username' or 'email'."
        script = os.path.join(repo, "blackbird.py")
        if not os.path.exists(script):
            return f"Blackbird not found at {script}."
        cmd = ["python3", "blackbird.py", "--no-update"]
        if username:
            cmd += ["-u", username]
        if email:
            cmd += ["-e", email]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, cwd=repo,
            )
            out = (proc.stdout or proc.stderr).strip()
        except Exception as exc:  # noqa: BLE001
            return f"Blackbird failed: {exc}"
        if username:
            mission.upsert_entity(
                Entity(name=username, type="username", sources=["blackbird"])
            )
        if email:
            mission.upsert_entity(
                Entity(name=email, type="email", sources=["blackbird"])
            )
        return out[:8000] or "No accounts found."

    return [
        Tool(
            name="blackbird_search",
            description=(
                "Fast username/email account search with Blackbird (WhatsMyName "
                "database, 600+ sites, low false-positive rate). Good first sweep "
                "and complements maigret by surfacing different accounts. Accepts a "
                "username, an email, or both."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username/handle."},
                    "email": {"type": "string", "description": "Email address."},
                },
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="maigret",
        name="maigret",
        category="accounts",
        summary="Deep username dossier across 3,000+ sites with profile parsing.",
        builder=_maigret,
        import_check="maigret",
        install_hint="pip install 'scout[accounts]' (or: pip install maigret)",
        docs="https://github.com/soxoj/maigret",
        keywords=("username", "handle", "alias", "screen name", "profile",
                  "social media account", "online accounts", "dossier",
                  "identity", "socmint"),
    ),
    ToolSpec(
        id="blackbird",
        name="Blackbird",
        category="accounts",
        summary="Fast username/email account search (WhatsMyName, 600+ sites).",
        builder=_blackbird,
        env_keys=("SCOUT_BLACKBIRD_PATH",),
        install_hint="clone p1ngul1n0/blackbird and set SCOUT_BLACKBIRD_PATH",
        docs="https://github.com/p1ngul1n0/blackbird",
        keywords=("username", "handle", "alias", "screen name", "profile",
                  "social media account", "online accounts", "whatsmyname"),
    ),
]
