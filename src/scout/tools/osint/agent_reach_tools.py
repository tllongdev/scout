"""Platforms provisioned by Agent Reach: YouTube, Twitter/X, and LinkedIn.

Agent Reach (Panniantong/Agent-Reach) is an installer, router, and health-checker
rather than a data CLI of its own: it provisions free upstream backends for ~15
platforms, keeps a preferred/fallback chain per platform, and reports which
backend is live via ``agent-reach doctor --json``. Agents then call the upstream
tool directly.

So each spec here gates on the *upstream binary it actually shells out to*, which
keeps ``scout tools`` honest about what will really run:

- **YouTube** -> ``yt-dlp``. Keyless and public: transcripts and search. This is
  the one genuinely zero-config platform of the three, so it is not flagged
  sensitive.
- **Twitter/X** -> ``twitter`` (twitter-cli). Needs ``TWITTER_AUTH_TOKEN`` and
  ``TWITTER_CT0`` from your own logged-in session, so it is flagged sensitive.
- **LinkedIn** -> ``mcporter`` driving ``mcp-server-linkedin``. Needs a persisted
  browser login, so it is flagged sensitive.

Only these three are wired up: they are the gaps in Scout's library. Agent Reach
also covers Reddit and Instagram, which Scout already handles (PullPush,
Instaloader/Toutatis), plus several China-focused platforms.

Credential note: the Twitter and LinkedIn paths reuse *your* authenticated
session. Treat them like any other credential you would not hand to an
autonomous process casually, and prefer a throwaway research account.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec

_MAX_OUT = 8000


def _run(cmd: list[str], timeout: int, cwd: str | None = None,
         env: dict[str, str] | None = None) -> tuple[bool, str]:
    """Run a command, returning (ok, output). Never raises."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env,
        )
    except FileNotFoundError:
        return False, f"{cmd[0]} is not on PATH."
    except subprocess.TimeoutExpired:
        return False, f"{cmd[0]} timed out after {timeout}s."
    except Exception as exc:  # noqa: BLE001
        return False, f"{cmd[0]} failed: {exc}"
    out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return proc.returncode == 0, out


# ── YouTube (yt-dlp) ────────────────────────────────────────────────────────

_VTT_SKIP = re.compile(r"^(WEBVTT|Kind:|Language:|NOTE\b|\s*$)")
_VTT_TIMESTAMP = re.compile(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->")
_VTT_TAG = re.compile(r"<[^>]+>")


def _vtt_to_text(raw: str) -> str:
    """Flatten a WebVTT subtitle track into readable prose.

    Auto-generated captions repeat each line as the caption scrolls, so
    consecutive duplicates are collapsed.
    """
    lines: list[str] = []
    for line in raw.splitlines():
        if _VTT_SKIP.match(line) or _VTT_TIMESTAMP.match(line):
            continue
        text = _VTT_TAG.sub("", line).strip()
        if not text or (lines and lines[-1] == text):
            continue
        lines.append(text)
    return " ".join(lines)


def _youtube(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _transcript(args: dict[str, Any]) -> str:
        url = str(args.get("url", "")).strip()
        if not url:
            return "Error: 'url' is required."
        lang = str(args.get("language", "en")).strip() or "en"
        with tempfile.TemporaryDirectory() as tmp:
            ok, out = _run(
                ["yt-dlp", "--write-sub", "--write-auto-sub",
                 "--sub-lang", lang, "--skip-download", "--no-warnings",
                 "-o", os.path.join(tmp, "%(id)s"), url],
                timeout=180,
            )
            tracks = sorted(Path(tmp).glob("*.vtt"))
            if not tracks:
                reason = out or "no subtitle track available"
                return (
                    f"No transcript available for {url} ({reason[:300]}). The video "
                    "may have captions disabled - try youtube_metadata instead."
                )
            text = _vtt_to_text(tracks[0].read_text(encoding="utf-8", errors="replace"))
        if not text:
            return f"Subtitle track for {url} was empty."
        mission.upsert_entity(Entity(name=url, type="video", sources=["youtube"]))
        return text[:_MAX_OUT]

    def _metadata(args: dict[str, Any]) -> str:
        url = str(args.get("url", "")).strip()
        if not url:
            return "Error: 'url' is required."
        ok, out = _run(["yt-dlp", "--dump-json", "--no-warnings", url], timeout=120)
        if not ok or not out:
            return f"yt-dlp could not read {url}: {out[:500] or 'no output'}"
        try:
            data = json.loads(out.splitlines()[0])
        except (json.JSONDecodeError, IndexError):
            return out[:_MAX_OUT]
        summary = {
            k: data.get(k)
            for k in ("title", "uploader", "uploader_url", "channel_id",
                      "upload_date", "duration", "view_count", "like_count",
                      "description")
        }
        if summary.get("description"):
            summary["description"] = str(summary["description"])[:1500]
        mission.upsert_entity(Entity(name=url, type="video", sources=["youtube"]))
        if summary.get("uploader"):
            mission.upsert_entity(
                Entity(name=str(summary["uploader"]), type="organization",
                       attributes={"platform": "youtube"}, sources=["youtube"])
            )
        return json.dumps(summary, indent=2)[:_MAX_OUT]

    def _search(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' is required."
        limit = max(1, min(int(args.get("limit", 5)), 20))
        ok, out = _run(
            ["yt-dlp", "--dump-json", "--flat-playlist", "--no-warnings",
             f"ytsearch{limit}:{query}"],
            timeout=180,
        )
        if not out:
            return f"No YouTube results for '{query}'."
        hits: list[dict[str, Any]] = []
        for line in out.splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            hits.append({
                "title": d.get("title"),
                "uploader": d.get("uploader") or d.get("channel"),
                "url": d.get("url") or d.get("webpage_url"),
                "duration": d.get("duration"),
                "views": d.get("view_count"),
            })
        if not hits:
            return f"No parseable YouTube results for '{query}'."
        return json.dumps(hits, indent=2)[:_MAX_OUT]

    return [
        Tool(
            name="youtube_transcript",
            description=(
                "Fetch the transcript/captions of a YouTube video as plain text. "
                "Use this to read what a video actually says instead of guessing "
                "from the title - ideal for talks, interviews, and statements."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube video URL or ID."},
                    "language": {
                        "type": "string",
                        "description": "Caption language code (default 'en').",
                    },
                },
                "required": ["url"],
            },
            handler=_transcript,
        ),
        Tool(
            name="youtube_metadata",
            description=(
                "Get metadata for a YouTube video: title, channel, upload date, "
                "duration, view/like counts, and description. Records the video and "
                "channel as entities."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube video URL or ID."},
                },
                "required": ["url"],
            },
            handler=_metadata,
        ),
        Tool(
            name="youtube_search",
            description=(
                "Search YouTube for videos matching a query and return titles, "
                "channels, URLs, and view counts. Pair with youtube_transcript to "
                "read the most relevant results."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms."},
                    "limit": {
                        "type": "integer",
                        "description": "How many results (1-20, default 5).",
                    },
                },
                "required": ["query"],
            },
            handler=_search,
        ),
    ]


# ── Twitter / X (twitter-cli) ───────────────────────────────────────────────


def _twitter(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _user(args: dict[str, Any]) -> str:
        handle = str(args.get("handle", "")).strip().lstrip("@")
        if not handle:
            return "Error: 'handle' is required."
        limit = max(1, min(int(args.get("limit", 20)), 100))
        ok, profile = _run(["twitter", "user", f"@{handle}"], timeout=120)
        posts_ok, posts = _run(
            ["twitter", "user-posts", f"@{handle}", "-n", str(limit)], timeout=180,
        )
        if not ok and not posts_ok:
            return (
                f"twitter-cli could not read @{handle}: "
                f"{(profile or posts)[:500] or 'no output'}. Check that "
                "TWITTER_AUTH_TOKEN and TWITTER_CT0 are still valid."
            )
        mission.upsert_entity(
            Entity(name=f"@{handle}", type="username",
                   attributes={"platform": "twitter"}, sources=["twitter-cli"])
        )
        parts = []
        if profile:
            parts.append("## Profile\n" + profile)
        if posts:
            parts.append(f"## Recent posts (up to {limit})\n" + posts)
        return "\n\n".join(parts)[:_MAX_OUT] or f"No data returned for @{handle}."

    def _tweet(args: dict[str, Any]) -> str:
        ref = str(args.get("tweet", "")).strip()
        if not ref:
            return "Error: 'tweet' (URL or ID) is required."
        # `article` renders long-form posts; `tweet` handles the normal case.
        cmd = "article" if args.get("long_form") else "tweet"
        ok, out = _run(["twitter", cmd, ref], timeout=120)
        if not out:
            return f"twitter-cli returned nothing for {ref}."
        return out[:_MAX_OUT]

    def _search(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' is required."
        limit = max(1, min(int(args.get("limit", 10)), 50))
        ok, out = _run(["twitter", "search", query, "-n", str(limit)], timeout=180)
        if not ok or not out:
            return (
                f"Twitter search for '{query}' failed or returned nothing "
                f"({out[:300] or 'no output'}). Search is the least reliable "
                "twitter-cli command; try twitter_user on a known handle instead."
            )
        return out[:_MAX_OUT]

    return [
        Tool(
            name="twitter_user",
            description=(
                "Read a Twitter/X account: profile details plus recent posts for a "
                "handle. Records the handle as an entity. This is the most reliable "
                "Twitter path - prefer it over search when you know the account."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "Handle, with or without @."},
                    "limit": {
                        "type": "integer",
                        "description": "How many recent posts (1-100, default 20).",
                    },
                },
                "required": ["handle"],
            },
            handler=_user,
        ),
        Tool(
            name="twitter_tweet",
            description=(
                "Read a single Twitter/X post by URL or ID, including long-form "
                "articles. Use to verify and quote an exact statement."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "tweet": {"type": "string", "description": "Post URL or numeric ID."},
                    "long_form": {
                        "type": "boolean",
                        "description": "Set true for long-form articles (default false).",
                    },
                },
                "required": ["tweet"],
            },
            handler=_tweet,
        ),
        Tool(
            name="twitter_search",
            description=(
                "Search Twitter/X posts by keyword. Useful for sentiment and event "
                "discovery, but upstream rate-limits this heavily - if it fails, "
                "fall back to twitter_user on specific accounts."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms."},
                    "limit": {
                        "type": "integer",
                        "description": "How many posts (1-50, default 10).",
                    },
                },
                "required": ["query"],
            },
            handler=_search,
        ),
    ]


# ── LinkedIn (mcporter -> mcp-server-linkedin) ──────────────────────────────


def _linkedin(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _call(method: str, params: dict[str, str], timeout: int = 180) -> tuple[bool, str]:
        cmd = ["mcporter", "call", f"linkedin.{method}"]
        cmd += [f"{k}={v}" for k, v in params.items() if v]
        return _run(cmd, timeout=timeout)

    def _person(args: dict[str, Any]) -> str:
        username = str(args.get("username", "")).strip().strip("/").split("/")[-1]
        if not username:
            return "Error: 'username' is required (the /in/<username> slug)."
        sections = str(args.get("sections", "experience,education")).strip()
        ok, out = _call("get_person_profile", {
            "linkedin_username": username, "sections": sections,
        })
        if not ok or not out:
            return (
                f"LinkedIn profile lookup for '{username}' failed "
                f"({out[:300] or 'no output'}). Re-authenticate with: "
                "uvx mcp-server-linkedin@latest --login"
            )
        mission.upsert_entity(
            Entity(name=username, type="person",
                   attributes={"platform": "linkedin",
                               "profile": f"https://linkedin.com/in/{username}"},
                   sources=["linkedin"])
        )
        return out[:_MAX_OUT]

    def _people(args: dict[str, Any]) -> str:
        keywords = str(args.get("keywords", "")).strip()
        if not keywords:
            return "Error: 'keywords' is required."
        ok, out = _call("search_people", {
            "keywords": keywords, "location": str(args.get("location", "")).strip(),
        })
        if not ok or not out:
            return f"LinkedIn people search failed ({out[:300] or 'no output'})."
        return out[:_MAX_OUT]

    def _company(args: dict[str, Any]) -> str:
        name = str(args.get("company", "")).strip()
        if not name:
            return "Error: 'company' is required."
        sections = str(args.get("sections", "posts,jobs")).strip()
        ok, out = _call("get_company_profile", {
            "company_name": name, "sections": sections,
        })
        if not ok or not out:
            return f"LinkedIn company lookup for '{name}' failed ({out[:300] or 'no output'})."
        mission.upsert_entity(
            Entity(name=name, type="organization",
                   attributes={"platform": "linkedin"}, sources=["linkedin"])
        )
        return out[:_MAX_OUT]

    return [
        Tool(
            name="linkedin_person",
            description=(
                "Fetch a LinkedIn person profile (experience, education, and more) "
                "by profile slug. Records the person as an entity. Use to establish "
                "employment history and professional affiliations."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Profile slug from linkedin.com/in/<slug>.",
                    },
                    "sections": {
                        "type": "string",
                        "description": "Comma-separated sections (default 'experience,education').",
                    },
                },
                "required": ["username"],
            },
            handler=_person,
        ),
        Tool(
            name="linkedin_search_people",
            description=(
                "Search LinkedIn for people by keywords and optional location. Use "
                "to find employees of an organization or holders of a given role."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "keywords": {"type": "string", "description": "e.g. 'CFO Acme Robotics'."},
                    "location": {"type": "string", "description": "Optional location filter."},
                },
                "required": ["keywords"],
            },
            handler=_people,
        ),
        Tool(
            name="linkedin_company",
            description=(
                "Fetch a LinkedIn company profile, optionally including recent posts "
                "and open jobs. Records the company as an entity. Good for headcount "
                "signals, hiring direction, and official messaging."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name or slug."},
                    "sections": {
                        "type": "string",
                        "description": "Comma-separated sections (default 'posts,jobs').",
                    },
                },
                "required": ["company"],
            },
            handler=_company,
        ),
    ]


SPECS = [
    ToolSpec(
        id="youtube",
        name="YouTube (yt-dlp)",
        category="video",
        summary="Video transcripts, metadata, and search; keyless and public.",
        builder=_youtube,
        binary_check="yt-dlp",
        keyless=True,
        install_hint="pip install 'scout-osint[reach]' (or: pip install yt-dlp)",
        docs="https://github.com/Panniantong/Agent-Reach",
        keywords=("youtube", "video", "transcript", "captions", "subtitles",
                  "interview", "talk", "podcast", "said in a video",
                  "what did they say"),
    ),
    ToolSpec(
        id="twitter",
        name="Twitter/X (twitter-cli)",
        category="social",
        summary="Read X profiles, posts, and search via your own session.",
        builder=_twitter,
        binary_check="twitter",
        env_keys=("TWITTER_AUTH_TOKEN", "TWITTER_CT0"),
        sensitive=True,
        install_hint=(
            "pip install agent-reach && agent-reach install --env=auto, then set "
            "TWITTER_AUTH_TOKEN + TWITTER_CT0 from your logged-in session"
        ),
        docs="https://github.com/Panniantong/Agent-Reach",
        keywords=("twitter", "tweet", "tweets", "x.com", "handle", "retweet",
                  "sentiment", "what are people saying", "posted"),
    ),
    ToolSpec(
        id="linkedin",
        name="LinkedIn (mcporter)",
        category="social",
        summary="Person/company profiles and people search via a logged-in session.",
        builder=_linkedin,
        binary_check="mcporter",
        sensitive=True,
        install_hint=(
            "pip install agent-reach && agent-reach install --env=auto, then log in: "
            "uvx mcp-server-linkedin@latest --login"
        ),
        docs="https://github.com/Panniantong/Agent-Reach",
        keywords=("linkedin", "employment", "employer", "job history",
                  "work history", "resume", "cv", "colleagues", "employees",
                  "professional background", "who works at"),
    ),
]
