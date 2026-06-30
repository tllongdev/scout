"""OSINT tools that are plain HTTP APIs - the cleanest fit for an agent.

Keyless services are available out of the box; keyed/commercial services light
up automatically when the relevant API key is present in the environment.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

import httpx

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec

_TIMEOUT = 25.0


# ── airplanes.live (free, keyless ADS-B flight tracking) ────────────────────


def _airplanes(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        qtype = str(args.get("query_type", "")).strip()
        value = str(args.get("value", "")).strip()
        if qtype not in {"hex", "callsign", "reg", "type", "squawk", "mil"}:
            return "Error: query_type must be hex|callsign|reg|type|squawk|mil."
        base = "https://api.airplanes.live/v2"
        if qtype == "mil":
            url = f"{base}/mil"
        elif not value:
            return "Error: 'value' is required for this query_type."
        else:
            url = f"{base}/{qtype}/{value}"
        try:
            resp = httpx.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            return f"airplanes.live request failed: {exc}"

        aircraft = data.get("ac", []) if isinstance(data, dict) else []
        for ac in aircraft[:25]:
            reg = ac.get("r") or ac.get("hex", "")
            if not reg:
                continue
            mission.upsert_entity(
                Entity(
                    name=str(reg),
                    type="aircraft",
                    attributes={
                        "callsign": str(ac.get("flight", "")).strip(),
                        "type": ac.get("t", ""),
                        "lat": ac.get("lat"),
                        "lon": ac.get("lon"),
                        "altitude": ac.get("alt_baro"),
                    },
                    sources=["https://airplanes.live"],
                )
            )
        return json.dumps(aircraft[:25], indent=2)[:8000] or "No aircraft found."

    return [
        Tool(
            name="track_aircraft",
            description=(
                "Look up live aircraft via airplanes.live (ADS-B). Query by hex, "
                "callsign, registration, ICAO type, squawk code, or list military "
                "aircraft. Returns positions/altitudes and records aircraft as "
                "entities. Free, uncensored coverage (incl. military)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "description": "hex | callsign | reg | type | squawk | mil",
                    },
                    "value": {
                        "type": "string",
                        "description": "The lookup value (omit for query_type=mil).",
                    },
                },
                "required": ["query_type"],
            },
            handler=_handle,
        )
    ]


# ── web-check (Lissy93) - website/host recon ────────────────────────────────

_WEBCHECK_CHECKS = (
    "get-ip", "ssl", "dns", "headers", "cookies", "whois", "quality",
    "tech-stack", "ports", "trace-route", "redirects", "txt-records",
    "hsts", "dnssec", "sitemap", "carbon",
)


def _web_check(ctx: BuildContext) -> list[Tool]:
    base = os.getenv("SCOUT_WEBCHECK_URL", "https://web-check.xyz").rstrip("/")

    def _handle(args: dict[str, Any]) -> str:
        url = str(args.get("url", "")).strip()
        check = str(args.get("check", "")).strip()
        if not url:
            return "Error: 'url' is required."
        if check not in _WEBCHECK_CHECKS:
            return f"Error: check must be one of {', '.join(_WEBCHECK_CHECKS)}."
        try:
            resp = httpx.get(
                f"{base}/api/{check}", params={"url": url}, timeout=_TIMEOUT
            )
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)[:8000]
        except Exception as exc:  # noqa: BLE001
            return f"web-check '{check}' failed: {exc}"

    return [
        Tool(
            name="web_recon",
            description=(
                "Run a website/host recon check via web-check: IP, SSL chain, DNS, "
                "HTTP headers, cookies, WHOIS, tech stack, open ports, redirects, "
                "DNSSEC, and more. One check per call. Great first pass on a domain."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Domain or URL."},
                    "check": {
                        "type": "string",
                        "description": f"One of: {', '.join(_WEBCHECK_CHECKS)}",
                    },
                },
                "required": ["url", "check"],
            },
            handler=_handle,
        )
    ]


# ── Grayhat Warfare - exposed cloud buckets/files (key) ─────────────────────


def _grayhat(ctx: BuildContext) -> list[Tool]:
    key = os.environ["GRAYHAT_API_KEY"]

    def _handle(args: dict[str, Any]) -> str:
        keywords = str(args.get("keywords", "")).strip()
        if not keywords:
            return "Error: 'keywords' is required."
        try:
            resp = httpx.get(
                "https://buckets.grayhatwarfare.com/api/v2/files",
                params={"keywords": keywords, "limit": int(args.get("limit", 20))},
                headers={"Authorization": f"Bearer {key}"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)[:8000]
        except Exception as exc:  # noqa: BLE001
            return f"Grayhat Warfare search failed: {exc}"

    return [
        Tool(
            name="search_exposed_buckets",
            description=(
                "Search Grayhat Warfare for publicly exposed cloud storage files "
                "(S3/Azure/GCS) by keyword/filename. Use to find leaked or "
                "misconfigured files. Scope queries responsibly and legally."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "keywords": {"type": "string", "description": "Search terms."},
                    "limit": {"type": "integer", "description": "Max results (default 20)."},
                },
                "required": ["keywords"],
            },
            handler=_handle,
        )
    ]


# ── FaceCheck.ID - reverse face search (paid, key) ──────────────────────────


def _facecheck(ctx: BuildContext) -> list[Tool]:
    token = os.environ["FACECHECK_API_TOKEN"]
    testing = os.getenv("FACECHECK_TESTING", "true").lower() != "false"

    def _handle(args: dict[str, Any]) -> str:
        path = str(args.get("image_path", "")).strip()
        if not path or not os.path.exists(path):
            return "Error: 'image_path' must point to a readable local image."
        headers = {"accept": "application/json", "Authorization": token}
        try:
            with open(path, "rb") as fh:
                up = httpx.post(
                    "https://facecheck.id/api/upload_pic",
                    headers=headers,
                    files={"images": fh},
                    timeout=_TIMEOUT,
                )
            up.raise_for_status()
            id_search = up.json().get("id_search")
            if not id_search:
                return f"Upload error: {up.json().get('message')}"
            payload = {
                "id_search": id_search,
                "with_progress": True,
                "status_only": False,
                "demo": testing,
            }
            for _ in range(20):
                sr = httpx.post(
                    "https://facecheck.id/api/search",
                    headers=headers,
                    json=payload,
                    timeout=_TIMEOUT,
                )
                sr.raise_for_status()
                body = sr.json()
                if body.get("output"):
                    items = body["output"].get("items", [])
                    return json.dumps(items[:15], indent=2)[:8000]
                time.sleep(2)
            return "Search timed out before results were ready."
        except Exception as exc:  # noqa: BLE001
            return f"FaceCheck search failed: {exc}"

    return [
        Tool(
            name="reverse_face_search",
            description=(
                "Reverse face search via FaceCheck.ID: given a local face photo, "
                "find where that face appears online. Paid per search. "
                "FACECHECK_TESTING=true runs in no-cost demo mode (no real results)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to a local image (mounted under /app/sources).",
                    }
                },
                "required": ["image_path"],
            },
            handler=_handle,
        )
    ]


# ── GeoSpy - AI image geolocation (commercial, key) ─────────────────────────


def _geospy(ctx: BuildContext) -> list[Tool]:
    key = os.environ["GEOSPY_API_KEY"]

    def _handle(args: dict[str, Any]) -> str:
        path = str(args.get("image_path", "")).strip()
        if not path or not os.path.exists(path):
            return "Error: 'image_path' must point to a readable local image."
        try:
            with open(path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
            resp = httpx.post(
                "https://dev.geospy.ai/predict_v1",
                headers={"Authorization": f"Bearer {key}"},
                json={"image": b64, "top_k": int(args.get("top_k", 5))},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)[:8000]
        except Exception as exc:  # noqa: BLE001
            return f"GeoSpy prediction failed: {exc}"

    return [
        Tool(
            name="geolocate_image_ai",
            description=(
                "Estimate where a photo was taken using GeoSpy's AI (pixels only, "
                "no EXIF needed). Returns ranked lat/lon guesses. Commercial API."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Local image path."},
                    "top_k": {"type": "integer", "description": "How many guesses (default 5)."},
                },
                "required": ["image_path"],
            },
            handler=_handle,
        )
    ]


# ── MarineTraffic / Kpler - vessel tracking (commercial, key) ───────────────


def _marinetraffic(ctx: BuildContext) -> list[Tool]:
    key = os.environ["MARINETRAFFIC_API_KEY"]
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        mmsi = str(args.get("mmsi", "")).strip()
        imo = str(args.get("imo", "")).strip()
        if not (mmsi or imo):
            return "Error: provide 'mmsi' or 'imo'."
        params: dict[str, Any] = {"v": 8, "protocol": "jsono"}
        if mmsi:
            params["mmsi"] = mmsi
        if imo:
            params["imo"] = imo
        try:
            resp = httpx.get(
                f"https://services.marinetraffic.com/api/exportvessel/{key}",
                params=params,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            return f"MarineTraffic request failed: {exc}"
        if isinstance(data, list):
            for v in data[:10]:
                name = str(v.get("SHIPNAME") or v.get("MMSI") or "")
                if name:
                    mission.upsert_entity(
                        Entity(name=name, type="vessel",
                               attributes={k: v[k] for k in list(v)[:8]},
                               sources=["https://marinetraffic.com"])
                    )
        return json.dumps(data, indent=2)[:8000]

    return [
        Tool(
            name="track_vessel",
            description=(
                "Look up a ship's latest position/details via MarineTraffic/Kpler "
                "AIS by MMSI or IMO number. Records vessels as entities. Commercial."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "mmsi": {"type": "string", "description": "Vessel MMSI."},
                    "imo": {"type": "string", "description": "Vessel IMO number."},
                },
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="airplanes_live",
        name="airplanes.live",
        category="aviation",
        summary="Live ADS-B flight tracking (incl. military); free, no key.",
        builder=_airplanes,
        keyless=True,
        docs="https://airplanes.live/api-guide/",
    ),
    ToolSpec(
        id="web_check",
        name="web-check",
        category="web recon",
        summary="One-shot domain/host recon: DNS, SSL, headers, WHOIS, ports.",
        builder=_web_check,
        keyless=True,
        install_hint="uses public web-check.xyz; set SCOUT_WEBCHECK_URL to self-host",
        docs="https://github.com/Lissy93/web-check",
    ),
    ToolSpec(
        id="grayhat_warfare",
        name="Grayhat Warfare",
        category="exposure",
        summary="Search publicly exposed S3/Azure/GCS buckets and files.",
        builder=_grayhat,
        env_keys=("GRAYHAT_API_KEY",),
        sensitive=True,
        install_hint="set GRAYHAT_API_KEY (free tier at grayhatwarfare.com)",
        docs="https://buckets.grayhatwarfare.com/docs/api/v2",
        keywords=("bucket", "buckets", "s3", "azure blob", "exposed file",
                  "leaked", "leak", "misconfigured", "cloud storage"),
    ),
    ToolSpec(
        id="facecheck",
        name="FaceCheck.ID",
        category="facial recognition",
        summary="Reverse face search across the web (paid per search).",
        builder=_facecheck,
        env_keys=("FACECHECK_API_TOKEN",),
        sensitive=True,
        install_hint="set FACECHECK_API_TOKEN (facecheck.id)",
        docs="https://facecheck.id",
        keywords=("face", "facial", "headshot", "selfie", "portrait",
                  "photo of a person", "identify this person", "who is this person"),
    ),
    ToolSpec(
        id="geospy",
        name="GeoSpy",
        category="geolocation",
        summary="AI photo geolocation from pixels alone (commercial).",
        builder=_geospy,
        env_keys=("GEOSPY_API_KEY",),
        sensitive=True,
        install_hint="set GEOSPY_API_KEY (enterprise access, geospy.ai)",
        docs="https://geospy.ai",
        keywords=("geolocate", "geolocation", "where was this photo",
                  "where was this taken", "location of this image", "photo location"),
    ),
    ToolSpec(
        id="marinetraffic",
        name="MarineTraffic / Kpler",
        category="maritime",
        summary="Vessel position/details by MMSI/IMO (commercial AIS).",
        builder=_marinetraffic,
        env_keys=("MARINETRAFFIC_API_KEY",),
        install_hint="set MARINETRAFFIC_API_KEY (kpler.com / marinetraffic.com)",
        docs="https://servicedocs.marinetraffic.com",
        keywords=("vessel", "ship", "shipping", "maritime", "mmsi", "imo",
                  "tanker", "cargo", "port call", "fleet"),
    ),
]
