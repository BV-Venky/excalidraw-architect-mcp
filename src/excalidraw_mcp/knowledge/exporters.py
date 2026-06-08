"""Export the knowledge graph to other graph formats.

The knowledge graph is format-agnostic — Excalidraw is one rendering target.
These exporters (Mermaid, Graphviz DOT, JSON) future-proof the model and make
it embeddable in docs/CI that expect those formats.
"""

from __future__ import annotations

from excalidraw_mcp.core.models import Direction, EdgeStyle
from excalidraw_mcp.knowledge.models import KnowledgeGraph

_MERMAID_DIR = {
    Direction.TOP_DOWN: "TD",
    Direction.LEFT_RIGHT: "LR",
    Direction.BOTTOM_UP: "BT",
    Direction.RIGHT_LEFT: "RL",
}

_MERMAID_EDGE = {
    EdgeStyle.SOLID: "-->",
    EdgeStyle.THICK: "==>",
    EdgeStyle.DASHED: "-.->",
    EdgeStyle.DOTTED: "-.->",
}


def to_mermaid(kg: KnowledgeGraph) -> str:
    """Render the graph as Mermaid flowchart syntax."""
    lines = [f"flowchart {_MERMAID_DIR.get(kg.direction, 'LR')}"]

    grouped: set[str] = set()
    for domain_id in kg.domain_ids:
        members = kg.domain_members(domain_id)
        if not members:
            continue
        lines.append(f'  subgraph {domain_id}["{kg.domain_label(domain_id)}"]')
        for sid in members:
            svc = kg.service_by_id(sid)
            lines.append(f'    {_safe(sid)}["{_esc(svc.label)}"]')
            grouped.add(sid)
        lines.append("  end")

    for s in kg.services:
        if s.id not in grouped:
            lines.append(f'  {_safe(s.id)}["{_esc(s.label)}"]')

    for d in kg.dependencies:
        arrow = _MERMAID_EDGE.get(d.style, "-->")
        if d.label:
            lines.append(f'  {_safe(d.from_id)} {arrow}|"{_esc(d.label)}"| {_safe(d.to_id)}')
        else:
            lines.append(f"  {_safe(d.from_id)} {arrow} {_safe(d.to_id)}")

    return "\n".join(lines) + "\n"


def to_dot(kg: KnowledgeGraph) -> str:
    """Render the graph as Graphviz DOT."""
    rankdir = _MERMAID_DIR.get(kg.direction, "LR")
    if rankdir in ("TD", "BT"):
        rankdir = "TB" if rankdir == "TD" else "BT"
    lines = ["digraph architecture {", f"  rankdir={rankdir};", "  node [shape=box];"]

    grouped: set[str] = set()
    for i, domain_id in enumerate(kg.domain_ids):
        members = kg.domain_members(domain_id)
        if not members:
            continue
        lines.append(f"  subgraph cluster_{i} {{")
        lines.append(f'    label="{_esc(kg.domain_label(domain_id))}";')
        for sid in members:
            svc = kg.service_by_id(sid)
            lines.append(f'    "{sid}" [label="{_esc(svc.label)}"];')
            grouped.add(sid)
        lines.append("  }")

    for s in kg.services:
        if s.id not in grouped:
            lines.append(f'  "{s.id}" [label="{_esc(s.label)}"];')

    for d in kg.dependencies:
        attrs = []
        if d.label:
            attrs.append(f'label="{_esc(d.label)}"')
        if d.style in (EdgeStyle.DASHED, EdgeStyle.DOTTED):
            attrs.append(f"style={d.style.value}")
        elif d.style == EdgeStyle.THICK:
            attrs.append("penwidth=2")
        attr_str = f" [{', '.join(attrs)}]" if attrs else ""
        lines.append(f'  "{d.from_id}" -> "{d.to_id}"{attr_str};')

    lines.append("}")
    return "\n".join(lines) + "\n"


def to_json(kg: KnowledgeGraph) -> str:
    """Render the full knowledge graph as JSON (lossless, incl. metadata)."""
    return kg.model_dump_json(indent=2)


def _esc(text: str | None) -> str:
    return (text or "").replace('"', '\\"')


def _safe(node_id: str) -> str:
    """Mermaid node ids must be identifier-like; sanitize defensively."""
    return "".join(c if (c.isalnum() or c == "_") else "_" for c in node_id)
