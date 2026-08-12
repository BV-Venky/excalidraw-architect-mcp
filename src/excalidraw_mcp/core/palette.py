"""Semantic color roles for the typed diagram families.

The existing ``Theme`` describes an architecture diagram: node fills, badge
colors, subgraph chrome. The typed diagrams need a different vocabulary --
chart series, focal accents, hairline rules, tier ramps -- so this module
derives those roles from the same three themes rather than introducing a
fourth source of truth.

The load-bearing rule: **accent is reserved.** One or two focal elements per
diagram get it; everything else is ``muted``. Using accent on five things
erases the signal it exists to carry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from excalidraw_mcp.core.models import ThemeName
from excalidraw_mcp.core.themes import Theme, get_theme


@dataclass(frozen=True)
class Palette:
    """Semantic roles used by typed diagram layouts."""

    canvas: str
    ink: str  # primary text
    muted: str  # secondary text, non-focal strokes
    rule: str  # hairlines: axes, gridlines, lane dividers
    surface: str  # neutral shape fill
    surface_alt: str  # zone / band fill (one step subtler than surface)
    accent: str  # the reserved focal color
    accent_soft: str  # accent at fill strength
    series: list[str] = field(default_factory=list)  # chart series ramp
    tiers: list[str] = field(default_factory=list)  # medallion / pyramid ramp

    def series_color(self, index: int) -> str:
        return self.series[index % len(self.series)] if self.series else self.muted

    def tier_color(self, index: int, total: int) -> str:
        """Pick a tier fill, spreading short ramps across the full range."""
        if not self.tiers:
            return self.surface
        if total <= 1:
            return self.tiers[0]
        pos = index / (total - 1)
        return self.tiers[min(int(pos * (len(self.tiers) - 1) + 0.5), len(self.tiers) - 1)]


_PALETTES: dict[ThemeName, Palette] = {
    ThemeName.DEFAULT: Palette(
        canvas="#ffffff",
        ink="#1e1e1e",
        muted="#868e96",
        rule="#ced4da",
        surface="#f8f9fa",
        surface_alt="#f1f3f5",
        accent="#e8590c",
        accent_soft="#ffe8cc",
        series=["#e8590c", "#1971c2", "#2f9e44", "#9c36b5", "#c2255c", "#0c8599"],
        tiers=["#f8f9fa", "#e9ecef", "#dee2e6", "#ced4da"],
    ),
    ThemeName.DARK: Palette(
        canvas="#1e1e1e",
        ink="#e0e0e0",
        muted="#909296",
        rule="#4d4d4d",
        surface="#2d2d2d",
        surface_alt="#252525",
        accent="#ff922b",
        accent_soft="#5c3a1a",
        series=["#ff922b", "#4dabf7", "#69db7c", "#da77f2", "#f783ac", "#3bc9db"],
        tiers=["#252525", "#2d2d2d", "#383838", "#454545"],
    ),
    ThemeName.COLORFUL: Palette(
        canvas="#ffffff",
        ink="#1e1e1e",
        muted="#5c7cfa",
        rule="#d0ebff",
        surface="#e7f5ff",
        surface_alt="#f3f0ff",
        accent="#f08c00",
        accent_soft="#fff3bf",
        series=["#f08c00", "#1971c2", "#2f9e44", "#7048e8", "#e64980", "#0c8599"],
        tiers=["#e7f5ff", "#d0ebff", "#a5d8ff", "#74c0fc"],
    ),
}


def get_palette(theme: ThemeName | str | Theme) -> Palette:
    """Resolve the semantic palette for a theme name or Theme instance."""
    name = theme.name if isinstance(theme, Theme) else theme
    resolved = get_theme(name)
    return _PALETTES.get(resolved.name, _PALETTES[ThemeName.DEFAULT])
