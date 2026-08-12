"""Scales and tick generation for the chart family.

Charts are the one family that needs a real coordinate transform: a domain of
data values mapped onto a pixel range, plus axis ticks that land on readable
numbers rather than wherever the data happens to stop. Everything here is
pure arithmetic with no Excalidraw awareness -- ``diagrams.charts`` turns the
output into primitives.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Nice numbers
# ---------------------------------------------------------------------------


def _nice_number(value: float, round_it: bool) -> float:
    """Round a number to 1, 2, 5, or 10 times a power of ten."""
    if value <= 0:
        return 1.0
    exp = math.floor(math.log10(value))
    frac = value / (10**exp)
    if round_it:
        nice = 1.0 if frac < 1.5 else 2.0 if frac < 3 else 5.0 if frac < 7 else 10.0
    else:
        nice = 1.0 if frac <= 1 else 2.0 if frac <= 2 else 5.0 if frac <= 5 else 10.0
    return nice * (10**exp)


def nice_ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    """Return evenly spaced tick values covering [lo, hi] at round numbers.

    The returned range may extend slightly beyond the data, which is what you
    want for an axis -- a bar topping out at 97 should sit under a 100 tick,
    not define the ceiling itself.
    """
    if not math.isfinite(lo) or not math.isfinite(hi):
        return [0.0, 1.0]
    if hi == lo:
        # Degenerate domain: fabricate a band around the value so the axis and
        # any bars drawn against it still have non-zero extent.
        delta = abs(hi) * 0.5 or 1.0
        lo, hi = lo - delta, hi + delta

    target = max(2, target)
    spacing = _nice_number((hi - lo) / (target - 1), round_it=True)
    nice_lo = math.floor(lo / spacing) * spacing
    nice_hi = math.ceil(hi / spacing) * spacing

    ticks: list[float] = []
    steps = int(round((nice_hi - nice_lo) / spacing))
    for i in range(steps + 1):
        value = nice_lo + i * spacing
        # Kill float dust like 0.30000000000000004 before it reaches a label.
        ticks.append(round(value, 10) + 0.0)
    return ticks


def format_tick(value: float) -> str:
    """Render a tick value compactly (1200 -> '1.2k', 3.0 -> '3')."""
    av = abs(value)
    if av >= 1_000_000:
        return f"{value / 1_000_000:g}M"
    if av >= 1_000:
        return f"{value / 1_000:g}k"
    if av == int(av):
        return str(int(value))
    return f"{value:g}"


# ---------------------------------------------------------------------------
# Scales
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LinearScale:
    """Maps a continuous domain onto a pixel range."""

    domain_min: float
    domain_max: float
    range_min: float
    range_max: float

    def __call__(self, value: float) -> float:
        span = self.domain_max - self.domain_min
        if span == 0:
            return self.range_min
        t = (value - self.domain_min) / span
        return self.range_min + t * (self.range_max - self.range_min)

    @classmethod
    def from_values(
        cls,
        values: list[float],
        range_min: float,
        range_max: float,
        *,
        target_ticks: int = 5,
        include_zero: bool = True,
    ) -> tuple[LinearScale, list[float]]:
        """Build a scale plus its tick values from raw data."""
        data = [v for v in values if math.isfinite(v)] or [0.0]
        lo, hi = min(data), max(data)
        if include_zero:
            lo, hi = min(lo, 0.0), max(hi, 0.0)
        ticks = nice_ticks(lo, hi, target_ticks)
        return cls(ticks[0], ticks[-1], range_min, range_max), ticks


@dataclass(frozen=True)
class BandScale:
    """Maps discrete categories onto evenly spaced pixel bands."""

    categories: list[str]
    range_min: float
    range_max: float
    padding: float = 0.2  # fraction of each band left as gutter

    @property
    def step(self) -> float:
        n = max(len(self.categories), 1)
        return (self.range_max - self.range_min) / n

    @property
    def band_width(self) -> float:
        return self.step * (1 - self.padding)

    def start(self, category: str) -> float:
        """Left/top edge of the drawable band for a category."""
        try:
            idx = self.categories.index(category)
        except ValueError:
            idx = 0
        return self.range_min + idx * self.step + (self.step - self.band_width) / 2

    def center(self, category: str) -> float:
        return self.start(category) + self.band_width / 2
