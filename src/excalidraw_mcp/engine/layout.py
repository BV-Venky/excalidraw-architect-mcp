"""Sugiyama hierarchical layout engine using grandalf.

The LLM never guesses coordinates. It provides a relationship map and this
module computes the optimal non-overlapping layout.

Grandalf always computes a top-down layout. For other directions we:
  1. Swap node dimensions fed to grandalf (so it allocates the right space)
  2. Swap spacing parameters
  3. Transform the resulting coordinates back to screen space
  4. Apply adaptive per-layer gaps based on edge label content
"""

from __future__ import annotations

from grandalf.graphs import Edge as GEdge
from grandalf.graphs import Graph as GGraph
from grandalf.graphs import Vertex as GVertex
from grandalf.layouts import SugiyamaLayout

from excalidraw_mcp.core.components import detect_component
from excalidraw_mcp.core.models import (
    DiagramGraph,
    Direction,
    Edge,
    EdgeStyle,
    LayoutResult,
    Node,
    PositionedEdge,
    PositionedNode,
    ShapeType,
)

# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------

CHAR_WIDTH = 9.0
LINE_HEIGHT = 24.0
PADDING_H = 40.0
PADDING_V = 20.0
BADGE_HEIGHT = 18.0
MIN_NODE_WIDTH = 140.0
MIN_NODE_HEIGHT = 55.0

# Layer gap adapts to edge label content, clamped to this range.
# MIN keeps unlabeled edges readable; MAX prevents verbose labels from
# blowing up the diagram into scroll-land.
MIN_LAYER_GAP = 80.0
MAX_LAYER_GAP = 300.0

SIBLING_GAP = 60.0
COMPONENT_GAP = 80.0  # extra space between disconnected sub-graphs

# Hub node stretching: nodes with >= this many fan-out or fan-in edges
# auto-stretch to span their connected peers.
HUB_THRESHOLD = 3
HUB_PADDING = 20.0
MAX_HUB_STRETCH = 5.0  # hub nodes stretch at most this factor of their natural size

# Tracks original (pre-stretch) sizes so repeated stretch calls don't compound.
_hub_natural_sizes: dict[str, tuple[float, float]] = {}

# Fan-out targets of hub nodes get extra spacing for clean arrow divergence.
HUB_FAN_GAP = SIBLING_GAP * 2.0

# Extra gap between auxiliary (non-solid-edge-only) nodes and core nodes.
AUXILIARY_EXTRA_GAP = COMPONENT_GAP

# Long diagonal arrows get a gentle arc when the sibling distance exceeds
# this fraction of the layer distance and the layer span is large enough.
_ARC_LAYER_THRESHOLD = MIN_LAYER_GAP * 2.5
_ARC_SIBLING_RATIO = 0.5

# Arrows stay this far from node corners to avoid visual clipping.
EDGE_MARGIN = 8.0

# Edge label measurement
LABEL_CHAR_WIDTH = 8.0
LABEL_PADDING = 50.0


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(val, hi))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _diamond_border_offset(pos: float, center: float, half_w: float, half_h: float) -> float:
    """Extra inset from bounding-box edge to the diamond border at *pos*.

    For a diamond centered at (center, cy) with half-extents (half_w, half_h),
    the border y at a given x is offset inward by |pos - center| * half_h / half_w.
    """
    if half_w == 0:
        return 0.0
    return abs(pos - center) / half_w * half_h


def _estimate_node_size(node: Node) -> tuple[float, float]:
    """Estimate width and height based on label text and badge presence."""
    style = detect_component(node.label, node.component_type)
    has_badge = bool(style.badge)

    lines = node.label.split("\n")
    max_line_len = max(len(line) for line in lines)
    text_width = max_line_len * CHAR_WIDTH + PADDING_H
    text_height = len(lines) * LINE_HEIGHT + PADDING_V

    if has_badge:
        badge_text_width = len(style.badge) * CHAR_WIDTH + 16
        text_width = max(text_width, badge_text_width)
        text_height += BADGE_HEIGHT

    width = max(text_width, MIN_NODE_WIDTH)
    height = max(text_height, MIN_NODE_HEIGHT)

    return width, height


class _VertexData:
    """Attached to each grandalf vertex to carry dimensions."""

    def __init__(self, w: float, h: float):
        self.w = w
        self.h = h


def _is_horizontal(direction: Direction) -> bool:
    return direction in (Direction.LEFT_RIGHT, Direction.RIGHT_LEFT)


def _measure_edge_label_extent(label: str | None, direction: Direction) -> float:
    """How much space an edge label needs along the *layer* axis.

    For LR/RL the layer axis is horizontal so text *width* matters.
    For TD/BU the layer axis is vertical so text *height* matters.
    """
    if not label:
        return 0.0
    lines = label.split("\n")
    if _is_horizontal(direction):
        max_line = max(len(line) for line in lines)
        return max_line * LABEL_CHAR_WIDTH + LABEL_PADDING
    return len(lines) * LINE_HEIGHT + LABEL_PADDING


# ---------------------------------------------------------------------------
# Layout computation
# ---------------------------------------------------------------------------


def compute_layout(graph: DiagramGraph) -> LayoutResult:
    """Run Sugiyama layout and return positioned elements.

    * Layer gaps adapt to edge label sizes (clamped to
      [MIN_LAYER_GAP, MAX_LAYER_GAP]) so short labels stay compact and
      verbose labels don't explode the canvas.
    * Disconnected sub-graphs are stacked so they never overlap.
    """
    if not graph.nodes:
        return LayoutResult()

    _hub_natural_sizes.clear()

    direction = graph.direction
    horizontal = _is_horizontal(direction)

    node_sizes: dict[str, tuple[float, float]] = {}
    for node in graph.nodes:
        node_sizes[node.id] = _estimate_node_size(node)

    # --- entry-point compression: remove leaf sources from Sugiyama -----
    # Leaf sources (0 incoming, exactly 1 outgoing) waste a full layer.
    # Exclude them from grandalf so their child moves up to a shallower
    # layer, then re-insert them as compact prefixes after layout.
    in_count: dict[str, int] = {}
    out_targets: dict[str, list[str]] = {}
    for edge in graph.edges:
        in_count[edge.to_id] = in_count.get(edge.to_id, 0) + 1
        out_targets.setdefault(edge.from_id, []).append(edge.to_id)

    leaf_sources: dict[str, str] = {}  # leaf_id -> child_id
    for node in graph.nodes:
        targets = out_targets.get(node.id, [])
        if in_count.get(node.id, 0) == 0 and len(targets) == 1:
            leaf_sources[node.id] = targets[0]

    # Skip compression when multiple leaf sources share the same child --
    # let Sugiyama handle their relative positioning naturally.
    child_leaf_count: dict[str, int] = {}
    for child_id in leaf_sources.values():
        child_leaf_count[child_id] = child_leaf_count.get(child_id, 0) + 1
    leaf_sources = {
        lid: cid for lid, cid in leaf_sources.items() if child_leaf_count[cid] == 1
    }

    leaf_edge_ids: set[str] = set()
    for edge in graph.edges:
        if edge.from_id in leaf_sources or edge.to_id in leaf_sources:
            leaf_edge_ids.add(f"{edge.from_id}->{edge.to_id}")

    layout_nodes = [n for n in graph.nodes if n.id not in leaf_sources]
    layout_edges = [e for e in graph.edges if f"{e.from_id}->{e.to_id}" not in leaf_edge_ids]

    vertices: dict[str, GVertex] = {}
    for node in layout_nodes:
        w, h = node_sizes[node.id]
        v = GVertex(node.id)
        if horizontal:
            v.view = _VertexData(h, w)
        else:
            v.view = _VertexData(w, h)
        vertices[node.id] = v

    g_edges: list[GEdge] = []
    for edge in layout_edges:
        if edge.from_id in vertices and edge.to_id in vertices:
            g_edges.append(GEdge(vertices[edge.from_id], vertices[edge.to_id]))

    g = GGraph(list(vertices.values()), g_edges)

    # --- lay out each connected component and stack them ----------------
    grandalf_centers: dict[str, tuple[float, float]] = {}
    sibling_offset = 0.0  # accumulates along the sibling axis (grandalf x)

    for component in g.C:
        sug = SugiyamaLayout(component)
        sug.xspace = SIBLING_GAP
        sug.yspace = MIN_LAYER_GAP
        sug.init_all()
        sug.draw()

        comp_min_x = float("inf")
        comp_max_x = float("-inf")

        for v in component.sV:
            if hasattr(v.view, "xy"):
                cx, cy = v.view.xy
                half_w = v.view.w / 2
                comp_min_x = min(comp_min_x, cx - half_w)
                comp_max_x = max(comp_max_x, cx + half_w)
                grandalf_centers[v.data] = (cx + sibling_offset, cy)

        if comp_min_x < float("inf"):
            sibling_offset += (comp_max_x - comp_min_x) + COMPONENT_GAP

    # --- transform to screen coordinates --------------------------------
    positioned_nodes: list[PositionedNode] = []
    for node in layout_nodes:
        w, h = node_sizes[node.id]
        cx, cy = grandalf_centers.get(node.id, (0.0, 0.0))
        x, y = _transform_coords(cx, cy, direction)
        positioned_nodes.append(
            PositionedNode(node=node, x=x - w / 2, y=y - h / 2, width=w, height=h)
        )

    # --- content-adaptive layer gaps ------------------------------------
    _apply_adaptive_layer_gaps(positioned_nodes, layout_edges, direction)

    # --- stretch hub nodes (fan-out / fan-in gates) ---------------------
    _stretch_hub_nodes(positioned_nodes, layout_edges, direction)

    # --- resolve any remaining node-vs-node overlaps --------------------
    _resolve_all_overlaps(positioned_nodes, direction)

    # --- generous spacing for hub fan-out targets -----------------------
    _space_hub_fanout_targets(positioned_nodes, layout_edges, direction)
    _resolve_all_overlaps(positioned_nodes, direction)

    # Re-stretch hubs: spacing may have pushed children apart.
    _stretch_hub_nodes(positioned_nodes, layout_edges, direction)

    # --- spread siblings whose fan-out labels would collide ---------------
    _spread_for_label_collisions(positioned_nodes, layout_edges, direction)
    _resolve_all_overlaps(positioned_nodes, direction)
    _stretch_hub_nodes(positioned_nodes, layout_edges, direction)
    _resolve_all_overlaps(positioned_nodes, direction)

    # --- displace auxiliary nodes to periphery --------------------------
    _displace_auxiliary_nodes(positioned_nodes, layout_edges, direction)
    _resolve_all_overlaps(positioned_nodes, direction)

    # --- re-insert leaf sources as compact prefixes ---------------------
    if leaf_sources:
        leaf_edge_labels: dict[str, str | None] = {}
        for edge in graph.edges:
            if edge.from_id in leaf_sources:
                leaf_edge_labels[edge.from_id] = edge.label

        node_map = {pn.node.id: pn for pn in positioned_nodes}
        leaf_node_objs = {n.id: n for n in graph.nodes if n.id in leaf_sources}
        for leaf_id, child_id in leaf_sources.items():
            child = node_map.get(child_id)
            if child is None:
                continue
            leaf_node = leaf_node_objs[leaf_id]
            w, h = node_sizes[leaf_id]
            label_extent = _measure_edge_label_extent(
                leaf_edge_labels.get(leaf_id),
                direction,
            )
            gap = max(MIN_LAYER_GAP, label_extent + MIN_LAYER_GAP * 0.5)
            if horizontal:
                x = child.x - w - gap
                y = child.y + child.height / 2 - h / 2
            else:
                x = child.x + child.width / 2 - w / 2
                y = child.y - h - gap
            positioned_nodes.append(PositionedNode(node=leaf_node, x=x, y=y, width=w, height=h))
        _resolve_all_overlaps(positioned_nodes, direction)

    _normalize_positions(positioned_nodes)
    positioned_edges = _route_edges(graph.edges, positioned_nodes, direction)

    all_x = [pn.x for pn in positioned_nodes]
    all_y = [pn.y for pn in positioned_nodes]
    all_r = [pn.x + pn.width for pn in positioned_nodes]
    all_b = [pn.y + pn.height for pn in positioned_nodes]
    total_w = max(all_r) - min(all_x) if all_x else 0
    total_h = max(all_b) - min(all_y) if all_y else 0

    return LayoutResult(
        nodes=positioned_nodes,
        edges=positioned_edges,
        subgraphs=graph.subgraphs,
        width=total_w,
        height=total_h,
    )


# ---------------------------------------------------------------------------
# Adaptive layer gaps
# ---------------------------------------------------------------------------


_MIN_ARROW_ANGLE_TAN = 0.27  # tan(~15deg) - minimum arrow steepness


def _apply_adaptive_layer_gaps(
    nodes: list[PositionedNode],
    edges: list[Edge],
    direction: Direction,
) -> None:
    """Re-space layers so each gap fits the widest edge label crossing it.

    Gaps are clamped to [MIN_LAYER_GAP, MAX_LAYER_GAP] - a paragraph on an
    arrow won't stretch the diagram into scroll-territory, while a short
    label like "events" gets just the room it needs.

    A second pass widens gaps when a hub fans out to distant children, so
    arrows stay steep enough to be readable (not nearly-horizontal).
    """
    if len(nodes) <= 1:
        return

    horizontal = _is_horizontal(direction)

    def _layer_center(pn: PositionedNode) -> float:
        return (pn.x + pn.width / 2) if horizontal else (pn.y + pn.height / 2)

    def _sibling_center(pn: PositionedNode) -> float:
        return (pn.y + pn.height / 2) if horizontal else (pn.x + pn.width / 2)

    def _layer_extent(pn: PositionedNode) -> float:
        return pn.width if horizontal else pn.height

    # Cluster nodes into layers by rounding their layer-axis center
    centers = [(pn, round(_layer_center(pn), 0)) for pn in nodes]
    unique_layers = sorted(set(c for _, c in centers))
    if len(unique_layers) <= 1:
        return

    layer_idx_map = {lc: i for i, lc in enumerate(unique_layers)}
    node_layer = {pn.node.id: layer_idx_map[lc] for pn, lc in centers}
    node_map = {pn.node.id: pn for pn in nodes}
    n_layers = len(unique_layers)

    # Max node extent in each layer along the layer axis
    layer_max_extent = [0.0] * n_layers
    for pn, lc in centers:
        idx = layer_idx_map[lc]
        layer_max_extent[idx] = max(layer_max_extent[idx], _layer_extent(pn))

    # Per-gap: find the widest label crossing that boundary
    desired_gaps: list[float] = []
    for i in range(n_layers - 1):
        max_label_extent = 0.0
        for edge in edges:
            fl = node_layer.get(edge.from_id)
            tl = node_layer.get(edge.to_id)
            if fl is None or tl is None:
                continue
            lo, hi = (fl, tl) if fl < tl else (tl, fl)
            if lo <= i < hi:
                ext = _measure_edge_label_extent(edge.label, direction)
                max_label_extent = max(max_label_extent, ext)

        gap = max(MIN_LAYER_GAP, max_label_extent)
        gap = min(gap, MAX_LAYER_GAP)
        desired_gaps.append(gap)

    # Hub fan-out aware: widen gaps when arrows to distant children
    # would be nearly horizontal.
    for i in range(n_layers - 1):
        for edge in edges:
            fl = node_layer.get(edge.from_id)
            tl = node_layer.get(edge.to_id)
            if fl is None or tl is None:
                continue
            lo, hi = (fl, tl) if fl < tl else (tl, fl)
            if not (lo <= i < hi):
                continue
            src_pn = node_map.get(edge.from_id)
            dst_pn = node_map.get(edge.to_id)
            if src_pn is None or dst_pn is None:
                continue
            sibling_dist = abs(_sibling_center(src_pn) - _sibling_center(dst_pn))
            num_gaps = hi - lo
            per_gap = sibling_dist * _MIN_ARROW_ANGLE_TAN / num_gaps
            desired_gaps[i] = max(desired_gaps[i], min(per_gap, MAX_LAYER_GAP))

    # Recompute layer center positions using adaptive gaps
    new_centers = [unique_layers[0]]
    for i in range(1, n_layers):
        dist = layer_max_extent[i - 1] / 2 + desired_gaps[i - 1] + layer_max_extent[i] / 2
        new_centers.append(new_centers[-1] + dist)

    # Apply shifts
    shift_by_layer = {unique_layers[i]: new_centers[i] - unique_layers[i] for i in range(n_layers)}
    for pn, lc in centers:
        shift = shift_by_layer[lc]
        if horizontal:
            pn.x += shift
        else:
            pn.y += shift


# ---------------------------------------------------------------------------
# Hub node stretching
# ---------------------------------------------------------------------------


def _stretch_hub_nodes(
    nodes: list[PositionedNode],
    edges: list[Edge],
    direction: Direction,
) -> None:
    """Stretch hub nodes (>= HUB_THRESHOLD fan-out or fan-in) to span their peers.

    An API Gateway with 4 outgoing edges becomes a tall rectangle spanning
    all 4 target services. A NAT Gateway with 4 incoming edges does the same.
    Only the sibling axis (vertical for LR, horizontal for TD) is stretched;
    the layer position stays fixed.
    """
    if len(nodes) <= 1:
        return

    horizontal = _is_horizontal(direction)
    node_map = {pn.node.id: pn for pn in nodes}

    out_targets: dict[str, list[str]] = {}
    in_sources: dict[str, list[str]] = {}
    for edge in edges:
        out_targets.setdefault(edge.from_id, []).append(edge.to_id)
        in_sources.setdefault(edge.to_id, []).append(edge.from_id)

    hub_ids: set[str] = set()

    for pn in nodes:
        nid = pn.node.id
        targets = out_targets.get(nid, [])
        sources = in_sources.get(nid, [])

        is_fan_out = len(targets) >= HUB_THRESHOLD
        is_fan_in = len(sources) >= HUB_THRESHOLD

        if not is_fan_out and not is_fan_in:
            continue

        peer_ids: set[str] = set()
        if is_fan_out:
            peer_ids.update(targets)
        if is_fan_in:
            peer_ids.update(sources)

        peers = [node_map[pid] for pid in peer_ids if pid in node_map]
        if not peers:
            continue

        if nid not in _hub_natural_sizes:
            _hub_natural_sizes[nid] = (pn.width, pn.height)
        nat_w, nat_h = _hub_natural_sizes[nid]

        if horizontal:
            span_top = min(p.y for p in peers) - HUB_PADDING
            span_bottom = max(p.y + p.height for p in peers) + HUB_PADDING
            desired = span_bottom - span_top
            max_size = nat_h * MAX_HUB_STRETCH
            new_height = min(desired, max_size)
            if new_height > pn.height:
                center = (span_top + span_bottom) / 2
                pn.y = center - new_height / 2
                pn.height = new_height
                hub_ids.add(nid)
        else:
            span_left = min(p.x for p in peers) - HUB_PADDING
            span_right = max(p.x + p.width for p in peers) + HUB_PADDING
            desired = span_right - span_left
            max_size = nat_w * MAX_HUB_STRETCH
            new_width = min(desired, max_size)
            if new_width > pn.width:
                center = (span_left + span_right) / 2
                pn.x = center - new_width / 2
                pn.width = new_width
                hub_ids.add(nid)

    if hub_ids:
        _resolve_hub_overlaps(nodes, hub_ids, direction)


def _resolve_hub_overlaps(
    nodes: list[PositionedNode],
    hub_ids: set[str],
    direction: Direction,
    gap: float = SIBLING_GAP,
) -> None:
    """Push non-hub nodes that overlap with a stretched hub out of the way.

    When multiple non-hub nodes overlap a hub on the same side, they are
    stacked sequentially so they don't pile on top of each other.
    """
    horizontal = _is_horizontal(direction)

    hub_nodes = [pn for pn in nodes if pn.node.id in hub_ids]
    non_hub = [pn for pn in nodes if pn.node.id not in hub_ids]

    for hub in hub_nodes:
        before: list[PositionedNode] = []
        after: list[PositionedNode] = []

        for other in non_hub:
            if not _rects_overlap(hub, other):
                continue
            if horizontal:
                other_center = other.y + other.height / 2
                hub_center = hub.y + hub.height / 2
            else:
                other_center = other.x + other.width / 2
                hub_center = hub.x + hub.width / 2

            if other_center < hub_center:
                before.append(other)
            else:
                after.append(other)

        if horizontal:
            before.sort(key=lambda p: p.y + p.height / 2)
            cursor = hub.y - gap
            for pn in reversed(before):
                pn.y = cursor - pn.height
                cursor = pn.y - gap

            after.sort(key=lambda p: p.y + p.height / 2)
            cursor = hub.y + hub.height + gap
            for pn in after:
                pn.y = cursor
                cursor = pn.y + pn.height + gap
        else:
            before.sort(key=lambda p: p.x + p.width / 2)
            cursor = hub.x - gap
            for pn in reversed(before):
                pn.x = cursor - pn.width
                cursor = pn.x - gap

            after.sort(key=lambda p: p.x + p.width / 2)
            cursor = hub.x + hub.width + gap
            for pn in after:
                pn.x = cursor
                cursor = pn.x + pn.width + gap


def _rects_overlap(a: PositionedNode, b: PositionedNode) -> bool:
    return (
        a.x < b.x + b.width
        and b.x < a.x + a.width
        and a.y < b.y + b.height
        and b.y < a.y + a.height
    )


def _resolve_all_overlaps(
    nodes: list[PositionedNode],
    direction: Direction,
    gap: float = SIBLING_GAP,
) -> None:
    """Push apart any overlapping nodes within the same layer.

    Unlike ``_resolve_hub_overlaps`` (which only fixes hub-vs-node conflicts),
    this handles **any** pair of nodes that ended up on top of each other -
    typically caused by grandalf placing multiple children of a high-fan-out
    parent at nearly the same position.
    """
    if len(nodes) < 2:
        return

    horizontal = _is_horizontal(direction)

    def _layer_key(pn: PositionedNode) -> float:
        return round(
            (pn.x + pn.width / 2) if horizontal else (pn.y + pn.height / 2),
            0,
        )

    layers: dict[float, list[PositionedNode]] = {}
    for pn in nodes:
        layers.setdefault(_layer_key(pn), []).append(pn)

    for _lc, group in layers.items():
        if len(group) < 2:
            continue

        if horizontal:
            group.sort(key=lambda p: p.y)
            for i in range(len(group) - 1):
                a, b = group[i], group[i + 1]
                a_end = a.y + a.height
                if b.y < a_end + gap:
                    b.y = a_end + gap
        else:
            group.sort(key=lambda p: p.x)
            for i in range(len(group) - 1):
                a, b = group[i], group[i + 1]
                a_end = a.x + a.width
                if b.x < a_end + gap:
                    b.x = a_end + gap


# ---------------------------------------------------------------------------
# Generous spacing for hub fan-out targets
# ---------------------------------------------------------------------------


def _space_hub_fanout_targets(
    nodes: list[PositionedNode],
    edges: list[Edge],
    direction: Direction,
) -> None:
    """Ensure generous spacing between fan-out targets of hub nodes.

    When a hub fans out to N targets in the same layer, those targets need
    extra breathing room so arrows can diverge cleanly.  Uses HUB_FAN_GAP
    (2x normal SIBLING_GAP) as the minimum edge-to-edge distance.
    """
    if len(nodes) <= 1:
        return

    horizontal = _is_horizontal(direction)
    node_map = {pn.node.id: pn for pn in nodes}

    def _layer_key(pn: PositionedNode) -> float:
        return round(
            (pn.x + pn.width / 2) if horizontal else (pn.y + pn.height / 2),
            0,
        )

    out_targets: dict[str, list[str]] = {}
    in_sources: dict[str, list[str]] = {}
    for edge in edges:
        out_targets.setdefault(edge.from_id, []).append(edge.to_id)
        in_sources.setdefault(edge.to_id, []).append(edge.from_id)

    processed: set[frozenset[str]] = set()

    for nid in list(out_targets.keys()) + list(in_sources.keys()):
        targets = out_targets.get(nid, [])
        sources = in_sources.get(nid, [])

        peer_ids: list[str] = []
        if len(targets) >= HUB_THRESHOLD:
            peer_ids.extend(targets)
        if len(sources) >= HUB_THRESHOLD:
            peer_ids.extend(sources)

        if len(peer_ids) < 2:
            continue

        group_key = frozenset(peer_ids)
        if group_key in processed:
            continue
        processed.add(group_key)

        peers = [node_map[pid] for pid in peer_ids if pid in node_map]
        if len(peers) < 2:
            continue

        layer_groups: dict[float, list[PositionedNode]] = {}
        for p in peers:
            layer_groups.setdefault(_layer_key(p), []).append(p)

        for _lk, group in layer_groups.items():
            if len(group) < 2:
                continue

            if horizontal:
                group.sort(key=lambda p: p.y)
                for i in range(len(group) - 1):
                    a, b = group[i], group[i + 1]
                    min_b = a.y + a.height + HUB_FAN_GAP
                    if b.y < min_b:
                        b.y = min_b
            else:
                group.sort(key=lambda p: p.x)
                for i in range(len(group) - 1):
                    a, b = group[i], group[i + 1]
                    min_b = a.x + a.width + HUB_FAN_GAP
                    if b.x < min_b:
                        b.x = min_b


# ---------------------------------------------------------------------------
# Auxiliary node displacement
# ---------------------------------------------------------------------------


def _displace_auxiliary_nodes(
    nodes: list[PositionedNode],
    edges: list[Edge],
    direction: Direction,
) -> None:
    """Push nodes connected only via non-solid edges to the periphery.

    Auxiliary nodes (monitoring, alerting, event sinks) are identified by
    having ALL their edges be dashed or dotted.  When such a node sits
    within the bounding box of the core nodes in its layer, it is displaced
    to the nearest edge of that bounding box with extra gap.
    """
    if len(nodes) < 2:
        return

    horizontal = _is_horizontal(direction)

    node_edge_styles: dict[str, list[EdgeStyle]] = {}
    for edge in edges:
        node_edge_styles.setdefault(edge.from_id, []).append(edge.style)
        node_edge_styles.setdefault(edge.to_id, []).append(edge.style)

    auxiliary_ids: set[str] = set()
    for nid, styles in node_edge_styles.items():
        if all(s in (EdgeStyle.DASHED, EdgeStyle.DOTTED) for s in styles):
            auxiliary_ids.add(nid)

    if not auxiliary_ids:
        return

    def _layer_key(pn: PositionedNode) -> float:
        return round(
            (pn.x + pn.width / 2) if horizontal else (pn.y + pn.height / 2),
            0,
        )

    layers: dict[float, list[PositionedNode]] = {}
    for pn in nodes:
        layers.setdefault(_layer_key(pn), []).append(pn)

    for _lc, group in layers.items():
        aux = [pn for pn in group if pn.node.id in auxiliary_ids]
        main = [pn for pn in group if pn.node.id not in auxiliary_ids]

        if not aux or not main:
            continue

        if horizontal:
            main_top = min(pn.y for pn in main)
            main_bottom = max(pn.y + pn.height for pn in main)
            main_center = (main_top + main_bottom) / 2

            for a in aux:
                a_center = a.y + a.height / 2
                if main_top <= a_center <= main_bottom:
                    if a_center <= main_center:
                        a.y = main_top - AUXILIARY_EXTRA_GAP - a.height
                    else:
                        a.y = main_bottom + AUXILIARY_EXTRA_GAP
        else:
            main_left = min(pn.x for pn in main)
            main_right = max(pn.x + pn.width for pn in main)
            main_center = (main_left + main_right) / 2

            for a in aux:
                a_center = a.x + a.width / 2
                if main_left <= a_center <= main_right:
                    if a_center <= main_center:
                        a.x = main_left - AUXILIARY_EXTRA_GAP - a.width
                    else:
                        a.x = main_right + AUXILIARY_EXTRA_GAP


# ---------------------------------------------------------------------------
# Fan-out label collision avoidance
# ---------------------------------------------------------------------------

LABEL_COLLISION_GAP = 12.0


def _measure_label_sibling_extent(label: str | None, direction: Direction) -> float:
    """Width of an edge label along the *sibling* axis (perpendicular to flow)."""
    if not label:
        return 0.0
    lines = label.split("\n")
    if _is_horizontal(direction):
        return len(lines) * LINE_HEIGHT + LABEL_PADDING
    max_line = max(len(line) for line in lines)
    return max_line * LABEL_CHAR_WIDTH + LABEL_PADDING


def _shift_creates_obstacle(
    node: PositionedNode,
    edges: list[Edge],
    node_map: dict[str, PositionedNode],
) -> bool:
    """Check whether *node* at its current position blocks any edge path."""
    for e in edges:
        if e.from_id == node.node.id or e.to_id == node.node.id:
            continue
        src = node_map.get(e.from_id)
        dst = node_map.get(e.to_id)
        if not src or not dst:
            continue
        start = (src.x + src.width / 2, src.y + src.height / 2)
        end = (dst.x + dst.width / 2, dst.y + dst.height / 2)
        if _find_obstacles(start, end, [node], e.from_id, e.to_id):
            return True
    return False


def _spread_for_label_collisions(
    nodes: list[PositionedNode],
    edges: list[Edge],
    direction: Direction,
    gap: float = LABEL_COLLISION_GAP,
) -> None:
    """Push apart sibling target nodes when fan-out arrow labels would overlap.

    For each source with multiple labeled outgoing edges, the label of each
    arrow is rendered at the geometric midpoint between source and target.
    When targets are close on the sibling axis, those midpoints cluster and
    labels collide.  This function increases the sibling-axis gap between
    such targets so that labels have room.

    Each shift is verified to not create new obstacles for other edges;
    if it would, the shift is skipped to avoid routing regressions.
    """
    horizontal = _is_horizontal(direction)
    node_map: dict[str, PositionedNode] = {pn.node.id: pn for pn in nodes}

    by_source: dict[str, list[Edge]] = {}
    for e in edges:
        if e.label:
            by_source.setdefault(e.from_id, []).append(e)

    for src_id, src_edges in by_source.items():
        if len(src_edges) < 2:
            continue
        src = node_map.get(src_id)
        if not src:
            continue

        src_c = (src.y + src.height / 2) if horizontal else (src.x + src.width / 2)

        items: list[tuple[PositionedNode, float, float]] = []
        for e in src_edges:
            tgt = node_map.get(e.to_id)
            if not tgt:
                continue
            tgt_c = (tgt.y + tgt.height / 2) if horizontal else (tgt.x + tgt.width / 2)
            mid = (src_c + tgt_c) / 2
            ext = _measure_label_sibling_extent(e.label, direction)
            items.append((tgt, mid, ext))

        if len(items) < 2:
            continue

        items.sort(key=lambda x: x[1])

        for k in range(len(items) - 1):
            tgt_a, mid_a, ext_a = items[k]
            tgt_b, mid_b, ext_b = items[k + 1]

            min_sep = (ext_a + ext_b) / 2 + gap
            actual_sep = mid_b - mid_a

            if actual_sep >= min_sep:
                continue

            needed_mid_shift = min_sep - actual_sep
            tgt_shift = needed_mid_shift * 2

            old_bx, old_by = tgt_b.x, tgt_b.y
            if horizontal:
                tgt_b.y += tgt_shift
            else:
                tgt_b.x += tgt_shift

            if _shift_creates_obstacle(tgt_b, edges, node_map):
                tgt_b.x, tgt_b.y = old_bx, old_by
                old_ax, old_ay = tgt_a.x, tgt_a.y
                if horizontal:
                    tgt_a.y -= tgt_shift
                else:
                    tgt_a.x -= tgt_shift
                if _shift_creates_obstacle(tgt_a, edges, node_map):
                    tgt_a.x, tgt_a.y = old_ax, old_ay
                else:
                    items[k] = (tgt_a, mid_a - needed_mid_shift, ext_a)
            else:
                items[k + 1] = (tgt_b, mid_b + needed_mid_shift, ext_b)


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------


def _transform_coords(x: float, y: float, direction: Direction) -> tuple[float, float]:
    """Transform grandalf's top-down coordinates to the requested direction."""
    match direction:
        case Direction.TOP_DOWN:
            return (x, y)
        case Direction.LEFT_RIGHT:
            return (y, x)
        case Direction.BOTTOM_UP:
            return (x, -y)
        case Direction.RIGHT_LEFT:
            return (-y, x)


def _normalize_positions(nodes: list[PositionedNode], margin: float = 50.0) -> None:
    """Shift all nodes so the top-left is at (margin, margin)."""
    if not nodes:
        return
    min_x = min(n.x for n in nodes)
    min_y = min(n.y for n in nodes)
    offset_x = margin - min_x
    offset_y = margin - min_y
    for n in nodes:
        n.x += offset_x
        n.y += offset_y


def _find_segment_obstacles(
    points: list[tuple[float, float]],
    nodes: list[PositionedNode],
    from_id: str,
    to_id: str,
    known: list[PositionedNode],
) -> list[PositionedNode]:
    """Check each segment of a multi-point path for new obstacle crossings.

    Returns nodes that the detour path passes through but that were NOT
    in the original *known* obstacle list.
    """
    known_ids = {o.node.id for o in known}
    extra: list[PositionedNode] = []
    seen: set[str] = set()
    for i in range(len(points) - 1):
        hits = _find_obstacles(points[i], points[i + 1], nodes, from_id, to_id)
        for h in hits:
            nid = h.node.id
            if nid not in known_ids and nid not in seen:
                extra.append(h)
                seen.add(nid)
    return extra


def _route_edges(
    edges: list[Edge],
    positioned_nodes: list[PositionedNode],
    direction: Direction,
) -> list[PositionedEdge]:
    """Compute edge routes, curving around any intermediate nodes in the path."""
    node_rects: dict[str, PositionedNode] = {}
    for pn in positioned_nodes:
        node_rects[pn.node.id] = pn

    # Pre-compute evenly distributed slots for nodes that have multiple
    # arrows arriving/departing on the same face.
    slots = _compute_port_slots(edges, node_rects, direction)

    horizontal = _is_horizontal(direction)
    layer_axis = 0 if horizontal else 1
    short_threshold = MIN_LAYER_GAP * 1.5

    detour_counts: dict[tuple[str, str], int] = {}

    result: list[PositionedEdge] = []
    for edge in edges:
        src = node_rects.get(edge.from_id)
        dst = node_rects.get(edge.to_id)
        if src and dst:
            edge_key = (edge.from_id, edge.to_id)
            src_slot = slots.get(("src", edge_key))
            dst_slot = slots.get(("dst", edge_key))
            start, end = _edge_endpoints(
                src,
                dst,
                direction,
                src_slot=src_slot,
                dst_slot=dst_slot,
            )
            layer_dist = abs(end[layer_axis] - start[layer_axis])
            if layer_dist < short_threshold:
                points = [start, end]
            else:
                obstacles = _find_obstacles(
                    start,
                    end,
                    positioned_nodes,
                    edge.from_id,
                    edge.to_id,
                )
                if obstacles:
                    det_key = (edge.from_id, "detour")
                    idx = detour_counts.get(det_key, 0)
                    detour_counts[det_key] = idx + 1
                    points = _route_around_obstacles(
                        start,
                        end,
                        obstacles,
                        direction,
                        offset=idx * _DETOUR_SPREAD,
                    )
                    # Check if the detour path itself crosses new nodes
                    # (e.g. hub-stretched nodes not on the original line).
                    extra = _find_segment_obstacles(
                        points,
                        positioned_nodes,
                        edge.from_id,
                        edge.to_id,
                        obstacles,
                    )
                    if extra:
                        points = _route_around_obstacles(
                            start,
                            end,
                            obstacles + extra,
                            direction,
                            offset=idx * _DETOUR_SPREAD,
                        )
                else:
                    points = [start, end]
            points = _soften_long_diagonal(points, direction)
            result.append(PositionedEdge(edge=edge, points=points))
        else:
            result.append(PositionedEdge(edge=edge, points=[]))

    _uncross_arrivals(result, direction)
    return result


def _uncross_arrivals(
    routed: list[PositionedEdge],
    direction: Direction,
) -> None:
    """Swap endpoint positions when obstacle detours cause arrows to cross.

    Port slots are assigned *before* obstacle routing, so an arrow that
    detours downward may be assigned the upper slot while its neighbor
    (going straight) gets the lower slot.  After routing we compare each
    arrow's approach direction to its endpoint position and swap when the
    ordering is inverted.
    """
    horizontal = _is_horizontal(direction)
    sibling = 1 if horizontal else 0  # y-index for LR/RL, x-index for TD/BU

    # Group by destination node
    dst_groups: dict[str, list[PositionedEdge]] = {}
    for pe in routed:
        if len(pe.points) >= 2:
            dst_groups.setdefault(pe.edge.to_id, []).append(pe)

    for _dst_id, group in dst_groups.items():
        if len(group) < 2:
            continue

        changed = True
        while changed:
            changed = False
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    a_end = a.points[-1][sibling]
                    b_end = b.points[-1][sibling]
                    a_approach = a.points[-2][sibling]
                    b_approach = b.points[-2][sibling]

                    end_order = a_end < b_end
                    approach_order = a_approach < b_approach
                    if end_order != approach_order:
                        # Swap the endpoints
                        a_pts = list(a.points[-1])
                        b_pts = list(b.points[-1])
                        a_pts[sibling], b_pts[sibling] = (
                            b_pts[sibling],
                            a_pts[sibling],
                        )
                        a.points[-1] = tuple(a_pts)
                        b.points[-1] = tuple(b_pts)
                        changed = True


def _is_backward(
    src: PositionedNode,
    dst: PositionedNode,
    direction: Direction,
) -> bool:
    """True when the edge goes against the natural flow direction."""
    src_cx = src.x + src.width / 2
    src_cy = src.y + src.height / 2
    dst_cx = dst.x + dst.width / 2
    dst_cy = dst.y + dst.height / 2
    match direction:
        case Direction.LEFT_RIGHT:
            return dst_cx < src_cx
        case Direction.RIGHT_LEFT:
            return dst_cx > src_cx
        case Direction.BOTTOM_UP:
            return dst_cy > src_cy
        case _:
            return dst_cy < src_cy


def _compute_port_slots(
    edges: list[Edge],
    node_rects: dict[str, PositionedNode],
    direction: Direction,
) -> dict[tuple[str, tuple[str, str]], float]:
    """Assign evenly-spaced positions along each node face.

    Returns a dict mapping ("src"|"dst", (from_id, to_id)) -> slot position
    (a y-coordinate for LR/RL, x-coordinate for TD/BU).

    Two passes:
      1. Per-face distribution - edges sharing a face get sorted by peer
         position and evenly spaced.  Single-edge faces are left untouched.
      2. Cross-face anti-crossing - if arrows on *different* faces of the
         same node would cross, their positions are redistributed evenly
         across the full node span.  Arrows that don't cross are never
         moved, so common cases stay natural.
    """
    horizontal = _is_horizontal(direction)
    m = EDGE_MARGIN

    # -- collect per-face groups ------------------------------------------

    departures: dict[tuple[str, str], list[tuple[tuple[str, str], float]]] = {}
    arrivals: dict[tuple[str, str], list[tuple[tuple[str, str], float]]] = {}

    for edge in edges:
        src = node_rects.get(edge.from_id)
        dst = node_rects.get(edge.to_id)
        if not src or not dst:
            continue

        backward = _is_backward(src, dst, direction)
        edge_key = (edge.from_id, edge.to_id)

        src_face = "bwd" if backward else "fwd"
        dst_face = "bwd" if not backward else "fwd"

        peer_center_for_src = (dst.y + dst.height / 2) if horizontal else (dst.x + dst.width / 2)
        peer_center_for_dst = (src.y + src.height / 2) if horizontal else (src.x + src.width / 2)

        dep_key = (edge.from_id, src_face)
        departures.setdefault(dep_key, []).append((edge_key, peer_center_for_src))

        arr_key = (edge.to_id, dst_face)
        arrivals.setdefault(arr_key, []).append((edge_key, peer_center_for_dst))

    result: dict[tuple[str, tuple[str, str]], float] = {}

    # -- pass 1: per-face even distribution --------------------------------

    def _assign_slots(
        groups: dict[tuple[str, str], list[tuple[tuple[str, str], float]]],
        role: str,
    ) -> None:
        for (node_id, _face), members in groups.items():
            if len(members) < 2:
                continue
            pn = node_rects[node_id]
            span = pn.height if horizontal else pn.width
            lo = (pn.y if horizontal else pn.x) + m
            hi = lo + span - 2 * m

            members.sort(key=lambda x: x[1])
            n = len(members)
            for i, (ek, _peer) in enumerate(members):
                slot = lo + (hi - lo) * (i + 1) / (n + 1)
                result[(role, ek)] = slot

    _assign_slots(departures, "src")
    _assign_slots(arrivals, "dst")

    # -- pass 2: cross-face anti-crossing ----------------------------------
    _fix_cross_face_crossings(
        arrivals,
        "dst",
        node_rects,
        horizontal,
        m,
        result,
    )
    _fix_cross_face_crossings(
        departures,
        "src",
        node_rects,
        horizontal,
        m,
        result,
    )

    return result


def _fix_cross_face_crossings(
    face_groups: dict[tuple[str, str], list[tuple[tuple[str, str], float]]],
    role: str,
    node_rects: dict[str, PositionedNode],
    horizontal: bool,
    margin: float,
    slots: dict[tuple[str, tuple[str, str]], float],
) -> None:
    """Detect and fix arrow crossings between different faces of the same node.

    For each node that has arrows on multiple faces, compute the natural
    (or already-assigned) positions, check for crossings, and redistribute
    only when crossings exist.
    """
    # Gather all face groups per node
    node_faces: dict[str, list[tuple[str, str]]] = {}
    for key in face_groups:
        node_id, _face = key
        node_faces.setdefault(node_id, []).append(key)

    for node_id, keys in node_faces.items():
        if len(keys) < 2:
            continue

        pn = node_rects[node_id]
        lo = (pn.y if horizontal else pn.x) + margin
        hi = lo + (pn.height if horizontal else pn.width) - 2 * margin

        # Collect all arrows at this node with their current positions
        all_arrows: list[tuple[tuple[str, str], float]] = []
        for key in keys:
            for edge_key, peer_center in face_groups[key]:
                current = slots.get((role, edge_key), _clamp(peer_center, lo, hi))
                all_arrows.append((edge_key, current))

        if len(all_arrows) < 2:
            continue

        # Detect crossing: arrows cross when their source ordering
        # disagrees with their destination y-ordering
        all_arrows.sort(key=lambda x: x[1])
        peer_positions = []
        for edge_key, _pos in all_arrows:
            for key in keys:
                for ek, pc in face_groups[key]:
                    if ek == edge_key:
                        peer_positions.append(pc)

        has_crossing = False
        for i in range(len(peer_positions) - 1):
            if peer_positions[i] > peer_positions[i + 1]:
                has_crossing = True
                break

        if not has_crossing:
            continue

        # Redistribute: sort by peer position, assign evenly
        all_arrows_by_peer: list[tuple[tuple[str, str], float]] = []
        for key in keys:
            for edge_key, peer_center in face_groups[key]:
                all_arrows_by_peer.append((edge_key, peer_center))

        all_arrows_by_peer.sort(key=lambda x: x[1])
        n = len(all_arrows_by_peer)
        for i, (ek, _peer) in enumerate(all_arrows_by_peer):
            slot = lo + (hi - lo) * (i + 1) / (n + 1)
            slots[(role, ek)] = slot


# ---------------------------------------------------------------------------
# Long-diagonal arc smoothing
# ---------------------------------------------------------------------------


def _soften_long_diagonal(
    points: list[tuple[float, float]],
    direction: Direction,
) -> list[tuple[float, float]]:
    """Insert a midpoint waypoint for long diagonal arrows.

    When a straight arrow spans a large layer distance AND has a large
    sibling-axis offset, insert a bend point that makes the path curve
    gently rather than slashing diagonally across the canvas.

    The bend is placed at 40% along the layer axis and 65% along the
    sibling axis, creating a path that is steep near the source (where
    arrows diverge) and levels out near the target.
    """
    if len(points) != 2:
        return points

    start, end = points
    horizontal = _is_horizontal(direction)
    layer_axis = 0 if horizontal else 1
    sibling_axis = 1 if horizontal else 0

    layer_dist = abs(end[layer_axis] - start[layer_axis])
    sibling_dist = abs(end[sibling_axis] - start[sibling_axis])

    if layer_dist < _ARC_LAYER_THRESHOLD:
        return points
    if sibling_dist < layer_dist * _ARC_SIBLING_RATIO:
        return points

    mid = [0.0, 0.0]
    mid[layer_axis] = start[layer_axis] + 0.4 * (end[layer_axis] - start[layer_axis])
    mid[sibling_axis] = start[sibling_axis] + 0.65 * (end[sibling_axis] - start[sibling_axis])
    return [start, (mid[0], mid[1]), end]


# ---------------------------------------------------------------------------
# Obstacle-aware routing
# ---------------------------------------------------------------------------

_OBSTACLE_MARGIN = 10.0  # clearance for obstacle *detection*
_DETOUR_CLEARANCE = 40.0  # breathing room for the detour *path*
_DETOUR_SPREAD = 20.0  # incremental offset between parallel detours


def _find_obstacles(
    start: tuple[float, float],
    end: tuple[float, float],
    nodes: list[PositionedNode],
    from_id: str,
    to_id: str,
) -> list[PositionedNode]:
    """Find nodes whose bounding rect is crossed by the straight line start→end."""
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy

    obstacles: list[PositionedNode] = []
    for pn in nodes:
        if pn.node.id in (from_id, to_id):
            continue

        # Quick x/y range rejection
        n_left = pn.x - _OBSTACLE_MARGIN
        n_right = pn.x + pn.width + _OBSTACLE_MARGIN
        n_top = pn.y - _OBSTACLE_MARGIN
        n_bottom = pn.y + pn.height + _OBSTACLE_MARGIN

        if dx != 0:
            # Parametric t where the line's x equals the node's x-range
            t_enter = (n_left - sx) / dx
            t_exit = (n_right - sx) / dx
            if t_enter > t_exit:
                t_enter, t_exit = t_exit, t_enter
            # Only care about the segment [0, 1]
            t_enter = max(t_enter, 0.0)
            t_exit = min(t_exit, 1.0)
            if t_enter >= t_exit:
                continue
            # Check if the line's y at any point in [t_enter, t_exit] is inside
            y_at_enter = sy + t_enter * dy
            y_at_exit = sy + t_exit * dy
            y_lo = min(y_at_enter, y_at_exit)
            y_hi = max(y_at_enter, y_at_exit)
            if y_hi < n_top or y_lo > n_bottom:
                continue
        else:
            # Vertical line - check x containment
            if sx < n_left or sx > n_right:
                continue
            if dy != 0:
                t_enter = (n_top - sy) / dy
                t_exit = (n_bottom - sy) / dy
                if t_enter > t_exit:
                    t_enter, t_exit = t_exit, t_enter
                if max(t_enter, 0.0) >= min(t_exit, 1.0):
                    continue
            else:
                continue

        obstacles.append(pn)

    return obstacles


def _route_around_obstacles(
    start: tuple[float, float],
    end: tuple[float, float],
    obstacles: list[PositionedNode],
    direction: Direction,
    *,
    offset: float = 0.0,
) -> list[tuple[float, float]]:
    """Insert waypoints so the path curves around all obstacles.

    For LR/RL layouts the detour is vertical (above or below obstacles).
    For TD/BU layouts the detour is horizontal (left or right).

    *offset* spreads parallel detours apart so multiple arrows from the
    same source don't overlap when they all route around the same obstacle.
    """
    horizontal = _is_horizontal(direction)
    cl = _DETOUR_CLEARANCE

    if horizontal:
        obs_top = min(o.y for o in obstacles) - cl
        obs_bottom = max(o.y + o.height for o in obstacles) + cl
        obs_left = min(o.x for o in obstacles) - cl
        obs_right = max(o.x + o.width for o in obstacles) + cl

        go_above = min(abs(obs_top - start[1]), abs(obs_top - end[1])) <= min(
            abs(obs_bottom - start[1]), abs(obs_bottom - end[1])
        )
        detour_y = (obs_top - offset) if go_above else (obs_bottom + offset)

        if start[0] <= end[0]:
            enter_x, exit_x = obs_left, obs_right
            enter_x = max(enter_x, start[0])
            exit_x = min(exit_x, end[0])
        else:
            enter_x, exit_x = obs_right, obs_left
            enter_x = min(enter_x, start[0])
            exit_x = max(exit_x, end[0])

        wp1 = (_lerp(start[0], enter_x, 0.7), detour_y)
        wp2 = (_lerp(end[0], exit_x, 0.7), detour_y)
        return [start, wp1, wp2, end]
    else:
        obs_left = min(o.x for o in obstacles) - cl
        obs_right = max(o.x + o.width for o in obstacles) + cl
        obs_top = min(o.y for o in obstacles) - cl
        obs_bottom = max(o.y + o.height for o in obstacles) + cl

        go_left = min(abs(obs_left - start[0]), abs(obs_left - end[0])) <= min(
            abs(obs_right - start[0]), abs(obs_right - end[0])
        )
        detour_x = (obs_left - offset) if go_left else (obs_right + offset)

        if start[1] <= end[1]:
            enter_y, exit_y = obs_top, obs_bottom
            enter_y = max(enter_y, start[1])
            exit_y = min(exit_y, end[1])
        else:
            enter_y, exit_y = obs_bottom, obs_top
            enter_y = min(enter_y, start[1])
            exit_y = max(exit_y, end[1])

        wp1 = (detour_x, _lerp(start[1], enter_y, 0.7))
        wp2 = (detour_x, _lerp(end[1], exit_y, 0.7))
        return [start, wp1, wp2, end]


def _edge_endpoints(
    src: PositionedNode,
    dst: PositionedNode,
    direction: Direction,
    *,
    src_slot: float | None = None,
    dst_slot: float | None = None,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Compute arrow start/end at shape borders.

    When multiple edges share a node face, pre-computed *slot* positions
    distribute them evenly so arrows never pile up on the same point.
    If no slot is provided, the position defaults to aiming at the peer's
    center (the previous behaviour, still correct for single-edge faces).

    Backward edges flip the departure/arrival faces so the arrow travels
    against the flow direction naturally.
    """
    src_cx = src.x + src.width / 2
    src_cy = src.y + src.height / 2
    dst_cx = dst.x + dst.width / 2
    dst_cy = dst.y + dst.height / 2

    m = EDGE_MARGIN
    backward = _is_backward(src, dst, direction)

    src_is_diamond = src.node.shape is ShapeType.DIAMOND
    dst_is_diamond = dst.node.shape is ShapeType.DIAMOND

    match direction:
        case Direction.LEFT_RIGHT | Direction.RIGHT_LEFT:
            sy = (
                src_slot
                if src_slot is not None
                else _clamp(
                    dst_cy,
                    src.y + m,
                    src.y + src.height - m,
                )
            )
            ey = (
                dst_slot
                if dst_slot is not None
                else _clamp(
                    src_cy,
                    dst.y + m,
                    dst.y + dst.height - m,
                )
            )
            if src_is_diamond:
                sy_off = _diamond_border_offset(
                    sy,
                    src_cy,
                    src.width / 2,
                    src.height / 2,
                )
            if dst_is_diamond:
                ey_off = _diamond_border_offset(
                    ey,
                    dst_cy,
                    dst.width / 2,
                    dst.height / 2,
                )
            if direction is Direction.LEFT_RIGHT:
                if backward:
                    sx = src.x + (sy_off if src_is_diamond else 0)
                    ex = dst.x + dst.width - (ey_off if dst_is_diamond else 0)
                    start = (sx, sy)
                    end = (ex, ey)
                else:
                    sx = src.x + src.width - (sy_off if src_is_diamond else 0)
                    ex = dst.x + (ey_off if dst_is_diamond else 0)
                    start = (sx, sy)
                    end = (ex, ey)
            else:
                if backward:
                    sx = src.x + src.width - (sy_off if src_is_diamond else 0)
                    ex = dst.x + (ey_off if dst_is_diamond else 0)
                    start = (sx, sy)
                    end = (ex, ey)
                else:
                    sx = src.x + (sy_off if src_is_diamond else 0)
                    ex = dst.x + dst.width - (ey_off if dst_is_diamond else 0)
                    start = (sx, sy)
                    end = (ex, ey)

        case Direction.BOTTOM_UP | _:
            sx = (
                src_slot
                if src_slot is not None
                else _clamp(
                    dst_cx,
                    src.x + m,
                    src.x + src.width - m,
                )
            )
            ex = (
                dst_slot
                if dst_slot is not None
                else _clamp(
                    src_cx,
                    dst.x + m,
                    dst.x + dst.width - m,
                )
            )
            if src_is_diamond:
                sx_off = _diamond_border_offset(
                    sx,
                    src_cx,
                    src.width / 2,
                    src.height / 2,
                )
            if dst_is_diamond:
                ex_off = _diamond_border_offset(
                    ex,
                    dst_cx,
                    dst.width / 2,
                    dst.height / 2,
                )
            if direction is Direction.BOTTOM_UP:
                if backward:
                    sy = src.y + src.height - (sx_off if src_is_diamond else 0)
                    ey = dst.y + (ex_off if dst_is_diamond else 0)
                    start = (sx, sy)
                    end = (ex, ey)
                else:
                    sy = src.y + (sx_off if src_is_diamond else 0)
                    ey = dst.y + dst.height - (ex_off if dst_is_diamond else 0)
                    start = (sx, sy)
                    end = (ex, ey)
            else:  # TOP_DOWN
                if backward:
                    sy = src.y + (sx_off if src_is_diamond else 0)
                    ey = dst.y + dst.height - (ex_off if dst_is_diamond else 0)
                    start = (sx, sy)
                    end = (ex, ey)
                else:
                    sy = src.y + src.height - (sx_off if src_is_diamond else 0)
                    ey = dst.y + (ex_off if dst_is_diamond else 0)
                    start = (sx, sy)
                    end = (ex, ey)

    return start, end


# ---------------------------------------------------------------------------
# Incremental layout (for modify_diagram)
# ---------------------------------------------------------------------------


def layout_new_node_near(
    existing_positions: dict[str, tuple[float, float, float, float]],
    new_node: Node,
    near_id: str | None,
    connected_ids: list[str],
) -> tuple[float, float, float, float]:
    """Find a position for a new node near existing nodes.

    Returns (x, y, width, height) for the new node.
    """
    w, h = _estimate_node_size(new_node)

    if near_id and near_id in existing_positions:
        ref = existing_positions[near_id]
        return (ref[0] + ref[2] + MIN_LAYER_GAP, ref[1], w, h)

    if connected_ids:
        valid = [existing_positions[cid] for cid in connected_ids if cid in existing_positions]
        if valid:
            avg_x = sum(p[0] for p in valid) / len(valid)
            max_bottom = max(p[1] + p[3] for p in valid)
            return (avg_x, max_bottom + SIBLING_GAP, w, h)

    if existing_positions:
        all_bottoms = [p[1] + p[3] for p in existing_positions.values()]
        all_lefts = [p[0] for p in existing_positions.values()]
        return (min(all_lefts), max(all_bottoms) + SIBLING_GAP, w, h)

    return (50.0, 50.0, w, h)
