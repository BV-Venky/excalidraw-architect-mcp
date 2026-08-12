"""Shared building blocks for typed diagram layouts.

Three things live here:

* **Styled primitive helpers** -- so every type draws a "muted box" or a
  "hairline" the same way, and the accent rule is enforced in one place.
* **``layered_positions``** -- longest-path layering with barycenter ordering.
  A compact stand-in for the full Sugiyama engine, used where boxes have
  wildly varying sizes (ER entities) or must honour fixed tracks (swimlanes).
* **``graph_to_drawables``** -- the adapter that lets any type reuse the
  existing, well-tested graph layout engine and still emit primitives.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field

from excalidraw_mcp.core.drawable import Box, Connector, Drawable, Poly, Style, Text
from excalidraw_mcp.core.models import DiagramGraph, LayoutResult
from excalidraw_mcp.core.palette import Palette
from excalidraw_mcp.engine.renderer import _measure_text

# ---------------------------------------------------------------------------
# Geometry defaults
# ---------------------------------------------------------------------------

NODE_W = 190.0
NODE_H = 66.0
GAP_MAIN = 90.0
GAP_CROSS = 40.0
TITLE_SIZE = 24
SUBTITLE_SIZE = 14
EYEBROW_SIZE = 11
BODY_SIZE = 14
LABEL_SIZE = 16


class TypedSpec(BaseModel):
    """Fields every typed diagram spec shares."""

    title: str | None = None
    subtitle: str | None = None


class Item(BaseModel):
    """A generic labelled thing. Reused wherever a type just needs a list."""

    id: str | None = None
    label: str
    note: str | None = None
    focal: bool = False

    @property
    def key(self) -> str:
        return self.id or self.label


# ---------------------------------------------------------------------------
# Styled primitives
# ---------------------------------------------------------------------------


def shape_style(pal: Palette, *, focal: bool = False, fill: str | None = None) -> Style:
    """Standard content-shape style. Accent is applied only when focal."""
    return Style(
        stroke=pal.accent if focal else pal.muted,
        fill=fill if fill is not None else (pal.accent_soft if focal else pal.surface),
        stroke_width=2 if focal else 1.5,
        roughness=1,
    )


def chrome_style(pal: Palette, *, dashed: bool = False, width: float = 1.0) -> Style:
    """Hairline style for axes, gridlines, dividers, lifelines.

    Chrome renders at ``roughness=0``. At roughness 1 a 1px rule turns into
    visual noise and fights the content for attention.
    """
    return Style(
        stroke=pal.rule,
        fill="transparent",
        stroke_width=width,
        stroke_style="dashed" if dashed else "solid",
        roughness=0,
        rounded=False,
    )


def zone_style(pal: Palette) -> Style:
    """Background band/zone style: present but recessive."""
    return Style(
        stroke=pal.rule,
        fill=pal.surface_alt,
        stroke_width=1,
        roughness=0,
        opacity=60,
    )


def connector_style(pal: Palette, *, focal: bool = False, dashed: bool = False) -> Style:
    return Style(
        stroke=pal.accent if focal else pal.muted,
        fill="transparent",
        stroke_width=2 if focal else 1.5,
        stroke_style="dashed" if dashed else "solid",
        roughness=1,
    )


def node_box(
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    pal: Palette,
    *,
    focal: bool = False,
    fill: str | None = None,
    node_id: str | None = None,
    group: str | None = None,
    size: int = LABEL_SIZE,
    shape: str = "rectangle",
) -> Box:
    return Box(
        x=x,
        y=y,
        width=w,
        height=h,
        shape=shape,
        label=label,
        label_size=size,
        label_color=pal.accent if focal else pal.ink,
        style=shape_style(pal, focal=focal, fill=fill),
        node_id=node_id,
        group=group,
    )


def hairline(
    p1: tuple[float, float],
    p2: tuple[float, float],
    pal: Palette,
    *,
    dashed: bool = False,
    width: float = 1.0,
) -> Poly:
    return Poly(points=[p1, p2], style=chrome_style(pal, dashed=dashed, width=width))


def caption(
    x: float,
    y: float,
    text: str,
    pal: Palette,
    *,
    size: int = BODY_SIZE,
    align: str = "left",
    muted: bool = True,
    focal: bool = False,
    angle: float = 0.0,
    group: str | None = None,
) -> Text:
    color = pal.accent if focal else (pal.muted if muted else pal.ink)
    return Text(x=x, y=y, text=text, size=size, color=color, align=align, angle=angle, group=group)


def eyebrow(x: float, y: float, text: str, pal: Palette, *, align: str = "left") -> Text:
    """Small uppercase label used for lane names, phases, and section tags."""
    return Text(
        x=x, y=y, text=text.upper(), size=EYEBROW_SIZE, color=pal.muted, align=align
    )


def text_width(text: str, size: int = BODY_SIZE) -> float:
    return _measure_text(text, size)[0]


def fit_box_size(
    label: str, *, min_w: float = NODE_W, min_h: float = NODE_H, size: int = LABEL_SIZE
) -> tuple[float, float]:
    """Size a box to its label with padding, never below the minimum."""
    w, h = _measure_text(label, size)
    return max(min_w, w + 44), max(min_h, h + 28)


# ---------------------------------------------------------------------------
# Layered layout
# ---------------------------------------------------------------------------


def assign_layers(
    keys: list[str], edges: list[tuple[str, str]], fixed: dict[str, int] | None = None
) -> dict[str, int]:
    """Longest-path layering. Cycles are broken by ignoring back edges."""
    if fixed:
        return {k: fixed.get(k, 0) for k in keys}

    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    key_set = set(keys)
    for a, b in edges:
        if a in key_set and b in key_set and a != b:
            outgoing[a].append(b)
            incoming[b].append(a)

    layer = {k: 0 for k in keys}
    # Relax repeatedly; the bound also terminates on cyclic input.
    for _ in range(len(keys)):
        changed = False
        for a, b in edges:
            if a in key_set and b in key_set and a != b and layer[b] < layer[a] + 1:
                layer[b] = layer[a] + 1
                changed = True
        if not changed:
            break
    return layer


def layered_positions(
    sizes: dict[str, tuple[float, float]],
    edges: list[tuple[str, str]],
    *,
    horizontal: bool = True,
    gap_main: float = GAP_MAIN,
    gap_cross: float = GAP_CROSS,
    fixed_layer: dict[str, int] | None = None,
    track_of: dict[str, float] | None = None,
    order: list[str] | None = None,
) -> dict[str, tuple[float, float]]:
    """Position boxes in layers, returning top-left coordinates.

    ``horizontal`` runs layers left-to-right (cross axis is vertical).
    ``track_of`` pins the cross-axis centre of a key -- that is how swimlanes
    keep every step inside its owner's band while still layering by flow.
    """
    keys = order or list(sizes.keys())
    layer = assign_layers(keys, edges, fixed_layer)

    by_layer: dict[int, list[str]] = defaultdict(list)
    for k in keys:
        by_layer[layer[k]].append(k)

    # Barycenter ordering: pull each node toward the average position of its
    # predecessors so edges cross less. Two sweeps is plenty at these sizes.
    preds: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        if a in sizes and b in sizes:
            preds[b].append(a)

    position_in_layer = {k: float(i) for lst in by_layer.values() for i, k in enumerate(lst)}
    for _ in range(2):
        for idx in sorted(by_layer):
            lst = by_layer[idx]
            if idx == 0 or track_of:
                continue
            lst.sort(
                key=lambda k: (
                    sum(position_in_layer[p] for p in preds[k]) / len(preds[k])
                    if preds[k]
                    else position_in_layer[k]
                )
            )
            for i, k in enumerate(lst):
                position_in_layer[k] = float(i)

    # Main-axis offsets: each layer is as wide as its widest member.
    main_offset: dict[int, float] = {}
    cursor = 0.0
    for idx in sorted(by_layer):
        main_offset[idx] = cursor
        extent = max(
            (sizes[k][0] if horizontal else sizes[k][1]) for k in by_layer[idx]
        )
        cursor += extent + gap_main

    positions: dict[str, tuple[float, float]] = {}
    for idx in sorted(by_layer):
        lst = by_layer[idx]
        if track_of is not None:
            for k in lst:
                cross_center = track_of.get(k, 0.0)
                cw, ch = sizes[k]
                if horizontal:
                    positions[k] = (main_offset[idx], cross_center - ch / 2)
                else:
                    positions[k] = (cross_center - cw / 2, main_offset[idx])
            continue

        total = sum((sizes[k][1] if horizontal else sizes[k][0]) for k in lst)
        total += gap_cross * (len(lst) - 1)
        cross = -total / 2
        for k in lst:
            cw, ch = sizes[k]
            if horizontal:
                positions[k] = (main_offset[idx], cross)
                cross += ch + gap_cross
            else:
                positions[k] = (cross, main_offset[idx])
                cross += cw + gap_cross

    return positions


def edge_points(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    *,
    horizontal: bool = True,
) -> list[tuple[float, float]]:
    """Straight connector between two boxes given as (x, y, w, h)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if horizontal:
        return [(ax + aw, ay + ah / 2), (bx, by + bh / 2)]
    return [(ax + aw / 2, ay + ah), (bx + bw / 2, by)]


# ---------------------------------------------------------------------------
# Graph engine adapter
# ---------------------------------------------------------------------------


def graph_to_drawables(
    layout: LayoutResult,
    pal: Palette,
    *,
    focal_ids: set[str] | None = None,
    fills: dict[str, str] | None = None,
    shapes: dict[str, str] | None = None,
) -> list[Drawable]:
    """Convert a ``LayoutResult`` from the Sugiyama engine into primitives.

    This is what lets tree, org chart, state machine, and IT current-state
    reuse the existing layout engine -- including its edge routing and overlap
    resolution -- while rendering through the typed pipeline.
    """
    focal_ids = focal_ids or set()
    fills = fills or {}
    shapes = shapes or {}
    out: list[Drawable] = []

    for pn in layout.nodes:
        nid = pn.node.id
        out.append(
            node_box(
                pn.x,
                pn.y,
                pn.width,
                pn.height,
                pn.node.label,
                pal,
                focal=nid in focal_ids,
                fill=fills.get(nid),
                node_id=nid,
                shape=shapes.get(nid, "rectangle"),
            )
        )

    for pe in layout.edges:
        pts = [(float(x), float(y)) for x, y in pe.points] or []
        if len(pts) < 2:
            continue
        focal = pe.edge.from_id in focal_ids and pe.edge.to_id in focal_ids
        out.append(
            Connector(
                points=pts,
                label=pe.edge.label,
                style=connector_style(
                    pal, focal=focal, dashed=pe.edge.style.value in ("dashed", "dotted")
                ),
                from_node=pe.edge.from_id,
                to_node=pe.edge.to_id,
            )
        )
    return out


def build_graph_layout(graph: DiagramGraph) -> LayoutResult:
    """Run the existing graph layout engine (imported lazily to avoid cycles)."""
    from excalidraw_mcp.engine.layout import compute_layout

    return compute_layout(graph)


# ---------------------------------------------------------------------------
# Titles
# ---------------------------------------------------------------------------


def title_block(
    title: str | None, subtitle: str | None, pal: Palette, left: float, baseline: float
) -> tuple[list[Drawable], float]:
    """Build the title/subtitle stack. Returns (drawables, height consumed)."""
    items: list[Drawable] = []
    y = baseline
    if title:
        items.append(Text(x=left, y=y, text=title, size=TITLE_SIZE, color=pal.ink))
        y += TITLE_SIZE * 1.6
    if subtitle:
        items.append(Text(x=left, y=y, text=subtitle, size=SUBTITLE_SIZE, color=pal.muted))
        y += SUBTITLE_SIZE * 1.8
    return items, (y - baseline)


class SpecError(ValueError):
    """Raised when a spec is structurally valid but semantically unusable."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SpecError(message)


def focal_keys(items: list[Item]) -> set[str]:
    return {i.key for i in items if i.focal}


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


__all__ = [
    "BODY_SIZE",
    "EYEBROW_SIZE",
    "GAP_CROSS",
    "GAP_MAIN",
    "LABEL_SIZE",
    "NODE_H",
    "NODE_W",
    "SUBTITLE_SIZE",
    "TITLE_SIZE",
    "Item",
    "SpecError",
    "TypedSpec",
    "assign_layers",
    "build_graph_layout",
    "caption",
    "chrome_style",
    "connector_style",
    "dedupe",
    "edge_points",
    "eyebrow",
    "fit_box_size",
    "focal_keys",
    "graph_to_drawables",
    "hairline",
    "layered_positions",
    "node_box",
    "require",
    "shape_style",
    "text_width",
    "title_block",
    "zone_style",
    "Field",
]
