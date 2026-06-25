"""Build a networkx graph from the mission and render an interactive view."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from pyvis.network import Network

from .models import Mission

# Colors by entity type for the rendered graph.
_TYPE_COLORS = {
    "person": "#5a5ad8",
    "organization": "#2bb673",
    "place": "#e8a13a",
    "asset": "#c64b8c",
    "event": "#4aa3df",
    "unknown": "#888888",
    "other": "#888888",
}


def build_graph(mission: Mission) -> nx.DiGraph:
    graph: nx.DiGraph = nx.DiGraph()
    for entity in mission.entities:
        graph.add_node(
            entity.name,
            type=entity.type,
            attributes=entity.attributes,
            sources=entity.sources,
        )
    for edge in mission.edges:
        # Ensure endpoints exist even if only referenced in a relationship.
        for endpoint in (edge.source, edge.target):
            if endpoint not in graph:
                graph.add_node(endpoint, type="unknown", attributes={}, sources=[])
        graph.add_edge(
            edge.source,
            edge.target,
            relationship=edge.relationship,
            confidence=edge.confidence,
            sources=edge.sources,
        )
    return graph


def render_graph_html(mission: Mission, out_path: Path) -> None:
    graph = build_graph(mission)

    net = Network(
        height="800px",
        width="100%",
        bgcolor="#0a0a0a",
        font_color="#f0f0f0",
        directed=True,
        notebook=False,
    )
    net.barnes_hut(gravity=-8000, spring_length=140)

    for name, data in graph.nodes(data=True):
        etype = data.get("type", "unknown")
        color = _TYPE_COLORS.get(etype, _TYPE_COLORS["unknown"])
        attrs = data.get("attributes") or {}
        tooltip = f"{name} ({etype})"
        if attrs:
            tooltip += "\n" + "\n".join(f"{k}: {v}" for k, v in attrs.items())
        net.add_node(name, label=name, title=tooltip, color=color, size=20)

    for source, target, data in graph.edges(data=True):
        net.add_edge(
            source,
            target,
            title=data.get("relationship", ""),
            label=data.get("relationship", ""),
            value=data.get("confidence", 0.5),
        )

    out_path.write_text(net.generate_html(notebook=False), encoding="utf-8")
