"""Low-level drawing primitives shared by every diagram type.

Layout strategies do not emit Excalidraw JSON directly. They emit a flat list
of ``Drawable`` primitives with absolute coordinates, and a single renderer
turns those into elements. This keeps 20+ diagram types independent of the
Excalidraw wire format and gives them one place to gain features (rotation,
roughness control, arrowhead variants).

The classic graph pipeline (``LayoutResult`` -> ``build_excalidraw_file``) is
one producer of drawables among many; see ``engine.draw_renderer``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------


class Style(BaseModel):
    """Visual attributes for a single primitive.

    ``roughness`` is deliberately per-primitive rather than per-diagram: chrome
    (axes, gridlines, ticks, lane dividers) renders at 0 so it stays crisp,
    while content shapes stay at 1 for the hand-drawn look. That contrast is
    what keeps sketchy charts legible instead of noisy.
    """

    stroke: str = "#1e1e1e"
    fill: str = "transparent"
    fill_style: str = "solid"  # solid | hachure | cross-hatch
    stroke_width: float = 2
    stroke_style: str = "solid"  # solid | dashed | dotted
    roughness: int = 1  # 0 = crisp, 1 = hand-drawn, 2 = loose
    opacity: int = 100
    rounded: bool = True

    def merge(self, **overrides: object) -> Style:
        """Return a copy with the given fields replaced."""
        return self.model_copy(update={k: v for k, v in overrides.items() if v is not None})


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


class Box(BaseModel):
    """A rectangle, ellipse, or diamond with an optional bound label.

    Covers every container shape. ``shape`` maps straight onto the Excalidraw
    element type, so a single primitive serves nodes, lane bands, chart bars,
    activation bars, and grid cells.
    """

    kind: Literal["box"] = "box"
    x: float
    y: float
    width: float
    height: float
    shape: str = "rectangle"  # rectangle | ellipse | diamond
    label: str | None = None
    label_size: int = 16
    label_color: str | None = None
    label_align: str = "center"  # left | center | right
    label_valign: str = "middle"  # top | middle | bottom
    style: Style = Field(default_factory=Style)
    group: str | None = None
    node_id: str | None = None  # round-trips into customData for graph types


class Poly(BaseModel):
    """An open polyline or a closed polygon, in absolute coordinates.

    Closed polys carry a fill, which is what makes pyramids (trapezoids) and
    funnel tiers possible -- Excalidraw has no triangle primitive.
    """

    kind: Literal["poly"] = "poly"
    points: list[tuple[float, float]]
    closed: bool = False
    curved: bool = False
    style: Style = Field(default_factory=Style)
    group: str | None = None


class Connector(BaseModel):
    """An arrow between two points, optionally labelled and optionally bound.

    ``from_node``/``to_node`` are optional: when both are set and the referenced
    boxes exist, the renderer binds the arrow so dragging a node in Excalidraw
    keeps the arrow attached. Geometry-only connectors (a Venn callout, a loop
    return arc) leave them unset.
    """

    kind: Literal["connector"] = "connector"
    points: list[tuple[float, float]]
    label: str | None = None
    label_size: int = 14
    label_color: str | None = None
    style: Style = Field(default_factory=Style)
    start_arrowhead: str | None = None
    end_arrowhead: str | None = "arrow"
    curved: bool = True
    group: str | None = None
    from_node: str | None = None
    to_node: str | None = None


class Text(BaseModel):
    """A free-standing text label.

    Unlike a ``Box`` label this is not bound to a container, so it can be
    rotated (``angle``, in radians) for vertical axis titles and placed at
    arbitrary positions for ticks, eyebrows, and annotations.
    """

    kind: Literal["text"] = "text"
    x: float
    y: float
    text: str
    size: int = 14
    color: str = "#1e1e1e"
    align: str = "left"  # left | center | right, relative to x
    angle: float = 0.0
    width: float | None = None
    opacity: int = 100
    group: str | None = None


Drawable = Box | Poly | Connector | Text


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


def drawable_bounds(items: list[Drawable]) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) across every primitive."""
    xs: list[float] = []
    ys: list[float] = []
    for it in items:
        if isinstance(it, Box):
            xs.extend([it.x, it.x + it.width])
            ys.extend([it.y, it.y + it.height])
        elif isinstance(it, Poly | Connector):
            xs.extend(p[0] for p in it.points)
            ys.extend(p[1] for p in it.points)
        else:
            # Mirror the renderer's placement rules, otherwise right-aligned
            # axis labels and rotated titles fall outside the computed box and
            # the normalised margin silently disappears.
            w = it.width or len(it.text) * it.size * 0.55
            h = it.size * 1.25
            if it.angle:
                half = max(w, h) / 2
                xs.extend([it.x - half, it.x + half])
                ys.extend([it.y - half, it.y + half])
                continue
            left = (
                it.x - w / 2
                if it.align == "center"
                else (it.x - w if it.align == "right" else it.x)
            )
            xs.extend([left, left + w])
            ys.extend([it.y, it.y + h])
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def translate(items: list[Drawable], dx: float, dy: float) -> list[Drawable]:
    """Shift every primitive by (dx, dy). Used to normalise the origin."""
    out: list[Drawable] = []
    for it in items:
        if isinstance(it, Box):
            out.append(it.model_copy(update={"x": it.x + dx, "y": it.y + dy}))
        elif isinstance(it, Poly):
            shifted = [(p[0] + dx, p[1] + dy) for p in it.points]
            out.append(it.model_copy(update={"points": shifted}))
        elif isinstance(it, Connector):
            shifted = [(p[0] + dx, p[1] + dy) for p in it.points]
            out.append(it.model_copy(update={"points": shifted}))
        else:
            out.append(it.model_copy(update={"x": it.x + dx, "y": it.y + dy}))
    return out


def normalize(items: list[Drawable], margin: float = 60.0) -> list[Drawable]:
    """Translate so the drawing sits at (margin, margin)."""
    min_x, min_y, _, _ = drawable_bounds(items)
    return translate(items, margin - min_x, margin - min_y)
