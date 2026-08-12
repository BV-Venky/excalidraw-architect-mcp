"""Export .excalidraw files to SVG and PNG.

Renders all non-deleted elements (rectangles, ellipses, diamonds, text,
arrows, and lines -- both open polylines and filled closed polygons) into a
standalone SVG using only the Python standard library. Rotated text is
supported so vertical axis titles survive the round trip.
PNG export requires the optional ``cairosvg`` package.
"""

from __future__ import annotations

import base64
import html
import json
import math
from pathlib import Path
from typing import Any

from excalidraw_mcp.export import sketch

PADDING = 40  # px around the diagram content

# Excalidraw's fontFamily 1 is Excalifont (Virgil before that) -- a bundled
# webfont, so a standalone SVG has nothing to resolve it to. Mapping it to the
# generic CSS `cursive` is worse than useless: on macOS that resolves to Apple
# Chancery, a formal calligraphic face that reads nothing like handwriting.
#
# So: name the real fonts first (exact if the viewer has Excalidraw's font
# installed), then fall back through genuine handwriting faces that ship with
# macOS and Windows, and only reach `cursive` as a last resort. Pass
# ``embed_font`` to ``export_to_svg`` to inline a font file and make the output
# fully self-contained and identical everywhere.
_FONT_STACKS: dict[int, str] = {
    1: (
        "Excalifont, Virgil, 'Segoe Print', 'Bradley Hand', "
        "'Chalkboard SE', Chalkboard, 'Comic Sans MS', cursive"
    ),
    2: "Helvetica, Arial, sans-serif",
    3: "'Cascadia Code', Consolas, 'Courier New', monospace",
}


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

        if el_type in ("arrow", "line"):
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
# Element renderers
# ---------------------------------------------------------------------------


def _rough_for(el: dict[str, Any]) -> tuple[sketch.Rough, sketch.Rng]:
    """Build roughjs options for an element, mirroring Excalidraw's own mapping.

    The important detail is ``disable_multi_stroke`` for non-solid strokes:
    Excalidraw draws dashed and dotted outlines as a single pass, because two
    jittered dashed passes read as a smudge.
    """
    stroke_style = el.get("strokeStyle", "solid")
    return (
        sketch.Rough(
            roughness=float(el.get("roughness", 1)),
            disable_multi_stroke=stroke_style != "solid",
        ),
        sketch.Rng(el.get("seed", 1) or 1),
    )


def _stroke_attrs(el: dict[str, Any]) -> str:
    sc = el.get("strokeColor", "#1e1e1e")
    sw = el.get("strokeWidth", 2)
    ss = el.get("strokeStyle", "solid")
    # Excalidraw thickens non-solid strokes slightly to keep dashes legible.
    if ss != "solid":
        sw = sw + 0.5
    dash = _stroke_dasharray(ss, sw)
    return (
        f'stroke="{_esc(sc)}" stroke-width="{sw}" fill="none" '
        f'stroke-linecap="round" stroke-linejoin="round"'
        + (f" {dash}" if dash else "")
    )


def _sketch_shape(
    el: dict[str, Any],
    outline: list[tuple[float, float]],
    *,
    closed: bool = True,
    smooth: bool = False,
) -> str:
    """Render one shape as an optional solid fill plus a jittered outline.

    Fill is generated before the stroke, matching roughjs's call order so the
    two consume the random stream in the same sequence.
    """
    o, rng = _rough_for(el)
    op = _opacity(el.get("opacity", 100))
    bg = _fill(el.get("backgroundColor", "transparent"))

    parts: list[str] = []
    if bg != "none" and closed:
        fill_d = sketch.solid_fill(outline, o, rng)
        if fill_d:
            parts.append(
                f'<path d="{fill_d}" fill="{_esc(bg)}" stroke="none" opacity="{op:.2f}"/>'
            )

    if smooth:
        stroke_d = sketch.curved_path(outline, o, rng, closed=closed)
    else:
        stroke_d = sketch.linear_path(outline, closed, o, rng)

    if stroke_d:
        parts.append(f'<path d="{stroke_d}" {_stroke_attrs(el)} opacity="{op:.2f}"/>')
    return "".join(parts)


def _render_rect(el: dict[str, Any], ox: float, oy: float) -> str:
    x, y = el["x"] - ox, el["y"] - oy
    w, h = el.get("width", 80), el.get("height", 40)

    if el.get("roundness"):
        radius = sketch.excalidraw_corner_radius(w, h)
        outline = sketch.rounded_rect_points(x, y, w, h, radius)
        return _sketch_shape(el, outline, smooth=True)

    outline = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return _sketch_shape(el, outline)


def _render_ellipse(el: dict[str, Any], ox: float, oy: float) -> str:
    w, h = el.get("width", 80), el.get("height", 40)
    cx = el["x"] - ox + w / 2
    cy = el["y"] - oy + h / 2

    o, rng = _rough_for(el)
    op = _opacity(el.get("opacity", 100))
    bg = _fill(el.get("backgroundColor", "transparent"))

    stroke_d, core = sketch.ellipse(cx, cy, w, h, o, rng)

    parts: list[str] = []
    if bg != "none" and core:
        fill_d = sketch.solid_fill(core, o, rng)
        if fill_d:
            parts.append(
                f'<path d="{fill_d}" fill="{_esc(bg)}" stroke="none" opacity="{op:.2f}"/>'
            )
    if stroke_d:
        parts.append(f'<path d="{stroke_d}" {_stroke_attrs(el)} opacity="{op:.2f}"/>')
    return "".join(parts)


def _render_diamond(el: dict[str, Any], ox: float, oy: float) -> str:
    x, y = el["x"] - ox, el["y"] - oy
    w, h = el.get("width", 80), el.get("height", 40)
    cx, cy = x + w / 2, y + h / 2
    outline = [(cx, y), (x + w, cy), (cx, y + h), (x, cy)]
    return _sketch_shape(el, outline)


def _render_text(el: dict[str, Any], ox: float, oy: float, mask_bg: str | None = None) -> str:
    text = el.get("text", "")
    if not text:
        return ""
    x = el["x"] - ox
    y = el["y"] - oy
    font_size = el.get("fontSize", 16)
    font_family = _FONT_STACKS.get(el.get("fontFamily", 1), _FONT_STACKS[2])
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

    # Mask the line behind an edge label so the arrow doesn't run through the
    # text (mirrors how Excalidraw renders bound arrow labels).
    bg = ""
    if mask_bg:
        h = el.get("height", line_h_px * len(lines))
        pad_x, pad_y = 4.0, 2.0
        bg = (
            f'<rect x="{x - pad_x:.2f}" y="{y - pad_y:.2f}" '
            f'width="{w + 2 * pad_x:.2f}" height="{h + 2 * pad_y:.2f}" '
            f'rx="3" fill="{_esc(mask_bg)}" opacity="{op:.2f}"/>'
        )

    parts: list[str] = []
    for i, line in enumerate(lines):
        dy = font_size + i * line_h_px if i == 0 else line_h_px
        parts.append(
            f'<tspan x="{tx:.2f}" dy="{dy:.2f}">{_esc(line) if line else "&#x200B;"}</tspan>'
        )

    tspans = "".join(parts)

    # Rotated labels (vertical axis titles) rotate about the element centre,
    # matching how Excalidraw applies `angle`.
    transform = ""
    angle = el.get("angle", 0) or 0
    if angle:
        h = el.get("height", line_h_px * len(lines))
        cx = x + w / 2
        cy = y + h / 2
        transform = f' transform="rotate({angle * 180 / 3.141592653589793:.2f} {cx:.2f} {cy:.2f})"'

    return (
        f"{bg}"
        f'<text x="{tx:.2f}" y="{y:.2f}" font-size="{font_size}" '
        f'font-family="{font_family}" fill="{_esc(color)}" '
        f'text-anchor="{anchor}" opacity="{op:.2f}"{transform}>'
        f"{tspans}</text>"
    )


def _render_line(el: dict[str, Any], ox: float, oy: float) -> str:
    """Render a line element: open polyline, or filled polygon when closed.

    Closed lines are how the typed diagrams draw shapes Excalidraw has no
    primitive for -- pyramid trapezoids and funnel tiers.
    """
    points_raw = el.get("points", [])
    if len(points_raw) < 2:
        return ""

    base_x = el.get("x", 0.0) - ox
    base_y = el.get("y", 0.0) - oy
    abs_pts = [(base_x + p[0], base_y + p[1]) for p in points_raw]

    closed = bool(el.get("polygon")) or (len(abs_pts) > 2 and abs_pts[0] == abs_pts[-1])
    if closed and len(abs_pts) > 2 and abs_pts[0] == abs_pts[-1]:
        abs_pts = abs_pts[:-1]  # sketch closes the loop itself

    smooth = bool(el.get("roundness")) and len(abs_pts) > 2
    return _sketch_shape(el, abs_pts, closed=closed, smooth=smooth)


def _arrowhead_path(
    tip: tuple[float, float],
    prev: tuple[float, float],
    el: dict[str, Any],
) -> str:
    """The two short strokes Excalidraw uses for an arrowhead.

    Excalidraw draws a V, not a filled triangle -- 30px legs at 20 degrees off
    the incoming segment, shortened on short arrows. A filled marker triangle
    is the single most obvious tell that a diagram was not rendered by
    Excalidraw.
    """
    dx, dy = tip[0] - prev[0], tip[1] - prev[1]
    distance = math.hypot(dx, dy)
    if distance < 1e-6:
        return ""

    nx, ny = dx / distance, dy / distance
    leg = min(30.0, distance / 2)
    bx, by = tip[0] - nx * leg, tip[1] - ny * leg

    o, rng = _rough_for(el)
    # Arrowheads are always single-stroke, however the shaft is drawn.
    o.disable_multi_stroke = True

    parts = []
    for degrees in (-20.0, 20.0):
        angle = math.radians(degrees)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        rx = tip[0] + (bx - tip[0]) * cos_a - (by - tip[1]) * sin_a
        ry = tip[1] + (bx - tip[0]) * sin_a + (by - tip[1]) * cos_a
        d = sketch.linear_path([tip, (rx, ry)], False, o, rng)
        if d:
            parts.append(d)
    return " ".join(parts)


def _render_arrow(el: dict[str, Any], ox: float, oy: float) -> str:
    points_raw = el.get("points", [])
    if len(points_raw) < 2:
        return ""

    base_x = el.get("x", 0.0) - ox
    base_y = el.get("y", 0.0) - oy
    abs_pts = [(base_x + p[0], base_y + p[1]) for p in points_raw]
    op = _opacity(el.get("opacity", 100))

    o, rng = _rough_for(el)
    if el.get("roundness") and len(abs_pts) > 2:
        shaft = sketch.curved_path(abs_pts, o, rng)
    else:
        shaft = sketch.linear_path(abs_pts, False, o, rng)

    heads: list[str] = []
    if el.get("endArrowhead") == "arrow":
        heads.append(_arrowhead_path(abs_pts[-1], abs_pts[-2], el))
    if el.get("startArrowhead") == "arrow":
        heads.append(_arrowhead_path(abs_pts[0], abs_pts[1], el))

    attrs = _stroke_attrs(el)
    parts = [f'<path d="{shaft}" {attrs} opacity="{op:.2f}"/>'] if shaft else []

    # Heads never inherit the shaft's dash pattern -- a dashed arrowhead reads
    # as a broken one.
    head_attrs = _stroke_attrs({**el, "strokeStyle": "solid"})
    parts += [
        f'<path d="{d}" {head_attrs} opacity="{op:.2f}"/>' for d in heads if d
    ]
    return "".join(parts)


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------


_FONT_MIME = {
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
}


def _font_face_block(embed_font: str | Path | None) -> str:
    """Inline a handwriting font so the SVG renders identically everywhere.

    Without this the SVG depends on whatever the viewer has installed. We do
    not ship a font -- Excalidraw's Excalifont is theirs to distribute -- but
    pointing at a local copy makes the export fully self-contained.
    """
    if not embed_font:
        return ""
    path = Path(embed_font)
    if not path.is_file():
        return ""

    mime = _FONT_MIME.get(path.suffix.lower(), "font/ttf")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        "<defs><style>@font-face{font-family:'Excalifont';"
        f"src:url(data:{mime};base64,{encoded});"
        "font-weight:normal;font-style:normal;}</style></defs>"
    )


def excalidraw_to_svg(data: dict[str, Any], embed_font: str | Path | None = None) -> str:
    """Convert an in-memory .excalidraw document to an SVG string.

    Args:
        data: A parsed .excalidraw document.
        embed_font: Optional path to a handwriting font (.woff2/.ttf/...) to
            inline as ``Excalifont``, making the output self-contained.
    """
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
    id_to_type = {e.get("id"): e.get("type", "") for e in elements}

    shape_svgs: list[str] = []
    arrow_svgs: list[str] = []
    text_svgs: list[str] = []

    for el in elements:
        el_type = el.get("type", "")
        if el_type == "rectangle":
            shape_svgs.append(_render_rect(el, ox, oy))
        elif el_type == "ellipse":
            shape_svgs.append(_render_ellipse(el, ox, oy))
        elif el_type == "diamond":
            shape_svgs.append(_render_diamond(el, ox, oy))
        elif el_type == "line":
            # Lines share the shape bucket so document order is preserved --
            # gridlines emitted before bars stay behind them.
            shape_svgs.append(_render_line(el, ox, oy))
        elif el_type == "arrow":
            arrow_svgs.append(_render_arrow(el, ox, oy))
        elif el_type == "text":
            # Labels bound to an arrow get a canvas-colored backing so the
            # line doesn't visually cut through the text.
            is_edge_label = id_to_type.get(el.get("containerId")) in arrow_types
            text_svgs.append(_render_text(el, ox, oy, mask_bg=bg_color if is_edge_label else None))

    defs = _font_face_block(embed_font)

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


def export_to_svg(
    input_path: str | Path,
    output_path: str | Path,
    embed_font: str | Path | None = None,
) -> Path:
    """Read an .excalidraw file and write a .svg file."""
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    svg = excalidraw_to_svg(data, embed_font=embed_font)
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
