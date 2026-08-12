"""Render a flat list of ``Drawable`` primitives into Excalidraw JSON.

This is the second renderer in the package and the one every typed diagram
goes through. The original ``renderer.build_excalidraw_file`` still owns the
graph pipeline (component styling, hub bindings, fixed points); this one is
deliberately dumber -- it draws exactly what the layout asked for.

Beyond the five element types the graph renderer emits, this adds ``line``
(open polylines and filled closed polygons) and rotated text, which is what
makes pyramids, lifelines, axes, and vertical axis titles possible.
"""

from __future__ import annotations

import math
from typing import Any

from excalidraw_mcp.core.drawable import Box, Connector, Drawable, Poly, Style, Text
from excalidraw_mcp.core.models import ThemeName
from excalidraw_mcp.core.themes import get_theme
from excalidraw_mcp.engine.renderer import (
    _LINE_HEIGHT,
    EXCALIDRAW_SOURCE,
    EXCALIDRAW_VERSION,
    FONT_FAMILY,
    _base_element,
    _measure_text,
    _uid,
)

_SHAPE_TYPES = {"rectangle", "ellipse", "diamond"}


# ---------------------------------------------------------------------------
# Group ids
# ---------------------------------------------------------------------------


class _Groups:
    """Maps layout-level group names onto stable Excalidraw group ids."""

    def __init__(self) -> None:
        self._ids: dict[str, str] = {}

    def get(self, name: str | None) -> list[str]:
        if not name:
            return []
        if name not in self._ids:
            self._ids[name] = _uid()
        return [self._ids[name]]


# ---------------------------------------------------------------------------
# Style application
# ---------------------------------------------------------------------------


def _apply_style(el: dict[str, Any], style: Style) -> None:
    el["strokeColor"] = style.stroke
    el["backgroundColor"] = style.fill
    el["fillStyle"] = style.fill_style
    el["strokeWidth"] = style.stroke_width
    el["strokeStyle"] = style.stroke_style
    el["roughness"] = style.roughness
    el["opacity"] = style.opacity


# ---------------------------------------------------------------------------
# Primitive builders
# ---------------------------------------------------------------------------


def _build_box(box: Box, groups: _Groups) -> list[dict[str, Any]]:
    shape = box.shape if box.shape in _SHAPE_TYPES else "rectangle"
    el = _base_element(
        shape,
        box.x,
        box.y,
        box.width,
        box.height,
        element_id=_uid(),
        custom_data={"node_id": box.node_id} if box.node_id else None,
    )
    _apply_style(el, box.style)
    el["roundness"] = {"type": 3} if box.style.rounded and shape == "rectangle" else None
    el["groupIds"] = groups.get(box.group)

    out = [el]
    if box.label:
        label_id = _uid()
        lw, lh = _measure_text(box.label, box.label_size, FONT_FAMILY)
        label = _base_element(
            "text",
            box.x + (box.width - lw) / 2,
            box.y + (box.height - lh) / 2,
            lw,
            lh,
            element_id=label_id,
        )
        label.update(
            {
                "text": box.label,
                "fontSize": box.label_size,
                "fontFamily": FONT_FAMILY,
                "textAlign": box.label_align,
                "verticalAlign": box.label_valign,
                "containerId": el["id"],
                "originalText": box.label,
                "autoResize": True,
                "lineHeight": _LINE_HEIGHT,
                "strokeColor": box.label_color or box.style.stroke,
                "opacity": box.style.opacity,
                "roughness": 0,
            }
        )
        label["groupIds"] = groups.get(box.group)
        el["boundElements"] = [{"id": label_id, "type": "text"}]
        out.append(label)
    return out


def _points_element(
    element_type: str,
    points: list[tuple[float, float]],
    style: Style,
    *,
    closed: bool = False,
    curved: bool = False,
) -> dict[str, Any]:
    """Build a line/arrow element from absolute points.

    Excalidraw stores points relative to the element origin, so the origin is
    the first point and every other point is an offset from it.
    """
    pts = list(points)
    if closed and pts and pts[0] != pts[-1]:
        pts.append(pts[0])

    ox, oy = pts[0]
    rel = [[round(px - ox, 2), round(py - oy, 2)] for px, py in pts]
    xs = [p[0] for p in rel]
    ys = [p[1] for p in rel]

    el = _base_element(
        element_type,
        ox,
        oy,
        max(max(xs) - min(xs), 1),
        max(max(ys) - min(ys), 1),
        element_id=_uid(),
    )
    _apply_style(el, style)
    el["points"] = rel
    el["lastCommittedPoint"] = None
    el["roundness"] = {"type": 2} if curved else None
    return el


def _build_poly(poly: Poly, groups: _Groups) -> list[dict[str, Any]]:
    if len(poly.points) < 2:
        return []
    el = _points_element(
        "line", poly.points, poly.style, closed=poly.closed, curved=poly.curved
    )
    el["groupIds"] = groups.get(poly.group)
    if poly.closed:
        # A closed line is what gives us triangles and trapezoids; Excalidraw
        # fills it exactly like a shape.
        el["polygon"] = True
    else:
        el["backgroundColor"] = "transparent"
    return [el]


def _polyline_midpoint(points: list[tuple[float, float]]) -> tuple[float, float]:
    """The point halfway along a polyline by arc length.

    Indexing the middle element instead is wrong for the common case: a
    two-point connector's "middle" index is its endpoint, which parks every
    label on top of the target shape.
    """
    lengths = [
        math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)
    ]
    total = sum(lengths)
    if total == 0:
        return points[0]

    target = total / 2
    for i, seg in enumerate(lengths):
        if target <= seg:
            t = target / seg if seg else 0.0
            (x1, y1), (x2, y2) = points[i], points[i + 1]
            return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        target -= seg
    return points[-1]


def _build_connector(
    conn: Connector, groups: _Groups, boxes_by_node: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    if len(conn.points) < 2:
        return []
    el = _points_element("arrow", conn.points, conn.style, curved=conn.curved)
    el["backgroundColor"] = "transparent"
    el["startArrowhead"] = conn.start_arrowhead
    el["endArrowhead"] = conn.end_arrowhead
    el["groupIds"] = groups.get(conn.group)

    src = boxes_by_node.get(conn.from_node or "")
    dst = boxes_by_node.get(conn.to_node or "")
    if src is not None:
        el["startBinding"] = {"elementId": src["id"], "focus": 0, "gap": 4}
        src.setdefault("boundElements", []).append({"id": el["id"], "type": "arrow"})
    if dst is not None:
        el["endBinding"] = {"elementId": dst["id"], "focus": 0, "gap": 4}
        dst.setdefault("boundElements", []).append({"id": el["id"], "type": "arrow"})

    out = [el]
    if conn.label:
        label_id = _uid()
        lw, lh = _measure_text(conn.label, conn.label_size, FONT_FAMILY)
        mid = _polyline_midpoint(conn.points)
        label = _base_element(
            "text",
            mid[0] - lw / 2,
            mid[1] - lh / 2,
            lw,
            lh,
            element_id=label_id,
        )
        label.update(
            {
                "text": conn.label,
                "fontSize": conn.label_size,
                "fontFamily": FONT_FAMILY,
                "textAlign": "center",
                "verticalAlign": "middle",
                "containerId": el["id"],
                "originalText": conn.label,
                "autoResize": True,
                "lineHeight": _LINE_HEIGHT,
                "strokeColor": conn.label_color or conn.style.stroke,
                "roughness": 0,
            }
        )
        label["groupIds"] = groups.get(conn.group)
        el["boundElements"] = [{"id": label_id, "type": "text"}]
        out.append(label)
    return out


def _build_text(text: Text, groups: _Groups) -> list[dict[str, Any]]:
    tw, th = _measure_text(text.text, text.size, FONT_FAMILY)
    width = text.width or tw

    if text.angle:
        # Rotation happens about the element centre, so for rotated text the
        # caller's (x, y) is treated as that centre -- placing a vertical axis
        # title by its midpoint is far easier than by its pre-rotation corner.
        x = text.x - width / 2
        y = text.y - th / 2
    else:
        x = text.x
        if text.align == "center":
            x -= width / 2
        elif text.align == "right":
            x -= width
        y = text.y

    el = _base_element("text", x, y, width, th, element_id=_uid())
    el.update(
        {
            "text": text.text,
            "fontSize": text.size,
            "fontFamily": FONT_FAMILY,
            "textAlign": text.align,
            "verticalAlign": "top",
            "containerId": None,
            "originalText": text.text,
            "autoResize": True,
            "lineHeight": _LINE_HEIGHT,
            "strokeColor": text.color,
            "opacity": text.opacity,
            "angle": round(text.angle, 4),
            "roughness": 0,
        }
    )
    el["groupIds"] = groups.get(text.group)
    return [el]


# ---------------------------------------------------------------------------
# File assembly
# ---------------------------------------------------------------------------


def drawables_to_elements(items: list[Drawable]) -> list[dict[str, Any]]:
    """Convert primitives into Excalidraw elements, preserving draw order."""
    groups = _Groups()
    boxes_by_node: dict[str, dict[str, Any]] = {}
    elements: list[dict[str, Any]] = []

    # Boxes first so connectors can bind to them regardless of list order.
    built: list[tuple[int, list[dict[str, Any]]]] = []
    for idx, item in enumerate(items):
        if isinstance(item, Box):
            els = _build_box(item, groups)
            if item.node_id:
                boxes_by_node[item.node_id] = els[0]
            built.append((idx, els))

    for idx, item in enumerate(items):
        if isinstance(item, Poly):
            built.append((idx, _build_poly(item, groups)))
        elif isinstance(item, Connector):
            built.append((idx, _build_connector(item, groups, boxes_by_node)))
        elif isinstance(item, Text):
            built.append((idx, _build_text(item, groups)))

    for _, els in sorted(built, key=lambda pair: pair[0]):
        elements.extend(els)
    return elements


def build_drawable_file(
    items: list[Drawable],
    theme_name: ThemeName | str = ThemeName.DEFAULT,
    *,
    diagram_type: str = "",
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a complete .excalidraw document from primitives.

    The validated spec is echoed into ``customData`` so ``modify_diagram`` can
    patch and re-render any typed diagram without reverse-engineering geometry
    back out of the elements.
    """
    theme = get_theme(theme_name)
    elements = drawables_to_elements(items)

    custom: dict[str, Any] = {
        "version": 2,
        "diagram_type": diagram_type,
        "theme": theme.name.value,
    }
    if spec is not None:
        custom["spec"] = spec

    return {
        "type": "excalidraw",
        "version": EXCALIDRAW_VERSION,
        "source": EXCALIDRAW_SOURCE,
        "elements": elements,
        "appState": {
            "gridSize": 20,
            "gridStep": 5,
            "gridModeEnabled": False,
            "viewBackgroundColor": theme.canvas_background,
            "customData": {"excalidraw_mcp": custom},
        },
        "files": {},
    }
