"""Flag unconfigured-but-relevant tools so the operator knows what to enable.

Unavailable tools are invisible to the agents (they can't be called), so the
agent can't suggest them. This pass inspects the mission brief and the planned
tasks for terms that imply a specialized tool would help, and surfaces any such
tool that isn't currently available - along with the exact step to turn it on.

Matching is deterministic keyword-based: no extra model calls, works in mock
mode, and never fabricates a recommendation.
"""

from __future__ import annotations

import re

from ..models import Mission, ToolSuggestion
from .registry import discover_tools


def _matches(keyword: str, haystack: str) -> bool:
    # Whole-word/phrase match so 'face' doesn't fire on 'surface', 'tor' on
    # 'actor', 'port' on 'report', etc. Lookarounds handle leading symbols
    # (e.g. '@gmail') and internal hyphens ('wi-fi').
    pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
    return re.search(pattern, haystack) is not None


def recommend_tools(mission: Mission) -> list[ToolSuggestion]:
    haystack = " ".join(
        [mission.brief]
        + [t.objective for t in mission.tasks]
        + [t.rationale for t in mission.tasks]
        + [s for t in mission.tasks for s in t.suggested_sources]
    ).lower()

    suggestions: list[ToolSuggestion] = []
    for found in discover_tools():
        spec = found.spec
        # Only recommend tools that exist but aren't usable yet.
        if found.available or not spec.keywords:
            continue
        matched = [kw for kw in spec.keywords if _matches(kw, haystack)]
        if not matched:
            continue
        suggestions.append(
            ToolSuggestion(
                tool_id=spec.id,
                name=spec.name,
                summary=spec.summary,
                why=f"mission mentions {', '.join(sorted(set(matched))[:3])}",
                how_to_enable=found.reason,
            )
        )
    return suggestions
