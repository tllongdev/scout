"""Tools the agent uses to write structured intelligence onto the mission.

As a collector reads sources, it records entities, relationships, and
observations. These accumulate into the mission graph that synthesis runs over.
"""

from __future__ import annotations

from typing import Any

from ..llm import Tool
from ..models import Edge, Entity, Mission, Observation


def record_entity_tool(mission: Mission, task_id: str) -> Tool:
    def _handle(args: dict[str, Any]) -> str:
        name = str(args.get("name", "")).strip()
        if not name:
            return "Error: 'name' is required."
        entity = Entity(
            name=name,
            type=str(args.get("type", "unknown")).strip() or "unknown",
            attributes=args.get("attributes") or {},
            sources=_as_list(args.get("source")),
        )
        mission.upsert_entity(entity)
        return f"Recorded entity: {name} ({entity.type})."

    return Tool(
        name="record_entity",
        description=(
            "Record an entity (person, organization, place, asset, event, ...) "
            "you discovered. Entities become nodes in the intelligence graph. "
            "Always include the source URL or file you found it in."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Canonical name."},
                "type": {
                    "type": "string",
                    "description": "person | organization | place | asset | event | other",
                },
                "attributes": {
                    "type": "object",
                    "description": "Key/value facts about the entity.",
                },
                "source": {
                    "type": "string",
                    "description": "URL or file the entity came from.",
                },
            },
            "required": ["name"],
        },
        handler=_handle,
    )


def record_edge_tool(mission: Mission, task_id: str) -> Tool:
    def _handle(args: dict[str, Any]) -> str:
        source = str(args.get("source", "")).strip()
        target = str(args.get("target", "")).strip()
        relationship = str(args.get("relationship", "")).strip()
        if not (source and target and relationship):
            return "Error: 'source', 'target', and 'relationship' are required."
        edge = Edge(
            source=source,
            target=target,
            relationship=relationship,
            confidence=float(args.get("confidence", 0.5)),
            sources=_as_list(args.get("evidence")),
        )
        mission.add_edge(edge)
        return f"Recorded edge: {source} -[{relationship}]-> {target}."

    return Tool(
        name="record_edge",
        description=(
            "Record a relationship between two entities (by name). Edges become "
            "the connections in the intelligence graph - e.g. 'funds', 'leads', "
            "'owns', 'partnered with'. Include evidence (the source)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source entity name."},
                "target": {"type": "string", "description": "Target entity name."},
                "relationship": {
                    "type": "string",
                    "description": "How they relate (short verb phrase).",
                },
                "confidence": {
                    "type": "number",
                    "description": "0.0-1.0 confidence in this relationship.",
                },
                "evidence": {
                    "type": "string",
                    "description": "URL or file supporting the relationship.",
                },
            },
            "required": ["source", "target", "relationship"],
        },
        handler=_handle,
    )


def record_observation_tool(mission: Mission, task_id: str) -> Tool:
    def _handle(args: dict[str, Any]) -> str:
        content = str(args.get("content", "")).strip()
        if not content:
            return "Error: 'content' is required."
        mission.observations.append(
            Observation(
                content=content,
                source=str(args.get("source", "")).strip(),
                task_id=task_id,
            )
        )
        return "Observation recorded."

    return Tool(
        name="record_observation",
        description=(
            "Record a noteworthy fact or finding that isn't itself an entity or "
            "edge - context, a quote, a data point, a contradiction. Include the "
            "source."
        ),
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The observation."},
                "source": {
                    "type": "string",
                    "description": "URL or file it came from.",
                },
            },
            "required": ["content"],
        },
        handler=_handle,
    )


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [str(value)]
