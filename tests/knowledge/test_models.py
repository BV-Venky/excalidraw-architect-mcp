"""Tests for the KnowledgeGraph model and projection to DiagramGraph."""

from __future__ import annotations

import pytest

from excalidraw_mcp.knowledge.models import (
    Dependency,
    KnowledgeGraph,
    KnowledgeGraphError,
    Service,
)


def test_add_service_and_lookup():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="A"))
    assert kg.has_service("a")
    assert kg.service_by_id("a").label == "A"
    assert kg.service_ids == {"a"}


def test_add_service_upsert_updates_in_place():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="A"))
    kg.add_service(Service(id="a", label="A2", owner="@x"))
    assert len(kg.services) == 1
    assert kg.service_by_id("a").label == "A2"
    assert kg.service_by_id("a").owner == "@x"


def test_add_duplicate_service_without_upsert_raises():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="A"))
    with pytest.raises(KnowledgeGraphError):
        kg.add_service(Service(id="a", label="A"), upsert=False)


def test_add_dependency_unknown_endpoint_raises():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="A"))
    with pytest.raises(KnowledgeGraphError):
        kg.add_dependency(Dependency(from_id="a", to_id="ghost"))


def test_self_dependency_raises():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="A"))
    with pytest.raises(KnowledgeGraphError):
        kg.add_dependency(Dependency(from_id="a", to_id="a"))


def test_remove_service_cascades_dependencies():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="A"))
    kg.add_service(Service(id="b", label="B"))
    kg.add_dependency(Dependency(from_id="a", to_id="b"))
    assert kg.remove_service("b") is True
    assert not kg.has_service("b")
    assert kg.dependencies == []


def test_dependency_upsert_same_triple_replaces():
    """Same (from, to, label) upserts (style updated), not duplicated."""
    from excalidraw_mcp.core.models import EdgeStyle

    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="A"))
    kg.add_service(Service(id="b", label="B"))
    kg.add_dependency(Dependency(from_id="a", to_id="b", label="rest"))
    kg.add_dependency(Dependency(from_id="a", to_id="b", label="rest", style=EdgeStyle.THICK))
    assert len(kg.dependencies) == 1
    assert kg.dependency("a", "b", "rest").style == EdgeStyle.THICK


def test_parallel_edges_with_different_labels_coexist():
    """Two communication modes between the same services are kept as two edges."""
    kg = KnowledgeGraph()
    kg.add_service(Service(id="orders", label="Orders"))
    kg.add_service(Service(id="payments", label="Payments"))
    kg.add_dependency(Dependency(from_id="orders", to_id="payments", label="REST /charge"))
    kg.add_dependency(Dependency(from_id="orders", to_id="payments", label="Kafka order.created"))
    assert len(kg.dependencies) == 2
    assert len(kg.dependencies_between("orders", "payments")) == 2
    # both surface as distinct edges in the projection
    dg = kg.to_diagram_graph()
    assert len(dg.edges) == 2
    assert {e.label for e in dg.edges} == {"REST /charge", "Kafka order.created"}


def test_remove_dependency_by_label():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="A"))
    kg.add_service(Service(id="b", label="B"))
    kg.add_dependency(Dependency(from_id="a", to_id="b", label="rest"))
    kg.add_dependency(Dependency(from_id="a", to_id="b", label="kafka"))
    assert kg.remove_dependency("a", "b", label="rest") == 1
    assert [d.label for d in kg.dependencies] == ["kafka"]


def test_remove_dependency_all_between():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="A"))
    kg.add_service(Service(id="b", label="B"))
    kg.add_dependency(Dependency(from_id="a", to_id="b", label="rest"))
    kg.add_dependency(Dependency(from_id="a", to_id="b", label="kafka"))
    assert kg.remove_dependency("a", "b") == 2
    assert kg.dependencies == []


def test_domain_membership_derived_from_services(sample_graph):
    assert set(sample_graph.domain_members("core")) == {"orders", "payments", "orders-db"}
    assert sample_graph.domain_members("edge") == ["gateway"]
    assert sample_graph.domain_label("core") == "Core Services"
    # unknown domain label falls back to id
    assert sample_graph.domain_label("nope") == "nope"


def test_to_diagram_graph_full(sample_graph):
    dg = sample_graph.to_diagram_graph()
    assert {n.id for n in dg.nodes} == {"gateway", "orders", "payments", "orders-db"}
    assert len(dg.edges) == 4
    assert {sg.id for sg in dg.subgraphs} == {"edge", "core"}


def test_to_diagram_graph_subset_induces_edges(sample_graph):
    dg = sample_graph.to_diagram_graph(["gateway", "orders"])
    assert {n.id for n in dg.nodes} == {"gateway", "orders"}
    # only the gateway->orders edge survives (both endpoints present)
    assert [(e.from_id, e.to_id) for e in dg.edges] == [("gateway", "orders")]


def test_to_diagram_graph_unknown_ids_ignored(sample_graph):
    dg = sample_graph.to_diagram_graph(["gateway", "ghost"])
    assert {n.id for n in dg.nodes} == {"gateway"}


def test_dangling_dependencies_detection():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="A"))
    kg.add_service(Service(id="b", label="B"))
    kg.add_dependency(Dependency(from_id="a", to_id="b"))
    # forcibly introduce a dangling edge (simulating a hand edit)
    kg.dependencies.append(Dependency(from_id="a", to_id="ghost"))
    dangling = kg.dangling_dependencies()
    assert len(dangling) == 1
    assert dangling[0].to_id == "ghost"
