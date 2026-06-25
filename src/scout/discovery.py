"""Discover the models actually available to the user, right now.

We never scrape the web or run an agent for this - it's plumbing. We ask each
provider's own model endpoint, scoped to whatever credentials the user has
configured. That returns exactly what their key/tier/local box can call, which
is far more reliable than any generic "latest models" list.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

_TIMEOUT = 10.0


@dataclass
class ProviderModels:
    provider: str
    models: list[str]
    note: str = ""  # e.g. an error or hint when discovery failed


def discover_all(api_base: str | None = None) -> list[ProviderModels]:
    """Query every provider we have credentials (or a local endpoint) for."""
    results: list[ProviderModels] = []

    if os.getenv("ANTHROPIC_API_KEY"):
        results.append(_anthropic())
    if os.getenv("OPENAI_API_KEY"):
        results.append(_openai())
    if os.getenv("GEMINI_API_KEY"):
        results.append(_gemini())

    # Local / self-hosted. Prefer an explicit SCOUT_API_BASE; otherwise try the
    # default Ollama port on the host.
    local_base = api_base or os.getenv("SCOUT_API_BASE") or None
    local = _local(local_base)
    if local is not None:
        results.append(local)

    return results


def _anthropic() -> ProviderModels:
    try:
        resp = httpx.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        ids = [m["id"] for m in resp.json().get("data", [])]
        return ProviderModels("anthropic", [f"anthropic/{i}" for i in sorted(ids)])
    except Exception as exc:  # noqa: BLE001
        return ProviderModels("anthropic", [], note=f"lookup failed: {exc}")


def _openai() -> ProviderModels:
    try:
        resp = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        ids = [m["id"] for m in resp.json().get("data", [])]
        # Keep chat-capable families; drop embeddings/audio/image/moderation.
        chat = [
            i
            for i in ids
            if i.startswith(("gpt-", "o1", "o3", "o4", "chatgpt"))
            and not any(x in i for x in ("audio", "realtime", "image", "transcribe", "tts"))
        ]
        return ProviderModels("openai", [f"openai/{i}" for i in sorted(chat)])
    except Exception as exc:  # noqa: BLE001
        return ProviderModels("openai", [], note=f"lookup failed: {exc}")


def _gemini() -> ProviderModels:
    try:
        resp = httpx.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": os.environ["GEMINI_API_KEY"]},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        names = []
        for m in resp.json().get("models", []):
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" not in methods:
                continue
            # API returns "models/gemini-2.0-flash"; litellm wants "gemini/<id>".
            short = m["name"].split("/", 1)[-1]
            names.append(f"gemini/{short}")
        return ProviderModels("gemini", sorted(names))
    except Exception as exc:  # noqa: BLE001
        return ProviderModels("gemini", [], note=f"lookup failed: {exc}")


def _local(api_base: str | None) -> ProviderModels | None:
    """Discover local models via Ollama tags or an OpenAI-compatible /models."""
    # Try Ollama first (its native endpoint lists installed models).
    ollama_base = _ollama_base(api_base)
    try:
        resp = httpx.get(f"{ollama_base}/api/tags", timeout=_TIMEOUT)
        if resp.status_code == 200:
            tags = [m["name"] for m in resp.json().get("models", [])]
            if tags:
                return ProviderModels(
                    "local (ollama)", [f"ollama/{t}" for t in sorted(tags)]
                )
    except Exception:  # noqa: BLE001
        pass

    # Then an explicit OpenAI-compatible endpoint, if one was given.
    if api_base:
        try:
            base = api_base.rstrip("/")
            url = base if base.endswith("/models") else f"{base}/models"
            resp = httpx.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
            ids = [m["id"] for m in resp.json().get("data", [])]
            if ids:
                return ProviderModels(
                    "local (openai-compatible)",
                    [f"openai/{i}" for i in sorted(ids)],
                    note=f"via {api_base}",
                )
        except Exception:  # noqa: BLE001
            return None

    return None


def _ollama_base(api_base: str | None) -> str:
    if api_base and "11434" in api_base:
        return api_base.rstrip("/").removesuffix("/v1")
    # Default: the host machine from inside Docker, else localhost.
    host = "host.docker.internal" if _in_docker() else "localhost"
    return f"http://{host}:11434"


def _in_docker() -> bool:
    return os.path.exists("/.dockerenv")
