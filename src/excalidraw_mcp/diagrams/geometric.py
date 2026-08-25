"""Geometric diagram types: position carries the meaning, not connectivity.

timeline · quadrant · pyramid · venn · loop · gantt

None of these run a graph algorithm. Coordinates come straight from the spec
via deterministic math, which is why they are individually small.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from excalidraw_mcp.core.drawable import Box, Connector, Drawable, Poly, Style, Text
from excalidraw_mcp.core.palette import Palette
from excalidraw_mcp.diagrams.base import (
    BODY_SIZE,
    LABEL_SIZE,
    Item,
    TypedSpec,
    caption,
    chrome_style,
    connector_style,
    eyebrow,
    node_box,
    require,
    uniform_box_width,
    zone_style,
)

# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


class Event(BaseModel):
    label: str
    when: str | None = None
    note: str | None = None
    focal: bool = False


class TimelineSpec(TypedSpec):
    """Events positioned along a single axis, alternating above and below."""

    events: list[Event] = Field(..., min_length=2)


def layout_timeline(spec: TimelineSpec, pal: Palette) -> list[Drawable]:
    card_w = uniform_box_width([ev.label for ev in spec.events], min_w=168.0, size=BODY_SIZE)
    # Keep a gutter between adjacent cards whatever width they settled on.
    pitch = max(200.0, card_w + 40.0)
    axis_y = 0.0
    span = (len(spec.events) - 1) * pitch
    card_h = 64.0

    out: list[Drawable] = [
        Poly(
            points=[(-40.0, axis_y), (span + 40.0, axis_y)],
            style=chrome_style(pal, width=1.5),
        )
    ]

    for i, ev in enumerate(spec.events):
        x = i * pitch
        above = i % 2 == 0
        out.append(
            Box(
                x=x - 6,
                y=axis_y - 6,
                width=12,
                height=12,
                shape="ellipse",
                style=Style(
                    stroke=pal.accent if ev.focal else pal.muted,
                    fill=pal.accent if ev.focal else pal.muted,
                    roughness=0,
                ),
            )
        )
        stem = 46.0
        cy = axis_y - stem - card_h if above else axis_y + stem
        out.append(
            Poly(
                points=[(x, axis_y), (x, cy + (card_h if above else 0))],
                style=chrome_style(pal),
            )
        )
        out.append(
            node_box(
                x - card_w / 2,
                cy,
                card_w,
                card_h,
                ev.label,
                pal,
                focal=ev.focal,
                size=BODY_SIZE,
            )
        )
        if ev.when:
            wy = cy - 22 if above else cy + card_h + 8
            out.append(eyebrow(x, wy, ev.when, pal, align="center"))
        if ev.note:
            ny = cy - 40 if above else cy + card_h + 26
            out.append(caption(x, ny, ev.note, pal, size=12, align="center"))
    return out


# ---------------------------------------------------------------------------
# Quadrant
# ---------------------------------------------------------------------------


class Axis(BaseModel):
    label: str
    low: str | None = None
    high: str | None = None


class Plot(BaseModel):
    label: str
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    focal: bool = False


class QuadrantSpec(TypedSpec):
    """Two-axis positioning. Optional named cells make it a consultant 2x2."""

    x_axis: Axis
    y_axis: Axis
    items: list[Plot] = Field(default_factory=list)
    quadrant_labels: list[str] = Field(default_factory=list)  # TL, TR, BL, BR


def layout_quadrant(spec: QuadrantSpec, pal: Palette) -> list[Drawable]:
    size = 560.0
    out: list[Drawable] = [
        Box(x=0, y=0, width=size, height=size, style=zone_style(pal)),
        Poly(points=[(size / 2, 0.0), (size / 2, size)], style=chrome_style(pal, width=1.5)),
        Poly(points=[(0.0, size / 2), (size, size / 2)], style=chrome_style(pal, width=1.5)),
    ]

    if len(spec.quadrant_labels) == 4:
        corners = [
            (size * 0.25, size * 0.10),
            (size * 0.75, size * 0.10),
            (size * 0.25, size * 0.90),
            (size * 0.75, size * 0.90),
        ]
        for (cx, cy), name in zip(corners, spec.quadrant_labels, strict=False):
            out.append(eyebrow(cx, cy, name, pal, align="center"))

    out.append(caption(size / 2, size + 42, spec.x_axis.label, pal, align="center", muted=False))
    out.append(
        caption(
            -52,
            size / 2,
            spec.y_axis.label,
            pal,
            align="center",
            muted=False,
            angle=-math.pi / 2,
        )
    )
    if spec.x_axis.low:
        out.append(caption(0, size + 14, spec.x_axis.low, pal, size=12))
    if spec.x_axis.high:
        out.append(caption(size, size + 14, spec.x_axis.high, pal, size=12, align="right"))
    if spec.y_axis.low:
        out.append(caption(-14, size - 8, spec.y_axis.low, pal, size=12, align="right"))
    if spec.y_axis.high:
        out.append(caption(-14, 0, spec.y_axis.high, pal, size=12, align="right"))

    for item in spec.items:
        px = item.x * size
        py = (1.0 - item.y) * size
        r = 9.0
        out.append(
            Box(
                x=px - r,
                y=py - r,
                width=r * 2,
                height=r * 2,
                shape="ellipse",
                style=Style(
                    stroke=pal.accent if item.focal else pal.muted,
                    fill=pal.accent if item.focal else pal.surface,
                    stroke_width=2 if item.focal else 1.5,
                    roughness=1,
                ),
            )
        )
        out.append(
            caption(
                px + 14,
                py - 8,
                item.label,
                pal,
                size=BODY_SIZE,
                muted=not item.focal,
                focal=item.focal,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Pyramid / funnel
# ---------------------------------------------------------------------------


class PyramidTier(BaseModel):
    label: str
    value: float | None = None
    note: str | None = None
    focal: bool = False


class PyramidSpec(TypedSpec):
    """Ranked hierarchy (pyramid) or conversion drop-off (funnel)."""

    tiers: list[PyramidTier] = Field(..., min_length=2)
    mode: str = "pyramid"  # pyramid | funnel


def layout_pyramid(spec: PyramidSpec, pal: Palette) -> list[Drawable]:
    base_w = 520.0
    tier_h = 88.0
    n = len(spec.tiers)
    cx = base_w / 2
    funnel = spec.mode == "funnel"

    if funnel:
        values = [
            t.value if t.value is not None else float(n - i) for i, t in enumerate(spec.tiers)
        ]
        top = max(values) or 1.0
        widths = [max(90.0, base_w * (v / top)) for v in values]
    else:
        widths = [base_w * (i + 1) / n for i in range(n)]

    out: list[Drawable] = []
    for i, tier in enumerate(spec.tiers):
        y = i * tier_h
        bot_half = widths[i] / 2
        top_half = (widths[i - 1] / 2) if i > 0 else (0.0 if not funnel else widths[0] / 2)

        style = Style(
            stroke=pal.accent if tier.focal else pal.muted,
            fill=pal.accent_soft if tier.focal else pal.tier_color(i, n),
            stroke_width=2 if tier.focal else 1.5,
            roughness=1,
            rounded=False,
        )
        if i == 0 and not funnel:
            points = [(cx, y), (cx + bot_half, y + tier_h), (cx - bot_half, y + tier_h)]
        else:
            points = [
                (cx - top_half, y),
                (cx + top_half, y),
                (cx + bot_half, y + tier_h),
                (cx - bot_half, y + tier_h),
            ]
        out.append(Poly(points=points, closed=True, style=style))

        label_y = y + tier_h / 2 - (LABEL_SIZE * 0.6)
        out.append(
            Text(
                x=cx,
                y=label_y,
                text=tier.label,
                size=LABEL_SIZE,
                color=pal.accent if tier.focal else pal.ink,
                align="center",
            )
        )
        side = max(bot_half, top_half)
        annotation = tier.note or (f"{tier.value:g}" if tier.value is not None else None)
        if annotation:
            out.append(caption(cx + side + 20, y + tier_h / 2 - 8, annotation, pal, size=BODY_SIZE))
    return out


# ---------------------------------------------------------------------------
# Venn
# ---------------------------------------------------------------------------


class Intersection(BaseModel):
    between: list[str]
    label: str


class VennSpec(TypedSpec):
    """Overlap between two or three sets."""

    sets: list[Item] = Field(..., min_length=2, max_length=3)
    intersections: list[Intersection] = Field(default_factory=list)


def layout_venn(spec: VennSpec, pal: Palette) -> list[Drawable]:
    r = 165.0
    n = len(spec.sets)

    if n == 2:
        centers = [(r * 0.75, r), (r * 1.85, r)]
    else:
        # Equilateral arrangement: two on top, one below centre.
        dx = r * 0.58
        dy = r * 0.62
        centers = [(r + -dx, r - dy * 0.7), (r + dx, r - dy * 0.7), (r, r + dy)]

    out: list[Drawable] = []
    for i, (s, (cx, cy)) in enumerate(zip(spec.sets, centers, strict=False)):
        color = pal.accent if s.focal else pal.series_color(i + 1)
        out.append(
            Box(
                x=cx - r,
                y=cy - r,
                width=r * 2,
                height=r * 2,
                shape="ellipse",
                style=Style(
                    stroke=color,
                    fill=color,
                    stroke_width=2,
                    roughness=1,
                    opacity=22,
                ),
            )
        )

    # Set titles sit outside the circles so they never collide with overlap text.
    for i, (s, (cx, cy)) in enumerate(zip(spec.sets, centers, strict=False)):
        color = pal.accent if s.focal else pal.series_color(i + 1)
        if n == 2:
            tx = cx + (-r * 0.62 if i == 0 else r * 0.62)
            ty = cy - 10
        else:
            offsets = [(-r * 0.62, -r * 0.35), (r * 0.62, -r * 0.35), (0.0, r * 0.62)]
            tx, ty = cx + offsets[i][0], cy + offsets[i][1]
        out.append(Text(x=tx, y=ty, text=s.label, size=LABEL_SIZE, color=color, align="center"))

    label_of = {s.label: i for i, s in enumerate(spec.sets)}
    for inter in spec.intersections:
        idxs = [label_of[name] for name in inter.between if name in label_of]
        if len(idxs) < 2:
            continue
        cx = sum(centers[i][0] for i in idxs) / len(idxs)
        cy = sum(centers[i][1] for i in idxs) / len(idxs)

        # With three sets, the midpoint of two centres falls inside the *triple*
        # overlap, so a pairwise label would sit in the wrong region. Push it
        # away from the excluded set until it clears that centre lens.
        excluded = [i for i in range(n) if i not in idxs]
        if len(idxs) == 2 and excluded:
            ex, ey = centers[excluded[0]]
            vx, vy = cx - ex, cy - ey
            dist = math.hypot(vx, vy) or 1.0
            cx += vx / dist * r * 0.52
            cy += vy / dist * r * 0.52

        out.append(Text(x=cx, y=cy, text=inter.label, size=12, color=pal.ink, align="center"))
    return out


# ---------------------------------------------------------------------------
# Loop / flywheel
# ---------------------------------------------------------------------------


class LoopSpec(TypedSpec):
    """A reinforcing cycle; optionally with a shared hub the stations feed."""

    stations: list[Item] = Field(..., min_length=3)
    hub: str | None = None
    hub_note: str | None = None


def layout_loop(spec: LoopSpec, pal: Palette) -> list[Drawable]:
    n = len(spec.stations)
    box_w = uniform_box_width([s.label for s in spec.stations], min_w=168.0, size=BODY_SIZE)
    box_h = 62.0

    # The hub is a circle, so its label needs the *inscribed* width, not the
    # diameter -- text at full width would poke out of the curve.
    hub_r = 0.0
    if spec.hub:
        hub_r = max(92.0, uniform_box_width([spec.hub], min_w=0.0, size=BODY_SIZE) / 1.35)

    # The ring has to clear three things at once: its own arc length (so wide
    # boxes don't collide with their neighbours), and the hub plus a station's
    # half-diagonal (so no station lands on top of the hub).
    station_reach = math.hypot(box_w / 2, box_h / 2)
    radius = max(
        220.0,
        n * 46.0,
        (box_w + 40.0) * n / (2 * math.pi) * 1.35,
        hub_r + station_reach + 28.0,
    )
    cx = cy = radius + box_w / 2

    angles = [-math.pi / 2 + 2 * math.pi * i / n for i in range(n)]
    centers = [(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in angles]

    out: list[Drawable] = []

    if spec.hub:
        out.append(
            Box(
                x=cx - hub_r,
                y=cy - hub_r,
                width=hub_r * 2,
                height=hub_r * 2,
                shape="ellipse",
                label=spec.hub,
                label_size=BODY_SIZE,
                label_color=pal.accent,
                style=Style(stroke=pal.accent, fill=pal.accent_soft, stroke_width=2, roughness=1),
            )
        )
    # Ring arrows first so the station boxes cover their endpoints. The angular
    # gap is derived from the box geometry -- a fixed gap starts the arc inside
    # the box it is supposed to be leaving.
    clearance = math.hypot(box_w / 2, box_h / 2) + 14.0
    gap = min(math.asin(min(clearance / radius, 0.99)), math.pi / n * 0.85)

    for i in range(n):
        a1 = angles[i]
        a2 = angles[(i + 1) % n]
        if a2 <= a1:
            a2 += 2 * math.pi
        start = (cx + radius * math.cos(a1 + gap), cy + radius * math.sin(a1 + gap))
        end = (cx + radius * math.cos(a2 - gap), cy + radius * math.sin(a2 - gap))
        mid_a = (a1 + a2) / 2
        bulge = radius * 1.04
        mid = (cx + bulge * math.cos(mid_a), cy + bulge * math.sin(mid_a))
        out.append(Connector(points=[start, mid, end], style=connector_style(pal), curved=True))

    for i, (station, (sx, sy)) in enumerate(zip(spec.stations, centers, strict=False)):
        out.append(
            node_box(
                sx - box_w / 2,
                sy - box_h / 2,
                box_w,
                box_h,
                station.label,
                pal,
                focal=station.focal,
                size=BODY_SIZE,
            )
        )
        if spec.hub:
            # Write-backs into the shared hub are dashed -- they are a different
            # kind of edge from the ring and must read that way.
            vx, vy = cx - sx, cy - sy
            dist = math.hypot(vx, vy) or 1.0
            ux, uy = vx / dist, vy / dist
            out.append(
                Connector(
                    points=[
                        (sx + ux * (box_h / 2 + 4), sy + uy * (box_h / 2 + 4)),
                        (cx - ux * 94, cy - uy * 94),
                    ],
                    style=connector_style(pal, dashed=True),
                    curved=False,
                )
            )

    if spec.hub and spec.hub_note:
        # Below the whole ring, not under the hub -- under the hub it lands on
        # top of the write-back arrows converging there.
        out.append(caption(cx, cy + radius + box_h, spec.hub_note, pal, size=12, align="center"))
    return out


# ---------------------------------------------------------------------------
# Gantt
# ---------------------------------------------------------------------------


class Task(BaseModel):
    label: str
    start: float = Field(..., ge=0)
    end: float = Field(..., gt=0)
    phase: str | None = None
    focal: bool = False


class GanttSpec(TypedSpec):
    """Tasks and phases on a timeline, measured in abstract units."""

    tasks: list[Task] = Field(..., min_length=1)
    unit_label: str = "Week"
    tick_every: int = 1
    marker: float | None = None  # e.g. "today"


def layout_gantt(spec: GanttSpec, pal: Palette) -> list[Drawable]:
    require(all(t.end > t.start for t in spec.tasks), "every gantt task needs end > start")

    label_col = 210.0
    track_w = 700.0
    row_h = 44.0
    bar_h = 26.0

    total = max(t.end for t in spec.tasks)
    pitch = track_w / total if total else track_w

    def to_x(unit: float) -> float:
        return label_col + unit * pitch

    n = len(spec.tasks)
    axis_y = -16.0
    out: list[Drawable] = [
        Poly(
            points=[(label_col, axis_y), (label_col + track_w, axis_y)],
            style=chrome_style(pal, width=1.5),
        )
    ]

    step = max(1, spec.tick_every)
    unit = 0
    while unit <= total:
        x = to_x(unit)
        out.append(
            caption(x, axis_y - 22, f"{spec.unit_label} {unit}", pal, size=11, align="center")
        )
        out.append(Poly(points=[(x, axis_y), (x, n * row_h)], style=chrome_style(pal)))
        unit += step

    seen_phase: set[str] = set()
    for i, task in enumerate(spec.tasks):
        y = i * row_h
        if task.phase and task.phase not in seen_phase:
            seen_phase.add(task.phase)
            out.append(eyebrow(0, y + 2, task.phase, pal))
            out.append(caption(0, y + 20, task.label, pal, size=BODY_SIZE, muted=False))
        else:
            out.append(caption(0, y + row_h / 2 - 9, task.label, pal, size=BODY_SIZE, muted=False))

        x0, x1 = to_x(task.start), to_x(task.end)
        out.append(
            Box(
                x=x0,
                y=y + (row_h - bar_h) / 2,
                width=max(x1 - x0, 6),
                height=bar_h,
                style=Style(
                    stroke=pal.accent if task.focal else pal.muted,
                    fill=pal.accent_soft if task.focal else pal.surface,
                    stroke_width=2 if task.focal else 1.5,
                    roughness=1,
                ),
            )
        )

    if spec.marker is not None:
        mx = to_x(spec.marker)
        out.append(
            Poly(
                points=[(mx, axis_y), (mx, n * row_h)],
                style=Style(
                    stroke=pal.accent,
                    stroke_width=1.5,
                    stroke_style="dashed",
                    roughness=0,
                    rounded=False,
                ),
            )
        )
    return out
