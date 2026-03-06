"""Basic tests for the layout engine."""

from __future__ import annotations

from excalidraw_mcp.core.models import (
    DiagramGraph,
    Direction,
    Edge,
    Node,
    ShapeType,
)
from excalidraw_mcp.engine.layout import compute_layout
from excalidraw_mcp.engine.renderer import build_excalidraw_file


def _simple_graph(direction: Direction = Direction.LEFT_RIGHT) -> DiagramGraph:
    return DiagramGraph(
        nodes=[
            Node(id="a", label="Service A"),
            Node(id="b", label="Service B"),
            Node(id="c", label="Service C"),
        ],
        edges=[
            Edge(from_id="a", to_id="b"),
            Edge(from_id="b", to_id="c"),
        ],
        direction=direction,
    )


def test_layout_produces_nodes_and_edges():
    result = compute_layout(_simple_graph())
    assert len(result.nodes) == 3
    assert len(result.edges) == 2


def test_no_node_overlaps():
    result = compute_layout(_simple_graph())
    nodes = list(result.nodes)
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            ox = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
            oy = min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
            assert ox <= 0 or oy <= 0, f"{a.node.id} overlaps {b.node.id}"


def test_all_directions():
    for direction in Direction:
        result = compute_layout(_simple_graph(direction))
        assert len(result.nodes) == 3


def test_hub_node_stretching():
    graph = DiagramGraph(
        nodes=[
            Node(id="gw", label="API Gateway"),
            Node(id="s1", label="Service 1"),
            Node(id="s2", label="Service 2"),
            Node(id="s3", label="Service 3"),
        ],
        edges=[
            Edge(from_id="gw", to_id="s1"),
            Edge(from_id="gw", to_id="s2"),
            Edge(from_id="gw", to_id="s3"),
        ],
        direction=Direction.LEFT_RIGHT,
    )
    result = compute_layout(graph)
    gw = next(pn for pn in result.nodes if pn.node.id == "gw")
    children = [pn for pn in result.nodes if pn.node.id != "gw"]
    span_top = min(c.y for c in children)
    span_bottom = max(c.y + c.height for c in children)
    assert gw.height >= (span_bottom - span_top) * 0.8


def test_renderer_produces_valid_excalidraw():
    result = compute_layout(_simple_graph())
    doc = build_excalidraw_file(result, theme_name="default", direction=Direction.LEFT_RIGHT)
    assert doc["type"] == "excalidraw"
    assert doc["version"] == 2
    assert len(doc["elements"]) > 0


def test_component_type_styling():
    graph = DiagramGraph(
        nodes=[
            Node(id="db", label="PostgreSQL", component_type="postgresql"),
            Node(id="cache", label="Redis", component_type="redis"),
        ],
        edges=[Edge(from_id="db", to_id="cache")],
        direction=Direction.LEFT_RIGHT,
    )
    result = compute_layout(graph)
    assert len(result.nodes) == 2


def test_diamond_shape():
    graph = DiagramGraph(
        nodes=[
            Node(id="a", label="Start"),
            Node(id="d", label="Decision?", shape=ShapeType.DIAMOND),
            Node(id="b", label="Yes"),
            Node(id="c", label="No"),
        ],
        edges=[
            Edge(from_id="a", to_id="d"),
            Edge(from_id="d", to_id="b", label="Yes"),
            Edge(from_id="d", to_id="c", label="No"),
        ],
        direction=Direction.TOP_DOWN,
    )
    result = compute_layout(graph)
    assert len(result.nodes) == 4


def test_no_overlaps_complex_graph():
    """Regression test: hub overlap resolution must not pile nodes."""
    graph = DiagramGraph(
        nodes=[
            Node(id="src1", label="Source 1"),
            Node(id="src2", label="Source 2"),
            Node(id="hub", label="Hub Node"),
            Node(id="t1", label="Target 1"),
            Node(id="t2", label="Target 2"),
            Node(id="t3", label="Target 3"),
            Node(id="t4", label="Target 4"),
        ],
        edges=[
            Edge(from_id="src1", to_id="hub"),
            Edge(from_id="src2", to_id="hub"),
            Edge(from_id="hub", to_id="t1"),
            Edge(from_id="hub", to_id="t2"),
            Edge(from_id="hub", to_id="t3"),
            Edge(from_id="hub", to_id="t4"),
        ],
        direction=Direction.TOP_DOWN,
    )
    result = compute_layout(graph)
    nodes = list(result.nodes)
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            ox = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
            oy = min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
            assert ox <= 0 or oy <= 0, f"{a.node.id} overlaps {b.node.id}"
