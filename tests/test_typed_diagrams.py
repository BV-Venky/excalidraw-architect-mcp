"""Tests for the typed diagram families, the registry, and spec-based editing."""

from __future__ import annotations

import json

import pytest

from excalidraw_mcp.core.drawable import Box, Poly, Text, drawable_bounds, normalize
from excalidraw_mcp.core.palette import get_palette
from excalidraw_mcp.diagrams.base import SpecError
from excalidraw_mcp.diagrams.registry import (
    DIAGRAM_TYPES,
    DiagramNotFoundError,
    build_typed_diagram,
    describe_type,
)
from excalidraw_mcp.engine.draw_renderer import _polyline_midpoint, drawables_to_elements
from excalidraw_mcp.engine.renderer import save_excalidraw
from excalidraw_mcp.engine.scales import BandScale, LinearScale, format_tick, nice_ticks
from excalidraw_mcp.export.svg_exporter import excalidraw_to_svg
from excalidraw_mcp.parsers.typed_state import (
    apply_spec_patch,
    deep_merge,
    read_typed_metadata,
    typed_summary,
)
from tests.typed_samples import SAMPLES

ALL_TYPES = sorted(DIAGRAM_TYPES)

# Required on every Excalidraw element for the file to open without repair.
REQUIRED_KEYS = {"id", "type", "x", "y", "width", "height", "angle", "strokeColor", "seed"}


# ---------------------------------------------------------------------------
# Every type renders
# ---------------------------------------------------------------------------


def test_every_registered_type_has_a_sample():
    assert set(ALL_TYPES) == set(SAMPLES), "each registered type needs a sample spec"


@pytest.mark.parametrize("name", ALL_TYPES)
def test_type_renders_valid_excalidraw(name):
    doc, summary = build_typed_diagram(name, SAMPLES[name])

    assert doc["type"] == "excalidraw"
    assert doc["elements"], f"{name} produced no elements"
    assert name in summary

    for el in doc["elements"]:
        missing = REQUIRED_KEYS - el.keys()
        assert not missing, f"{name}: element {el.get('type')} missing {missing}"
        assert isinstance(el["x"], int | float)
        assert el["width"] >= 0 and el["height"] >= 0


@pytest.mark.parametrize("name", ALL_TYPES)
def test_type_round_trips_spec_into_custom_data(name):
    doc, _ = build_typed_diagram(name, SAMPLES[name])
    meta = doc["appState"]["customData"]["excalidraw_mcp"]

    assert meta["diagram_type"] == name
    assert "spec" in meta
    # The stored spec must be re-renderable without the original input.
    again, _ = build_typed_diagram(name, meta["spec"])
    assert len(again["elements"]) == len(doc["elements"])


@pytest.mark.parametrize("name", ALL_TYPES)
def test_type_exports_to_svg(name):
    doc, _ = build_typed_diagram(name, SAMPLES[name])
    svg = excalidraw_to_svg(doc)

    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "NaN" not in svg
    assert "None" not in svg


@pytest.mark.parametrize("name", ALL_TYPES)
@pytest.mark.parametrize("theme", ["default", "dark", "colorful"])
def test_type_renders_in_every_theme(name, theme):
    doc, _ = build_typed_diagram(name, SAMPLES[name], theme=theme)
    assert doc["elements"]
    assert doc["appState"]["viewBackgroundColor"]


# ---------------------------------------------------------------------------
# Layout invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ALL_TYPES)
def test_content_stays_on_canvas(name):
    """Nothing should sit at negative coordinates after normalisation."""
    doc, _ = build_typed_diagram(name, SAMPLES[name])
    for el in doc["elements"]:
        if el["type"] in ("arrow", "line"):
            xs = [el["x"] + p[0] for p in el["points"]]
            ys = [el["y"] + p[1] for p in el["points"]]
            assert min(xs) >= -1 and min(ys) >= -1, f"{name}: {el['type']} off-canvas"
        else:
            assert el["x"] >= -1 and el["y"] >= -1, f"{name}: {el['type']} off-canvas"


@pytest.mark.parametrize("name", ALL_TYPES)
def test_bound_labels_reference_a_real_container(name):
    doc, _ = build_typed_diagram(name, SAMPLES[name])
    ids = {el["id"] for el in doc["elements"]}
    for el in doc["elements"]:
        container = el.get("containerId")
        if container:
            assert container in ids, f"{name}: dangling containerId"


def test_focal_elements_get_the_accent_color():
    pal = get_palette("default")
    doc, _ = build_typed_diagram("layers", SAMPLES["layers"])
    strokes = {el["strokeColor"] for el in doc["elements"]}
    assert pal.accent in strokes, "the focal layer should carry the accent stroke"


def test_non_focal_diagram_uses_no_accent():
    spec = {"layers": [{"label": "A"}, {"label": "B"}]}
    pal = get_palette("default")
    doc, _ = build_typed_diagram("layers", spec)
    strokes = {el["strokeColor"] for el in doc["elements"]}
    assert pal.accent not in strokes


def test_title_and_subtitle_are_rendered():
    doc, _ = build_typed_diagram("it_state", SAMPLES["it_state"])
    texts = {el.get("text") for el in doc["elements"] if el["type"] == "text"}
    assert "Current-state landscape" in texts
    assert "Before the 2026 modernization" in texts


def test_chrome_renders_crisp_and_content_sketchy():
    """Gridlines at roughness 1 read as noise; bars at roughness 0 look dead."""
    doc, _ = build_typed_diagram("bar", SAMPLES["bar"])
    gridlines = [el for el in doc["elements"] if el["type"] == "line"]
    bars = [el for el in doc["elements"] if el["type"] == "rectangle"]

    assert gridlines and all(el["roughness"] == 0 for el in gridlines)
    assert bars and all(el["roughness"] == 1 for el in bars)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_unknown_type_is_rejected():
    with pytest.raises(DiagramNotFoundError):
        build_typed_diagram("sankey", {})


def test_type_lookup_normalises_separators():
    assert describe_type("dp-integration")["type"] == "dp_integration"
    assert describe_type("Org Chart")["type"] == "org_chart"


@pytest.mark.parametrize("name", ALL_TYPES)
def test_describe_type_exposes_schema_and_guidance(name):
    described = describe_type(name)
    assert described["schema"]["type"] == "object"
    assert described["use_when"] and described["avoid_when"]
    assert described["family"] in {"structural", "flow", "geometric", "chart"}


# ---------------------------------------------------------------------------
# Spec validation
# ---------------------------------------------------------------------------


def test_invalid_spec_reports_the_type():
    with pytest.raises(SpecError, match="pyramid"):
        build_typed_diagram("pyramid", {"tiers": []})


def test_line_chart_rejects_too_many_points():
    spec = {
        "x_labels": [f"p{i}" for i in range(20)],
        "series": [{"name": "s", "values": list(range(20))}],
    }
    with pytest.raises(SpecError, match="capped at 15"):
        build_typed_diagram("line", spec)


def test_bar_rejects_series_length_mismatch():
    spec = {"categories": ["a", "b"], "series": [{"name": "s", "values": [1]}]}
    with pytest.raises(SpecError, match="one value per category"):
        build_typed_diagram("bar", spec)


def test_sequence_rejects_unknown_actor():
    spec = {
        "actors": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "messages": [{"from_id": "a", "to_id": "ghost"}],
    }
    with pytest.raises(SpecError, match="declared in"):
        build_typed_diagram("sequence", spec)


def test_gantt_rejects_zero_length_task():
    spec = {"tasks": [{"label": "t", "start": 3, "end": 3}]}
    with pytest.raises(SpecError):
        build_typed_diagram("gantt", spec)


def test_swimlane_rejects_step_in_undeclared_lane():
    spec = {
        "lanes": ["A"],
        "steps": [{"id": "s1", "label": "Step", "lane": "B"}],
    }
    with pytest.raises(SpecError, match="lane list"):
        build_typed_diagram("swimlane", spec)


def test_tree_requires_a_root():
    spec = {"nodes": [{"id": "a", "label": "A", "parent": "b"},
                      {"id": "b", "label": "B", "parent": "a"}]}
    with pytest.raises(SpecError, match="root"):
        build_typed_diagram("tree", spec)


# ---------------------------------------------------------------------------
# Type-specific behaviour
# ---------------------------------------------------------------------------


def test_swimlane_keeps_steps_inside_their_lane():
    doc, _ = build_typed_diagram("swimlane", SAMPLES["swimlane"])
    boxes = {
        el["customData"]["node_id"]: el
        for el in doc["elements"]
        if el.get("customData", {}).get("node_id")
    }
    lane_of = {s["id"]: s["lane"] for s in SAMPLES["swimlane"]["steps"]}

    centers: dict[str, list[float]] = {}
    for node_id, el in boxes.items():
        centers.setdefault(lane_of[node_id], []).append(el["y"] + el["height"] / 2)

    # Every step in a lane shares one band, and bands never overlap.
    bands = {lane: (min(v), max(v)) for lane, v in centers.items()}
    for lane, (lo, hi) in bands.items():
        assert hi - lo < 1, f"{lane} steps are not aligned on one band"
    ordered = sorted(bands.values())
    assert all(a[1] < b[0] for a, b in zip(ordered, ordered[1:], strict=False))


def test_swimlane_same_lane_steps_never_share_a_column():
    """Two steps in one lane at the same flow position would overlap."""
    spec = {
        "lanes": ["Solo"],
        "steps": [
            {"id": "a", "label": "A", "lane": "Solo"},
            {"id": "b", "label": "B", "lane": "Solo"},
            {"id": "c", "label": "C", "lane": "Solo"},
        ],
    }
    doc, _ = build_typed_diagram("swimlane", spec)
    boxes = [
        el for el in doc["elements"] if el.get("customData", {}).get("node_id")
    ]
    xs = sorted((el["x"], el["x"] + el["width"]) for el in boxes)
    assert all(a[1] <= b[0] for a, b in zip(xs, xs[1:], strict=False))


def test_state_start_and_end_render_as_markers_not_boxes():
    doc, _ = build_typed_diagram("state", SAMPLES["state"])
    ellipses = [el for el in doc["elements"] if el["type"] == "ellipse"]
    # Filled start dot, plus the end ring and its inner dot.
    assert len(ellipses) >= 3


def test_pyramid_apex_is_a_triangle():
    doc, _ = build_typed_diagram("pyramid", SAMPLES["pyramid"])
    polys = [el for el in doc["elements"] if el["type"] == "line"]
    # Closed polys repeat the first point, so a triangle has 4 stored points.
    assert any(len(el["points"]) == 4 for el in polys), "apex tier should be a triangle"
    assert all(el.get("polygon") for el in polys)


def test_funnel_widths_track_values():
    spec = {
        "mode": "funnel",
        "tiers": [
            {"label": "Visit", "value": 1000},
            {"label": "Trial", "value": 250},
            {"label": "Paid", "value": 50},
        ],
    }
    doc, _ = build_typed_diagram("pyramid", spec)
    polys = [el for el in doc["elements"] if el["type"] == "line"]
    widths = [el["width"] for el in polys]
    assert widths == sorted(widths, reverse=True), "funnel tiers must narrow downward"


def test_sequence_never_points_backwards_in_time():
    doc, _ = build_typed_diagram("sequence", SAMPLES["sequence"])
    arrows = [el for el in doc["elements"] if el["type"] == "arrow"]
    for el in arrows:
        ys = [el["y"] + p[1] for p in el["points"]]
        assert ys[-1] >= ys[0] - 1, "a message arrow must not travel upward"


def test_scatter_legend_appears_only_with_groups():
    doc, _ = build_typed_diagram("scatter", SAMPLES["scatter"])
    texts = {el.get("text") for el in doc["elements"] if el["type"] == "text"}
    assert {"core", "edge"} <= texts


# ---------------------------------------------------------------------------
# Scales
# ---------------------------------------------------------------------------


def test_nice_ticks_are_round_and_cover_the_data():
    ticks = nice_ticks(0, 97)
    assert ticks[0] <= 0 and ticks[-1] >= 97
    assert ticks == sorted(ticks)
    spacing = {round(b - a, 6) for a, b in zip(ticks, ticks[1:], strict=False)}
    assert len(spacing) == 1, "ticks must be evenly spaced"


def test_nice_ticks_handles_a_flat_domain():
    ticks = nice_ticks(5, 5)
    assert len(ticks) >= 2
    assert ticks[0] < 5 < ticks[-1]


def test_nice_ticks_produce_clean_labels():
    assert all("0000000" not in format_tick(t) for t in nice_ticks(0, 1))


def test_format_tick_compacts_large_numbers():
    assert format_tick(1500) == "1.5k"
    assert format_tick(2_000_000) == "2M"
    assert format_tick(3.0) == "3"


def test_linear_scale_maps_domain_onto_range():
    scale = LinearScale(0, 10, 100, 0)  # inverted, as a y axis is
    assert scale(0) == 100
    assert scale(10) == 0
    assert scale(5) == 50


def test_band_scale_keeps_bands_inside_the_range():
    band = BandScale(["a", "b", "c"], 0, 300, padding=0.2)
    for cat in ["a", "b", "c"]:
        assert band.start(cat) >= 0
        assert band.start(cat) + band.band_width <= 300


# ---------------------------------------------------------------------------
# Drawable primitives
# ---------------------------------------------------------------------------


def test_polyline_midpoint_is_halfway_by_arc_length():
    # A two-point line's "middle index" is its endpoint - the bug this guards.
    assert _polyline_midpoint([(0, 0), (10, 0)]) == (5, 0)
    assert _polyline_midpoint([(0, 0), (10, 0), (10, 10)]) == (10, 0)


def test_connector_label_sits_at_the_midpoint_not_the_target():
    from excalidraw_mcp.core.drawable import Connector

    elements = drawables_to_elements(
        [Connector(points=[(0, 0), (200, 0)], label="mid")]
    )
    label = next(el for el in elements if el["type"] == "text")
    assert 80 < label["x"] + label["width"] / 2 < 120


def test_bounds_account_for_text_alignment():
    right = Text(x=100, y=0, text="value", align="right")
    min_x, _, max_x, _ = drawable_bounds([right])
    assert min_x < 100 and max_x <= 101


def test_normalize_moves_content_to_the_margin():
    items = [Box(x=-500, y=-300, width=10, height=10)]
    min_x, min_y, _, _ = drawable_bounds(normalize(items, margin=60))
    assert (round(min_x), round(min_y)) == (60, 60)


def test_closed_poly_is_filled_and_open_poly_is_not():
    from excalidraw_mcp.core.drawable import Style

    style = Style(fill="#ff0000")
    tri = Poly(points=[(0, 0), (10, 0), (5, 9)], closed=True, style=style)
    closed = drawables_to_elements([tri])
    open_ = drawables_to_elements([Poly(points=[(0, 0), (10, 0)], style=style)])

    assert closed[0]["backgroundColor"] == "#ff0000"
    assert closed[0]["points"][0] == closed[0]["points"][-1]
    assert open_[0]["backgroundColor"] == "transparent"


def test_rotated_text_is_positioned_by_its_centre():
    import math

    elements = drawables_to_elements([Text(x=0, y=0, text="axis", angle=-math.pi / 2)])
    el = elements[0]
    assert el["angle"] != 0
    assert el["x"] + el["width"] / 2 == pytest.approx(0, abs=0.01)


# ---------------------------------------------------------------------------
# Spec-based editing
# ---------------------------------------------------------------------------


def test_deep_merge_replaces_lists_wholesale():
    base = {"a": {"b": 1, "c": 2}, "items": [1, 2, 3]}
    merged = deep_merge(base, {"a": {"c": 9}, "items": [7]})
    assert merged == {"a": {"b": 1, "c": 9}, "items": [7]}
    assert base["items"] == [1, 2, 3], "merge must not mutate the input"


def test_patch_spec_re_renders_in_place(tmp_path):
    doc, _ = build_typed_diagram("pyramid", SAMPLES["pyramid"])
    path = save_excalidraw(doc, tmp_path / "p.excalidraw")

    apply_spec_patch(path, {"title": "Revised strategy"})

    updated = json.loads(path.read_text())
    texts = {el.get("text") for el in updated["elements"] if el["type"] == "text"}
    assert "Revised strategy" in texts
    assert "Test strategy" not in texts

    meta = read_typed_metadata(path)
    assert meta["spec"]["title"] == "Revised strategy"
    # Untouched keys survive the patch.
    assert len(meta["spec"]["tiers"]) == 3


def test_patch_rejects_a_non_typed_diagram(tmp_path):
    path = tmp_path / "plain.excalidraw"
    path.write_text(json.dumps({"type": "excalidraw", "elements": [], "appState": {}}))
    with pytest.raises(ValueError, match="not a typed diagram"):
        apply_spec_patch(path, {"title": "x"})


def test_typed_summary_includes_the_spec(tmp_path):
    doc, _ = build_typed_diagram("venn", SAMPLES["venn"])
    path = save_excalidraw(doc, tmp_path / "v.excalidraw")
    summary = typed_summary(path)
    assert "venn" in summary
    assert "Security" in summary


def test_typed_summary_is_empty_for_graph_diagrams(tmp_path):
    path = tmp_path / "plain.excalidraw"
    path.write_text(json.dumps({"type": "excalidraw", "elements": [], "appState": {}}))
    assert typed_summary(path) == ""


# ---------------------------------------------------------------------------
# Companion skill
# ---------------------------------------------------------------------------


def test_skill_docs_are_in_sync_with_the_registry():
    """Guidance is authored once in the registry and projected into the skill.

    If this fails, run: python scripts/sync_skill_docs.py
    """
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "sync_skill_docs.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_type_appears_in_the_skill_selection_table():
    from pathlib import Path

    skill = (
        Path(__file__).resolve().parent.parent
        / "skills"
        / "excalidraw-architect"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    table = skill.split("<!-- BEGIN:selection-table -->")[1].split("<!-- END")[0]
    for name in ALL_TYPES:
        assert f"`{name}`" in table, f"{name} missing from the skill selection table"
