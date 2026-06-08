"""Tests for importing existing .excalidraw diagrams into the knowledge graph."""

from __future__ import annotations

import pytest

from excalidraw_mcp.core.models import DiagramGraph, Direction, Edge, Node
from excalidraw_mcp.engine.layout import compute_layout
from excalidraw_mcp.engine.renderer import build_excalidraw_file, save_excalidraw
from excalidraw_mcp.knowledge import migrate
from excalidraw_mcp.knowledge.models import KnowledgeGraph, Service


def _make_excalidraw(tmp_path):
    graph = DiagramGraph(
        nodes=[
            Node(id="web", label="Web", component_type="nginx"),
            Node(id="api", label="API"),
            Node(id="db", label="Database", component_type="postgresql"),
        ],
        edges=[Edge(from_id="web", to_id="api"), Edge(from_id="api", to_id="db")],
        direction=Direction.LEFT_RIGHT,
    )
    layout = compute_layout(graph)
    doc = build_excalidraw_file(layout, direction=Direction.LEFT_RIGHT)
    path = tmp_path / "arch.excalidraw"
    save_excalidraw(doc, path)
    return path


def test_import_into_empty_graph(tmp_path):
    src = _make_excalidraw(tmp_path)
    kg = KnowledgeGraph()
    added_s, added_d = migrate.merge_excalidraw(kg, src)
    assert added_s == 3
    assert added_d == 2
    assert kg.service_by_id("db").component_type == "postgresql"
    assert kg.dependency("web", "api") is not None


def test_import_does_not_clobber_existing(tmp_path):
    src = _make_excalidraw(tmp_path)
    kg = KnowledgeGraph()
    kg.add_service(Service(id="api", label="My Custom API", owner="@me"))
    added_s, _ = migrate.merge_excalidraw(kg, src)
    assert added_s == 2  # web + db, not api
    assert kg.service_by_id("api").label == "My Custom API"
    assert kg.service_by_id("api").owner == "@me"


def test_import_is_idempotent(tmp_path):
    src = _make_excalidraw(tmp_path)
    kg = KnowledgeGraph()
    migrate.merge_excalidraw(kg, src)
    added_s, added_d = migrate.merge_excalidraw(kg, src)
    assert added_s == 0
    assert added_d == 0


def test_import_non_tool_file_raises(tmp_path):
    bad = tmp_path / "plain.excalidraw"
    bad.write_text('{"type": "excalidraw", "elements": [], "appState": {}}', encoding="utf-8")
    with pytest.raises(ValueError):
        migrate.merge_excalidraw(KnowledgeGraph(), bad)
