"""Runtime configuration, loaded from environment / .env.

Scout is model-agnostic: the user brings their own provider and credentials.
Nothing here is provider-specific beyond reading the standard env var names
that litellm already understands (ANTHROPIC_API_KEY, OPENAI_API_KEY, ...).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when Scout is not configured well enough to run."""


@dataclass(frozen=True)
class Config:
    model: str
    api_base: str | None
    max_tasks: int
    max_steps: int
    temperature: float

    @classmethod
    def from_env(cls) -> "Config":
        model = os.getenv("SCOUT_MODEL", "").strip()
        if not model:
            raise ConfigError(
                "SCOUT_MODEL is not set. Copy .env.example to .env and choose a "
                "model (e.g. anthropic/claude-sonnet-4-5)."
            )

        api_base = os.getenv("SCOUT_API_BASE", "").strip() or None

        return cls(
            model=model,
            api_base=api_base,
            max_tasks=_int_env("SCOUT_MAX_TASKS", 6),
            max_steps=_int_env("SCOUT_MAX_STEPS", 12),
            temperature=_float_env("SCOUT_TEMPERATURE", 0.4),
        )

    @property
    def provider(self) -> str:
        """The provider prefix, e.g. 'anthropic' from 'anthropic/claude-...'."""
        return self.model.split("/", 1)[0] if "/" in self.model else self.model

    def check_credentials(self) -> None:
        """Best-effort check that a key exists for the chosen provider.

        Local providers (ollama, or anything behind SCOUT_API_BASE) don't need
        a key, so we skip the check for those.
        """
        if self.api_base or self.provider == "ollama":
            return

        required = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }.get(self.provider)

        if required and not os.getenv(required):
            raise ConfigError(
                f"{required} is not set, but SCOUT_MODEL uses the "
                f"'{self.provider}' provider. Add it to your .env."
            )


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}.") from exc


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}.") from exc
