"""Flow diagram types: work moving across actors, roles, and time.

swimlane · process · data_flow · dp_integration · sequence

Swimlane and process share one engine -- lanes plus flow-order layering, with
the cross axis pinned to the owner's band. Sequence is the odd one out: time
is an axis, so its layout is fully deterministic and ignores layering.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from excalidraw_mcp.core.drawable import Box, Connector, Drawable, Style, Text
from excalidraw_mcp.core.palette import Palette
from excalidraw_mcp.diagrams.base import (
    BODY_SIZE,
    LABEL_SIZE,
    Item,
    TypedSpec,
    assign_layers,
    caption,
    connector_style,
    eyebrow,
    hairline,
    node_box,
    require,
    uniform_box_width,
    zone_style,
)

# ---------------------------------------------------------------------------
# Swimlane / process (shared lane engine)
# ---------------------------------------------------------------------------


class Step(BaseModel):
    id: str
    label: str
    lane: str
    focal: bool = False


class Flow(BaseModel):
    from_id: str
    to_id: str
    label: str | None = None
    dashed: bool = False
    focal: bool = False


class SwimlaneSpec(TypedSpec):
    """Cross-functional flow: one lane per actor, steps owned by exactly one."""

    lanes: list[str] = Field(..., min_length=1)
    steps: list[Step] = Field(..., min_length=1)
    connections: list[Flow] = Field(default_factory=list)


class ProcessSpec(TypedSpec):
    """Multi-actor sequential workflow drawn as vertical actor columns."""

    actors: list[str] = Field(..., min_length=1)
    steps: list[Step] = Field(..., min_length=1)
    connections: list[Flow] = Field(default_factory=list)


_STEP_W = 190.0
_STEP_H = 66.0
_LANE_PAD = 26.0
_LANE_LABEL = 128.0
_COL_GAP = 56.0


def _lane_columns(steps: list[Step], connections: list[Flow]) -> dict[str, int]:
    """Assign a flow-order column to each step, avoiding same-lane collisions.

    Layering gives the flow position; the collision pass then pushes any two
    steps that would land in the same lane *and* column apart, which is the
    only way a lane band can stay one row tall.
    """
    keys = [s.id for s in steps]
    edges = [(c.from_id, c.to_id) for c in connections]
    layer = assign_layers(keys, edges)

    taken: set[tuple[str, int]] = set()
    lane_of = {s.id: s.lane for s in steps}
    for key in sorted(keys, key=lambda k: (layer[k], keys.index(k))):
        col = layer[key]
        while (lane_of[key], col) in taken:
            col += 1
        layer[key] = col
        taken.add((lane_of[key], col))
    return layer


def _lane_layout(
    lanes: list[str],
    steps: list[Step],
    connections: list[Flow],
    pal: Palette,
    *,
    vertical: bool,
) -> list[Drawable]:
    known = set(lanes)
    require(
        all(s.lane in known for s in steps),
        "every step's lane must appear in the lane list",
    )

    step_w = uniform_box_width([s.label for s in steps], min_w=_STEP_W)
    col = _lane_columns(steps, connections)
    n_cols = max(col.values()) + 1 if col else 1
    lane_index = {name: i for i, name in enumerate(lanes)}

    lane_extent = _STEP_H + _LANE_PAD * 2 if not vertical else step_w + _LANE_PAD * 2
    col_pitch = (step_w + _COL_GAP) if not vertical else (_STEP_H + _COL_GAP)
    track_len = n_cols * col_pitch - _COL_GAP + _LANE_PAD * 2

    out: list[Drawable] = []
    rects: dict[str, tuple[float, float, float, float]] = {}

    # Lane bands
    for name in lanes:
        i = lane_index[name]
        if vertical:
            x = _LANE_LABEL + i * lane_extent
            out.append(Box(x=x, y=0, width=lane_extent, height=track_len, style=zone_style(pal)))
            out.append(
                Text(
                    x=x + lane_extent / 2,
                    y=-24,
                    text=name.upper(),
                    size=11,
                    color=pal.muted,
                    align="center",
                )
            )
        else:
            y = i * lane_extent
            out.append(
                Box(x=_LANE_LABEL, y=y, width=track_len, height=lane_extent, style=zone_style(pal))
            )
            out.append(eyebrow(0, y + lane_extent / 2 - 6, name, pal))
            if i > 0:
                out.append(hairline((_LANE_LABEL, y), (_LANE_LABEL + track_len, y), pal))

    # Steps
    for s in steps:
        c = col[s.id]
        li = lane_index[s.lane]
        if vertical:
            x = _LANE_LABEL + li * lane_extent + _LANE_PAD
            y = _LANE_PAD + c * col_pitch
            w, h = step_w, _STEP_H
        else:
            x = _LANE_LABEL + _LANE_PAD + c * col_pitch
            y = li * lane_extent + _LANE_PAD
            w, h = step_w, _STEP_H
        rects[s.id] = (x, y, w, h)
        out.append(node_box(x, y, w, h, s.label, pal, focal=s.focal, node_id=s.id))

    # Handoffs (lane changes) are the load-bearing edges, so they read heavier
    # than within-lane steps -- but in *weight*, not color. In most lane
    # diagrams nearly every edge is a handoff, so accenting them all would
    # spend the one signal the palette reserves. Accent stays opt-in per edge.
    lane_of = {s.id: s.lane for s in steps}
    for c in connections:
        if c.from_id not in rects or c.to_id not in rects:
            continue
        a, b = rects[c.from_id], rects[c.to_id]
        handoff = lane_of[c.from_id] != lane_of[c.to_id]
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        if vertical:
            pts = [(ax + aw / 2, ay + ah), (bx + bw / 2, by)]
        elif abs(ay - by) < 1:
            pts = [(ax + aw, ay + ah / 2), (bx, by + bh / 2)]
        else:
            # Crossing lanes: leave from the face that points at the target.
            pts = [
                (ax + aw / 2, ay + ah if by > ay else ay),
                (bx + bw / 2, by + bh if by < ay else by),
            ]
        style = connector_style(pal, focal=c.focal, dashed=c.dashed)
        if handoff and not c.focal:
            style = style.merge(stroke_width=2.5)
        out.append(
            Connector(
                points=pts,
                label=c.label,
                style=style,
                from_node=c.from_id,
                to_node=c.to_id,
            )
        )
    return out


def layout_swimlane(spec: SwimlaneSpec, pal: Palette) -> list[Drawable]:
    return _lane_layout(spec.lanes, spec.steps, spec.connections, pal, vertical=False)


def layout_process(spec: ProcessSpec, pal: Palette) -> list[Drawable]:
    return _lane_layout(spec.actors, spec.steps, spec.connections, pal, vertical=True)


# ---------------------------------------------------------------------------
# Data flow (role-scoped pipeline)
# ---------------------------------------------------------------------------


class DataStep(BaseModel):
    label: str
    role: str | None = None
    note: str | None = None
    focal: bool = False


class DataFlowSpec(TypedSpec):
    """Pipeline stages, each tagged with the role that owns it."""

    steps: list[DataStep] = Field(..., min_length=2)


def layout_data_flow(spec: DataFlowSpec, pal: Palette) -> list[Drawable]:
    step_w = uniform_box_width([s.label for s in spec.steps], min_w=186.0)
    step_h = 74.0
    gap = 70.0
    out: list[Drawable] = []

    for i, step in enumerate(spec.steps):
        x = i * (step_w + gap)
        if step.role:
            out.append(eyebrow(x + step_w / 2, -22, step.role, pal, align="center"))
        out.append(node_box(x, 0, step_w, step_h, step.label, pal, focal=step.focal))
        if step.note:
            out.append(
                caption(x + step_w / 2, step_h + 14, step.note, pal, size=12, align="center")
            )
        if i < len(spec.steps) - 1:
            out.append(
                Connector(
                    points=[(x + step_w, step_h / 2), (x + step_w + gap, step_h / 2)],
                    style=connector_style(pal),
                    curved=False,
                )
            )
    return out


# ---------------------------------------------------------------------------
# DP integration (sources -> core -> consumers)
# ---------------------------------------------------------------------------


class CoreBlock(BaseModel):
    label: str = "Data Platform"
    components: list[str] = Field(default_factory=list)


class DpIntegrationSpec(TypedSpec):
    """Integration topology: producers on the left, consumers on the right."""

    sources: list[Item] = Field(..., min_length=1)
    core: CoreBlock = Field(default_factory=CoreBlock)
    consumers: list[Item] = Field(..., min_length=1)


def layout_dp_integration(spec: DpIntegrationSpec, pal: Palette) -> list[Drawable]:
    box_w = uniform_box_width(
        [i.label for i in [*spec.sources, *spec.consumers]],
        min_w=176.0,
        size=BODY_SIZE,
    )
    box_h = 58.0
    v_gap = 18.0
    col_gap = 130.0
    core_w = uniform_box_width(
        [spec.core.label, *spec.core.components], min_w=230.0, padding=56.0
    )
    core_pad = 22.0
    core_header = 44.0
    comp_h = 46.0
    comp_gap = 12.0

    core_h = max(
        core_header + core_pad + len(spec.core.components) * (comp_h + comp_gap),
        180.0,
    )
    src_h = len(spec.sources) * (box_h + v_gap) - v_gap
    con_h = len(spec.consumers) * (box_h + v_gap) - v_gap
    total_h = max(src_h, con_h, core_h)

    core_x = box_w + col_gap
    out: list[Drawable] = [
        Box(
            x=core_x,
            y=(total_h - core_h) / 2,
            width=core_w,
            height=core_h,
            style=Style(
                stroke=pal.accent,
                fill=pal.accent_soft,
                stroke_width=2,
                roughness=1,
            ),
        ),
        Text(
            x=core_x + core_w / 2,
            y=(total_h - core_h) / 2 + 14,
            text=spec.core.label,
            size=LABEL_SIZE,
            color=pal.accent,
            align="center",
        ),
    ]

    cy = (total_h - core_h) / 2 + core_header
    for comp in spec.core.components:
        out.append(
            Box(
                x=core_x + core_pad,
                y=cy,
                width=core_w - core_pad * 2,
                height=comp_h,
                label=comp,
                label_size=BODY_SIZE,
                label_color=pal.ink,
                style=Style(stroke=pal.muted, fill=pal.canvas, stroke_width=1.2, roughness=1),
            )
        )
        cy += comp_h + comp_gap

    # Fan the edges across distinct points on the core's faces. Aiming every
    # arrow at the single midpoint stacks the arrowheads into an ink blob.
    core_top = (total_h - core_h) / 2

    def core_port(index: int, count: int) -> float:
        return core_top + core_h * (index + 1) / (count + 1)

    y = (total_h - src_h) / 2
    for i, s in enumerate(spec.sources):
        out.append(node_box(0, y, box_w, box_h, s.label, pal, focal=s.focal, size=BODY_SIZE))
        out.append(
            Connector(
                points=[(box_w, y + box_h / 2), (core_x, core_port(i, len(spec.sources)))],
                style=connector_style(pal),
                curved=False,
            )
        )
        y += box_h + v_gap

    cons_x = core_x + core_w + col_gap
    y = (total_h - con_h) / 2
    for i, c in enumerate(spec.consumers):
        out.append(node_box(cons_x, y, box_w, box_h, c.label, pal, focal=c.focal, size=BODY_SIZE))
        out.append(
            Connector(
                points=[
                    (core_x + core_w, core_port(i, len(spec.consumers))),
                    (cons_x, y + box_h / 2),
                ],
                style=connector_style(pal, focal=c.focal),
                curved=False,
            )
        )
        y += box_h + v_gap

    return out


# ---------------------------------------------------------------------------
# Sequence
# ---------------------------------------------------------------------------


class Actor(BaseModel):
    id: str
    label: str
    focal: bool = False


class Message(BaseModel):
    from_id: str
    to_id: str
    label: str | None = None
    kind: str = "call"  # call | return
    focal: bool = False


class SequenceSpec(TypedSpec):
    """Time-ordered messages between actors, newest at the bottom."""

    actors: list[Actor] = Field(..., min_length=2)
    messages: list[Message] = Field(..., min_length=1)


_ACTOR_W = 170.0
_ACTOR_H = 58.0
_ACTOR_GAP = 90.0
_MSG_GAP = 62.0
_SEQ_TOP = 96.0


def layout_sequence(spec: SequenceSpec, pal: Palette) -> list[Drawable]:
    ids = {a.id for a in spec.actors}
    require(
        all(m.from_id in ids and m.to_id in ids for m in spec.messages),
        "every message must reference actors declared in `actors`",
    )

    centers: dict[str, float] = {}
    out: list[Drawable] = []
    for i, actor in enumerate(spec.actors):
        x = i * (_ACTOR_W + _ACTOR_GAP)
        centers[actor.id] = x + _ACTOR_W / 2
        out.append(node_box(x, 0, _ACTOR_W, _ACTOR_H, actor.label, pal, focal=actor.focal))

    bottom = _SEQ_TOP + len(spec.messages) * _MSG_GAP

    # Lifelines: dashed hairlines, drawn before the messages so arrows sit on top.
    for actor in spec.actors:
        out.append(
            hairline((centers[actor.id], _ACTOR_H), (centers[actor.id], bottom), pal, dashed=True)
        )

    # Activation bars span an actor's first to last participation. Deriving
    # them rather than asking for explicit open/close pairs makes the "bar that
    # never closes" anti-pattern unrepresentable.
    for actor in spec.actors:
        involved = [
            i for i, m in enumerate(spec.messages) if actor.id in (m.from_id, m.to_id)
        ]
        if len(involved) < 2:
            continue
        top = _SEQ_TOP + involved[0] * _MSG_GAP - 10
        end = _SEQ_TOP + involved[-1] * _MSG_GAP + 10
        out.append(
            Box(
                x=centers[actor.id] - 5,
                y=top,
                width=10,
                height=end - top,
                style=Style(
                    stroke=pal.muted,
                    fill=pal.surface_alt,
                    stroke_width=1,
                    roughness=0,
                    rounded=False,
                ),
            )
        )

    for i, msg in enumerate(spec.messages):
        y = _SEQ_TOP + i * _MSG_GAP
        x1, x2 = centers[msg.from_id], centers[msg.to_id]
        style = connector_style(pal, focal=msg.focal, dashed=msg.kind == "return")

        if msg.from_id == msg.to_id:
            # Self-message: a short U-loop back onto the same lifeline.
            out.append(
                Connector(
                    points=[(x1 + 5, y), (x1 + 74, y), (x1 + 74, y + 26), (x1 + 5, y + 26)],
                    label=msg.label,
                    style=style,
                    curved=False,
                )
            )
            continue

        sign = 1 if x2 > x1 else -1
        out.append(
            Connector(
                points=[(x1 + 6 * sign, y), (x2 - 6 * sign, y)],
                label=msg.label,
                style=style,
                curved=False,
            )
        )
    return out
