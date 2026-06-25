"""The planner decomposes a mission brief into concrete collection tasks.

It reasons about *where* intelligence might live and *how* to get it - including
sources that aren't on the open web and may require human help.
"""

from __future__ import annotations

from ..llm import LLM, extract_json
from ..models import Mission, Task

_SYSTEM = """You are the planning module of an autonomous intelligence collector.
Given a mission brief, break it into a focused set of collection tasks.

Think broadly about where the relevant intelligence could live:
- the open web (news, filings, registries, social, academic, archives)
- structured/public APIs and datasets
- local or private documents the operator can provide
- offline or gated sources that require credentials or human access

For each task, decide whether a human will likely need to help (credentials,
access to a gated/offline system, or first-hand knowledge).

Return ONLY a JSON array (no prose). Each item:
{
  "objective": "specific, single-focus collection goal",
  "rationale": "why this matters to the mission",
  "suggested_sources": ["concrete starting points or source types"],
  "needs_human": true|false
}
Produce at most {max_tasks} tasks. Prefer fewer, sharper tasks over many vague ones."""


def plan_mission(llm: LLM, mission: Mission, max_tasks: int) -> list[Task]:
    system = _SYSTEM.replace("{max_tasks}", str(max_tasks))
    user = f"MISSION BRIEF:\n{mission.brief}"
    raw = llm.chat(system, user)

    try:
        data = extract_json(raw)
    except ValueError:
        # Fall back to a single catch-all task so the run can still proceed.
        return [
            Task(
                objective=mission.brief,
                rationale="Planner could not produce structured tasks; "
                "collecting against the brief directly.",
            )
        ]

    tasks: list[Task] = []
    for item in data[:max_tasks]:
        if not isinstance(item, dict):
            continue
        objective = str(item.get("objective", "")).strip()
        if not objective:
            continue
        tasks.append(
            Task(
                objective=objective,
                rationale=str(item.get("rationale", "")).strip(),
                suggested_sources=[
                    str(s) for s in (item.get("suggested_sources") or []) if s
                ],
                needs_human=bool(item.get("needs_human", False)),
            )
        )

    return tasks or [Task(objective=mission.brief)]
