"""Write mission results to disk: raw data, graph, and a findings report."""

from __future__ import annotations

import json
from pathlib import Path

from .graph import build_graph, render_graph_html
from .models import Mission


def write_outputs(mission: Mission, out_dir: Path) -> dict[str, Path]:
    run_dir = out_dir / f"mission-{mission.created_at[:10]}-{mission.id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    # Full structured mission state.
    mission_path = run_dir / "mission.json"
    mission_path.write_text(mission.model_dump_json(indent=2), encoding="utf-8")
    paths["mission"] = mission_path

    # Raw collected documents, preserved verbatim.
    raw_path = run_dir / "raw_documents.json"
    raw_path.write_text(
        json.dumps([d.model_dump() for d in mission.raw_documents], indent=2),
        encoding="utf-8",
    )
    paths["raw"] = raw_path

    # Graph as node-link JSON.
    graph = build_graph(mission)
    graph_path = run_dir / "graph.json"
    graph_path.write_text(
        json.dumps(_node_link(graph), indent=2), encoding="utf-8"
    )
    paths["graph_json"] = graph_path

    # Interactive graph.
    graph_html = run_dir / "graph.html"
    try:
        render_graph_html(mission, graph_html)
        paths["graph_html"] = graph_html
    except Exception:  # noqa: BLE001 - viz is best-effort
        pass

    # Human-readable report.
    report_path = run_dir / "findings.md"
    report_path.write_text(_render_report(mission), encoding="utf-8")
    paths["report"] = report_path

    return paths


def _node_link(graph: object) -> dict:
    import networkx as nx

    return nx.node_link_data(graph, edges="links")  # type: ignore[arg-type]


def _render_report(mission: Mission) -> str:
    lines: list[str] = []
    lines.append("# Intelligence Report")
    lines.append(f"\n**Mission:** {mission.brief}")
    lines.append(f"\n**Run:** {mission.id} · {mission.created_at}")

    lines.append("\n## Executive Summary\n")
    lines.append(mission.summary or "_No summary produced._")

    lines.append("\n## Findings\n")
    if mission.findings:
        ranked = sorted(mission.findings, key=lambda f: f.confidence, reverse=True)
        for i, finding in enumerate(ranked, 1):
            lines.append(f"### {i}. {finding.statement}")
            lines.append(f"- Confidence: {finding.confidence:.0%}")
            if finding.supporting_entities:
                lines.append(
                    "- Entities: " + ", ".join(finding.supporting_entities)
                )
            if finding.supporting_sources:
                lines.append(
                    "- Sources: " + ", ".join(finding.supporting_sources)
                )
            lines.append("")
    else:
        lines.append("_No findings produced._")

    lines.append("## Entities\n")
    if mission.entities:
        for e in mission.entities:
            attrs = (
                " — " + ", ".join(f"{k}: {v}" for k, v in e.attributes.items())
                if e.attributes
                else ""
            )
            lines.append(f"- **{e.name}** ({e.type}){attrs}")
    else:
        lines.append("_None._")

    lines.append("\n## Relationships\n")
    if mission.edges:
        for edge in mission.edges:
            lines.append(
                f"- {edge.source} → **{edge.relationship}** → {edge.target} "
                f"({edge.confidence:.0%})"
            )
    else:
        lines.append("_None._")

    lines.append("\n## Tasks Executed\n")
    for task in mission.tasks:
        flag = " 🧑 needs-human" if task.needs_human else ""
        lines.append(f"- [{task.status}] {task.objective}{flag}")

    lines.append(
        f"\n## Provenance\n\n{len(mission.raw_documents)} raw documents collected "
        "(see `raw_documents.json`)."
    )

    return "\n".join(lines) + "\n"
