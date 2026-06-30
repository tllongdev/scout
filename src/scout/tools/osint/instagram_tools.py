"""Instagram OSINT via Instaloader.

Pulls public profile metadata for an Instagram account - full name, bio,
external link, follower/following/post counts, verified/private flags, and
profile-pic URL - without downloading media. Imported lazily so Instaloader is
an optional dependency. Anonymous access works for public profiles; Instagram
increasingly rate-limits unauthenticated requests, so heavy use may need a
logged-in session.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec


def _instaloader(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        username = str(args.get("username", "")).strip().lstrip("@")
        if not username:
            return "Error: 'username' is required."
        try:
            import instaloader

            loader = instaloader.Instaloader(
                download_pictures=False,
                download_videos=False,
                download_comments=False,
                save_metadata=False,
                quiet=True,
            )
            profile = instaloader.Profile.from_username(loader.context, username)
            data = {
                "username": profile.username,
                "full_name": profile.full_name,
                "userid": profile.userid,
                "is_private": profile.is_private,
                "is_verified": profile.is_verified,
                "followers": profile.followers,
                "followees": profile.followees,
                "posts": profile.mediacount,
                "biography": profile.biography,
                "external_url": profile.external_url,
                "profile_pic_url": profile.profile_pic_url,
            }
        except Exception as exc:  # noqa: BLE001
            return f"Instaloader failed for @{username}: {exc}"

        mission.upsert_entity(
            Entity(
                name=f"@{username}",
                type="instagram_account",
                attributes={
                    "full_name": str(data["full_name"] or ""),
                    "followers": str(data["followers"]),
                    "external_url": str(data["external_url"] or ""),
                    "verified": str(data["is_verified"]),
                },
                sources=[f"https://instagram.com/{username}"],
            )
        )
        lines = [f"{k}: {v}" for k, v in data.items()]
        return "\n".join(lines)[:8000]

    return [
        Tool(
            name="instagram_profile",
            description=(
                "Fetch public Instagram profile metadata with Instaloader: full "
                "name, bio, external link, follower/following/post counts, "
                "verified/private flags, and profile-pic URL. Records the account "
                "as an entity. No media is downloaded."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Instagram handle (without @)."}
                },
                "required": ["username"],
            },
            handler=_handle,
        )
    ]


def _toutatis(ctx: BuildContext) -> list[Tool]:
    session = os.environ["TOUTATIS_SESSION_ID"]
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        username = str(args.get("username", "")).strip().lstrip("@")
        if not username:
            return "Error: 'username' is required."
        try:
            proc = subprocess.run(
                ["toutatis", "-s", session, "-u", username],
                capture_output=True, text=True, timeout=120,
            )
            out = (proc.stdout or proc.stderr).strip()
        except Exception as exc:  # noqa: BLE001
            return f"Toutatis failed: {exc}"
        mission.upsert_entity(
            Entity(
                name=f"@{username}",
                type="instagram_account",
                sources=[f"https://instagram.com/{username}", "toutatis"],
            )
        )
        return out[:8000] or "No data returned."

    return [
        Tool(
            name="instagram_contact_info",
            description=(
                "Extract deeper Instagram account info with Toutatis: obfuscated "
                "email/phone, account creation hints, and IDs that Instaloader does "
                "not surface. Requires an Instagram session ID. Use after "
                "instagram_profile when you need contact-level detail."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Instagram handle (without @)."}
                },
                "required": ["username"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="instaloader",
        name="Instaloader",
        category="social",
        summary="Public Instagram profile metadata (no media download).",
        builder=_instaloader,
        import_check="instaloader",
        install_hint="pip install instaloader",
        docs="https://github.com/instaloader/instaloader",
        keywords=("instagram", "insta", "ig account", "ig profile", "@",
                  "instagram handle"),
    ),
    ToolSpec(
        id="toutatis",
        name="Toutatis",
        category="social",
        summary="Deep Instagram extraction (obfuscated email/phone) via session.",
        builder=_toutatis,
        binary_check="toutatis",
        env_keys=("TOUTATIS_SESSION_ID",),
        sensitive=True,
        install_hint="pip install toutatis && set TOUTATIS_SESSION_ID (your IG sessionid cookie)",
        docs="https://github.com/megadose/toutatis",
        keywords=("instagram", "insta", "ig account", "instagram email",
                  "instagram phone", "contact info"),
    ),
]
