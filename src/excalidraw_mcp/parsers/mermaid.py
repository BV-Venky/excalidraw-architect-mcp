"""Mermaid flowchart parser.

Parses the subset of Mermaid syntax that AI agents commonly generate:
  - graph/flowchart declarations with direction (TD, LR, BT, RL)
  - Node shapes: [text], {text}, ((text)), ([text]), [(text)], [/text/]
  - Edge types: -->, ---, -.->  ==>  with optional |label|
  - Subgraphs: subgraph Title ... end

Outputs a DiagramGraph ready for the layout engine.

Strategy: two-pass parsing per line.
  1. Extract all node definitions (id + optional shape/label) via regex
  2. Reduce the line to bare node IDs, then parse edges
"""

from __future__ import annotations

import re

from excalidraw_mcp.core.models import (
    DiagramGraph,
    Direction,
    Edge,
    EdgeStyle,
    Node,
    ShapeType,
    Subgraph,
)

# ---------------------------------------------------------------------------
# Direction mapping
# ---------------------------------------------------------------------------

_DIRECTION_MAP: dict[str, Direction] = {
    "TD": Direction.TOP_DOWN,
    "TB": Direction.TOP_DOWN,
    "LR": Direction.LEFT_RIGHT,
    "BT": Direction.BOTTOM_UP,
    "RL": Direction.RIGHT_LEFT,
}

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_GRAPH_DECL = re.compile(r"^\s*(?:graph|flowchart)\s+(TD|TB|LR|BT|RL)\s*$", re.IGNORECASE)

_SUBGRAPH_START = re.compile(
    r"^\s*subgraph\s+(?:(\w+)\s*\[([^\]]*)\]|(\w+)\s*$|(.+))\s*", re.IGNORECASE
)
_SUBGRAPH_END = re.compile(r"^\s*end\s*$", re.IGNORECASE)

# Ordered list of shape patterns: (open_re, close_re, ShapeType)
# Order matters -- more specific patterns must come before less specific ones.
_SHAPE_PATTERNS: list[tuple[str, str, ShapeType]] = [
    (r"\(\(", r"\)\)", ShapeType.CIRCLE),  # ((text))  - circle
    (r"\(\[", r"\]\)", ShapeType.STADIUM),  # ([text])  - stadium
    (r"\[\(", r"\)\]", ShapeType.ELLIPSE),  # [(text)]  - cylinder/DB
    (r"\{\{", r"\}\}", ShapeType.RECTANGLE),  # {{text}}  - hexagon -> rect
    (r"\{", r"\}", ShapeType.DIAMOND),  # {text}    - diamond
    (r"\[/", r"/\]", ShapeType.PARALLELOGRAM),  # [/text/]  - parallelogram
    (r"\[\\", r"\\\]", ShapeType.PARALLELOGRAM),  # [\text\]  - parallelogram alt
    (r"\[", r"\]", ShapeType.RECTANGLE),  # [text]    - rectangle (last!)
]

_SINGLE_NODE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)")


def _try_extract_shape(text: str, start: int) -> tuple[str, ShapeType] | None:
    """Try to match a shape definition starting at position `start` in text."""
    remaining = text[start:]
    for open_re, close_re, shape in _SHAPE_PATTERNS:
        m = re.match(rf"\s*{open_re}(.+?){close_re}", remaining)
        if m:
            return m.group(1).strip(), shape
    return None


# Edge patterns (operate on cleaned lines with bare IDs)
_EDGE_PATTERN = re.compile(
    r"(?P<from_id>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*"
    r"(?P<arrow>"
    r"==+>|--+>|---+|-\.+->|-\.-+"
    r")"
    r"(?:\|(?P<label>[^|]*)\|)?"
    r"\s*"
    r"(?P<to_id>[A-Za-z_][A-Za-z0-9_]*)"
)

_EDGE_WITH_TEXT = re.compile(
    r"(?P<from_id>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*"
    r"(?:--\s+(?P<inline_label>[^-]+?)\s+-->)"
    r"\s*"
    r"(?P<to_id>[A-Za-z_][A-Za-z0-9_]*)"
)


# ---------------------------------------------------------------------------
# Node extraction (pass 1)
# ---------------------------------------------------------------------------


def _extract_nodes_from_line(
    line: str,
    nodes: dict[str, Node],
    subgraph_stack: list[Subgraph],
) -> str:
    """Extract all node definitions from a line, updating the nodes dict.

    Returns a cleaned version of the line where shape annotations are
    stripped, leaving only bare node IDs for edge parsing.
    """
    result_parts: list[str] = []
    last_end = 0

    for m in _SINGLE_NODE.finditer(line):
        node_id = m.group(1)
        shape_end = m.end()

        shape_info = _try_extract_shape(line, shape_end)

        if shape_info:
            label, shape = shape_info
            remaining_after_id = line[shape_end:]
            for open_re, close_re, s in _SHAPE_PATTERNS:
                sm = re.match(rf"\s*{open_re}(.+?){close_re}", remaining_after_id)
                if sm:
                    full_end = shape_end + sm.end()
                    result_parts.append(line[last_end : m.start()])
                    result_parts.append(node_id)
                    last_end = full_end
                    break

            if node_id not in nodes:
                nodes[node_id] = Node(id=node_id, label=label, shape=shape)
                _add_to_subgraph(node_id, subgraph_stack)
            else:
                nodes[node_id].label = label
                nodes[node_id].shape = shape
        else:
            if node_id not in nodes:
                pass  # Will be created with default label when used in edge

    result_parts.append(line[last_end:])
    return "".join(result_parts)


# ---------------------------------------------------------------------------
# Edge extraction (pass 2)
# ---------------------------------------------------------------------------


def _extract_edge_style(arrow: str) -> EdgeStyle:
    if arrow.startswith("=="):
        return EdgeStyle.THICK
    if "-." in arrow:
        return EdgeStyle.DASHED
    if ".." in arrow:
        return EdgeStyle.DOTTED
    return EdgeStyle.SOLID


def _extract_edges_from_line(
    cleaned_line: str,
    nodes: dict[str, Node],
    edges: list[Edge],
    subgraph_stack: list[Subgraph],
) -> None:
    """Extract edges from a cleaned line (shape annotations already stripped)."""
    # Try inline-label edges first: A -- text --> B
    for m in _EDGE_WITH_TEXT.finditer(cleaned_line):
        from_id = m.group("from_id")
        to_id = m.group("to_id")
        label = m.group("inline_label").strip() if m.group("inline_label") else None

        _ensure_node(from_id, nodes, subgraph_stack)
        _ensure_node(to_id, nodes, subgraph_stack)
        edges.append(Edge(from_id=from_id, to_id=to_id, label=label, style=EdgeStyle.SOLID))
        return

    # Standard edges: A --> B, A -->|label| B
    for m in _EDGE_PATTERN.finditer(cleaned_line):
        from_id = m.group("from_id")
        to_id = m.group("to_id")
        arrow = m.group("arrow")
        label = m.group("label").strip() if m.group("label") else None
        style = _extract_edge_style(arrow)

        _ensure_node(from_id, nodes, subgraph_stack)
        _ensure_node(to_id, nodes, subgraph_stack)
        edges.append(Edge(from_id=from_id, to_id=to_id, label=label, style=style))


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse_mermaid(source: str) -> DiagramGraph:
    """Parse mermaid flowchart source into a DiagramGraph."""
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    subgraphs: list[Subgraph] = []
    direction = Direction.TOP_DOWN
    subgraph_stack: list[Subgraph] = []

    for raw_line in source.strip().splitlines():
        line = raw_line.strip()

        if not line or line.startswith("%%"):
            continue
        line = re.sub(r"%%.*$", "", line).strip()
        if not line:
            continue

        m = _GRAPH_DECL.match(line)
        if m:
            direction = _DIRECTION_MAP.get(m.group(1).upper(), Direction.TOP_DOWN)
            continue

        m = _SUBGRAPH_START.match(line)
        if m:
            sg_id = m.group(1) or m.group(3) or _sanitize_id(m.group(4) or "subgraph")
            sg_label = m.group(2) or m.group(4) or m.group(3) or sg_id
            sg = Subgraph(id=sg_id, label=sg_label.strip())
            subgraph_stack.append(sg)
            continue

        if _SUBGRAPH_END.match(line):
            if subgraph_stack:
                subgraphs.append(subgraph_stack.pop())
            continue

        # Pass 1: extract node definitions, get cleaned line
        cleaned = _extract_nodes_from_line(line, nodes, subgraph_stack)

        # Pass 2: extract edges from cleaned line
        _extract_edges_from_line(cleaned, nodes, edges, subgraph_stack)

        # If no edges found and no nodes extracted, try as standalone node
        if not edges or edges[-1].from_id not in {n.id for n in nodes.values()}:
            pass  # Nodes already handled in pass 1

    while subgraph_stack:
        subgraphs.append(subgraph_stack.pop())

    return DiagramGraph(
        nodes=list(nodes.values()),
        edges=edges,
        subgraphs=subgraphs,
        direction=direction,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_node(
    node_id: str,
    nodes: dict[str, Node],
    subgraph_stack: list[Subgraph],
) -> None:
    """Ensure a node exists (created with default label if missing)."""
    if node_id not in nodes:
        nodes[node_id] = Node(id=node_id, label=node_id, shape=ShapeType.RECTANGLE)
        _add_to_subgraph(node_id, subgraph_stack)


def _add_to_subgraph(node_id: str, subgraph_stack: list[Subgraph]) -> None:
    if subgraph_stack:
        subgraph_stack[-1].node_ids.append(node_id)


def _sanitize_id(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text.strip()).strip("_")[:32]
