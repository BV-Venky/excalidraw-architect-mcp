"""FastMCP server exposing Excalidraw diagram tools.

Diagram tools:
  1. create_diagram        -- Build a diagram of any supported type
  2. mermaid_to_excalidraw -- Convert mermaid flowchart syntax to .excalidraw
  3. modify_diagram        -- Iteratively edit an existing diagram
  4. get_diagram_info      -- Read current diagram state for LLM reasoning
  5. export_diagram        -- Export an .excalidraw file to SVG or PNG
  6. list_diagram_types    -- Every diagram type with when-to-use guidance
  7. get_diagram_schema    -- Spec schema for one diagram type

Diagram types come in two shapes. Architecture and flowchart are graphs, built
from nodes and connections by the Sugiyama layout engine. Everything else is a
*typed* diagram with its own spec and layout strategy (see ``diagrams``), and
carries that spec in customData so it can be patched and re-rendered.

Knowledge-graph tools (kg_*): a persistent, version-controlled architecture
model (default .claude/architecture.md) that is the single source of truth;
diagrams are rendered views of it. Registered via knowledge.tools.register.
"""

import json
from typing import Any

from fastmcp import FastMCP

from excalidraw_mcp.core.components import detect_component
from excalidraw_mcp.core.models import (
    AddConnectionOp,
    AddNodeOp,
    DiagramGraph,
    Direction,
    Edge,
    EdgeStyle,
    ModifyOperation,
    Node,
    RemoveConnectionOp,
    RemoveNodeOp,
    ShapeType,
    UpdateNodeOp,
)
from excalidraw_mcp.diagrams.base import SpecError
from excalidraw_mcp.diagrams.registry import (
    DiagramNotFoundError,
    build_typed_diagram,
    describe_type,
    list_types,
)
from excalidraw_mcp.engine.layout import compute_layout
from excalidraw_mcp.engine.renderer import build_excalidraw_file, save_excalidraw
from excalidraw_mcp.export.svg_exporter import export_to_png, export_to_svg
from excalidraw_mcp.knowledge.tools import register as register_knowledge_tools
from excalidraw_mcp.parsers.mermaid import parse_mermaid
from excalidraw_mcp.parsers.state import apply_modifications, get_diagram_summary
from excalidraw_mcp.parsers.typed_state import (
    apply_spec_patch,
    read_typed_metadata,
    typed_summary,
)

mcp = FastMCP(
    "Excalidraw Architect",
    instructions=(
        "Generate beautiful Excalidraw architecture diagrams with perfect "
        "auto-layout, stateful editing, and architecture-aware component "
        "styling. No API keys required."
    ),
)


# ---------------------------------------------------------------------------
# Tool 1: create_diagram
# ---------------------------------------------------------------------------


@mcp.tool
def create_diagram(
    output_path: str,
    diagram_type: str = "architecture",
    spec: dict[str, Any] | None = None,
    nodes: list[dict[str, Any]] | None = None,
    connections: list[dict[str, Any]] | None = None,
    direction: str = "LR",
    theme: str = "default",
) -> str:
    """Create a new Excalidraw diagram of any supported type.

    Two input modes:

    1. **Graph types** (``architecture``, ``flowchart``) - pass ``nodes`` and
       ``connections``. The tool handles layout, styling, and rendering; no
       coordinates needed.
    2. **Typed diagrams** (every other type) - pass ``diagram_type`` and a
       ``spec`` object shaped for that type. Call ``list_diagram_types`` to
       choose a type and ``get_diagram_schema`` to see its spec shape.

    Args:
        output_path: File path to save the .excalidraw file (e.g., "./arch.excalidraw")
        diagram_type: One of the types from ``list_diagram_types``. Default
            "architecture". Pick the type that matches what the reader needs
            to learn, not the one that is easiest to fill in.
        spec: Type-specific payload. Required for every type other than
            architecture/flowchart. Every spec accepts optional "title" and
            "subtitle". Mark 1-2 elements ``"focal": true`` to earn the accent
            color - marking five erases the signal.
        nodes: Graph types only. List of nodes. Each dict has:
            - id (str, required): Unique identifier
            - label (str, required): Display text
            - component_type (str, optional): Technology name for auto-styling
              (e.g., "kafka", "postgresql", "redis", "nginx", "kubernetes").
              If omitted, the label is used for auto-detection.
            - shape (str, optional): Override shape - "rectangle", "diamond",
              "ellipse", "circle", "stadium", "parallelogram"
        connections: Graph types only. List of connections. Each dict has:
            - from_id (str, required): Source node id
            - to_id (str, required): Target node id
            - label (str, optional): Edge label text
            - style (str, optional): "solid", "dashed", "dotted", "thick"
        direction: Layout direction for graph types - "LR" (left-right),
                   "TD" (top-down), "BT" (bottom-up), "RL" (right-left).
        theme: Color theme - "default", "dark", "colorful". Default: "default"

    Returns:
        Summary of the created diagram with file path.
    """
    graph_types = {"architecture", "flowchart"}
    if diagram_type.lower() not in graph_types or spec is not None:
        if spec is None:
            return (
                f"Error: diagram_type '{diagram_type}' requires a `spec`. "
                f"Call get_diagram_schema('{diagram_type}') to see its shape."
            )
        try:
            doc, summary = build_typed_diagram(diagram_type, spec, theme=theme)
        except DiagramNotFoundError as exc:
            return f"Error: {exc}"
        except SpecError as exc:
            return f"Error: {exc}"
        path = save_excalidraw(doc, output_path)
        return (
            f"Created diagram at: {path}\n{summary}\n\n"
            f"Open with the VS Code Excalidraw extension or drag into excalidraw.com"
        )

    if not nodes:
        return "Error: architecture/flowchart diagrams require `nodes`."
    connections = connections or []

    graph_nodes = [
        Node(
            id=n["id"],
            label=n.get("label", n["id"]),
            shape=ShapeType(n["shape"]) if "shape" in n else ShapeType.RECTANGLE,
            component_type=n.get("component_type"),
        )
        for n in nodes
    ]

    graph_edges = [
        Edge(
            from_id=c["from_id"],
            to_id=c["to_id"],
            label=c.get("label"),
            style=EdgeStyle(c["style"]) if "style" in c else EdgeStyle.SOLID,
        )
        for c in connections
    ]

    dir_upper = direction.upper()
    try:
        dir_enum = Direction(dir_upper)
    except ValueError:
        dir_enum = Direction.LEFT_RIGHT
    graph = DiagramGraph(nodes=graph_nodes, edges=graph_edges, direction=dir_enum)

    layout = compute_layout(graph)
    doc = build_excalidraw_file(layout, theme_name=theme, direction=dir_enum)
    path = save_excalidraw(doc, output_path)

    comp_summary = []
    for n in graph_nodes:
        style = detect_component(n.label, n.component_type)
        if style.category:
            comp_summary.append(f'  - {n.id}: "{n.label}" [{style.category}]')
        else:
            comp_summary.append(f'  - {n.id}: "{n.label}"')

    return (
        f"Created diagram at: {path}\n"
        f"Nodes ({len(graph_nodes)}):\n" + "\n".join(comp_summary) + "\n"
        f"Connections: {len(graph_edges)}\n"
        f"Direction: {dir_enum.value}\n"
        f"Theme: {theme}\n\n"
        f"Open with the VS Code Excalidraw extension or drag into excalidraw.com"
    )


# ---------------------------------------------------------------------------
# Tool 2: mermaid_to_excalidraw
# ---------------------------------------------------------------------------


@mcp.tool
def mermaid_to_excalidraw(
    mermaid_syntax: str,
    output_path: str,
    theme: str = "default",
) -> str:
    """Convert Mermaid flowchart syntax into an Excalidraw diagram.

    Supports the mermaid flowchart subset that AI agents commonly generate:
    - Directions: graph TD, LR, BT, RL
    - Node shapes: [text], {text}, ((text)), ([text])
    - Edge types: -->, ---, -.->  ==>  with |label|
    - Subgraphs: subgraph Title ... end

    Component types are auto-detected from node labels (e.g., a node labeled
    "PostgreSQL DB" automatically gets database styling).

    Args:
        mermaid_syntax: Mermaid flowchart source code.
        output_path: File path to save the .excalidraw file.
        theme: Color theme - "default", "dark", "colorful". Default: "default"

    Returns:
        Summary of the converted diagram.
    """
    graph = parse_mermaid(mermaid_syntax)
    layout = compute_layout(graph)
    doc = build_excalidraw_file(layout, theme_name=theme, direction=graph.direction)
    path = save_excalidraw(doc, output_path)

    return (
        f"Converted mermaid to excalidraw at: {path}\n"
        f"Nodes: {len(graph.nodes)}\n"
        f"Connections: {len(graph.edges)}\n"
        f"Subgraphs: {len(graph.subgraphs)}\n"
        f"Direction: {graph.direction.value}\n"
        f"Theme: {theme}\n\n"
        f"Open with the VS Code Excalidraw extension or drag into excalidraw.com"
    )


# ---------------------------------------------------------------------------
# Tool 3: modify_diagram
# ---------------------------------------------------------------------------


@mcp.tool
def modify_diagram(
    file_path: str,
    operations: list[dict[str, Any]],
    theme: str = "default",
) -> str:
    """Modify an existing Excalidraw diagram created by this tool.

    Supports iterative editing: add components, remove nodes, update labels,
    and rewire connections - without recreating the entire diagram.

    IMPORTANT: Call get_diagram_info first to understand the current diagram
    state before making modifications.

    For **typed diagrams** (sequence, pyramid, bar, swimlane, ...) there is a
    single operation:

        {"op": "update_spec", "patch": {"tiers": [...], "title": "New title"}}

    The patch is deep-merged into the stored spec and the diagram re-rendered.
    Lists are replaced wholesale, so send the complete list to change one
    entry. The node/connection operations below apply to architecture and
    flowchart diagrams only.

    Args:
        file_path: Path to the existing .excalidraw file.
        operations: Ordered list of operations. Each dict has:
            - op: "add_node" | "remove_node" | "update_node" |
                  "add_connection" | "remove_connection"

            For add_node:
              - id (str): New node identifier
              - label (str): Display text
              - component_type (str, optional): Technology for auto-styling
              - shape (str, optional): Shape override
              - near (str, optional): Place near this existing node id

            For remove_node:
              - id (str): Node to remove (also removes its connections)

            For update_node:
              - id (str): Node to update
              - label (str, optional): New label
              - component_type (str, optional): New component type

            For add_connection:
              - from_id (str): Source node id
              - to_id (str): Target node id
              - label (str, optional): Edge label

            For remove_connection:
              - from_id (str): Source node id
              - to_id (str): Target node id

        theme: Color theme for re-rendering. Default: "default"

    Returns:
        Summary of applied modifications.
    """
    # Typed diagrams are edited by patching their stored spec, not by
    # reconstructing a node graph -- "add_node" has no meaning on a Venn.
    if read_typed_metadata(file_path) is not None:
        patch: dict[str, Any] = {}
        for op_dict in operations:
            if op_dict.get("op") != "update_spec":
                return (
                    "Error: this is a typed diagram. Use a single operation "
                    '{"op": "update_spec", "patch": {...}}. Call get_diagram_info '
                    "first to see the current spec."
                )
            patch.update(op_dict.get("patch", {}))
        try:
            return apply_spec_patch(file_path, patch, theme=theme)
        except (SpecError, ValueError) as exc:
            return f"Error: {exc}"

    parsed_ops: list[ModifyOperation] = []
    for op_dict in operations:
        op_type = op_dict.get("op", "")
        match op_type:
            case "add_node":
                parsed_ops.append(
                    AddNodeOp(
                        id=op_dict["id"],
                        label=op_dict.get("label", op_dict["id"]),
                        component_type=op_dict.get("component_type"),
                        shape=(
                            ShapeType(op_dict["shape"])
                            if "shape" in op_dict
                            else ShapeType.RECTANGLE
                        ),
                        near=op_dict.get("near"),
                    )
                )
            case "remove_node":
                parsed_ops.append(RemoveNodeOp(id=op_dict["id"]))
            case "update_node":
                parsed_ops.append(
                    UpdateNodeOp(
                        id=op_dict["id"],
                        label=op_dict.get("label"),
                        component_type=op_dict.get("component_type"),
                    )
                )
            case "add_connection":
                parsed_ops.append(
                    AddConnectionOp(
                        from_id=op_dict["from_id"],
                        to_id=op_dict["to_id"],
                        label=op_dict.get("label"),
                    )
                )
            case "remove_connection":
                parsed_ops.append(
                    RemoveConnectionOp(
                        from_id=op_dict["from_id"],
                        to_id=op_dict["to_id"],
                    )
                )
            case _:
                return f"Error: Unknown operation type '{op_type}'"

    return apply_modifications(file_path, parsed_ops, theme=theme)


# ---------------------------------------------------------------------------
# Tool 4: get_diagram_info
# ---------------------------------------------------------------------------


@mcp.tool
def get_diagram_info(file_path: str) -> str:
    """Get a structured summary of an existing Excalidraw diagram.

    Call this BEFORE modify_diagram to understand what nodes and connections
    currently exist. The summary includes node ids, labels, component types,
    and the full connection topology.

    Args:
        file_path: Path to the .excalidraw file.

    Returns:
        Human-readable summary of all nodes and connections. For typed
        diagrams (sequence, pyramid, bar, ...) this returns the stored spec,
        which is what you patch with modify_diagram.
    """
    typed = typed_summary(file_path)
    return typed or get_diagram_summary(file_path)


# ---------------------------------------------------------------------------
# Tool 5: export_diagram
# ---------------------------------------------------------------------------


@mcp.tool
def export_diagram(
    input_path: str,
    output_path: str,
    format: str = "svg",
    scale: float = 2.0,
) -> str:
    """Export an .excalidraw file to SVG or PNG image.

    Converts an existing .excalidraw diagram into a portable image file
    without requiring a browser or the Excalidraw application.

    Args:
        input_path: Path to the source .excalidraw file.
        output_path: Destination file path (e.g., "./arch.svg" or "./arch.png").
        format: Output format - "svg" (default) or "png".
                PNG export requires the cairosvg package
                (``pip install cairosvg``).
        scale: Resolution multiplier for PNG output (default 2.0 = 2×).
               Has no effect on SVG output.

    Returns:
        Path to the exported image file.
    """
    fmt = format.lower().strip()
    if fmt not in ("svg", "png"):
        return f"Error: unsupported format '{format}'. Choose 'svg' or 'png'."

    try:
        if fmt == "svg":
            out = export_to_svg(input_path, output_path)
            return f"Exported SVG to: {out}"
        else:
            out = export_to_png(input_path, output_path, scale=scale)
            return f"Exported PNG ({scale}× scale) to: {out}"
    except FileNotFoundError:
        return f"Error: file not found: {input_path}"
    except ImportError as exc:
        return f"Error: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"Error during export: {exc}"


# ---------------------------------------------------------------------------
# Tool 6: list_diagram_types
# ---------------------------------------------------------------------------


@mcp.tool
def list_diagram_types() -> str:
    """List every supported diagram type with guidance on when to use it.

    Call this BEFORE create_diagram when the right diagram type isn't obvious.
    Picking the wrong type is the most common way a diagram fails - a
    swimlane drawn as a flowchart loses the handoffs that were the point.

    Two rules worth applying whatever you pick:
      - Target density ~4/10. Above 9 nodes it is probably two diagrams.
      - Mark only 1-2 elements "focal": true. The accent color is a signal,
        and using it everywhere destroys it.

    Returns:
        A table of type -> family, when to use it, and when not to.
    """
    by_family: dict[str, list[str]] = {}
    for dt in list_types():
        by_family.setdefault(dt.family, []).append(
            f"  {dt.name}\n    use when:  {dt.use_when}\n    avoid when: {dt.avoid_when}"
        )

    sections = [
        "architecture / flowchart  (graph family, use `nodes` + `connections`)",
        "  use when:  Components and the connections between them; decision logic with branches.",
        "",
    ]
    for family in ("structural", "flow", "geometric", "chart"):
        if family in by_family:
            sections.append(f"--- {family} ---")
            sections.extend(by_family[family])
            sections.append("")
    sections.append("Call get_diagram_schema(<type>) for the exact spec shape.")
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Tool 7: get_diagram_schema
# ---------------------------------------------------------------------------


@mcp.tool
def get_diagram_schema(diagram_type: str) -> str:
    """Get the JSON schema and selection guidance for one diagram type.

    Call this before passing a `spec` to create_diagram for a type you have
    not used yet, so the payload matches on the first attempt.

    Args:
        diagram_type: A type name from list_diagram_types (e.g. "sequence",
            "pyramid", "bar", "swimlane").

    Returns:
        JSON with the spec schema, plus use_when / avoid_when guidance.
    """
    try:
        return json.dumps(describe_type(diagram_type), indent=2)
    except DiagramNotFoundError as exc:
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# Knowledge-graph tools (kg_*)
# ---------------------------------------------------------------------------

register_knowledge_tools(mcp)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Run the MCP server over stdio."""
    mcp.run()
