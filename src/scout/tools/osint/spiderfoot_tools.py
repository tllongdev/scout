"""SpiderFoot - the all-in-one OSINT automation engine (200+ modules).

SpiderFoot correlates data from a huge module catalog (DNS, WHOIS, crt.sh,
breach data, search engines, threat-intel feeds, etc.) into one scan. We run it
from a cloned repo via its CLI with JSON output. Use cases:

- ``passive`` (default) - never touches the target directly; safe for stealth.
- ``footprint`` / ``investigate`` / ``all`` - actively probe the target; only
  use with authorization (hence this tool is flagged sensitive).
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec

_USE_CASES = {"passive", "footprint", "investigate", "all"}


def _spiderfoot(ctx: BuildContext) -> list[Tool]:
    repo = os.environ["SCOUT_SPIDERFOOT_PATH"]
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        target = str(args.get("target", "")).strip()
        if not target:
            return "Error: 'target' is required (domain, IP, email, name, etc.)."
        use_case = str(args.get("use_case", "passive")).strip().lower()
        if use_case not in _USE_CASES:
            use_case = "passive"
        script = os.path.join(repo, "sf.py")
        if not os.path.exists(script):
            return f"SpiderFoot not found at {script}."
        try:
            proc = subprocess.run(
                ["python3", "sf.py", "-s", target, "-u", use_case, "-o", "json", "-q"],
                capture_output=True, text=True, timeout=900, cwd=repo,
            )
            out = (proc.stdout or proc.stderr).strip()
        except Exception as exc:  # noqa: BLE001
            return f"SpiderFoot failed: {exc}"
        mission.upsert_entity(
            Entity(name=target, type="osint_target", sources=["spiderfoot"])
        )
        return out[:8000] or "SpiderFoot returned no events."

    return [
        Tool(
            name="spiderfoot_scan",
            description=(
                "Run a SpiderFoot OSINT scan against a target (domain, IP, email, "
                "name, phone, username) using its 200+ modules and return correlated "
                "events as JSON. Records the target as an entity. Defaults to a "
                "'passive' use case (no direct contact with the target); only use "
                "'footprint'/'investigate'/'all' with authorization."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Seed: domain, IP, email, name, phone, or username.",
                    },
                    "use_case": {
                        "type": "string",
                        "description": "passive (default) | footprint | investigate | all.",
                    },
                },
                "required": ["target"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="spiderfoot",
        name="SpiderFoot",
        category="recon",
        summary="All-in-one OSINT automation across 200+ modules; correlated scan.",
        builder=_spiderfoot,
        env_keys=("SCOUT_SPIDERFOOT_PATH",),
        sensitive=True,
        install_hint="clone smicallef/spiderfoot and set SCOUT_SPIDERFOOT_PATH",
        docs="https://github.com/smicallef/spiderfoot",
        keywords=("footprint", "attack surface", "threat intelligence",
                  "reconnaissance", "investigate", "correlate", "full osint",
                  "everything about", "comprehensive scan"),
    ),
]
