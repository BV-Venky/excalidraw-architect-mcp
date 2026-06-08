"""Bootstrap the knowledge graph from existing .excalidraw diagrams.

Reads the ``DiagramMetadata`` that ``create_diagram`` / ``modify_diagram``
already embed in a file's ``appState.customData`` and merges it into the
knowledge graph, so users can adopt the feature without re-describing their
architecture.
"""

from __future__ import annotations

from pathlib import Path

from excalidraw_mcp.knowledge.models import Dependency, KnowledgeGraph, Service
from excalidraw_mcp.parsers.state import read_diagram_metadata


def merge_excalidraw(kg: KnowledgeGraph, excalidraw_path: str | Path) -> tuple[int, int]:
    """Merge an .excalidraw file's metadata into ``kg`` in place.

    Returns ``(services_added, dependencies_added)``. Existing services are
    not overwritten (the knowledge graph stays authoritative); new ones and
    new dependencies are appended.
    """
    meta = read_diagram_metadata(excalidraw_path)
    if meta is None:
        raise ValueError(
            f"No excalidraw-architect-mcp metadata in {excalidraw_path}; "
            "only diagrams created by this tool can be imported."
        )

    services_added = 0
    for nm in meta.nodes.values():
        if kg.has_service(nm.node_id):
            continue
        kg.add_service(
            Service(
                id=nm.node_id,
                label=nm.label,
                component_type=nm.component_type,
            )
        )
        services_added += 1

    deps_added = 0
    for c in meta.connections:
        if kg.dependency(c.from_id, c.to_id, c.label) is not None:
            continue
        if not (kg.has_service(c.from_id) and kg.has_service(c.to_id)):
            continue
        kg.add_dependency(Dependency(from_id=c.from_id, to_id=c.to_id, label=c.label))
        deps_added += 1

    # adopt the diagram's direction only when the graph is otherwise empty
    if services_added and len(kg.services) == services_added:
        kg.direction = meta.direction

    return services_added, deps_added
