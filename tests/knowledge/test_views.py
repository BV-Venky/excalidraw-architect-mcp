"""Tests for rendering projections to .excalidraw."""

from __future__ import annotations

import json

from excalidraw_mcp.knowledge import views


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _node_count(doc) -> int:
    # exact node count from embedded metadata (rendered rectangles also include
    # domain/subgraph bounding boxes, so don't count shapes)
    return len(doc["appState"]["customData"]["excalidraw_mcp"]["nodes"])


def test_render_full(sample_graph, tmp_path):
    out = tmp_path / "full.excalidraw"
    msg = views.render(sample_graph, out)
    assert "4 node" in msg
    doc = _load(out)
    assert doc["type"] == "excalidraw"
    assert _node_count(doc) == 4


def test_render_view_subset(sample_graph, tmp_path):
    out = tmp_path / "view.excalidraw"
    msg = views.render_view(sample_graph, ["gateway", "orders"], out)
    assert "2 node" in msg
    assert _node_count(_load(out)) == 2


def test_render_view_reports_unknown(sample_graph, tmp_path):
    out = tmp_path / "view.excalidraw"
    msg = views.render_view(sample_graph, ["gateway", "ghost"], out)
    assert "skipped unknown" in msg
    assert "ghost" in msg


def test_render_around(sample_graph, tmp_path):
    out = tmp_path / "around.excalidraw"
    msg = views.render_around(sample_graph, "orders", depth=1, output_path=out)
    # orders + gateway, payments, orders-db all within 1 hop
    assert "4 node" in msg


def test_render_around_downstream_only(sample_graph, tmp_path):
    out = tmp_path / "around.excalidraw"
    msg = views.render_around(
        sample_graph, "orders", depth=1, output_path=out, direction="downstream"
    )
    # orders + payments + orders-db = 3
    assert "3 node" in msg


def test_render_domain(sample_graph, tmp_path):
    out = tmp_path / "domain.excalidraw"
    msg = views.render_domain(sample_graph, "core", out)
    assert "3 node" in msg


def test_parallel_edges_render_as_distinct_arrows(tmp_path):
    """Two communication modes between the same pair render as two routes."""
    from excalidraw_mcp.core.models import EdgeStyle
    from excalidraw_mcp.engine.layout import compute_layout
    from excalidraw_mcp.knowledge.models import Dependency, KnowledgeGraph, Service

    kg = KnowledgeGraph()
    kg.add_service(Service(id="orders", label="Orders"))
    kg.add_service(Service(id="payments", label="Payments"))
    kg.add_dependency(Dependency(from_id="orders", to_id="payments", label="REST"))
    kg.add_dependency(
        Dependency(from_id="orders", to_id="payments", label="Kafka", style=EdgeStyle.DASHED)
    )
    layout = compute_layout(kg.to_diagram_graph())
    assert len(layout.edges) == 2
    routes = [e.points for e in layout.edges]
    # distinct routes, and at least one bowed (3-point) so they don't overlap
    assert routes[0] != routes[1]
    assert any(len(r) == 3 for r in routes)


def test_render_empty_graph(tmp_path):
    from excalidraw_mcp.knowledge.models import KnowledgeGraph

    msg = views.render(KnowledgeGraph(), tmp_path / "x.excalidraw")
    assert "empty" in msg.lower()
