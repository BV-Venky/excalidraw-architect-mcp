"""Round-trip and tolerance tests for the markdown DSL parser."""

from __future__ import annotations

from excalidraw_mcp.core.models import Direction, EdgeStyle, ShapeType
from excalidraw_mcp.knowledge.models import Dependency, KnowledgeGraph, Service
from excalidraw_mcp.knowledge.parser import is_knowledge_graph, parse, serialize


def test_round_trip_identity(sample_graph):
    """parse(serialize(kg)) == kg for an API-built graph."""
    assert parse(serialize(sample_graph)) == sample_graph


def test_round_trip_empty_graph():
    kg = KnowledgeGraph()
    assert parse(serialize(kg)) == kg


def test_round_trip_preserves_all_service_fields():
    kg = KnowledgeGraph()
    kg.add_service(
        Service(
            id="svc",
            label="My Service",
            component_type="kafka",
            shape=ShapeType.DIAMOND,
            description="does things",
            domain="data",
            owner="@team",
            tags=["a", "b", "c"],
            links=["https://x", "https://y"],
        )
    )
    out = parse(serialize(kg))
    s = out.service_by_id("svc")
    assert s.label == "My Service"
    assert s.component_type == "kafka"
    assert s.shape == ShapeType.DIAMOND
    assert s.description == "does things"
    assert s.domain == "data"
    assert s.owner == "@team"
    assert s.tags == ["a", "b", "c"]
    assert s.links == ["https://x", "https://y"]


def test_round_trip_dependency_style_and_label():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="a"))
    kg.add_service(Service(id="b", label="b"))
    kg.add_dependency(Dependency(from_id="a", to_id="b", label="calls", style=EdgeStyle.DASHED))
    out = parse(serialize(kg))
    d = out.dependency("a", "b")
    assert d.label == "calls"
    assert d.style == EdgeStyle.DASHED


def test_label_omitted_when_equal_to_id():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="redis", label="redis"))
    text = serialize(kg)
    assert "- redis\n" in text or "- redis " in text or text.count("redis") == 1
    assert ": redis" not in text  # no redundant label


def test_parse_is_tolerant_of_hand_edits():
    text = """# Hand Written

## Services
-   gateway :  API Gateway   [type: nginx]
- db [type: postgres]

## Dependencies
- gateway   ->   db   :  "queries"
"""
    kg = parse(text)
    assert kg.title == "Hand Written"
    assert kg.service_by_id("gateway").label == "API Gateway"
    assert kg.service_by_id("gateway").component_type == "nginx"
    assert kg.dependency("gateway", "db").label == "queries"


def test_parse_direction_comment():
    text = "# T\n<!-- direction: TD -->\n\n## Services\n- a\n"
    assert parse(text).direction == Direction.TOP_DOWN


def test_parse_ignores_unknown_lines():
    text = "# T\n\nsome prose that is not a list item\n\n## Services\n- a\n> a quote\n"
    kg = parse(text)
    assert kg.service_ids == {"a"}


def test_is_knowledge_graph_detection(sample_graph):
    assert is_knowledge_graph(serialize(sample_graph))
    assert not is_knowledge_graph("# Just a normal markdown file\n")


def test_parallel_edges_round_trip():
    """Two labelled edges between the same services survive serialize/parse."""
    kg = KnowledgeGraph()
    kg.add_service(Service(id="orders", label="orders"))
    kg.add_service(Service(id="payments", label="payments"))
    kg.add_dependency(Dependency(from_id="orders", to_id="payments", label="REST"))
    kg.add_dependency(
        Dependency(from_id="orders", to_id="payments", label="Kafka", style=EdgeStyle.DASHED)
    )
    out = parse(serialize(kg))
    assert out == kg
    between = out.dependencies_between("orders", "payments")
    assert {d.label for d in between} == {"REST", "Kafka"}


def test_dependency_without_label_round_trips():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="a"))
    kg.add_service(Service(id="b", label="b"))
    kg.add_dependency(Dependency(from_id="a", to_id="b"))
    out = parse(serialize(kg))
    d = out.dependency("a", "b")
    assert d.label is None
    assert d.style == EdgeStyle.SOLID
