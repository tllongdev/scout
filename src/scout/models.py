"""Core data structures shared across the agents.

Everything an agent discovers flows into a single ``Mission`` object: entities
become graph nodes, edges become relationships, observations and raw documents
preserve provenance, and findings are the synthesized conclusions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Task(BaseModel):
    """A single collection objective produced by the planner."""

    id: str = Field(default_factory=_new_id)
    objective: str
    rationale: str = ""
    suggested_sources: list[str] = Field(default_factory=list)
    needs_human: bool = False
    status: str = "pending"  # pending | running | done | failed


class Entity(BaseModel):
    """A node in the intelligence graph (person, org, place, asset, ...)."""

    id: str = Field(default_factory=_new_id)
    name: str
    type: str = "unknown"
    attributes: dict[str, Any] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    """A directed relationship between two entities, by name."""

    id: str = Field(default_factory=_new_id)
    source: str
    target: str
    relationship: str
    confidence: float = 0.5
    sources: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    """A discrete fact or note an agent recorded, with provenance."""

    id: str = Field(default_factory=_new_id)
    content: str
    source: str = ""
    task_id: str = ""
    created_at: str = Field(default_factory=_now)


class RawDocument(BaseModel):
    """Raw collected content, preserved verbatim for auditability."""

    id: str = Field(default_factory=_new_id)
    url: str = ""
    title: str = ""
    content: str = ""
    retrieved_at: str = Field(default_factory=_now)


class Finding(BaseModel):
    """A synthesized conclusion drawn from the collected intelligence."""

    id: str = Field(default_factory=_new_id)
    statement: str
    confidence: float = 0.5
    supporting_entities: list[str] = Field(default_factory=list)
    supporting_sources: list[str] = Field(default_factory=list)


class Mission(BaseModel):
    """The full state of a collection run."""

    id: str = Field(default_factory=_new_id)
    brief: str
    created_at: str = Field(default_factory=_now)
    tasks: list[Task] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    raw_documents: list[RawDocument] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    summary: str = ""

    # ── mutation helpers (merge-by-name so agents don't create duplicates) ──

    def upsert_entity(self, entity: Entity) -> Entity:
        for existing in self.entities:
            if existing.name.lower() == entity.name.lower():
                existing.attributes.update(entity.attributes)
                existing.sources = _dedupe(existing.sources + entity.sources)
                if entity.type != "unknown":
                    existing.type = entity.type
                return existing
        self.entities.append(entity)
        return entity

    def add_edge(self, edge: Edge) -> Edge:
        for existing in self.edges:
            if (
                existing.source.lower() == edge.source.lower()
                and existing.target.lower() == edge.target.lower()
                and existing.relationship.lower() == edge.relationship.lower()
            ):
                existing.sources = _dedupe(existing.sources + edge.sources)
                existing.confidence = max(existing.confidence, edge.confidence)
                return existing
        self.edges.append(edge)
        return edge


def _dedupe(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        if item:
            seen.setdefault(item, None)
    return list(seen.keys())
