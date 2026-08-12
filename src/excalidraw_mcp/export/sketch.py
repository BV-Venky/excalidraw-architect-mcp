"""A pure-Python port of the roughjs stroke generator.

Excalidraw's hand-drawn look is not stored in the file -- it is produced at
render time. Every shape is re-drawn by `roughjs` as two slightly different
jittered strokes, with the jitter derived deterministically from the element's
``seed`` and scaled by its ``roughness``. An exporter that emits a plain
``<rect>`` reproduces the geometry perfectly and the *look* not at all.

This module reproduces the generator so ``export_diagram`` output matches what
you see on the Excalidraw canvas, with no browser and no JS runtime.

Faithfulness: the PRNG is the same Park-Miller/Lehmer generator roughjs uses
(so output is stable and seed-driven), and the line, curve, ellipse, and
solid-fill routines follow the same algorithms in the same order. It is
visually equivalent to roughjs rather than guaranteed byte-identical.

Reference: rough.js `lib/renderer.ts` (MIT).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]

_UINT32 = 0xFFFFFFFF
_INT32_MAX = 0x7FFFFFFF


# ---------------------------------------------------------------------------
# PRNG
# ---------------------------------------------------------------------------


def _imul(a: int, b: int) -> int:
    """Emulate JavaScript's Math.imul: 32-bit signed integer multiply."""
    product = (a * b) & _UINT32
    return product - 0x100000000 if product >= 0x80000000 else product


class Rng:
    """The seeded generator roughjs uses, so exports are reproducible."""

    __slots__ = ("seed",)

    def __init__(self, seed: int) -> None:
        self.seed = int(seed) & _UINT32

    def next(self) -> float:
        self.seed = _imul(48271, self.seed)
        return (_INT32_MAX & self.seed) / 2**31


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------


@dataclass
class Rough:
    """The subset of roughjs options Excalidraw actually varies."""

    roughness: float = 1.0
    bowing: float = 1.0
    max_offset: float = 2.0
    curve_step_count: float = 9.0
    curve_fitting: float = 0.95
    curve_tightness: float = 0.0
    disable_multi_stroke: bool = False
    preserve_vertices: bool = False


def _offset(rng: Rng, lo: float, hi: float, o: Rough, gain: float = 1.0) -> float:
    return o.roughness * gain * (rng.next() * (hi - lo) + lo)


def _offset_opt(rng: Rng, x: float, o: Rough, gain: float = 1.0) -> float:
    return _offset(rng, -x, x, o, gain)


# ---------------------------------------------------------------------------
# Path command accumulation
# ---------------------------------------------------------------------------


def _fmt(value: float) -> str:
    return f"{value:.2f}"


class Path:
    """Accumulates SVG path commands."""

    def __init__(self) -> None:
        self._parts: list[str] = []

    def move(self, x: float, y: float) -> None:
        self._parts.append(f"M {_fmt(x)} {_fmt(y)}")

    def line(self, x: float, y: float) -> None:
        self._parts.append(f"L {_fmt(x)} {_fmt(y)}")

    def curve(self, x1: float, y1: float, x2: float, y2: float, x: float, y: float) -> None:
        self._parts.append(
            f"C {_fmt(x1)} {_fmt(y1)}, {_fmt(x2)} {_fmt(y2)}, {_fmt(x)} {_fmt(y)}"
        )

    def close(self) -> None:
        self._parts.append("Z")

    def __str__(self) -> str:
        return " ".join(self._parts)

    def __bool__(self) -> bool:
        return bool(self._parts)


# ---------------------------------------------------------------------------
# Line
# ---------------------------------------------------------------------------


def _line(
    path: Path,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    o: Rough,
    rng: Rng,
    *,
    move: bool,
    overlay: bool,
) -> None:
    """One jittered stroke from (x1,y1) to (x2,y2), as a single cubic curve.

    The two-pass call (overlay False then True) is what produces the
    characteristic doubled pencil line.
    """
    length_sq = (x1 - x2) ** 2 + (y1 - y2) ** 2
    length = math.sqrt(length_sq)

    # Long lines get proportionally less jitter, or they read as wobbly.
    if length < 200:
        gain = 1.0
    elif length > 500:
        gain = 0.4
    else:
        gain = -0.0016668 * length + 1.233334

    offset = o.max_offset
    if offset * offset * 100 > length_sq:
        offset = length / 10
    half = offset / 2

    diverge = 0.2 + rng.next() * 0.2

    mid_x = o.bowing * o.max_offset * (y2 - y1) / 200
    mid_y = o.bowing * o.max_offset * (x1 - x2) / 200
    mid_x = _offset_opt(rng, mid_x, o, gain)
    mid_y = _offset_opt(rng, mid_y, o, gain)

    def rand_half() -> float:
        return _offset_opt(rng, half, o, gain)

    def rand_full() -> float:
        return _offset_opt(rng, offset, o, gain)

    keep = o.preserve_vertices

    if move:
        if overlay:
            path.move(x1 + (0 if keep else rand_half()), y1 + (0 if keep else rand_half()))
        else:
            path.move(x1 + (0 if keep else rand_full()), y1 + (0 if keep else rand_full()))

    jitter = rand_half if overlay else rand_full
    path.curve(
        mid_x + x1 + (x2 - x1) * diverge + jitter(),
        mid_y + y1 + (y2 - y1) * diverge + jitter(),
        mid_x + x1 + 2 * (x2 - x1) * diverge + jitter(),
        mid_y + y1 + 2 * (y2 - y1) * diverge + jitter(),
        x2 + (0 if keep else jitter()),
        y2 + (0 if keep else jitter()),
    )


def _double_line(
    path: Path, x1: float, y1: float, x2: float, y2: float, o: Rough, rng: Rng
) -> None:
    _line(path, x1, y1, x2, y2, o, rng, move=True, overlay=False)
    if not o.disable_multi_stroke:
        _line(path, x1, y1, x2, y2, o, rng, move=True, overlay=True)


# ---------------------------------------------------------------------------
# Public stroke generators
# ---------------------------------------------------------------------------


def linear_path(points: list[Point], closed: bool, o: Rough, rng: Rng) -> str:
    """Sketchy polyline / polygon through the given vertices."""
    if len(points) < 2:
        return ""
    path = Path()
    for a, b in zip(points, points[1:], strict=False):
        _double_line(path, a[0], a[1], b[0], b[1], o, rng)
    if closed and len(points) > 2:
        _double_line(path, points[-1][0], points[-1][1], points[0][0], points[0][1], o, rng)
    return str(path)


def _curve_pass(path: Path, points: list[Point], o: Rough) -> None:
    """Catmull-Rom through `points`, emitted as cubic beziers."""
    n = len(points)
    if n < 3:
        if n == 2:
            path.move(*points[0])
            path.line(*points[1])
        return

    s = 1 - o.curve_tightness
    path.move(points[1][0], points[1][1])
    for i in range(1, n - 2):
        p0, p1, p2, p3 = points[i - 1], points[i], points[i + 1], points[i + 2]
        path.curve(
            p1[0] + (s * p2[0] - s * p0[0]) / 6,
            p1[1] + (s * p2[1] - s * p0[1]) / 6,
            p2[0] + (s * p1[0] - s * p3[0]) / 6,
            p2[1] + (s * p1[1] - s * p3[1]) / 6,
            p2[0],
            p2[1],
        )


def curved_path(points: list[Point], o: Rough, rng: Rng, *, closed: bool = False) -> str:
    """Sketchy smooth curve through the given points (two passes).

    ``_curve_pass`` draws from ``points[1]`` to ``points[-2]``, so the ends
    need padding to be reached at all. An open path duplicates its endpoints;
    a closed one wraps around circularly instead -- duplicating the endpoints
    of a loop makes the stroke double back on itself and pinch at the join,
    which is exactly what a rounded rectangle must not do at its corners.
    """
    if len(points) < 2:
        return ""

    def jittered(scale: float) -> list[Point]:
        pts = [
            (
                p[0] + _offset_opt(rng, scale, o),
                p[1] + _offset_opt(rng, scale, o),
            )
            for p in points
        ]
        if closed and len(pts) > 2:
            return [pts[-1], *pts, pts[0], pts[1]]
        return [pts[0], *pts, pts[-1]]

    # Offsets follow roughjs's `curve()`: the second pass wanders slightly more.
    path = Path()
    _curve_pass(path, jittered(1.0 * (1 + o.roughness * 0.2)), o)
    if not o.disable_multi_stroke:
        _curve_pass(path, jittered(1.5 * (1 + o.roughness * 0.22)), o)
    return str(path)


def _ellipse_points(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    increment: float,
    offset: float,
    overlap: float,
    o: Rough,
    rng: Rng,
) -> tuple[list[Point], list[Point]]:
    """Perturbed points around an ellipse; returns (all_points, core_points).

    `all_points` carries the extra lead-in/overshoot vertices that make the
    stroke overlap itself at the start, the way a real pen does.
    """
    all_points: list[Point] = []
    core: list[Point] = []

    rad_offset = _offset_opt(rng, 0.5, o) - math.pi / 2
    all_points.append(
        (
            _offset_opt(rng, offset, o) + cx + 0.9 * rx * math.cos(rad_offset - increment),
            _offset_opt(rng, offset, o) + cy + 0.9 * ry * math.sin(rad_offset - increment),
        )
    )

    angle = rad_offset
    end = math.pi * 2 + rad_offset - 0.01
    while angle < end:
        p = (
            _offset_opt(rng, offset, o) + cx + rx * math.cos(angle),
            _offset_opt(rng, offset, o) + cy + ry * math.sin(angle),
        )
        core.append(p)
        all_points.append(p)
        angle += increment

    # Three closing vertices that carry the stroke past its own start and then
    # tuck inward, which is what makes the join look drawn rather than snapped.
    tail = (
        (1.00, rad_offset + math.pi * 2 + overlap * 0.5),
        (0.98, rad_offset + overlap),
        (0.90, rad_offset + overlap * 0.5),
    )
    for factor, angle_at in tail:
        all_points.append(
            (
                _offset_opt(rng, offset, o) + cx + factor * rx * math.cos(angle_at),
                _offset_opt(rng, offset, o) + cy + factor * ry * math.sin(angle_at),
            )
        )
    return all_points, core


def ellipse(
    cx: float, cy: float, width: float, height: float, o: Rough, rng: Rng
) -> tuple[str, list[Point]]:
    """Sketchy ellipse. Returns (stroke path, core points for filling)."""
    perimeter = math.sqrt(
        math.pi * 2 * math.sqrt(((width / 2) ** 2 + (height / 2) ** 2) / 2)
    )
    step_count = max(o.curve_step_count, (o.curve_step_count / math.sqrt(200)) * perimeter)
    increment = (math.pi * 2) / step_count

    rx = abs(width / 2)
    ry = abs(height / 2)
    fit = 1 - o.curve_fitting
    rx += _offset_opt(rng, rx * fit, o)
    ry += _offset_opt(rng, ry * fit, o)

    overlap = increment * _offset(rng, 0.1, _offset(rng, 0.4, 1, o), o)
    all1, core = _ellipse_points(cx, cy, rx, ry, increment, 1.0, overlap, o, rng)

    # No endpoint padding here: `_ellipse_points` already emits the lead-in and
    # overshoot vertices that let the curve pass reach all the way round.
    path = Path()
    _curve_pass(path, all1, o)
    if not o.disable_multi_stroke:
        all2, _ = _ellipse_points(cx, cy, rx, ry, increment, 1.5, 0.0, o, rng)
        _curve_pass(path, all2, o)
    return str(path), core


def solid_fill(points: list[Point], o: Rough, rng: Rng) -> str:
    """A filled polygon whose outline is nudged, so fill and stroke disagree
    slightly -- exactly the crayon-inside-the-lines effect Excalidraw has."""
    if len(points) < 3:
        return ""
    path = Path()
    offset = o.max_offset
    path.move(
        points[0][0] + _offset_opt(rng, offset, o), points[0][1] + _offset_opt(rng, offset, o)
    )
    for p in points[1:]:
        path.line(p[0] + _offset_opt(rng, offset, o), p[1] + _offset_opt(rng, offset, o))
    path.close()
    return str(path)


# ---------------------------------------------------------------------------
# Rounded rectangles
# ---------------------------------------------------------------------------


def rounded_rect_points(
    x: float, y: float, w: float, h: float, radius: float, per_corner: int = 3
) -> list[Point]:
    """Sample a rounded-rectangle outline into points.

    Excalidraw draws rounded rectangles through roughjs's SVG-path renderer,
    which jitters per path *segment*. Sampling the outline and running it
    through the curve generator gets the same look without a path parser --
    but the sampling has to stay coarse. Dense corner samples sit only a few
    pixels apart, and per-point jitter of that spacing turns a smooth corner
    into a zigzag.
    """
    r = max(0.0, min(radius, min(abs(w), abs(h)) / 2))
    if r <= 0.01:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]

    pts: list[Point] = []
    corners = (
        (x + w - r, y + r, -math.pi / 2, 0.0),
        (x + w - r, y + h - r, 0.0, math.pi / 2),
        (x + r, y + h - r, math.pi / 2, math.pi),
        (x + r, y + r, math.pi, math.pi * 3 / 2),
    )
    for cx, cy, start, stop in corners:
        for i in range(per_corner + 1):
            t = start + (stop - start) * (i / per_corner)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def excalidraw_corner_radius(width: float, height: float) -> float:
    """Adaptive corner radius, matching Excalidraw's roundness type 3."""
    return min(min(abs(width), abs(height)) * 0.25, 32.0)
