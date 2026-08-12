"""Chart types drawn in Excalidraw's hand-drawn idiom.

bar · line · scatter

The whole family shares one axis frame. The defining rule: **chrome renders
crisp, data renders sketchy.** Axes, gridlines, and ticks use roughness 0
because a 1px rule at roughness 1 is indistinguishable from noise; bars,
lines, and dots keep roughness 1 so the chart still reads as hand-drawn.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from excalidraw_mcp.core.drawable import Box, Drawable, Poly, Style
from excalidraw_mcp.core.palette import Palette
from excalidraw_mcp.diagrams.base import (
    TypedSpec,
    caption,
    chrome_style,
    require,
)
from excalidraw_mcp.engine.scales import BandScale, LinearScale, format_tick

PLOT_W = 660.0
PLOT_H = 400.0
MAX_LINE_POINTS = 15


class Series(BaseModel):
    name: str
    values: list[float]
    focal: bool = False


# ---------------------------------------------------------------------------
# Shared axis frame
# ---------------------------------------------------------------------------


def _value_axis(
    values: list[float], pal: Palette, *, width: float = PLOT_W, height: float = PLOT_H
) -> tuple[LinearScale, list[Drawable]]:
    """Y axis: gridlines, tick labels, and the baseline."""
    scale, ticks = LinearScale.from_values(values, height, 0.0)
    out: list[Drawable] = []
    for t in ticks:
        y = scale(t)
        out.append(Poly(points=[(0.0, y), (width, y)], style=chrome_style(pal)))
        out.append(caption(-12, y - 8, format_tick(t), pal, size=11, align="right"))
    out.append(Poly(points=[(0.0, 0.0), (0.0, height)], style=chrome_style(pal, width=1.5)))
    out.append(
        Poly(points=[(0.0, scale(0.0)), (width, scale(0.0))], style=chrome_style(pal, width=1.5))
    )
    return scale, out


def _axis_titles(
    x_label: str | None, y_label: str | None, pal: Palette, *, width: float, height: float
) -> list[Drawable]:
    import math

    out: list[Drawable] = []
    if x_label:
        out.append(caption(width / 2, height + 54, x_label, pal, align="center", muted=False))
    if y_label:
        out.append(
            caption(-74, height / 2, y_label, pal, align="center", muted=False, angle=-math.pi / 2)
        )
    return out


def _legend(series: list[Series], pal: Palette, y: float) -> list[Drawable]:
    """Horizontal legend strip. Skipped for single-series charts.

    Swatch colors come from the same helper the marks use, so a focal series
    and its legend entry can never disagree.
    """
    if len(series) < 2:
        return []
    out: list[Drawable] = []
    x = 0.0
    for i, s in enumerate(series):
        color = _series_color(pal, i, s.focal)
        out.append(
            Box(
                x=x,
                y=y,
                width=18,
                height=10,
                style=Style(stroke=color, fill=color, roughness=1, stroke_width=1, rounded=False),
            )
        )
        out.append(caption(x + 26, y - 3, s.name, pal, size=12, muted=False))
        x += 34 + len(s.name) * 7.5
    return out


def _series_color(pal: Palette, index: int, focal: bool) -> str:
    return pal.accent if focal else pal.series_color(index + 1)


# ---------------------------------------------------------------------------
# Bar
# ---------------------------------------------------------------------------


class BarSpec(TypedSpec):
    """Categorical comparison. Multiple series render as grouped bars."""

    categories: list[str] = Field(..., min_length=1)
    series: list[Series] = Field(..., min_length=1)
    x_label: str | None = None
    y_label: str | None = None


def layout_bar(spec: BarSpec, pal: Palette) -> list[Drawable]:
    require(
        all(len(s.values) == len(spec.categories) for s in spec.series),
        "each bar series must have exactly one value per category",
    )

    all_values = [v for s in spec.series for v in s.values]
    scale, out = _value_axis(all_values, pal)

    band = BandScale(spec.categories, 0.0, PLOT_W, padding=0.28)
    zero_y = scale(0.0)
    group_n = len(spec.series)
    sub_w = band.band_width / group_n

    for si, s in enumerate(spec.series):
        color = _series_color(pal, si, s.focal)
        for ci, cat in enumerate(spec.categories):
            value = s.values[ci]
            x = band.start(cat) + si * sub_w
            y_val = scale(value)
            top = min(y_val, zero_y)
            out.append(
                Box(
                    x=x,
                    y=top,
                    width=max(sub_w - 4, 4),
                    height=max(abs(zero_y - y_val), 2),
                    style=Style(
                        stroke=color,
                        fill=color,
                        fill_style="solid",
                        stroke_width=2 if s.focal else 1.5,
                        roughness=1,
                        opacity=100 if s.focal else 70,
                        rounded=False,
                    ),
                )
            )

    for cat in spec.categories:
        out.append(caption(band.center(cat), PLOT_H + 14, cat, pal, size=12, align="center"))

    out.extend(_axis_titles(spec.x_label, spec.y_label, pal, width=PLOT_W, height=PLOT_H))
    out.extend(_legend(spec.series, pal, PLOT_H + 82))
    return out


# ---------------------------------------------------------------------------
# Line
# ---------------------------------------------------------------------------


class LineSpec(TypedSpec):
    """Trends over an ordered axis.

    Capped at 15 points per series: a sketchy polyline through more than that
    stops reading as a trend and starts reading as a seismograph.
    """

    x_labels: list[str] = Field(..., min_length=2)
    series: list[Series] = Field(..., min_length=1)
    x_label: str | None = None
    y_label: str | None = None
    show_points: bool = True

    @field_validator("x_labels")
    @classmethod
    def _cap_points(cls, v: list[str]) -> list[str]:
        if len(v) > MAX_LINE_POINTS:
            raise ValueError(
                f"line charts are capped at {MAX_LINE_POINTS} points "
                f"(got {len(v)}); downsample or split the chart"
            )
        return v


def layout_line(spec: LineSpec, pal: Palette) -> list[Drawable]:
    require(
        all(len(s.values) == len(spec.x_labels) for s in spec.series),
        "each line series must have exactly one value per x label",
    )

    all_values = [v for s in spec.series for v in s.values]
    scale, out = _value_axis(all_values, pal)

    n = len(spec.x_labels)
    pitch = PLOT_W / max(n - 1, 1)

    for si, s in enumerate(spec.series):
        color = _series_color(pal, si, s.focal)
        pts = [(i * pitch, scale(v)) for i, v in enumerate(s.values)]
        out.append(
            Poly(
                points=pts,
                curved=True,
                style=Style(
                    stroke=color,
                    fill="transparent",
                    stroke_width=2.5 if s.focal else 1.5,
                    roughness=1,
                    rounded=False,
                ),
            )
        )
        # Vertex dots only on the focal series -- the rule that keeps a
        # multi-series chart readable instead of speckled.
        if spec.show_points and (s.focal or len(spec.series) == 1):
            for px, py in pts:
                out.append(
                    Box(
                        x=px - 5,
                        y=py - 5,
                        width=10,
                        height=10,
                        shape="ellipse",
                        style=Style(stroke=color, fill=color, roughness=1, stroke_width=1),
                    )
                )

    for i, label in enumerate(spec.x_labels):
        out.append(caption(i * pitch, PLOT_H + 14, label, pal, size=12, align="center"))

    out.extend(_axis_titles(spec.x_label, spec.y_label, pal, width=PLOT_W, height=PLOT_H))
    out.extend(_legend(spec.series, pal, PLOT_H + 82))
    return out


# ---------------------------------------------------------------------------
# Scatter
# ---------------------------------------------------------------------------


class ScatterPoint(BaseModel):
    x: float
    y: float
    label: str | None = None
    group: str | None = None
    focal: bool = False


class ScatterSpec(TypedSpec):
    """Distribution and correlation between two continuous variables."""

    points: list[ScatterPoint] = Field(..., min_length=2)
    x_label: str | None = None
    y_label: str | None = None


def layout_scatter(spec: ScatterSpec, pal: Palette) -> list[Drawable]:
    ys = [p.y for p in spec.points]
    xs = [p.x for p in spec.points]

    y_scale, out = _value_axis(ys, pal)
    x_scale, x_ticks = LinearScale.from_values(xs, 0.0, PLOT_W)
    for t in x_ticks:
        x = x_scale(t)
        out.append(Poly(points=[(x, 0.0), (x, PLOT_H)], style=chrome_style(pal)))
        out.append(caption(x, PLOT_H + 14, format_tick(t), pal, size=11, align="center"))

    groups = [g for g in dict.fromkeys(p.group for p in spec.points if p.group)]
    for p in spec.points:
        gi = groups.index(p.group) if p.group in groups else 0
        color = pal.accent if p.focal else pal.series_color(gi + 1)
        px, py = x_scale(p.x), y_scale(p.y)
        r = 8.0 if p.focal else 6.5
        out.append(
            Box(
                x=px - r,
                y=py - r,
                width=r * 2,
                height=r * 2,
                shape="ellipse",
                style=Style(
                    stroke=color,
                    fill=color,
                    stroke_width=1.5,
                    roughness=1,
                    opacity=100 if p.focal else 75,
                ),
            )
        )
        if p.label:
            out.append(
                caption(px + r + 6, py - 8, p.label, pal, size=11, muted=not p.focal, focal=p.focal)
            )

    out.extend(_axis_titles(spec.x_label, spec.y_label, pal, width=PLOT_W, height=PLOT_H))
    if groups:
        out.extend(
            _legend([Series(name=g, values=[]) for g in groups], pal, PLOT_H + 82)
        )
    return out
