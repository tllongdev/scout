"""Model-agnostic LLM access and the tool-calling agent loop.

We lean on litellm so a single ``model`` string (plus optional ``api_base``)
works across Anthropic, OpenAI, Gemini, Ollama, and any OpenAI-compatible
endpoint. Tool schemas use the OpenAI function-calling shape, which litellm
normalizes for every provider.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import litellm
from rich.console import Console

from .config import Config

# litellm is chatty by default; keep our console clean.
litellm.suppress_debug_info = True


@dataclass
class Tool:
    """A callable the model can invoke, plus its JSON-schema description."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], str]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class LLM:
    """Thin wrapper around litellm for completions and agent loops."""

    def __init__(self, config: Config, console: Console | None = None) -> None:
        self.config = config
        self.console = console or Console()

    def _complete(self, messages: list[dict[str, Any]], tools: list[Tool] | None) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
        }
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
        if tools:
            kwargs["tools"] = [t.schema() for t in tools]
            kwargs["tool_choice"] = "auto"
        response = litellm.completion(**kwargs)
        return response.choices[0].message

    def chat(self, system: str, user: str) -> str:
        """A single completion with no tools. Returns the text content."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        message = self._complete(messages, tools=None)
        return (message.content or "").strip()

    def run_agent(
        self,
        system: str,
        user: str,
        tools: list[Tool],
        max_steps: int,
        on_step: Callable[[int, str], None] | None = None,
    ) -> str:
        """Run a tool-calling loop until the model stops requesting tools.

        Returns the model's final text response.
        """
        by_name = {t.name: t for t in tools}
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        last_text = ""
        for step in range(1, max_steps + 1):
            message = self._complete(messages, tools=tools)
            messages.append(_serialize_assistant(message))

            tool_calls = getattr(message, "tool_calls", None)
            if not tool_calls:
                last_text = (message.content or "").strip()
                if on_step:
                    on_step(step, "done")
                break

            for call in tool_calls:
                name = call.function.name
                if on_step:
                    on_step(step, name)
                args = _safe_json(call.function.arguments)
                tool = by_name.get(name)
                if tool is None:
                    result = f"Error: unknown tool '{name}'."
                else:
                    try:
                        result = tool.handler(args)
                    except Exception as exc:  # noqa: BLE001 - surface to the model
                        result = f"Error running {name}: {exc}"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": str(result)[:12000],
                    }
                )
        else:
            # Loop exhausted without a final answer; ask for a wrap-up.
            messages.append(
                {
                    "role": "user",
                    "content": "Step budget reached. Summarize what you found.",
                }
            )
            message = self._complete(messages, tools=None)
            last_text = (message.content or "").strip()

        return last_text


def _serialize_assistant(message: Any) -> dict[str, Any]:
    """Convert a provider message object into a plain dict for the next turn."""
    tool_calls = getattr(message, "tool_calls", None)
    payload: dict[str, Any] = {
        "role": "assistant",
        "content": message.content or "",
    }
    if tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in tool_calls
        ]
    return payload


def _safe_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {}


def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of a model response.

    Models sometimes wrap JSON in prose or code fences; this is forgiving.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("No JSON found in model response.")
