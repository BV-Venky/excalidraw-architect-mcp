"""Structural diagram types: hierarchy, containment, stacks, and entities.

tree · org_chart · state · nested · layers · medallion · er · high_level ·
it_state

Where a type is genuinely a layered graph (tree, org chart, state machine, IT
current-state) it delegates to the existing Sugiyama engine via
``build_graph_layout`` rather than reimplementing layout. The rest are
deterministic geometry.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from excalidraw_mcp.core.drawable import Box, Connector, Drawable, Style, Text
from excalidraw_mcp.core.models import DiagramGraph, Direction, Edge, Node
from excalidraw_mcp.core.palette import Palette
from excalidraw_mcp.diagrams.base import (
    BODY_SIZE,
    LABEL_SIZE,
    Item,
    TypedSpec,
    build_graph_layout,
    caption,
    connector_style,
    edge_points,
    eyebrow,
    fit_box_size,
    graph_to_drawables,
    hairline,
    layered_positions,
    node_box,
    require,
    shape_style,
    text_width,
    uniform_box_width,
    zone_style,
)

# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------


class TreeNode(BaseModel):
    id: str
    label: str
    parent: str | None = None
    focal: bool = False


class TreeSpec(TypedSpec):
    """Parent -> children hierarchy."""

    nodes: list[TreeNode] = Field(..., min_length=1)
    direction: str = "TD"  # TD | LR


def layout_tree(spec: TreeSpec, pal: Palette) -> list[Drawable]:
    ids = {n.id for n in spec.nodes}
    roots = [n for n in spec.nodes if not n.parent or n.parent not in ids]
    require(bool(roots), "tree needs at least one node without a parent (the root)")

    graph = DiagramGraph(
        nodes=[Node(id=n.id, label=n.label) for n in spec.nodes],
        edges=[
            Edge(from_id=n.parent, to_id=n.id) for n in spec.nodes if n.parent and n.parent in ids
        ],
        direction=Direction(spec.direction.upper())
        if spec.direction.upper() in {d.value for d in Direction}
        else Direction.TOP_DOWN,
    )
    layout = build_graph_layout(graph)
    return graph_to_drawables(layout, pal, focal_ids={n.id for n in spec.nodes if n.focal})


# ---------------------------------------------------------------------------
# Org chart
# ---------------------------------------------------------------------------


class Person(BaseModel):
    id: str
    name: str
    role: str | None = None
    reports_to: str | None = None
    focal: bool = False


class OrgChartSpec(TypedSpec):
    """Reporting / ownership hierarchy."""

    people: list[Person] = Field(..., min_length=1)


def layout_org_chart(spec: OrgChartSpec, pal: Palette) -> list[Drawable]:
    tree = TreeSpec(
        nodes=[
            TreeNode(
                id=p.id,
                label=f"{p.name}\n{p.role}" if p.role else p.name,
                parent=p.reports_to,
                focal=p.focal,
            )
            for p in spec.people
        ],
        direction="TD",
    )
    return layout_tree(tree, pal)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


class StateNode(BaseModel):
    id: str
    label: str
    kind: str = "normal"  # normal | start | end
    focal: bool = False


class Transition(BaseModel):
    from_id: str
    to_id: str
    label: str | None = None


class StateSpec(TypedSpec):
    """States, transitions, and guards."""

    states: list[StateNode] = Field(..., min_length=1)
    transitions: list[Transition] = Field(default_factory=list)
    direction: str = "TD"


def layout_state(spec: StateSpec, pal: Palette) -> list[Drawable]:
    ids = {s.id for s in spec.states}
    # Self-transitions are drawn by hand afterwards; the layered engine has no
    # sensible place to put an edge whose endpoints are the same node.
    flow = [t for t in spec.transitions if t.from_id != t.to_id]
    loops = [t for t in spec.transitions if t.from_id == t.to_id]

    graph = DiagramGraph(
        nodes=[
            Node(id=s.id, label=s.label, shape="ellipse" if s.kind != "normal" else "rectangle")
            for s in spec.states
        ],
        edges=[
            Edge(from_id=t.from_id, to_id=t.to_id, label=t.label)
            for t in flow
            if t.from_id in ids and t.to_id in ids
        ],
        direction=Direction(spec.direction.upper())
        if spec.direction.upper() in {d.value for d in Direction}
        else Direction.TOP_DOWN,
    )
    layout = build_graph_layout(graph)
    kinds = {s.id: s.kind for s in spec.states}
    out = graph_to_drawables(layout, pal, focal_ids={s.id for s in spec.states if s.focal})

    rects = {pn.node.id: pn for pn in layout.nodes}

    # Replace start/end node boxes with the conventional markers.
    marked: list[Drawable] = []
    for item in out:
        if isinstance(item, Box) and item.node_id and kinds.get(item.node_id) in ("start", "end"):
            pn = rects[item.node_id]
            cx, cy = pn.x + pn.width / 2, pn.y + pn.height / 2
            if kinds[item.node_id] == "start":
                r = 13.0
                marked.append(
                    Box(
                        x=cx - r,
                        y=cy - r,
                        width=r * 2,
                        height=r * 2,
                        shape="ellipse",
                        style=Style(stroke=pal.ink, fill=pal.ink, roughness=1, stroke_width=2),
                        node_id=item.node_id,
                    )
                )
            else:
                r = 17.0
                marked.append(
                    Box(
                        x=cx - r,
                        y=cy - r,
                        width=r * 2,
                        height=r * 2,
                        shape="ellipse",
                        style=Style(stroke=pal.ink, fill="transparent", roughness=1),
                        node_id=item.node_id,
                    )
                )
                marked.append(
                    Box(
                        x=cx - r + 6,
                        y=cy - r + 6,
                        width=(r - 6) * 2,
                        height=(r - 6) * 2,
                        shape="ellipse",
                        style=Style(stroke=pal.ink, fill=pal.ink, roughness=1),
                    )
                )
            marked.append(
                caption(cx, cy + r + 8, item.label or "", pal, size=BODY_SIZE, align="center")
            )
        else:
            marked.append(item)

    # Self-transitions: a small arc off the right edge.
    for t in loops:
        pn = rects.get(t.from_id)
        if pn is None:
            continue
        x = pn.x + pn.width
        y = pn.y + pn.height / 2
        marked.append(
            Connector(
                points=[(x, y - 12), (x + 46, y - 30), (x + 46, y + 30), (x, y + 12)],
                label=t.label,
                style=connector_style(pal),
                curved=True,
            )
        )
    return marked


# ---------------------------------------------------------------------------
# Nested (containment)
# ---------------------------------------------------------------------------


class NestedNode(BaseModel):
    label: str
    children: list[NestedNode] = Field(default_factory=list)
    focal: bool = False


NestedNode.model_rebuild()


class NestedSpec(TypedSpec):
    """Hierarchy expressed by containment rather than edges."""

    root: NestedNode


_NEST_PAD = 22.0
_NEST_HEADER = 34.0
_NEST_GAP = 16.0
_NEST_MAX_COLS = 3


def _measure_nested(node: NestedNode) -> tuple[float, float]:
    if not node.children:
        return fit_box_size(node.label, min_w=140, min_h=54)

    sizes = [_measure_nested(c) for c in node.children]
    cols = min(_NEST_MAX_COLS, max(1, int(math.ceil(math.sqrt(len(sizes))))))
    rows = int(math.ceil(len(sizes) / cols))

    col_w = [0.0] * cols
    row_h = [0.0] * rows
    for i, (w, h) in enumerate(sizes):
        col_w[i % cols] = max(col_w[i % cols], w)
        row_h[i // cols] = max(row_h[i // cols], h)

    inner_w = sum(col_w) + _NEST_GAP * (cols - 1)
    inner_h = sum(row_h) + _NEST_GAP * (rows - 1)
    header_w = text_width(node.label, LABEL_SIZE) + _NEST_PAD * 2
    return (
        max(inner_w + _NEST_PAD * 2, header_w),
        inner_h + _NEST_PAD * 2 + _NEST_HEADER,
    )


def _place_nested(node: NestedNode, x: float, y: float, pal: Palette, depth: int) -> list[Drawable]:
    w, h = _measure_nested(node)
    out: list[Drawable] = []

    if not node.children:
        out.append(node_box(x, y, w, h, node.label, pal, focal=node.focal))
        return out

    out.append(
        Box(
            x=x,
            y=y,
            width=w,
            height=h,
            style=Style(
                stroke=pal.accent if node.focal else pal.rule,
                fill=pal.surface_alt if depth % 2 == 0 else pal.canvas,
                stroke_width=1.5 if node.focal else 1,
                roughness=1,
                opacity=100 if node.focal else 80,
            ),
        )
    )
    out.append(
        Text(
            x=x + _NEST_PAD,
            y=y + 11,
            text=node.label,
            size=LABEL_SIZE,
            color=pal.accent if node.focal else pal.ink,
        )
    )

    sizes = [_measure_nested(c) for c in node.children]
    cols = min(_NEST_MAX_COLS, max(1, int(math.ceil(math.sqrt(len(sizes))))))
    rows = int(math.ceil(len(sizes) / cols))
    col_w = [0.0] * cols
    row_h = [0.0] * rows
    for i, (cw, ch) in enumerate(sizes):
        col_w[i % cols] = max(col_w[i % cols], cw)
        row_h[i // cols] = max(row_h[i // cols], ch)

    oy = y + _NEST_HEADER + _NEST_PAD
    for r in range(rows):
        ox = x + _NEST_PAD
        for c in range(cols):
            idx = r * cols + c
            if idx >= len(node.children):
                break
            out.extend(_place_nested(node.children[idx], ox, oy, pal, depth + 1))
            ox += col_w[c] + _NEST_GAP
        oy += row_h[r] + _NEST_GAP
    return out


def layout_nested(spec: NestedSpec, pal: Palette) -> list[Drawable]:
    return _place_nested(spec.root, 0.0, 0.0, pal, 0)


# ---------------------------------------------------------------------------
# Layer stack
# ---------------------------------------------------------------------------


class LayersSpec(TypedSpec):
    """Stacked abstraction levels, topmost first."""

    layers: list[Item] = Field(..., min_length=1)
    width: float = 520.0
    show_dividers: bool = True


def layout_layers(spec: LayersSpec, pal: Palette) -> list[Drawable]:
    out: list[Drawable] = []
    y = 0.0
    row_h = 78.0
    for layer in spec.layers:
        out.append(
            Box(
                x=0,
                y=y,
                width=spec.width,
                height=row_h,
                label=layer.label,
                label_size=LABEL_SIZE,
                label_color=pal.accent if layer.focal else pal.ink,
                style=shape_style(pal, focal=layer.focal),
            )
        )
        if layer.note:
            out.append(caption(spec.width + 20, y + row_h / 2 - BODY_SIZE / 2, layer.note, pal))
        y += row_h + (8 if spec.show_dividers else 0)
    return out


# ---------------------------------------------------------------------------
# Medallion (multi-tier data storage)
# ---------------------------------------------------------------------------


class Tier(BaseModel):
    label: str
    description: str | None = None
    datasets: list[str] = Field(default_factory=list)
    focal: bool = False


class MedallionSpec(TypedSpec):
    """Bronze / silver / gold style storage tiers with a flow between them."""

    tiers: list[Tier] = Field(..., min_length=2)


def layout_medallion(spec: MedallionSpec, pal: Palette) -> list[Drawable]:
    out: list[Drawable] = []
    tier_w = uniform_box_width(
        [t.label for t in spec.tiers]
        + [t.description for t in spec.tiers]
        + [d for t in spec.tiers for d in t.datasets],
        min_w=250.0,
        size=BODY_SIZE,
        padding=40.0,
    )
    gap = 84.0
    header_h = 62.0
    row_h = 30.0

    heights = [header_h + 14 + row_h * len(t.datasets) + 14 for t in spec.tiers]
    max_h = max(heights)

    for i, tier in enumerate(spec.tiers):
        x = i * (tier_w + gap)
        h = heights[i]
        y = (max_h - h) / 2
        fill = pal.accent_soft if tier.focal else pal.tier_color(i, len(spec.tiers))
        out.append(
            Box(
                x=x,
                y=y,
                width=tier_w,
                height=h,
                style=Style(
                    stroke=pal.accent if tier.focal else pal.muted,
                    fill=fill,
                    stroke_width=2 if tier.focal else 1.5,
                    roughness=1,
                ),
            )
        )
        out.append(
            Text(
                x=x + tier_w / 2,
                y=y + 16,
                text=tier.label,
                size=LABEL_SIZE,
                color=pal.accent if tier.focal else pal.ink,
                align="center",
            )
        )
        if tier.description:
            out.append(
                caption(x + tier_w / 2, y + 38, tier.description, pal, align="center", size=12)
            )
        out.append(hairline((x + 16, y + header_h), (x + tier_w - 16, y + header_h), pal))

        dy = y + header_h + 12
        for ds in tier.datasets:
            out.append(caption(x + 20, dy, ds, pal, size=BODY_SIZE, muted=False))
            dy += row_h

        if i < len(spec.tiers) - 1:
            out.append(
                Connector(
                    points=[(x + tier_w, max_h / 2), (x + tier_w + gap, max_h / 2)],
                    style=connector_style(pal),
                    curved=False,
                )
            )
    return out


# ---------------------------------------------------------------------------
# ER / data model
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    name: str
    fields: list[str] = Field(default_factory=list)
    focal: bool = False


class Relationship(BaseModel):
    from_entity: str
    to_entity: str
    label: str | None = None
    cardinality: str | None = None  # free text, e.g. "1..*"


class ErSpec(TypedSpec):
    """Entities, their fields, and the relationships between them."""

    entities: list[Entity] = Field(..., min_length=1)
    relationships: list[Relationship] = Field(default_factory=list)


_ER_HEADER = 40.0
_ER_ROW = 26.0
_ER_PAD = 16.0


def layout_er(spec: ErSpec, pal: Palette) -> list[Drawable]:
    sizes: dict[str, tuple[float, float]] = {}
    for e in spec.entities:
        widest = max(
            [text_width(e.name, LABEL_SIZE)] + [text_width(f, BODY_SIZE) for f in e.fields]
        )
        sizes[e.name] = (
            max(200.0, widest + _ER_PAD * 2),
            _ER_HEADER + _ER_ROW * len(e.fields) + _ER_PAD,
        )

    edges = [
        (r.from_entity, r.to_entity)
        for r in spec.relationships
        if r.from_entity in sizes and r.to_entity in sizes
    ]
    pos = layered_positions(sizes, edges, horizontal=True, gap_main=140, gap_cross=56)

    out: list[Drawable] = []
    rects: dict[str, tuple[float, float, float, float]] = {}
    for e in spec.entities:
        x, y = pos[e.name]
        w, h = sizes[e.name]
        rects[e.name] = (x, y, w, h)
        out.append(
            Box(
                x=x,
                y=y,
                width=w,
                height=h,
                style=shape_style(pal, focal=e.focal, fill=pal.canvas),
            )
        )
        out.append(
            Box(
                x=x,
                y=y,
                width=w,
                height=_ER_HEADER,
                label=e.name,
                label_size=LABEL_SIZE,
                label_color=pal.accent if e.focal else pal.ink,
                style=Style(
                    stroke="transparent",
                    fill=pal.accent_soft if e.focal else pal.surface_alt,
                    roughness=0,
                    stroke_width=0,
                ),
            )
        )
        out.append(hairline((x, y + _ER_HEADER), (x + w, y + _ER_HEADER), pal))
        fy = y + _ER_HEADER + 8
        for f in e.fields:
            out.append(caption(x + _ER_PAD, fy, f, pal, size=BODY_SIZE, muted=False))
            fy += _ER_ROW

    for r in spec.relationships:
        if r.from_entity not in rects or r.to_entity not in rects:
            continue
        label = " ".join(p for p in (r.cardinality, r.label) if p) or None
        out.append(
            Connector(
                points=edge_points(rects[r.from_entity], rects[r.to_entity], horizontal=True),
                label=label,
                style=connector_style(pal),
                end_arrowhead=None,
                curved=False,
            )
        )
    return out


# ---------------------------------------------------------------------------
# High-level (cluster wrapping a stack)
# ---------------------------------------------------------------------------


class LayerRow(BaseModel):
    label: str
    items: list[str] = Field(default_factory=list)
    focal: bool = False


class HighLevelSpec(TypedSpec):
    """End-to-end stack drawn inside a named cluster boundary."""

    cluster_label: str = "Platform"
    rows: list[LayerRow] = Field(..., min_length=1)


def layout_high_level(spec: HighLevelSpec, pal: Palette) -> list[Drawable]:
    pad = 28.0
    header = 44.0
    row_gap = 18.0
    item_w = uniform_box_width([name for row in spec.rows for name in row.items], min_w=168.0)
    item_h = 58.0
    item_gap = 14.0
    label_col = 132.0

    max_items = max(len(r.items) for r in spec.rows)
    inner_w = label_col + max_items * item_w + (max_items - 1) * item_gap
    inner_h = len(spec.rows) * item_h + (len(spec.rows) - 1) * row_gap

    out: list[Drawable] = [
        Box(
            x=0,
            y=0,
            width=inner_w + pad * 2,
            height=inner_h + pad * 2 + header,
            style=Style(
                stroke=pal.muted,
                fill=pal.surface_alt,
                stroke_width=1.5,
                stroke_style="dashed",
                roughness=1,
                opacity=70,
            ),
        ),
        Text(x=pad, y=15, text=spec.cluster_label, size=LABEL_SIZE, color=pal.ink),
    ]

    y = pad + header
    for row in spec.rows:
        out.append(eyebrow(pad, y + item_h / 2 - 6, row.label, pal))
        x = pad + label_col
        for name in row.items:
            out.append(node_box(x, y, item_w, item_h, name, pal, focal=row.focal))
            x += item_w + item_gap
        y += item_h + row_gap
    return out


# ---------------------------------------------------------------------------
# IT current-state
# ---------------------------------------------------------------------------


class ItGroup(BaseModel):
    label: str
    items: list[Item] = Field(default_factory=list)


class ItStateSpec(TypedSpec):
    """Legacy landscape grouped by phase or department."""

    groups: list[ItGroup] = Field(..., min_length=1)
    connections: list[Transition] = Field(default_factory=list)
    columns: int = 3


def layout_it_state(spec: ItStateSpec, pal: Palette) -> list[Drawable]:
    pad = 20.0
    header = 38.0
    item_h = 52.0
    item_gap = 10.0
    zone_w = 260.0
    zone_gap = 34.0

    cols = max(1, spec.columns)
    heights = [header + pad + len(g.items) * (item_h + item_gap) for g in spec.groups]
    row_heights: list[float] = []
    for i in range(0, len(spec.groups), cols):
        row_heights.append(max(heights[i : i + cols]))

    out: list[Drawable] = []
    rects: dict[str, tuple[float, float, float, float]] = {}
    y = 0.0
    for row_idx, start in enumerate(range(0, len(spec.groups), cols)):
        x = 0.0
        for g in spec.groups[start : start + cols]:
            zh = row_heights[row_idx]
            out.append(Box(x=x, y=y, width=zone_w, height=zh, style=zone_style(pal)))
            out.append(eyebrow(x + pad, y + 14, g.label, pal))
            iy = y + header
            for item in g.items:
                out.append(
                    node_box(
                        x + pad,
                        iy,
                        zone_w - pad * 2,
                        item_h,
                        item.label,
                        pal,
                        focal=item.focal,
                        node_id=item.key,
                        size=BODY_SIZE,
                    )
                )
                rects[item.key] = (x + pad, iy, zone_w - pad * 2, item_h)
                iy += item_h + item_gap
            x += zone_w + zone_gap
        y += row_heights[row_idx] + zone_gap

    for conn in spec.connections:
        if conn.from_id not in rects or conn.to_id not in rects:
            continue
        a, b = rects[conn.from_id], rects[conn.to_id]
        out.append(
            Connector(
                points=[(a[0] + a[2], a[1] + a[3] / 2), (b[0], b[1] + b[3] / 2)],
                label=conn.label,
                style=connector_style(pal, dashed=True),
                from_node=conn.from_id,
                to_node=conn.to_id,
            )
        )
    return out
