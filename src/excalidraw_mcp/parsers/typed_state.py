"""Stateful editing for typed diagrams.

Graph diagrams are edited by reconstructing a node/edge model from the
elements. That mechanism has no meaning for a Venn diagram or a bar chart, so
typed diagrams take the other route: the validated spec is stored in
``customData`` at render time, and editing means patching that spec and
re-rendering. One mechanism, every type.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from excalidraw_mcp.diagrams.registry import build_typed_diagram, get_type
from excalidraw_mcp.engine.renderer import load_excalidraw, save_excalidraw


def read_typed_metadata(file_path: str | Path) -> dict[str, Any] | None:
    """Return the typed-diagram metadata block, or None if not a typed file."""
    try:
        data = load_excalidraw(file_path)
    except (OSError, json.JSONDecodeError):
        return None
    meta = data.get("appState", {}).get("customData", {}).get("excalidraw_mcp", {})
    if meta.get("diagram_type") and "spec" in meta:
        return meta
    return None


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``patch`` into ``base``.

    Lists are replaced wholesale rather than merged element-wise: a spec list
    is ordered content (tiers, messages, categories), and index-merging it
    produces results nobody predicts. To change one entry, send the new list.
    """
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def typed_summary(file_path: str | Path) -> str:
    """Human-readable description of a typed diagram's current spec."""
    meta = read_typed_metadata(file_path)
    if meta is None:
        return ""

    dt = get_type(meta["diagram_type"])
    spec = meta["spec"]
    lines = [
        f"Diagram type: {dt.name} ({dt.family} family)",
        f"Theme: {meta.get('theme', 'default')}",
        f"Use when: {dt.use_when}",
        "",
        "Current spec (patch any subset of these keys with modify_diagram):",
        json.dumps(spec, indent=2, ensure_ascii=False),
    ]
    return "\n".join(lines)


def apply_spec_patch(
    file_path: str | Path,
    patch: dict[str, Any],
    *,
    theme: str | None = None,
) -> str:
    """Deep-merge a patch into the stored spec and re-render in place."""
    meta = read_typed_metadata(file_path)
    if meta is None:
        raise ValueError(
            f"{file_path} is not a typed diagram; use node/connection operations instead"
        )

    merged = deep_merge(meta["spec"], patch)
    doc, summary = build_typed_diagram(
        meta["diagram_type"], merged, theme=theme or meta.get("theme", "default")
    )
    path = save_excalidraw(doc, file_path)
    changed = ", ".join(sorted(patch)) or "(nothing)"
    return f"Patched {changed} on {path}\n{summary}"
