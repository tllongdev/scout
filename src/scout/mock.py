"""A no-key 'mock' provider for trying Scout end to end.

Set ``SCOUT_MODEL=mock`` to run a full mission - plan, collect (with real
tool calls), synthesize, graph, and report - without any API key or local
model. The "reasoning" is scripted, so findings are illustrative rather than
real, but every moving part of the pipeline runs exactly as it would with a
live model. It's meant for demos and smoke tests, not actual intelligence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

DEMO_SOURCE = "demo://mock-run"


# ── Minimal stand-ins for a provider's message / tool-call objects ──────────


@dataclass
class _MockFunction:
    name: str
    arguments: str


@dataclass
class _MockToolCall:
    id: str
    function: _MockFunction
    type: str = "function"


@dataclass
class _MockMessage:
    content: str | None = None
    tool_calls: list[_MockToolCall] | None = None


def _call(idx: int, name: str, args: dict[str, Any]) -> _MockToolCall:
    return _MockToolCall(
        id=f"mock_{name}_{idx}",
        function=_MockFunction(name=name, arguments=json.dumps(args)),
    )


# ── Text helpers so the demo output relates to the user's brief ─────────────


_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "about", "into", "any", "all", "their", "its", "this", "that", "these",
    "find", "map", "identify", "surface", "collect", "gather", "research",
    "investigate", "analyze", "analyse", "examine", "assess", "review",
    "explore", "track", "trace", "locate", "monitor", "evaluate", "study",
    "look", "search", "discover", "determine", "understand", "area",
}


def _keywords(text: str, limit: int = 6) -> list[str]:
    """Pull proper-noun-ish words from text for believable entity names."""
    caps = re.findall(r"\b[A-Z][A-Za-z0-9&.\-]{2,}\b", text)
    seen: dict[str, None] = {}
    for word in caps:
        if word.lower() not in _STOP:
            seen.setdefault(word, None)
    if seen:
        return list(seen)[:limit]
    # Fall back to longest plain words so we still produce something relevant.
    words = [w for w in re.findall(r"[A-Za-z]{4,}", text) if w.lower() not in _STOP]
    words.sort(key=len, reverse=True)
    return [w.title() for w in dict.fromkeys(words)][:limit] or ["Subject"]


def _subject(brief: str) -> str:
    return _keywords(brief, limit=1)[0]


def _topic(objective: str, brief: str) -> str:
    """Pick a lead distinct from the subject, varied per task objective."""
    subj = _subject(brief)
    candidates = [k for k in _keywords(brief, limit=8) if k.lower() != subj.lower()]
    if not candidates:
        candidates = [k for k in _keywords(objective, limit=4) if k.lower() != subj.lower()]
    if not candidates:
        return f"Lead {abs(hash(objective)) % 90 + 10}"
    # Deterministically vary the chosen lead across tasks.
    return candidates[abs(hash(objective)) % len(candidates)]


# ── Scripted agent behavior ─────────────────────────────────────────────────


def _system_of(messages: list[dict[str, Any]]) -> str:
    for m in messages:
        if m.get("role") == "system":
            return str(m.get("content", ""))
    return ""


def _user_of(messages: list[dict[str, Any]]) -> str:
    for m in messages:
        if m.get("role") == "user":
            return str(m.get("content", ""))
    return ""


def _brief_from(user: str) -> str:
    # Collector/synthesizer prompts embed the brief after a known label.
    for label in ("OVERALL MISSION:\n", "MISSION BRIEF:\n"):
        if label in user:
            return user.split(label, 1)[1].splitlines()[0].strip()
    return user.strip().splitlines()[0] if user.strip() else "the subject"


def _objective_from(user: str) -> str:
    if "YOUR TASK:\n" in user:
        return user.split("YOUR TASK:\n", 1)[1].splitlines()[0].strip()
    return _brief_from(user)


def _plan(brief: str) -> str:
    subject = _subject(brief)
    tasks = [
        {
            "objective": f"Map {subject} and its public footprint",
            "rationale": "Establish a baseline of who/what the subject is before going deeper.",
            "suggested_sources": ["web search", "official site", "news"],
            "needs_human": False,
        },
        {
            "objective": f"Identify key people and organizations connected to {subject}",
            "rationale": "Connections reveal influence, dependencies, and leads.",
            "suggested_sources": ["registries", "news", "social"],
            "needs_human": False,
        },
        {
            "objective": f"Surface notable events, claims, and open questions about {subject}",
            "rationale": "Events and contradictions are where the real signal lives.",
            "suggested_sources": ["archives", "filings", "press"],
            "needs_human": False,
        },
    ]
    return json.dumps(tasks)


def _synthesis(payload_user: str) -> str:
    names = re.findall(r"^- (.+?) \[", payload_user, flags=re.MULTILINE)
    names = list(dict.fromkeys(names))[:5]
    brief = _brief_from(payload_user)
    findings = [
        {
            "statement": f"Demo: the collected nodes cluster around {names[0]}."
            if names
            else "Demo: a small illustrative graph was assembled for this run.",
            "confidence": 0.4,
            "supporting_entities": names[:3],
            "supporting_sources": [DEMO_SOURCE],
        },
        {
            "statement": "Demo: this run used the mock provider, so findings are "
            "illustrative - configure a real model for genuine intelligence.",
            "confidence": 0.99,
            "supporting_entities": [],
            "supporting_sources": [DEMO_SOURCE],
        },
    ]
    summary = (
        f"[MOCK RUN] This is a scripted demonstration for the brief: {brief!r}. "
        f"Scout planned tasks, ran collector agents that exercised real tools, "
        f"recorded {len(names)} sample entities into the graph, and produced these "
        f"placeholder findings. Set SCOUT_MODEL to a real provider for live results."
    )
    return json.dumps({"summary": summary, "findings": findings})


@dataclass
class _State:
    """Tracks collector progress within a single run_agent loop."""

    turns: int = 0


# A loop is identified by its (immutable) task objective; we count assistant
# turns already present in the message list instead of holding state, so the
# provider stays stateless across calls.


def mock_complete(
    messages: list[dict[str, Any]], tools: list[Any] | None
) -> _MockMessage:
    system = _system_of(messages)
    user = _user_of(messages)

    # Toolless calls are the planner and synthesizer (LLM.chat).
    if not tools:
        if "planning module" in system:
            return _MockMessage(content=_plan(_brief_from(user)))
        if "synthesis module" in system:
            return _MockMessage(content=_synthesis(user))
        return _MockMessage(content="[MOCK] No live model configured.")

    # Otherwise we're inside a collector tool-calling loop.
    prior_turns = sum(1 for m in messages if m.get("role") == "assistant")
    brief = _brief_from(user)
    objective = _objective_from(user)
    subject = _subject(brief)
    topic = _topic(objective, brief)

    if prior_turns == 0:
        # Step 1: exercise a real tool so the pipeline is genuinely exercised.
        return _MockMessage(
            tool_calls=[_call(0, "web_search", {"query": objective, "max_results": 3})]
        )

    if prior_turns == 1:
        # Step 2: write structured intelligence into the mission graph.
        return _MockMessage(
            tool_calls=[
                _call(
                    1,
                    "record_entity",
                    {"name": subject, "type": "subject", "source": DEMO_SOURCE},
                ),
                _call(
                    2,
                    "record_entity",
                    {"name": topic, "type": "lead", "source": DEMO_SOURCE},
                ),
                _call(
                    3,
                    "record_edge",
                    {
                        "source": subject,
                        "target": topic,
                        "relationship": "connected to",
                        "confidence": 0.4,
                        "evidence": DEMO_SOURCE,
                    },
                ),
                _call(
                    4,
                    "record_observation",
                    {
                        "content": f"[MOCK] Demo observation linking {subject} to {topic}.",
                        "source": DEMO_SOURCE,
                    },
                ),
            ]
        )

    # Step 3+: stop and summarize.
    return _MockMessage(
        content=(
            f"[MOCK] Recorded {subject} and {topic} plus one relationship for the "
            "demo. No live model was used; configure SCOUT_MODEL for real collection."
        )
    )
