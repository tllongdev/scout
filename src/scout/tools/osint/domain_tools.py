"""Domain-centric OSINT: dnstwist (lookalike/typosquat detection) and Photon
(fast OSINT crawler).

- ``dnstwist`` generates and resolves permutations of a domain to surface
  typosquats, phishing/lookalike domains, and brand-impersonation. Pip package
  exposing a ``dnstwist`` CLI.
- ``Photon`` crawls a site and extracts URLs, emails, social handles, secrets,
  and files. Run from a cloned repo, so we invoke it by path and read its
  output directory.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec


def _dnstwist(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        domain = str(args.get("domain", "")).strip().lower()
        if not domain:
            return "Error: 'domain' is required."
        cmd = ["dnstwist", "--format", "json"]
        if args.get("registered_only", True):
            cmd.append("--registered")
        cmd.append(domain)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
            )
            raw = (proc.stdout or "").strip()
        except Exception as exc:  # noqa: BLE001
            return f"dnstwist failed: {exc}"
        if not raw:
            return (proc.stderr or "No permutations resolved.").strip()[:8000]
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            return raw[:8000]
        mission.upsert_entity(
            Entity(name=domain, type="domain", sources=["dnstwist"])
        )
        trimmed = [
            {
                "domain": r.get("domain"),
                "fuzzer": r.get("fuzzer"),
                "dns_a": r.get("dns_a"),
                "dns_mx": r.get("dns_mx"),
            }
            for r in rows
            if r.get("domain") != domain
        ]
        return json.dumps(trimmed, indent=2)[:8000] or "No lookalike domains found."

    return [
        Tool(
            name="lookalike_domains",
            description=(
                "Find registered typosquat / lookalike / phishing domains for a "
                "domain using dnstwist (permutation + DNS resolution). Useful for "
                "brand-impersonation and phishing-infrastructure investigations."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Domain to permute, e.g. example.com."},
                    "registered_only": {
                        "type": "boolean",
                        "description": "Only return resolving/registered permutations (default true).",
                    },
                },
                "required": ["domain"],
            },
            handler=_handle,
        )
    ]


def _photon(ctx: BuildContext) -> list[Tool]:
    repo = os.environ["SCOUT_PHOTON_PATH"]
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        url = str(args.get("url", "")).strip()
        if not url:
            return "Error: 'url' is required."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        script = os.path.join(repo, "photon.py")
        if not os.path.exists(script):
            return f"Photon not found at {script}."
        level = int(args.get("depth", 2))
        with tempfile.TemporaryDirectory() as outdir:
            try:
                subprocess.run(
                    ["python3", "photon.py", "-u", url, "-o", outdir,
                     "-l", str(level), "-t", "10"],
                    capture_output=True, text=True, timeout=300, cwd=repo,
                )
            except Exception as exc:  # noqa: BLE001
                return f"Photon failed: {exc}"
            sections: list[str] = []
            for fname in ("emails.txt", "social.txt", "external.txt",
                          "internal.txt", "files.txt", "intel.txt"):
                path = os.path.join(outdir, fname)
                if not os.path.exists(path):
                    continue
                with open(path, encoding="utf-8", errors="replace") as fh:
                    lines = [ln.strip() for ln in fh if ln.strip()]
                if lines:
                    sections.append(f"## {fname} ({len(lines)})\n" + "\n".join(lines[:50]))
        mission.upsert_entity(Entity(name=url, type="website", sources=["photon"]))
        return ("\n\n".join(sections))[:8000] or "Photon crawled the site but found no extractable artifacts."

    return [
        Tool(
            name="osint_crawl",
            description=(
                "Crawl a website with Photon and extract emails, social handles, "
                "external/internal links, files, and intel (secrets/keys). Records "
                "the site as an entity. Use to map a target's web footprint."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Site URL to crawl."},
                    "depth": {"type": "integer", "description": "Crawl depth/level (default 2)."},
                },
                "required": ["url"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="dnstwist",
        name="dnstwist",
        category="web recon",
        summary="Typosquat / lookalike / phishing domain detection.",
        builder=_dnstwist,
        binary_check="dnstwist",
        install_hint="pip install dnstwist",
        docs="https://github.com/elceef/dnstwist",
        keywords=("typosquat", "lookalike domain", "phishing domain",
                  "brand impersonation", "domain squatting", "spoofed domain",
                  "fake domain"),
    ),
    ToolSpec(
        id="photon",
        name="Photon",
        category="web recon",
        summary="Fast OSINT crawler: emails, handles, links, files, secrets.",
        builder=_photon,
        env_keys=("SCOUT_PHOTON_PATH",),
        install_hint="clone s0md3v/Photon and set SCOUT_PHOTON_PATH",
        docs="https://github.com/s0md3v/Photon",
        keywords=("crawl", "spider", "scrape site", "extract emails",
                  "site footprint", "web footprint", "harvest urls"),
    ),
]
