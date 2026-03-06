"""Color themes for diagram rendering.

Each theme overrides the default component colors with a cohesive palette.
Themes affect background colors, stroke colors, arrow colors, and the canvas.
"""

from __future__ import annotations

from dataclasses import dataclass

from excalidraw_mcp.core.models import ThemeName


@dataclass(frozen=True)
class Theme:
    """Complete color scheme for rendering a diagram."""

    name: ThemeName

    canvas_background: str

    # Default element colors (used when no component style overrides)
    default_bg: str
    default_stroke: str
    default_text: str

    # Arrow / edge colors
    arrow_stroke: str
    arrow_label_color: str

    # Badge colors
    badge_bg: str
    badge_text: str

    # Subgraph / group colors
    group_bg: str
    group_stroke: str
    group_label_color: str

    # Whether to darken component background colors for this theme
    invert_component_colors: bool = False


THEMES: dict[ThemeName, Theme] = {
    ThemeName.DEFAULT: Theme(
        name=ThemeName.DEFAULT,
        canvas_background="#ffffff",
        default_bg="#f8f9fa",
        default_stroke="#495057",
        default_text="#1e1e1e",
        arrow_stroke="#495057",
        arrow_label_color="#495057",
        badge_bg="#e9ecef",
        badge_text="#495057",
        group_bg="#f8f9fa",
        group_stroke="#ced4da",
        group_label_color="#868e96",
    ),
    ThemeName.DARK: Theme(
        name=ThemeName.DARK,
        canvas_background="#1e1e1e",
        default_bg="#2d2d2d",
        default_stroke="#a0a0a0",
        default_text="#e0e0e0",
        arrow_stroke="#a0a0a0",
        arrow_label_color="#c0c0c0",
        badge_bg="#3d3d3d",
        badge_text="#c0c0c0",
        group_bg="#252525",
        group_stroke="#4d4d4d",
        group_label_color="#808080",
        invert_component_colors=True,
    ),
    ThemeName.COLORFUL: Theme(
        name=ThemeName.COLORFUL,
        canvas_background="#ffffff",
        default_bg="#e7f5ff",
        default_stroke="#1971c2",
        default_text="#1e1e1e",
        arrow_stroke="#495057",
        arrow_label_color="#495057",
        badge_bg="#d0ebff",
        badge_text="#1864ab",
        group_bg="#fff9db",
        group_stroke="#f08c00",
        group_label_color="#e67700",
    ),
}


def get_theme(name: ThemeName | str) -> Theme:
    """Resolve a theme by name, falling back to DEFAULT."""
    if isinstance(name, str):
        try:
            name = ThemeName(name)
        except ValueError:
            name = ThemeName.DEFAULT
    return THEMES.get(name, THEMES[ThemeName.DEFAULT])


def darken_hex(color: str, factor: float = 0.35) -> str:
    """Darken a hex color by a factor (0 = unchanged, 1 = black).

    Used by the dark theme to adapt component background colors.
    """
    color = color.lstrip("#")
    r, g, b = int(color[:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    r = int(r * (1 - factor))
    g = int(g * (1 - factor))
    b = int(b * (1 - factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def lighten_hex(color: str, factor: float = 0.3) -> str:
    """Lighten a hex color by a factor (0 = unchanged, 1 = white)."""
    color = color.lstrip("#")
    r, g, b = int(color[:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"
