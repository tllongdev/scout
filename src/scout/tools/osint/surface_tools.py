"""Attack-surface mapping with ProjectDiscovery's subfinder and httpx.

- ``subfinder`` does fast *passive* subdomain enumeration (26+ DNS sources),
  emitting JSONL. Lighter and faster than BBOT when you only need subdomains.
- ``httpx`` probes a list of hosts and reports which are live, plus status code,
  page title, and detected technologies.

Together they form the classic recon pipeline: subfinder -> httpx. Both are Go
binaries. Note: ``httpx`` collides by name with the Python ``httpx`` library's
optional CLI; set ``SCOUT_HTTPX_PATH`` to disambiguate if needed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec

_SPLIT = re.compile(r"[\s,]+")


def _httpx_binary() -> str:
    return os.getenv("SCOUT_HTTPX_PATH", "httpx")


def _httpx_is_projectdiscovery() -> tuple[bool, str]:
    """The binary named ``httpx`` collides with python's ``httpx[cli]``. Confirm
    the resolved binary is ProjectDiscovery's, which supports ``-version``."""
    import shutil

    binary = _httpx_binary()
    if shutil.which(binary) is None and not os.path.isfile(binary):
        return False, (
            "install the ProjectDiscovery httpx binary "
            "(go install github.com/projectdiscovery/httpx/cmd/httpx@latest)"
        )
    try:
        proc = subprocess.run(
            [binary, "-version"], capture_output=True, text=True, timeout=15
        )
    except Exception:  # noqa: BLE001
        return False, "could not run httpx -version"
    blob = f"{proc.stdout}\n{proc.stderr}".lower()
    if proc.returncode == 0 and ("projectdiscovery" in blob or "httpx version" in blob):
        return True, "ready"
    return False, (
        "the 'httpx' on PATH looks like python httpx[cli], not ProjectDiscovery's; "
        "set SCOUT_HTTPX_PATH to the ProjectDiscovery binary"
    )


def _subfinder(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        domain = str(args.get("domain", "")).strip().lower()
        if not domain:
            return "Error: 'domain' is required."
        cmd = ["subfinder", "-d", domain, "-oJ", "-silent", "-nc"]
        if args.get("all_sources"):
            cmd.append("-all")
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
            )
        except Exception as exc:  # noqa: BLE001
            return f"subfinder failed: {exc}"
        hosts: list[str] = []
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                hosts.append(json.loads(line).get("host", ""))
            except json.JSONDecodeError:
                continue
        hosts = sorted({h for h in hosts if h})
        if not hosts:
            return (proc.stderr or "No subdomains found.").strip()[:8000]
        mission.upsert_entity(
            Entity(
                name=domain,
                type="domain",
                attributes={"subdomain_count": str(len(hosts))},
                sources=["subfinder"],
            )
        )
        return "\n".join(hosts)[:8000]

    return [
        Tool(
            name="enumerate_subdomains",
            description=(
                "Passively enumerate subdomains for a domain with subfinder (fast, "
                "no direct contact with the target). Records the domain as an entity "
                "and returns the list of discovered subdomains - feed these to "
                "probe_hosts to find which are live."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Root domain, e.g. example.com."},
                    "all_sources": {
                        "type": "boolean",
                        "description": "Use all passive sources (slower, broader).",
                    },
                },
                "required": ["domain"],
            },
            handler=_handle,
        )
    ]


def _httpx(ctx: BuildContext) -> list[Tool]:
    binary = _httpx_binary()

    def _handle(args: dict[str, Any]) -> str:
        raw = str(args.get("hosts", "")).strip()
        if not raw:
            return "Error: 'hosts' is required (one or more hosts/URLs)."
        hosts = [h for h in _SPLIT.split(raw) if h]
        if not hosts:
            return "Error: no valid hosts parsed."
        try:
            proc = subprocess.run(
                [binary, "-json", "-silent", "-no-color", "-title",
                 "-status-code", "-tech-detect"],
                input="\n".join(hosts), capture_output=True, text=True, timeout=300,
            )
        except Exception as exc:  # noqa: BLE001
            return f"httpx failed: {exc}"
        rows: list[dict[str, Any]] = []
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append({
                "url": d.get("url"),
                "status_code": d.get("status_code"),
                "title": d.get("title"),
                "tech": d.get("tech") or d.get("technologies"),
                "webserver": d.get("webserver"),
            })
        if not rows:
            return (proc.stderr or "No live hosts found.").strip()[:8000]
        return json.dumps(rows, indent=2)[:8000]

    return [
        Tool(
            name="probe_hosts",
            description=(
                "Probe one or more hosts/URLs with httpx to find which are live and "
                "report status code, page title, web server, and detected "
                "technologies. Accepts a comma/space/newline-separated list - pair "
                "with enumerate_subdomains to triage a domain's live surface."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "hosts": {
                        "type": "string",
                        "description": "Hosts or URLs, separated by commas/spaces/newlines.",
                    }
                },
                "required": ["hosts"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="subfinder",
        name="subfinder",
        category="web recon",
        summary="Fast passive subdomain enumeration (26+ sources).",
        builder=_subfinder,
        binary_check="subfinder",
        install_hint=(
            "install the subfinder binary "
            "(go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest)"
        ),
        docs="https://github.com/projectdiscovery/subfinder",
        keywords=("subdomain", "attack surface", "dns enumeration",
                  "asset discovery", "domain recon"),
    ),
    ToolSpec(
        id="httpx",
        name="httpx (ProjectDiscovery)",
        category="web recon",
        summary="Probe hosts for liveness, status, title, and technologies.",
        builder=_httpx,
        probe=_httpx_is_projectdiscovery,
        install_hint=(
            "install the ProjectDiscovery httpx binary "
            "(go install github.com/projectdiscovery/httpx/cmd/httpx@latest); "
            "set SCOUT_HTTPX_PATH if it clashes with python httpx[cli]"
        ),
        docs="https://github.com/projectdiscovery/httpx",
        keywords=("live hosts", "http probe", "status code", "web technologies",
                  "tech stack", "fingerprint", "which hosts are up"),
    ),
]
