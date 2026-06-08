"""Tests for the pure graph-query algorithms."""

from __future__ import annotations

from excalidraw_mcp.knowledge import query
from excalidraw_mcp.knowledge.models import Dependency, KnowledgeGraph, Service


def _chain(*ids: str) -> KnowledgeGraph:
    kg = KnowledgeGraph()
    for i in ids:
        kg.add_service(Service(id=i, label=i))
    for a, b in zip(ids, ids[1:]):
        kg.add_dependency(Dependency(from_id=a, to_id=b))
    return kg


def test_dependencies_and_dependents(sample_graph):
    assert query.dependencies(sample_graph, "gateway") == ["orders", "payments"]
    assert query.dependents(sample_graph, "payments") == ["gateway", "orders"]
    assert query.dependents(sample_graph, "gateway") == []


def test_neighbors(sample_graph):
    assert query.neighbors(sample_graph, "orders") == ["gateway", "orders-db", "payments"]


def test_connected_downstream_depth(sample_graph):
    assert query.connected(sample_graph, "gateway", depth=1, direction="downstream") == [
        "orders",
        "payments",
    ]
    assert query.connected(sample_graph, "gateway", depth=2, direction="downstream") == [
        "orders",
        "orders-db",
        "payments",
    ]


def test_connected_upstream(sample_graph):
    assert query.connected(sample_graph, "orders-db", direction="upstream") == [
        "gateway",
        "orders",
    ]


def test_impact(sample_graph):
    imp = query.impact(sample_graph, "payments")
    assert imp["directly_affected"] == ["gateway", "orders"]
    assert set(imp["transitively_affected"]) == {"gateway", "orders"}


def test_find_path(sample_graph):
    assert query.find_path(sample_graph, "gateway", "orders-db") == [
        "gateway",
        "orders",
        "orders-db",
    ]
    # no path against the arrow direction
    assert query.find_path(sample_graph, "orders-db", "gateway") is None


def test_roots_leaves_orphans():
    kg = _chain("a", "b", "c")
    kg.add_service(Service(id="lonely", label="lonely"))
    assert query.roots(kg) == ["a", "lonely"]
    assert query.leaves(kg) == ["c", "lonely"]
    assert query.orphans(kg) == ["lonely"]


def test_cycles_detected():
    kg = _chain("a", "b", "c")
    kg.add_dependency(Dependency(from_id="c", to_id="a"))
    assert query.cycles(kg) == [["a", "b", "c"]]
    assert query.has_cycle(kg)


def test_no_cycles_on_dag(sample_graph):
    assert query.cycles(sample_graph) == []
    assert not query.has_cycle(sample_graph)


def test_single_point_of_failure():
    # a - b - c : b is the articulation point
    kg = KnowledgeGraph()
    for i in ("a", "b", "c"):
        kg.add_service(Service(id=i, label=i))
    kg.add_dependency(Dependency(from_id="a", to_id="b"))
    kg.add_dependency(Dependency(from_id="b", to_id="c"))
    assert query.single_points_of_failure(kg) == ["b"]


def test_no_spof_in_triangle():
    kg = KnowledgeGraph()
    for i in ("a", "b", "c"):
        kg.add_service(Service(id=i, label=i))
    kg.add_dependency(Dependency(from_id="a", to_id="b"))
    kg.add_dependency(Dependency(from_id="b", to_id="c"))
    kg.add_dependency(Dependency(from_id="c", to_id="a"))
    assert query.single_points_of_failure(kg) == []


def test_hubs(sample_graph):
    hubs = query.hubs(sample_graph, min_degree=3)
    ids = [h[0] for h in hubs]
    assert "orders" in ids


def test_services_by_owner(sample_graph):
    by_owner = query.services_by_owner(sample_graph)
    assert by_owner["@orders"] == ["orders"]
    assert "(unowned)" in by_owner


def test_unowned_services(sample_graph):
    unowned = query.unowned_services(sample_graph)
    assert "gateway" in unowned
    assert "orders" not in unowned
