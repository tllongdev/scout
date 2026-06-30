"""CVE / vulnerability lookup against the NIST National Vulnerability Database.

Queries the NVD REST API by CVE id or keyword (product/vendor/technology). No
key is required; setting NVD_API_KEY only raises the rate limit. Useful after
recon (web-check, httpx tech-detect, BBOT) to assess known vulnerabilities in a
target's stack.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec

_TIMEOUT = 30.0
_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_CVE_ID = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)


def _nvd(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' is required (a CVE id or product keyword)."
        params: dict[str, Any] = {}
        if _CVE_ID.match(query):
            params["cveId"] = query.upper()
        else:
            params["keywordSearch"] = query
            params["resultsPerPage"] = int(args.get("limit", 10))
        headers = {}
        if os.getenv("NVD_API_KEY"):
            headers["apiKey"] = os.environ["NVD_API_KEY"]
        try:
            resp = httpx.get(_API, params=params, headers=headers, timeout=_TIMEOUT)
            resp.raise_for_status()
            vulns = resp.json().get("vulnerabilities", [])
        except Exception as exc:  # noqa: BLE001
            return f"NVD request failed: {exc}"

        if not vulns:
            return f"No CVEs found for '{query}'."

        trimmed = []
        for v in vulns:
            cve = v.get("cve", {})
            metrics = cve.get("metrics", {})
            score, severity = _best_score(metrics)
            descs = cve.get("descriptions", [])
            text = next((d.get("value") for d in descs if d.get("lang") == "en"), "")
            trimmed.append({
                "id": cve.get("id"),
                "cvss": score,
                "severity": severity,
                "published": cve.get("published"),
                "summary": (text or "")[:300],
            })
        mission.upsert_entity(
            Entity(name=query, type="vulnerability_query", sources=["nvd"])
        )
        return json.dumps(trimmed, indent=2)[:8000]

    return [
        Tool(
            name="cve_lookup",
            description=(
                "Look up vulnerabilities in the NIST NVD by CVE id (e.g. "
                "CVE-2021-44228) or by product/technology keyword (e.g. 'apache "
                "log4j'). Returns CVSS score, severity, publish date, and summary. "
                "Use to assess known vulns in a target's detected tech stack."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "CVE id or product/technology keyword.",
                    },
                    "limit": {"type": "integer", "description": "Max CVEs for keyword search (default 10)."},
                },
                "required": ["query"],
            },
            handler=_handle,
        )
    ]


def _best_score(metrics: dict[str, Any]) -> tuple[float | None, str]:
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key)
        if entries:
            data = entries[0].get("cvssData", {})
            sev = entries[0].get("baseSeverity") or data.get("baseSeverity", "")
            return data.get("baseScore"), sev
    return None, ""


SPECS = [
    ToolSpec(
        id="nvd_cve",
        name="NVD CVE Lookup",
        category="cyber",
        summary="Look up CVEs by id or product keyword (CVSS, severity, summary).",
        builder=_nvd,
        keyless=True,
        install_hint="works without a key; set NVD_API_KEY to raise the rate limit",
        docs="https://nvd.nist.gov/developers/vulnerabilities",
        keywords=("cve", "vulnerability", "vulnerabilities", "exploit",
                  "cvss", "security advisory", "patch", "known vulnerability"),
    ),
]
