"""Geolocation tools: open-source image geolocation, image matching, WiFi geo."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec

# Cache the (heavy) GeoCLIP model across calls within a run.
_geoclip_model = None


def _geoclip(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        global _geoclip_model
        path = str(args.get("image_path", "")).strip()
        if not path or not os.path.exists(path):
            return "Error: 'image_path' must point to a readable local image."
        try:
            if _geoclip_model is None:
                from geoclip import GeoCLIP

                _geoclip_model = GeoCLIP()
            top_k = int(args.get("top_k", 5))
            coords, probs = _geoclip_model.predict(path, top_k=top_k)
        except Exception as exc:  # noqa: BLE001
            return f"GeoCLIP prediction failed: {exc}"

        guesses = [
            {"lat": float(lat), "lon": float(lon), "confidence": float(p)}
            for (lat, lon), p in zip(coords, probs, strict=False)
        ]
        if guesses:
            top = guesses[0]
            mission.upsert_entity(
                Entity(
                    name=f"GeoCLIP location ({top['lat']:.3f},{top['lon']:.3f})",
                    type="place",
                    attributes={"lat": top["lat"], "lon": top["lon"],
                                "confidence": top["confidence"], "image": path},
                    sources=["geoclip"],
                )
            )
        return json.dumps(guesses, indent=2)

    return [
        Tool(
            name="geolocate_image",
            description=(
                "Estimate where a photo was taken using GeoCLIP (open-source, "
                "offline, pixels only). Returns ranked lat/lon guesses. Best on "
                "outdoor/landmark scenes; less precise than commercial GeoSpy."
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


def _image_match(ctx: BuildContext) -> list[Tool]:
    def _handle(args: dict[str, Any]) -> str:
        a = str(args.get("image_a", "")).strip()
        b = str(args.get("image_b", "")).strip()
        if not (os.path.exists(a) and os.path.exists(b)):
            return "Error: 'image_a' and 'image_b' must be readable local images."
        try:
            from imcui.api import ImageMatchAPI
            from imcui.ui.utils import load_image

            api = ImageMatchAPI()
            pred = api(load_image(a), load_image(b))
            n = len(pred.get("mkeypoints0", []))
            return json.dumps({"matched_keypoints": n}, indent=2)
        except Exception as exc:  # noqa: BLE001
            return f"Image matching failed: {exc}"

    return [
        Tool(
            name="match_images",
            description=(
                "Compare two local images and count matching keypoints using "
                "image-matching-webui (SuperGlue/LoFTR). High match counts suggest "
                "the same place/object/scene. Useful for corroborating imagery."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "image_a": {"type": "string", "description": "First local image."},
                    "image_b": {"type": "string", "description": "Second local image."},
                },
                "required": ["image_a", "image_b"],
            },
            handler=_handle,
        )
    ]


def _geowifi(ctx: BuildContext) -> list[Tool]:
    script = os.environ["SCOUT_GEOWIFI_PATH"]

    def _handle(args: dict[str, Any]) -> str:
        kind = str(args.get("kind", "bssid")).strip()
        value = str(args.get("value", "")).strip()
        if kind not in {"bssid", "ssid"} or not value:
            return "Error: provide kind=bssid|ssid and a value."
        if not os.path.exists(script):
            return f"geowifi.py not found at {script}."
        try:
            proc = subprocess.run(
                ["python3", script, "-s", kind, "-o", "json", value],
                capture_output=True, text=True, timeout=90,
                cwd=os.path.dirname(script) or ".",
            )
            out = proc.stdout.strip() or proc.stderr.strip()
            return out[:8000] or "No location data returned."
        except Exception as exc:  # noqa: BLE001
            return f"geowifi failed: {exc}"

    return [
        Tool(
            name="geolocate_wifi",
            description=(
                "Geolocate a WiFi network by BSSID (MAC) or SSID using geowifi "
                "(aggregates Wigle/Apple/Google/etc.). Returns coordinates as JSON."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "bssid | ssid"},
                    "value": {"type": "string", "description": "The BSSID or SSID."},
                },
                "required": ["kind", "value"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="geoclip",
        name="GeoCLIP",
        category="geolocation",
        summary="Open-source image -> GPS geolocation, offline.",
        builder=_geoclip,
        import_check="geoclip",
        install_hint="pip install 'scout[geo]' (or: pip install geoclip)",
        docs="https://github.com/VicenteVivan/geo-clip",
        keywords=("geolocate", "geolocation", "where was this photo",
                  "where was this taken", "location of this image", "photo location"),
    ),
    ToolSpec(
        id="image_matching",
        name="image-matching-webui",
        category="imagery",
        summary="Feature-match two images (SuperGlue/LoFTR) to corroborate scenes.",
        builder=_image_match,
        import_check="imcui",
        install_hint="pip install imcui",
        docs="https://github.com/Vincentqyw/image-matching-webui",
        keywords=("compare images", "same photo", "same place", "image match",
                  "matching images", "corroborate photo", "duplicate image"),
    ),
    ToolSpec(
        id="geowifi",
        name="geowifi",
        category="geolocation",
        summary="Geolocate a WiFi BSSID/SSID via aggregated providers.",
        builder=_geowifi,
        env_keys=("SCOUT_GEOWIFI_PATH",),
        install_hint="clone GONZOsint/geowifi and set SCOUT_GEOWIFI_PATH to geowifi.py",
        docs="https://github.com/GONZOsint/geowifi",
        keywords=("wifi", "wi-fi", "bssid", "ssid", "access point",
                  "mac address", "router location"),
    ),
]
