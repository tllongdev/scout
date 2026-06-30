"""A pluggable registry of optional OSINT/intelligence tools.

Each tool is described by a :class:`ToolSpec` that declares what it needs to
run - an API key, an importable Python package, or a binary on PATH. At mission
start Scout probes availability (exactly like model discovery) and only hands
the agents the tools that are actually usable right now. Nothing here forces a
heavy dependency on the base install: integrations import their libraries lazily
and degrade gracefully when a dependency or credential is missing.

Enable/disable via env:
    SCOUT_TOOLS          comma-separated tool ids to allow (allowlist; others off)
    SCOUT_DISABLE_TOOLS  comma-separated tool ids to disable (denylist)
"""

from __future__ import annotations

import importlib.util
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field

from rich.console import Console

from ..config import Config
from ..llm import Tool
from ..models import Mission


@dataclass
class BuildContext:
    """Everything a tool builder might need to construct its Tool(s)."""

    mission: Mission
    console: Console
    config: Config


# A builder turns a context into one or more ready-to-use Tools.
Builder = Callable[[BuildContext], list[Tool]]


@dataclass
class ToolSpec:
    id: str
    name: str
    category: str
    summary: str
    builder: Builder
    # Availability requirements (all that are set must be satisfied):
    env_keys: tuple[str, ...] = ()       # every one of these env vars must be set
    any_env_keys: tuple[str, ...] = ()   # at least one of these must be set
    import_check: str | None = None      # this module must be importable
    binary_check: str | None = None      # this executable must be on PATH
    keyless: bool = False                # no creds needed (informational)
    sensitive: bool = False              # legal/ethical weight - flagged in UI
    install_hint: str = ""               # how to make it available
    docs: str = ""                       # repo or doc URL
    keywords: tuple[str, ...] = ()       # mission terms that imply this tool helps

    def availability(self) -> tuple[bool, str]:
        """Return (available, reason). reason explains a failure or confirms ok."""
        missing_env = [k for k in self.env_keys if not os.getenv(k)]
        if missing_env:
            return False, f"set {', '.join(missing_env)}"
        if self.any_env_keys and not any(os.getenv(k) for k in self.any_env_keys):
            return False, f"set one of {', '.join(self.any_env_keys)}"
        if self.import_check and importlib.util.find_spec(self.import_check) is None:
            hint = self.install_hint or f"install '{self.import_check}'"
            return False, hint
        if self.binary_check and shutil.which(self.binary_check) is None:
            hint = self.install_hint or f"install '{self.binary_check}' on PATH"
            return False, hint
        return True, "ready"


# Populated at import time from the osint subpackage.
_REGISTRY: list[ToolSpec] = []


def register(specs: list[ToolSpec]) -> None:
    _REGISTRY.extend(specs)


def all_specs() -> list[ToolSpec]:
    _ensure_loaded()
    return list(_REGISTRY)


@dataclass
class Discovered:
    spec: ToolSpec
    available: bool
    reason: str
    enabled: bool


def _enable_filters() -> tuple[set[str] | None, set[str]]:
    allow_raw = os.getenv("SCOUT_TOOLS", "").strip()
    deny_raw = os.getenv("SCOUT_DISABLE_TOOLS", "").strip()
    allow = {t.strip() for t in allow_raw.split(",") if t.strip()} if allow_raw else None
    deny = {t.strip() for t in deny_raw.split(",") if t.strip()}
    return allow, deny


def discover_tools() -> list[Discovered]:
    """Probe every registered tool for availability and enablement."""
    allow, deny = _enable_filters()
    out: list[Discovered] = []
    for spec in all_specs():
        available, reason = spec.availability()
        enabled = available and spec.id not in deny
        if allow is not None:
            enabled = enabled and spec.id in allow
        out.append(Discovered(spec, available, reason, enabled))
    return out


def build_enabled_tools(ctx: BuildContext) -> list[Tool]:
    """Construct Tools for every available + enabled spec, skipping failures."""
    tools: list[Tool] = []
    for found in discover_tools():
        if not found.enabled:
            continue
        try:
            tools.extend(found.spec.builder(ctx))
        except Exception as exc:  # noqa: BLE001 - one bad tool shouldn't kill the run
            ctx.console.print(
                f"[yellow]Skipping tool '{found.spec.id}': {exc}[/yellow]"
            )
    return tools


_loaded = False


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    # Importing the package registers all bundled specs.
    from . import osint  # noqa: F401
