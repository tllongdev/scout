"""Human-in-the-loop tool.

When an agent hits a wall that only a person can clear - credentials, access to
a gated system, a judgment call, or knowledge that isn't written down anywhere -
it calls ``ask_human`` and the run pauses for an answer in the terminal.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ..llm import Tool


def ask_human_tool(console: Console) -> Tool:
    def _ask(args: dict[str, Any]) -> str:
        question = str(args.get("question", "")).strip()
        reason = str(args.get("reason", "")).strip()
        sensitive = bool(args.get("sensitive", False))

        if not question:
            return "Error: 'question' is required."

        body = f"[bold]{question}[/bold]"
        if reason:
            body += f"\n\n[dim]Why: {reason}[/dim]"
        console.print(
            Panel(
                body,
                title="[yellow]The agent needs your help[/yellow]",
                border_style="yellow",
            )
        )

        answer = Prompt.ask(
            "[yellow]Your response[/yellow] (press Enter to skip)",
            password=sensitive,
            default="",
            show_default=False,
        )
        if not answer.strip():
            return "The human skipped this request. Proceed without it."
        return f"Human responded: {answer}"

    return Tool(
        name="ask_human",
        description=(
            "Ask the human operator for help when you cannot proceed alone: "
            "credentials, access to a gated or offline source, a clarifying "
            "decision, or first-hand knowledge. Set sensitive=true to mask the "
            "input (for passwords, API keys, tokens)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "What you need from the human.",
                },
                "reason": {
                    "type": "string",
                    "description": "Briefly, why you need it.",
                },
                "sensitive": {
                    "type": "boolean",
                    "description": "Mask the typed answer (credentials/secrets).",
                },
            },
            "required": ["question"],
        },
        handler=_ask,
    )
