"""Stateful diagram manager for iterative editing.

Reads existing .excalidraw files, reconstructs the logical graph from
embedded metadata, applies modification operations, and triggers
incremental re-layout.
"""

from __future__ import annotations

from pathlib import Path

from excalidraw_mcp.core.components import detect_component
from excalidraw_mcp.core.models import (
    AddConnectionOp,
    AddNodeOp,
    ConnectionMetadata,
    DiagramGraph,
    DiagramMetadata,
    Edge,
    ModifyOperation,
    Node,
    NodeMetadata,
    RemoveConnectionOp,
    RemoveNodeOp,
    ThemeName,
    UpdateNodeOp,
)
from excalidraw_mcp.engine.layout import compute_layout
from excalidraw_mcp.engine.renderer import (
    build_excalidraw_file,
    load_excalidraw,
    save_excalidraw,
)

# ---------------------------------------------------------------------------
# Read existing diagram
# ---------------------------------------------------------------------------


def read_diagram_metadata(file_path: str | Path) -> DiagramMetadata | None:
    """Extract the embedded metadata from an .excalidraw file."""
    data = load_excalidraw(file_path)
    custom = data.get("appState", {}).get("customData", {}).get("excalidraw_mcp")
    if not custom:
        return None
    return DiagramMetadata.model_validate(custom)


def get_diagram_summary(file_path: str | Path) -> str:
    """Return a human-readable summary of an existing diagram.

    This is what the LLM sees when it calls get_diagram_info, enabling it
    to reason about modifications.
    """
    meta = read_diagram_metadata(file_path)
    if meta is None:
        return (
            f"File '{file_path}' exists but has no excalidraw-architect-mcp metadata. "
            "It may have been created outside this tool. "
            "Use create_diagram to rebuild it with metadata support."
        )

    lines: list[str] = []
    path_str = Path(file_path).name
    n_nodes = len(meta.nodes)
    n_conns = len(meta.connections)
    lines.append(f"Diagram: {path_str} ({n_nodes} nodes, {n_conns} connections)")
    lines.append(f"Direction: {meta.direction.value}")
    lines.append("")

    if meta.nodes:
        lines.append("Nodes:")
        for nid, nm in meta.nodes.items():
            comp = detect_component(nm.label, nm.component_type)
            comp_info = f" [{comp.category}/{nm.component_type or 'auto'}]" if comp.category else ""
            incoming = [c for c in meta.connections if c.to_id == nid]
            outgoing = [c for c in meta.connections if c.from_id == nid]
            conn_parts: list[str] = []
            if incoming:
                conn_parts.append(f"from: {', '.join(c.from_id for c in incoming)}")
            if outgoing:
                conn_parts.append(f"to: {', '.join(c.to_id for c in outgoing)}")
            conn_str = f" ({'; '.join(conn_parts)})" if conn_parts else ""
            lines.append(f'  - {nid}: "{nm.label}"{comp_info}{conn_str}')

    if meta.connections:
        lines.append("")
        lines.append("Connections:")
        for c in meta.connections:
            label_str = f' (label: "{c.label}")' if c.label else ""
            lines.append(f"  - {c.from_id} -> {c.to_id}{label_str}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reconstruct DiagramGraph from metadata
# ---------------------------------------------------------------------------


def _metadata_to_graph(meta: DiagramMetadata) -> DiagramGraph:
    """Reconstruct a DiagramGraph from stored metadata."""
    nodes = [
        Node(
            id=nm.node_id,
            label=nm.label,
            component_type=nm.component_type,
        )
        for nm in meta.nodes.values()
    ]
    edges = [Edge(from_id=c.from_id, to_id=c.to_id, label=c.label) for c in meta.connections]
    return DiagramGraph(nodes=nodes, edges=edges, direction=meta.direction)


# ---------------------------------------------------------------------------
# Apply modifications
# ---------------------------------------------------------------------------


def apply_modifications(
    file_path: str | Path,
    operations: list[ModifyOperation],
    theme: ThemeName | str = ThemeName.DEFAULT,
) -> str:
    """Apply a list of modification operations to an existing diagram.

    Returns a summary string describing what was changed.
    """
    meta = read_diagram_metadata(file_path)
    if meta is None:
        return (
            "Error: No excalidraw-architect-mcp metadata found in the file. "
            "Cannot modify a diagram not created by this tool."
        )

    changes: list[str] = []

    for op in operations:
        match op:
            case AddNodeOp():
                _apply_add_node(meta, op)
                changes.append(f"Added node '{op.id}' ({op.label})")

            case RemoveNodeOp():
                _apply_remove_node(meta, op)
                changes.append(f"Removed node '{op.id}'")

            case UpdateNodeOp():
                _apply_update_node(meta, op)
                changes.append(f"Updated node '{op.id}'")

            case AddConnectionOp():
                _apply_add_connection(meta, op)
                label_str = f" with label '{op.label}'" if op.label else ""
                changes.append(f"Added connection {op.from_id} -> {op.to_id}{label_str}")

            case RemoveConnectionOp():
                _apply_remove_connection(meta, op)
                changes.append(f"Removed connection {op.from_id} -> {op.to_id}")

    graph = _metadata_to_graph(meta)
    layout = compute_layout(graph)
    doc = build_excalidraw_file(layout, theme_name=theme, direction=meta.direction)
    save_excalidraw(doc, file_path)

    summary = f"Applied {len(changes)} operation(s) to {Path(file_path).name}:\n"
    summary += "\n".join(f"  - {c}" for c in changes)
    return summary


def _apply_add_node(meta: DiagramMetadata, op: AddNodeOp) -> None:
    meta.nodes[op.id] = NodeMetadata(
        node_id=op.id,
        label=op.label,
        component_type=op.component_type,
    )


def _apply_remove_node(meta: DiagramMetadata, op: RemoveNodeOp) -> None:
    meta.nodes.pop(op.id, None)
    meta.connections = [c for c in meta.connections if c.from_id != op.id and c.to_id != op.id]


def _apply_update_node(meta: DiagramMetadata, op: UpdateNodeOp) -> None:
    nm = meta.nodes.get(op.id)
    if nm is None:
        return
    if op.label is not None:
        nm.label = op.label
    if op.component_type is not None:
        nm.component_type = op.component_type


def _apply_add_connection(meta: DiagramMetadata, op: AddConnectionOp) -> None:
    meta.connections.append(ConnectionMetadata(from_id=op.from_id, to_id=op.to_id, label=op.label))


def _apply_remove_connection(meta: DiagramMetadata, op: RemoveConnectionOp) -> None:
    meta.connections = [
        c for c in meta.connections if not (c.from_id == op.from_id and c.to_id == op.to_id)
    ]
