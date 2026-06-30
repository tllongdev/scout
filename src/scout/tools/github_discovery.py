"""Discover OSINT tools on GitHub.

Queries the GitHub search API for the most-starred repositories under common
OSINT topics, merges/dedupes them, and flags which ones Scout already
integrates. This is a maintainer aid for finding new tools worth wrapping into
the registry - not something the agents call mid-mission.

Unauthenticated calls are rate-limited (10 req/min); set GITHUB_TOKEN to raise
that to 30/min.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import httpx

from .registry import all_specs

_TIMEOUT = 20.0
_TOPICS = ("osint", "osint-tools", "reconnaissance", "threat-intelligence")
_GH_REPO_RE = re.compile(r"github\.com/([^/]+/[^/#?]+)", re.IGNORECASE)


@dataclass
class Repo:
    full_name: str
    url: str
    description: str
    stars: int
    pushed_at: str
    topics: list[str]
    integrated: bool


def _integrated_repos() -> set[str]:
    """The 'owner/repo' slugs Scout already wraps, from each spec's docs URL."""
    slugs: set[str] = set()
    for spec in all_specs():
        match = _GH_REPO_RE.search(spec.docs or "")
        if match:
            slugs.add(match.group(1).lower().removesuffix(".git"))
    return slugs


def discover_github_osint(
    limit: int = 30, query: str | None = None
) -> tuple[list[Repo], str | None]:
    """Return (repos, error). Repos are deduped and sorted by stars desc."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    integrated = _integrated_repos()
    seen: dict[str, Repo] = {}
    queries = [f"q={query} topic:osint"] if query else [f"topic:{t}" for t in _TOPICS]

    error: str | None = None
    for q in queries:
        try:
            resp = httpx.get(
                "https://api.github.com/search/repositories",
                params={"q": q, "sort": "stars", "order": "desc", "per_page": 30},
                headers=headers,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            error = f"GitHub query '{q}' failed: {exc}"
            continue
        for item in resp.json().get("items", []):
            full = item["full_name"]
            if full in seen:
                continue
            seen[full] = Repo(
                full_name=full,
                url=item["html_url"],
                description=(item.get("description") or "").strip(),
                stars=int(item.get("stargazers_count", 0)),
                pushed_at=(item.get("pushed_at") or "")[:10],
                topics=item.get("topics", []),
                integrated=full.lower() in integrated,
            )

    repos = sorted(seen.values(), key=lambda r: r.stars, reverse=True)[:limit]
    return repos, (error if not repos else None)
