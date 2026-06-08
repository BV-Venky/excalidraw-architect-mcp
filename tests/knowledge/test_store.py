"""Tests for the file-backed store + CRUD orchestration."""

from __future__ import annotations

from excalidraw_mcp.knowledge import store


def test_init_and_load(tmp_path):
    p = tmp_path / "arch.md"
    store.init_graph(p, title="My Sys", direction="TD")
    kg = store.load_graph(p)
    assert kg.title == "My Sys"
    assert kg.direction.value == "TD"
    assert kg.services == []


def test_init_does_not_overwrite_by_default(tmp_path):
    p = tmp_path / "arch.md"
    store.init_graph(p)
    store.add_service(p, id="a", label="A")
    msg = store.init_graph(p)
    assert "already exists" in msg
    assert store.load_graph(p).has_service("a")


def test_load_missing_returns_empty(tmp_path):
    kg = store.load_graph(tmp_path / "nope.md")
    assert kg.services == []


def test_add_service_persists(tmp_path):
    p = tmp_path / "arch.md"
    store.add_service(p, id="db", label="Postgres", component_type="postgresql")
    kg = store.load_graph(p)
    assert kg.service_by_id("db").component_type == "postgresql"


def test_link_requires_existing_services(tmp_path):
    p = tmp_path / "arch.md"
    store.add_service(p, id="a", label="A")
    msg = store.link(p, from_id="a", to_id="ghost")
    assert "Error" in msg
    assert store.load_graph(p).dependencies == []


def test_link_and_unlink(tmp_path):
    p = tmp_path / "arch.md"
    store.add_service(p, id="a", label="A")
    store.add_service(p, id="b", label="B")
    store.link(p, from_id="a", to_id="b", label="calls")
    assert store.load_graph(p).dependency("a", "b").label == "calls"
    store.unlink(p, from_id="a", to_id="b")
    assert store.load_graph(p).dependencies == []


def test_remove_service_via_store(tmp_path):
    p = tmp_path / "arch.md"
    store.add_service(p, id="a", label="A")
    store.add_service(p, id="b", label="B")
    store.link(p, from_id="a", to_id="b")
    msg = store.remove_service(p, id="b")
    assert "Removed" in msg
    kg = store.load_graph(p)
    assert not kg.has_service("b")
    assert kg.dependencies == []


def test_set_domain(tmp_path):
    p = tmp_path / "arch.md"
    store.add_service(p, id="a", label="A")
    store.set_domain(p, service_id="a", domain="core", label="Core")
    kg = store.load_graph(p)
    assert kg.service_by_id("a").domain == "core"
    assert kg.domain_label("core") == "Core"


def test_graph_summary(tmp_path):
    p = tmp_path / "arch.md"
    store.add_service(p, id="a", label="A", owner="@x")
    store.add_service(p, id="b", label="B")
    store.link(p, from_id="a", to_id="b")
    summary = store.graph_summary(p)
    assert "2 service" in summary
    assert "a" in summary and "b" in summary


def test_summary_missing_file(tmp_path):
    assert "No knowledge graph" in store.graph_summary(tmp_path / "nope.md")
