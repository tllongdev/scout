"""Synthesis turns the collected graph + observations into findings.

It runs over everything the collectors recorded and produces ranked, sourced
conclusions plus a short executive summary.
"""

from __future__ import annotations

from ..llm import LLM, extract_json
from ..models import Finding, Mission

_SYSTEM = """You are the synthesis module of an intelligence operation. You are
given the structured intelligence collected for a mission: entities, the
relationships between them, and free-text observations (all with sources).

Produce conclusions that directly serve the mission brief. Draw connections the
raw data implies but doesn't state outright. Be honest about uncertainty and
note gaps.

Return ONLY JSON (no prose) of the form:
{
  "summary": "3-5 sentence executive summary answering the brief",
  "findings": [
    {
      "statement": "a specific, sourced conclusion",
      "confidence": 0.0-1.0,
      "supporting_entities": ["entity names"],
      "supporting_sources": ["urls or files"]
    }
  ]
}"""


def synthesize(llm: LLM, mission: Mission) -> None:
    payload = _serialize_for_synthesis(mission)
    user = f"MISSION BRIEF:\n{mission.brief}\n\nCOLLECTED INTELLIGENCE:\n{payload}"
    raw = llm.chat(_SYSTEM, user)

    try:
        data = extract_json(raw)
    except ValueError:
        mission.summary = raw.strip()[:2000]
        return

    if not isinstance(data, dict):
        mission.summary = str(data)[:2000]
        return

    mission.summary = str(data.get("summary", "")).strip()
    for item in data.get("findings", []):
        if not isinstance(item, dict):
            continue
        statement = str(item.get("statement", "")).strip()
        if not statement:
            continue
        mission.findings.append(
            Finding(
                statement=statement,
                confidence=_clamp(item.get("confidence", 0.5)),
                supporting_entities=[
                    str(e) for e in (item.get("supporting_entities") or []) if e
                ],
                supporting_sources=[
                    str(s) for s in (item.get("supporting_sources") or []) if s
                ],
            )
        )


def _serialize_for_synthesis(mission: Mission) -> str:
    lines: list[str] = []

    lines.append(f"ENTITIES ({len(mission.entities)}):")
    for e in mission.entities:
        attrs = ", ".join(f"{k}={v}" for k, v in e.attributes.items())
        lines.append(f"- {e.name} [{e.type}] {attrs}".rstrip())

    lines.append(f"\nRELATIONSHIPS ({len(mission.edges)}):")
    for edge in mission.edges:
        lines.append(
            f"- {edge.source} -[{edge.relationship}]-> {edge.target} "
            f"(conf {edge.confidence:.1f})"
        )

    lines.append(f"\nOBSERVATIONS ({len(mission.observations)}):")
    for obs in mission.observations:
        src = f" (src: {obs.source})" if obs.source else ""
        lines.append(f"- {obs.content}{src}")

    text = "\n".join(lines)
    return text[:20000]


def _clamp(value: object) -> float:
    try:
        return max(0.0, min(1.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.5
