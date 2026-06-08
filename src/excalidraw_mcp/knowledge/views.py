"""Render projections of the knowledge graph to .excalidraw files.

Every render path projects the (filtered) KnowledgeGraph down to a
:class:`DiagramGraph` and hands it to the existing engine
(``compute_layout`` -> ``build_excalidraw_file`` -> ``save_excalidraw``).
The layout/render/export engine is reused unchanged.
"""

from __future__ import annotations

from pathlib import Path

from excalidraw_mcp.core.models import DiagramGraph
from excalidraw_mcp.engine.layout import compute_layout
from excalidraw_mcp.engine.renderer import build_excalidraw_file, save_excalidraw
from excalidraw_mcp.knowledge import query
from excalidraw_mcp.knowledge.models import KnowledgeGraph


def _render(graph: DiagramGraph, output_path: str | Path, theme: str) -> Path:
    layout = compute_layout(graph)
    doc = build_excalidraw_file(layout, theme_name=theme, direction=graph.direction)
    return save_excalidraw(doc, output_path)


def _summary(kind: str, graph: DiagramGraph, path: Path) -> str:
    return (
        f"Rendered {kind} to {path}: "
        f"{len(graph.nodes)} node(s), {len(graph.edges)} edge(s), "
        f"{len(graph.subgraphs)} group(s)."
    )


def render(
    kg: KnowledgeGraph,
    output_path: str | Path,
    theme: str = "default",
) -> str:
    """Render the entire knowledge graph."""
    graph = kg.to_diagram_graph()
    if not graph.nodes:
        return "Knowledge graph is empty — nothing to render."
    path = _render(graph, output_path, theme)
    return _summary("full architecture", graph, path)


def render_view(
    kg: KnowledgeGraph,
    node_ids: list[str],
    output_path: str | Path,
    theme: str = "default",
) -> str:
    """Render a focused slice containing exactly the given services."""
    known = [nid for nid in node_ids if kg.has_service(nid)]
    missing = [nid for nid in node_ids if not kg.has_service(nid)]
    if not known:
        return f"None of the requested services exist: {', '.join(node_ids)}."
    graph = kg.to_diagram_graph(known)
    path = _render(graph, output_path, theme)
    note = f" (skipped unknown: {', '.join(missing)})" if missing else ""
    return _summary("focused view", graph, path) + note


def render_around(
    kg: KnowledgeGraph,
    service_id: str,
    depth: int,
    output_path: str | Path,
    theme: str = "default",
    direction: str = "both",
) -> str:
    """Render ``service_id`` plus everything within ``depth`` hops."""
    if not kg.has_service(service_id):
        return f"Service '{service_id}' not found."
    nodes = [service_id, *query.connected(kg, service_id, depth=depth, direction=direction)]
    graph = kg.to_diagram_graph(nodes)
    path = _render(graph, output_path, theme)
    return _summary(f"{depth}-hop neighborhood of '{service_id}'", graph, path)


def render_domain(
    kg: KnowledgeGraph,
    domain: str,
    output_path: str | Path,
    theme: str = "default",
) -> str:
    """Render only the services in one domain."""
    members = kg.domain_members(domain)
    if not members:
        return f"Domain '{domain}' has no services."
    graph = kg.to_diagram_graph(members)
    path = _render(graph, output_path, theme)
    return _summary(f"domain '{kg.domain_label(domain)}'", graph, path)
