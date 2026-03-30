"""Export .excalidraw files to SVG and PNG.

Renders all non-deleted elements (rectangles, ellipses, diamonds, text,
arrows) into a standalone SVG using only the Python standard library.
PNG export requires the optional ``cairosvg`` package.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

PADDING = 40  # px around the diagram content


# ---------------------------------------------------------------------------
# Bounding box
# ---------------------------------------------------------------------------


def _bounds(elements: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) across all visible elements."""
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    for el in elements:
        if el.get("isDeleted"):
            continue
        el_type = el.get("type", "")
        x, y = el.get("x", 0.0), el.get("y", 0.0)
        w, h = el.get("width", 0.0), el.get("height", 0.0)

        if el_type == "arrow":
            ox, oy = x, y
            for p in el.get("points", [[0, 0]]):
                px, py = ox + p[0], oy + p[1]
                min_x = min(min_x, px)
                min_y = min(min_y, py)
                max_x = max(max_x, px)
                max_y = max(max_y, py)
        else:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)

    if min_x == float("inf"):
        return 0.0, 0.0, 400.0, 300.0
    return min_x, min_y, max_x, max_y


# ---------------------------------------------------------------------------
# SVG attribute helpers
# ---------------------------------------------------------------------------


def _stroke_dasharray(stroke_style: str, stroke_width: float) -> str:
    sw = max(stroke_width, 1.0)
    if stroke_style == "dashed":
        return f'stroke-dasharray="{sw * 6},{sw * 3}"'
    if stroke_style == "dotted":
        return f'stroke-dasharray="{sw},{sw * 3}"'
    return ""


def _opacity(value: int | float) -> float:
    return max(0.0, min(1.0, float(value) / 100.0))


def _fill(bg: str) -> str:
    return "none" if bg in ("transparent", "", "none") else bg


def _esc(text: str) -> str:
    return html.escape(text)


# ---------------------------------------------------------------------------
# Arrow marker registry
# ---------------------------------------------------------------------------


def _marker_id(color: str) -> str:
    return "arr-" + color.lstrip("#")


def _arrowhead_marker(color: str) -> str:
    mid = _marker_id(color)
    return (
        f'<marker id="{mid}" markerWidth="10" markerHeight="7" '
        f'refX="9" refY="3.5" orient="auto">'
        f'<polygon points="0 0, 10 3.5, 0 7" fill="{_esc(color)}"/>'
        f"</marker>"
    )


# ---------------------------------------------------------------------------
# Element renderers
# ---------------------------------------------------------------------------


def _render_rect(
    el: dict[str, Any], ox: float, oy: float
) -> str:
    x = el["x"] - ox
    y = el["y"] - oy
    w = el.get("width", 80)
    h = el.get("height", 40)
    sc = el.get("strokeColor", "#1e1e1e")
    bg = _fill(el.get("backgroundColor", "transparent"))
    sw = el.get("strokeWidth", 2)
    ss = el.get("strokeStyle", "solid")
    op = _opacity(el.get("opacity", 100))
    roundness = el.get("roundness")
    rx = 8 if roundness else 0
    dash = _stroke_dasharray(ss, sw)
    dash_attr = f" {dash}" if dash else ""
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'rx="{rx}" fill="{_esc(bg)}" stroke="{_esc(sc)}" stroke-width="{sw}" '
        f'opacity="{op:.2f}"{dash_attr}/>'
    )


def _render_ellipse(
    el: dict[str, Any], ox: float, oy: float
) -> str:
    cx = el["x"] - ox + el.get("width", 80) / 2
    cy = el["y"] - oy + el.get("height", 40) / 2
    rx = el.get("width", 80) / 2
    ry = el.get("height", 40) / 2
    sc = el.get("strokeColor", "#1e1e1e")
    bg = _fill(el.get("backgroundColor", "transparent"))
    sw = el.get("strokeWidth", 2)
    ss = el.get("strokeStyle", "solid")
    op = _opacity(el.get("opacity", 100))
    dash = _stroke_dasharray(ss, sw)
    dash_attr = f" {dash}" if dash else ""
    return (
        f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" '
        f'fill="{_esc(bg)}" stroke="{_esc(sc)}" stroke-width="{sw}" '
        f'opacity="{op:.2f}"{dash_attr}/>'
    )


def _render_diamond(
    el: dict[str, Any], ox: float, oy: float
) -> str:
    x = el["x"] - ox
    y = el["y"] - oy
    w = el.get("width", 80)
    h = el.get("height", 40)
    cx, cy = x + w / 2, y + h / 2
    pts = f"{cx:.2f},{y:.2f} {x + w:.2f},{cy:.2f} {cx:.2f},{y + h:.2f} {x:.2f},{cy:.2f}"
    sc = el.get("strokeColor", "#1e1e1e")
    bg = _fill(el.get("backgroundColor", "transparent"))
    sw = el.get("strokeWidth", 2)
    ss = el.get("strokeStyle", "solid")
    op = _opacity(el.get("opacity", 100))
    dash = _stroke_dasharray(ss, sw)
    dash_attr = f" {dash}" if dash else ""
    return (
        f'<polygon points="{pts}" fill="{_esc(bg)}" stroke="{_esc(sc)}" '
        f'stroke-width="{sw}" opacity="{op:.2f}"{dash_attr}/>'
    )


def _render_text(
    el: dict[str, Any], ox: float, oy: float
) -> str:
    text = el.get("text", "")
    if not text:
        return ""
    x = el["x"] - ox
    y = el["y"] - oy
    font_size = el.get("fontSize", 16)
    font_family_id = el.get("fontFamily", 1)
    family_map = {1: "cursive", 2: "sans-serif", 3: "monospace"}
    font_family = family_map.get(font_family_id, "sans-serif")
    color = el.get("strokeColor", "#1e1e1e")
    op = _opacity(el.get("opacity", 100))
    align = el.get("textAlign", "left")
    line_height = el.get("lineHeight", 1.25)
    line_h_px = font_size * line_height
    w = el.get("width", 100)

    # Anchor based on text alignment
    anchor_map = {"left": "start", "center": "middle", "right": "end"}
    anchor = anchor_map.get(align, "start")
    if align == "center":
        tx = x + w / 2
    elif align == "right":
        tx = x + w
    else:
        tx = x

    lines = text.split("\n")
    parts: list[str] = []
    for i, line in enumerate(lines):
        dy = font_size + i * line_h_px if i == 0 else line_h_px
        parts.append(
            f'<tspan x="{tx:.2f}" dy="{dy:.2f}">{_esc(line) if line else "&#x200B;"}</tspan>'
        )

    tspans = "".join(parts)
    return (
        f'<text x="{tx:.2f}" y="{y:.2f}" font-size="{font_size}" '
        f'font-family="{font_family}" fill="{_esc(color)}" '
        f'text-anchor="{anchor}" opacity="{op:.2f}">'
        f"{tspans}</text>"
    )


def _render_arrow(
    el: dict[str, Any], ox: float, oy: float, used_colors: set[str]
) -> str:
    points_raw = el.get("points", [])
    if len(points_raw) < 2:
        return ""

    base_x = el.get("x", 0.0) - ox
    base_y = el.get("y", 0.0) - oy
    sc = el.get("strokeColor", "#1e1e1e")
    sw = el.get("strokeWidth", 2)
    ss = el.get("strokeStyle", "solid")
    op = _opacity(el.get("opacity", 100))
    end_head = el.get("endArrowhead")
    start_head = el.get("startArrowhead")

    # Absolute coordinates
    abs_pts = [(base_x + p[0], base_y + p[1]) for p in points_raw]

    # Build SVG path
    path_d = "M " + " L ".join(f"{px:.2f},{py:.2f}" for px, py in abs_pts)

    dash = _stroke_dasharray(ss, sw)
    dash_attr = f" {dash}" if dash else ""

    # Arrow markers
    marker_end = ""
    marker_start = ""
    if end_head == "arrow":
        used_colors.add(sc)
        marker_end = f' marker-end="url(#{_marker_id(sc)})"'
    if start_head == "arrow":
        used_colors.add(sc)
        marker_start = f' marker-start="url(#{_marker_id(sc)})"'

    return (
        f'<path d="{path_d}" fill="none" stroke="{_esc(sc)}" stroke-width="{sw}" '
        f'opacity="{op:.2f}"{dash_attr}{marker_end}{marker_start}/>'
    )


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------


def excalidraw_to_svg(data: dict[str, Any]) -> str:
    """Convert an in-memory .excalidraw document to an SVG string."""
    elements = [e for e in data.get("elements", []) if not e.get("isDeleted")]
    bg_color = data.get("appState", {}).get("viewBackgroundColor", "#ffffff")

    if not elements:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">'
            f'<rect width="400" height="300" fill="{_esc(bg_color)}"/>'
            "</svg>"
        )

    min_x, min_y, max_x, max_y = _bounds(elements)
    ox = min_x - PADDING
    oy = min_y - PADDING
    width = max_x - min_x + PADDING * 2
    height = max_y - min_y + PADDING * 2

    # Two-pass rendering: shapes first, then text on top
    arrow_types = {"arrow", "line"}

    shape_svgs: list[str] = []
    arrow_svgs: list[str] = []
    text_svgs: list[str] = []
    used_colors: set[str] = set()

    for el in elements:
        el_type = el.get("type", "")
        if el_type == "rectangle":
            shape_svgs.append(_render_rect(el, ox, oy))
        elif el_type == "ellipse":
            shape_svgs.append(_render_ellipse(el, ox, oy))
        elif el_type == "diamond":
            shape_svgs.append(_render_diamond(el, ox, oy))
        elif el_type in arrow_types:
            arrow_svgs.append(_render_arrow(el, ox, oy, used_colors))
        elif el_type == "text":
            text_svgs.append(_render_text(el, ox, oy))

    markers = "\n    ".join(_arrowhead_marker(c) for c in sorted(used_colors))
    defs = f"<defs>\n    {markers}\n  </defs>" if markers else ""

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.2f}" height="{height:.2f}" '
        f'viewBox="0 0 {width:.2f} {height:.2f}">',
        defs,
        f'<rect width="{width:.2f}" height="{height:.2f}" fill="{_esc(bg_color)}"/>',
    ]
    parts.extend(shape_svgs)
    parts.extend(arrow_svgs)
    parts.extend(text_svgs)
    parts.append("</svg>")

    return "\n".join(p for p in parts if p)


def export_to_svg(input_path: str | Path, output_path: str | Path) -> Path:
    """Read an .excalidraw file and write a .svg file."""
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    svg = excalidraw_to_svg(data)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    return out


def export_to_png(input_path: str | Path, output_path: str | Path, scale: float = 2.0) -> Path:
    """Read an .excalidraw file and write a .png file.

    Requires the ``cairosvg`` package (``pip install cairosvg``).
    """
    try:
        import cairosvg  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "PNG export requires cairosvg. Install it with: pip install cairosvg"
        ) from exc

    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    svg = excalidraw_to_svg(data)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out), scale=scale)
    return out
