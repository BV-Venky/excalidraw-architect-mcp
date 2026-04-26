"""FastMCP server exposing Excalidraw diagram tools.

Five tools:
  1. create_diagram        -- Build a new diagram from structured node/connection data
  2. mermaid_to_excalidraw -- Convert mermaid flowchart syntax to .excalidraw
  3. modify_diagram        -- Iteratively edit an existing diagram
  4. get_diagram_info      -- Read current diagram state for LLM reasoning
  5. export_diagram        -- Export an .excalidraw file to SVG or PNG
"""

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
from excalidraw_mcp.engine.layout import compute_layout
from excalidraw_mcp.engine.renderer import build_excalidraw_file, save_excalidraw
from excalidraw_mcp.export.svg_exporter import export_to_png, export_to_svg
from excalidraw_mcp.parsers.mermaid import parse_mermaid
from excalidraw_mcp.parsers.state import apply_modifications, get_diagram_summary

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
    nodes: list[dict[str, Any]],
    connections: list[dict[str, Any]],
    output_path: str,
    direction: str = "LR",
    theme: str = "default",
) -> str:
    """Create a new Excalidraw diagram from structured node and connection data.

    The LLM provides a relationship map - this tool handles layout, styling,
    and rendering. No need to specify coordinates.

    Args:
        nodes: List of nodes. Each dict has:
            - id (str, required): Unique identifier
            - label (str, required): Display text
            - component_type (str, optional): Technology name for auto-styling
              (e.g., "kafka", "postgresql", "redis", "nginx", "kubernetes").
              If omitted, the label is used for auto-detection.
            - shape (str, optional): Override shape - "rectangle", "diamond",
              "ellipse", "circle", "stadium", "parallelogram"
        connections: List of connections. Each dict has:
            - from_id (str, required): Source node id
            - to_id (str, required): Target node id
            - label (str, optional): Edge label text
            - style (str, optional): "solid", "dashed", "dotted", "thick"
        output_path: File path to save the .excalidraw file (e.g., "./arch.excalidraw")
        direction: Layout direction - "LR" (left-right), "TD" (top-down),
                   "BT" (bottom-up), "RL" (right-left). Default: "LR"
        theme: Color theme - "default", "dark", "colorful". Default: "default"

    Returns:
        Summary of the created diagram with file path.
    """
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
        Human-readable summary of all nodes and connections.
    """
    return get_diagram_summary(file_path)


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
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Run the MCP server over stdio."""
    mcp.run()
