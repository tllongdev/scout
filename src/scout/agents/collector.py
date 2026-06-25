"""A collector agent executes one task via a tool-calling loop.

It decides which sources to hit, reads them, asks the human when blocked, and
records entities, edges, and observations onto the shared mission.
"""

from __future__ import annotations

from collections.abc import Callable

from rich.console import Console

from ..config import Config
from ..llm import LLM, Tool
from ..models import Mission, Task
from ..tools.human import ask_human_tool
from ..tools.local_files import local_files_tool
from ..tools.record import (
    record_edge_tool,
    record_entity_tool,
    record_observation_tool,
)
from ..tools.web_fetch import web_fetch_tool
from ..tools.web_search import web_search_tool

_SYSTEM = """You are a field collector for an autonomous intelligence operation.
You have ONE task. Pursue it methodically:

1. Reason about where the answer lives, then search and read sources.
2. Cross-check claims across more than one source where you can.
3. If you hit a wall only a person can clear (credentials, gated/offline access,
   first-hand knowledge), call ask_human - do not guess at secrets.
4. As you learn, record findings continuously:
   - record_entity for people/orgs/places/assets/events
   - record_edge for relationships between entities
   - record_observation for facts, quotes, data points, contradictions
5. Always attach the source (URL or file) to what you record.

Be efficient with your steps. When the task is satisfied (or you've exhausted
reasonable avenues), stop calling tools and give a 2-3 sentence summary of what
you collected and any gaps."""


def build_collector_tools(
    config: Config, mission: Mission, task: Task, console: Console
) -> list[Tool]:
    return [
        web_search_tool(),
        web_fetch_tool(mission),
        local_files_tool(mission),
        ask_human_tool(console),
        record_entity_tool(mission, task.id),
        record_edge_tool(mission, task.id),
        record_observation_tool(mission, task.id),
    ]


def run_collector(
    llm: LLM,
    config: Config,
    mission: Mission,
    task: Task,
    console: Console,
    on_step: Callable[[int, str], None] | None = None,
) -> str:
    tools = build_collector_tools(config, mission, task, console)

    sources = (
        "\nSuggested starting points: " + "; ".join(task.suggested_sources)
        if task.suggested_sources
        else ""
    )
    human_note = (
        "\nNote: the planner expects this task may need human assistance."
        if task.needs_human
        else ""
    )
    user = (
        f"OVERALL MISSION:\n{mission.brief}\n\n"
        f"YOUR TASK:\n{task.objective}\n"
        f"Rationale: {task.rationale}{sources}{human_note}"
    )

    return llm.run_agent(
        system=_SYSTEM,
        user=user,
        tools=tools,
        max_steps=config.max_steps,
        on_step=on_step,
    )
