"""Tests for lint, exporters, diff, docgen, and drift."""

from __future__ import annotations

from excalidraw_mcp.knowledge import diff, docgen, drift, exporters, lint
from excalidraw_mcp.knowledge.models import Dependency, KnowledgeGraph, Service

# --- lint ------------------------------------------------------------------


def test_lint_clean_dag(sample_graph):
    report = lint.lint(sample_graph)
    assert not report.errors
    # gateway/orders/orders-db chain: orders is a SPOF-ish articulation -> warnings allowed
    assert all(f.severity != "error" for f in report.findings)


def test_lint_flags_cycle():
    kg = KnowledgeGraph()
    for i in ("a", "b"):
        kg.add_service(Service(id=i, label=i))
    kg.add_dependency(Dependency(from_id="a", to_id="b"))
    kg.add_dependency(Dependency(from_id="b", to_id="a"))
    codes = {f.code for f in lint.lint(kg).findings}
    assert "cycle" in codes


def test_lint_flags_dangling():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="a"))
    kg.add_service(Service(id="b", label="b"))
    kg.dependencies.append(Dependency(from_id="a", to_id="ghost"))
    report = lint.lint(kg)
    assert any(f.code == "dangling-dependency" for f in report.errors)


def test_lint_flags_orphan():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="a"))
    kg.add_service(Service(id="b", label="b"))
    kg.add_service(Service(id="lonely", label="lonely"))
    kg.add_dependency(Dependency(from_id="a", to_id="b"))
    codes = {f.code for f in lint.lint(kg).findings}
    assert "orphan" in codes


def test_lint_check_owners():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="a"))
    report = lint.lint(kg, check_owners=True)
    assert any(f.code == "unowned" for f in report.findings)


def test_lint_text_render(sample_graph):
    assert isinstance(lint.lint(sample_graph).to_text(), str)


# --- exporters -------------------------------------------------------------


def test_to_mermaid(sample_graph):
    out = exporters.to_mermaid(sample_graph)
    assert out.startswith("flowchart TD")
    assert "gateway --> orders" in out or 'gateway -->|"REST"| orders' in out
    assert "subgraph core" in out


def test_to_dot(sample_graph):
    out = exporters.to_dot(sample_graph)
    assert out.startswith("digraph architecture")
    assert '"gateway" -> "orders"' in out
    assert "cluster_" in out


def test_to_json_round_trips(sample_graph):
    out = exporters.to_json(sample_graph)
    restored = KnowledgeGraph.model_validate_json(out)
    assert restored == sample_graph


def test_mermaid_sanitizes_ids():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="orders-db", label="Orders DB"))
    out = exporters.to_mermaid(kg)
    assert "orders_db" in out  # hyphen sanitized for mermaid


# --- diff ------------------------------------------------------------------


def test_diff_added_removed_changed():
    old = KnowledgeGraph()
    old.add_service(Service(id="a", label="A"))
    old.add_service(Service(id="b", label="B"))
    old.add_dependency(Dependency(from_id="a", to_id="b"))

    new = KnowledgeGraph()
    new.add_service(Service(id="a", label="A renamed"))
    new.add_service(Service(id="c", label="C"))
    new.add_dependency(Dependency(from_id="a", to_id="c"))

    d = diff.diff_graphs(old, new)
    assert d.added_services == ["c"]
    assert d.removed_services == ["b"]
    assert [c.id for c in d.changed_services] == ["a"]
    assert "label" in d.changed_services[0].fields
    assert ("a", "c", "") in d.added_dependencies
    assert ("a", "b", "") in d.removed_dependencies
    assert not d.is_empty


def test_diff_empty_when_identical(sample_graph):
    d = diff.diff_graphs(sample_graph, sample_graph.model_copy(deep=True))
    assert d.is_empty
    assert d.to_text() == "No architectural changes."


# --- docgen ----------------------------------------------------------------


def test_onboarding_doc(sample_graph):
    md = docgen.to_onboarding_markdown(sample_graph)
    assert "# Shop — Onboarding Guide" in md
    assert "Entry points" in md
    assert "gateway" in md
    assert "Orders DB" in md  # data store section
    assert "Core Services" in md  # domain heading


# --- drift -----------------------------------------------------------------


def test_compute_drift_undeclared():
    kg = KnowledgeGraph()
    for i in ("a", "b"):
        kg.add_service(Service(id=i, label=i))
    # graph declares nothing; code shows a -> b
    report = drift.compute_drift(kg, [("a", "b")])
    assert report.undeclared == [("a", "b")]
    assert report.possibly_stale == []


def test_compute_drift_possibly_stale():
    kg = KnowledgeGraph()
    for i in ("a", "b"):
        kg.add_service(Service(id=i, label=i))
    kg.add_dependency(Dependency(from_id="a", to_id="b"))
    # both covered, but no observed edge -> declared edge is possibly stale
    report = drift.compute_drift(kg, [], covered_services=["a", "b"])
    assert report.possibly_stale == [("a", "b")]


def test_compute_drift_unknown_service():
    kg = KnowledgeGraph()
    kg.add_service(Service(id="a", label="a"))
    report = drift.compute_drift(kg, [("a", "ghost")])
    assert "ghost" in report.unknown_services


def test_compute_drift_in_sync():
    kg = KnowledgeGraph()
    for i in ("a", "b"):
        kg.add_service(Service(id=i, label=i))
    kg.add_dependency(Dependency(from_id="a", to_id="b"))
    report = drift.compute_drift(kg, [("a", "b")])
    assert report.in_sync


def test_scan_python_imports(tmp_path):
    # build two fake packages: svc_a imports svc_b
    (tmp_path / "svc_a").mkdir()
    (tmp_path / "svc_b").mkdir()
    (tmp_path / "svc_a" / "__init__.py").write_text("import svc_b\n", encoding="utf-8")
    (tmp_path / "svc_b" / "__init__.py").write_text("", encoding="utf-8")
    edges, covered = drift.scan_python_imports(tmp_path)
    assert ("svc_a", "svc_b") in edges
    assert set(covered) == {"svc_a", "svc_b"}
