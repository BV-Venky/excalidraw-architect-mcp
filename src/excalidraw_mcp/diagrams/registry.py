"""The diagram-type registry.

One entry per type: its spec model, its layout function, and the guidance an
LLM needs to pick it correctly. That guidance is served through
``list_diagram_types`` / ``get_diagram_schema`` so the MCP works in clients
that have no access to the companion skill.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from excalidraw_mcp.core.drawable import Drawable, drawable_bounds, normalize, translate
from excalidraw_mcp.core.models import ThemeName
from excalidraw_mcp.core.palette import Palette, get_palette
from excalidraw_mcp.diagrams import charts, flow, geometric, structural
from excalidraw_mcp.diagrams.base import SpecError, TypedSpec, title_block
from excalidraw_mcp.engine.draw_renderer import build_drawable_file

LayoutFn = Callable[[Any, Palette], list[Drawable]]


class DiagramNotFoundError(KeyError):
    """Raised for an unknown diagram type."""


@dataclass(frozen=True)
class DiagramType:
    name: str
    family: str  # structural | flow | geometric | chart
    spec: type[TypedSpec]
    layout: LayoutFn
    use_when: str
    avoid_when: str


def _t(
    name: str,
    family: str,
    spec: type[TypedSpec],
    layout: LayoutFn,
    use_when: str,
    avoid_when: str,
) -> tuple[str, DiagramType]:
    return name, DiagramType(name, family, spec, layout, use_when, avoid_when)


DIAGRAM_TYPES: dict[str, DiagramType] = dict(
    [
        # -- structural -----------------------------------------------------
        _t(
            "tree", "structural", structural.TreeSpec, structural.layout_tree,
            "Parent -> children: taxonomies, file hierarchies, decision breakdowns.",
            "Use org_chart for people or teams; use nested when containment is the point.",
        ),
        _t(
            "org_chart", "structural", structural.OrgChartSpec, structural.layout_org_chart,
            "Human, team, or agent ownership: reporting lines, escalation, routing.",
            "Not for system components -- that is architecture.",
        ),
        _t(
            "state", "structural", structural.StateSpec, structural.layout_state,
            "States, transitions, and guards. Order lifecycles, retry machines, approval flows.",
            "Not for time-ordered messages between actors -- that is sequence.",
        ),
        _t(
            "nested", "structural", structural.NestedSpec, structural.layout_nested,
            "Hierarchy by containment or scope: bounded contexts, module trees, org scopes.",
            "Beyond three levels of nesting, split into an overview plus a detail diagram.",
        ),
        _t(
            "layers", "structural", structural.LayersSpec, structural.layout_layers,
            "Stacked abstraction levels where each layer sits on the one below.",
            "If the layers exchange traffic in both directions, use architecture instead.",
        ),
        _t(
            "medallion", "structural", structural.MedallionSpec, structural.layout_medallion,
            "Multi-tier data storage with quality levels: bronze/silver/gold, raw/curated/serving.",
            "Use data_flow when the emphasis is who does what rather than where data rests.",
        ),
        _t(
            "er", "structural", structural.ErSpec, structural.layout_er,
            "Entities, their fields, and relationships. Data models and schema documentation.",
            "Above ~8 entities, split by bounded context.",
        ),
        _t(
            "high_level", "structural", structural.HighLevelSpec, structural.layout_high_level,
            "End-to-end stack drawn inside one named boundary (a cluster, an account, a VPC).",
            "Use architecture when the boundary is not the point.",
        ),
        _t(
            "it_state", "structural", structural.ItStateSpec, structural.layout_it_state,
            "Legacy landscape grouped by phase or department; the 'before' state.",
            "Use architecture for a target-state design.",
        ),
        # -- flow -----------------------------------------------------------
        _t(
            "swimlane", "flow", flow.SwimlaneSpec, flow.layout_swimlane,
            "Cross-functional process where step ownership matters. Handoffs are the story.",
            "If every step has the same owner, use flowchart.",
        ),
        _t(
            "process", "flow", flow.ProcessSpec, flow.layout_process,
            "Multi-actor sequential workflow drawn as vertical actor columns with data handoffs.",
            "Use swimlane for horizontal lanes and a wider flow.",
        ),
        _t(
            "data_flow", "flow", flow.DataFlowSpec, flow.layout_data_flow,
            "A pipeline where each stage is tagged with the role that owns it.",
            "Use medallion when storage tiers, not roles, are the subject.",
        ),
        _t(
            "dp_integration", "flow", flow.DpIntegrationSpec, flow.layout_dp_integration,
            "Integration topology of a platform: sources -> core -> consumers.",
            "Use architecture when the core needs to be decomposed in detail.",
        ),
        _t(
            "sequence", "flow", flow.SequenceSpec, flow.layout_sequence,
            "Time-ordered messages between actors: API traces, protocols, incident replays.",
            "Never draw a message arrow that points backwards in time; use state for lifecycles.",
        ),
        # -- geometric ------------------------------------------------------
        _t(
            "timeline", "geometric", geometric.TimelineSpec, geometric.layout_timeline,
            "Events positioned in time along a single axis. Roadmaps, incident chronologies.",
            "Use gantt when items have duration rather than a single instant.",
        ),
        _t(
            "quadrant", "geometric", geometric.QuadrantSpec, geometric.layout_quadrant,
            "Two-axis positioning and prioritization. Add quadrant_labels for a consultant 2x2.",
            "Use scatter when the axes carry real units rather than relative position.",
        ),
        _t(
            "pyramid", "geometric", geometric.PyramidSpec, geometric.layout_pyramid,
            "Ranked hierarchy (mode='pyramid') or conversion drop-off (mode='funnel').",
            "Use bar when the values matter more than the ranking.",
        ),
        _t(
            "venn", "geometric", geometric.VennSpec, geometric.layout_venn,
            "Overlap between two or three sets, where the intersection is the insight.",
            "Four or more sets is unreadable -- use a table.",
        ),
        _t(
            "loop", "geometric", geometric.LoopSpec, geometric.layout_loop,
            "A reinforcing cycle; add a hub for shared state the stations write back to.",
            "Use process when the flow has a real beginning and end.",
        ),
        _t(
            "gantt", "geometric", geometric.GanttSpec, geometric.layout_gantt,
            "Tasks and phases with duration on a timeline. Shows overlap and parallel tracks.",
            "Above ~12 tasks, collapse to a phase-level view.",
        ),
        # -- charts ---------------------------------------------------------
        _t(
            "bar", "chart", charts.BarSpec, charts.layout_bar,
            "Quantitative comparison across categories. Multiple series render as grouped bars.",
            "Use line when the x axis is continuous time.",
        ),
        _t(
            "line", "chart", charts.LineSpec, charts.layout_line,
            "Continuous trends over an ordered axis. Capped at 15 points per series.",
            "Use bar for a handful of discrete categories.",
        ),
        _t(
            "scatter", "chart", charts.ScatterSpec, charts.layout_scatter,
            "Distribution and correlation between two continuous variables.",
            "Use quadrant when position is relative judgement rather than measurement.",
        ),
    ]
)


def list_types() -> list[DiagramType]:
    return list(DIAGRAM_TYPES.values())


def get_type(name: str) -> DiagramType:
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    if key not in DIAGRAM_TYPES:
        raise DiagramNotFoundError(
            f"unknown diagram type '{name}'. Known types: {', '.join(sorted(DIAGRAM_TYPES))}"
        )
    return DIAGRAM_TYPES[key]


def describe_type(name: str) -> dict[str, Any]:
    """Return the JSON schema plus selection guidance for one type."""
    dt = get_type(name)
    return {
        "type": dt.name,
        "family": dt.family,
        "use_when": dt.use_when,
        "avoid_when": dt.avoid_when,
        "schema": dt.spec.model_json_schema(),
    }


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build_typed_diagram(
    diagram_type: str,
    spec_data: dict[str, Any],
    *,
    theme: ThemeName | str = ThemeName.DEFAULT,
) -> tuple[dict[str, Any], str]:
    """Validate a spec, lay it out, and assemble the .excalidraw document.

    Returns (document, human-readable summary).
    """
    dt = get_type(diagram_type)
    try:
        spec: TypedSpec = dt.spec.model_validate(spec_data)
    except ValidationError as exc:
        raise SpecError(f"invalid spec for '{dt.name}': {exc}") from exc

    pal = get_palette(theme)
    items: list[Drawable] = dt.layout(spec, pal)
    if not items:
        raise SpecError(f"'{dt.name}' layout produced nothing to draw")

    items = normalize(items, margin=60.0)

    # The title block is applied centrally so every type places it identically.
    header, consumed = title_block(spec.title, spec.subtitle, pal, 60.0, 40.0)
    if consumed:
        items = translate(items, 0.0, consumed + 16.0)
        items = header + items

    min_x, min_y, max_x, max_y = drawable_bounds(items)
    doc = build_drawable_file(
        items,
        theme,
        diagram_type=dt.name,
        spec=spec.model_dump(mode="json", exclude_none=True),
    )

    summary = (
        f"type: {dt.name} ({dt.family})\n"
        f"elements: {len(doc['elements'])}\n"
        f"canvas: {round(max_x - min_x)}x{round(max_y - min_y)}px"
    )
    return doc, summary
