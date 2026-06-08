"""Detect drift between the declared architecture and the real code.

The documented graph promises to stay accurate; drift detection enforces it.
``compute_drift`` is the pure, testable core: given edges *observed* from some
source of truth (import scan, traces, service mesh), it reports couplings that
exist but aren't documented, and documented couplings that no longer appear.

``scan_python_imports`` is a best-effort observer that infers edges from Python
``import`` statements, treating each top-level package under a root as a service.
It is intentionally simple and language-specific; richer observers can feed
``compute_drift`` directly.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, Field

from excalidraw_mcp.knowledge.models import KnowledgeGraph


class DriftReport(BaseModel):
    # Observed in code but not declared in the knowledge graph.
    undeclared: list[tuple[str, str]] = Field(default_factory=list)
    # Declared in the graph but never observed (between covered services).
    possibly_stale: list[tuple[str, str]] = Field(default_factory=list)
    # Services referenced in observations that aren't in the graph.
    unknown_services: list[str] = Field(default_factory=list)

    @property
    def in_sync(self) -> bool:
        return not (self.undeclared or self.possibly_stale)

    def to_text(self) -> str:
        if self.in_sync and not self.unknown_services:
            return "Architecture is in sync with the observed code."
        lines = ["Drift report:"]
        for f, t in self.undeclared:
            lines.append(f"  + undocumented dependency {f} -> {t} (found in code)")
        for f, t in self.possibly_stale:
            lines.append(f"  ? declared dependency {f} -> {t} not observed (possibly stale)")
        if self.unknown_services:
            lines.append(f"  ! observed services not in graph: {', '.join(self.unknown_services)}")
        return "\n".join(lines)


def compute_drift(
    kg: KnowledgeGraph,
    observed_edges: Iterable[tuple[str, str]],
    covered_services: Iterable[str] | None = None,
) -> DriftReport:
    """Compare declared dependencies against observed edges.

    Args:
        kg: the declared architecture.
        observed_edges: (from, to) couplings found in the real system.
        covered_services: services for which observation data exists. A declared
            edge is only flagged ``possibly_stale`` when *both* endpoints are
            covered (so partial observation doesn't raise false positives).
            Defaults to every service that appears in ``observed_edges``.
    """
    ids = kg.service_ids
    observed = {(f, t) for f, t in observed_edges if f != t}

    unknown = sorted({s for edge in observed for s in edge} - ids)

    observed_known = {(f, t) for f, t in observed if f in ids and t in ids}
    declared = {d.key for d in kg.dependencies}

    if covered_services is None:
        covered = {s for edge in observed_known for s in edge}
    else:
        covered = set(covered_services)

    undeclared = sorted(observed_known - declared)
    possibly_stale = sorted(
        edge for edge in (declared - observed_known) if edge[0] in covered and edge[1] in covered
    )

    return DriftReport(
        undeclared=undeclared,
        possibly_stale=possibly_stale,
        unknown_services=unknown,
    )


def scan_python_imports(
    root: str | Path,
    service_packages: dict[str, str] | None = None,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Infer dependency edges from Python imports under ``root``.

    Each top-level package directory under ``root`` is treated as a service
    (id = directory name) unless ``service_packages`` maps service-id ->
    top-level package name explicitly.

    Returns ``(observed_edges, covered_services)``.
    """
    root_path = Path(root)
    if service_packages is None:
        service_packages = {
            p.name: p.name
            for p in root_path.iterdir()
            if p.is_dir() and not p.name.startswith(".") and (p / "__init__.py").exists()
        }
    pkg_to_service = {pkg: sid for sid, pkg in service_packages.items()}

    edges: set[tuple[str, str]] = set()
    covered: set[str] = set()

    for sid, pkg in service_packages.items():
        pkg_dir = root_path / pkg
        if not pkg_dir.exists():
            continue
        covered.add(sid)
        for py in pkg_dir.rglob("*.py"):
            for imported_pkg in _imported_top_levels(py):
                target = pkg_to_service.get(imported_pkg)
                if target and target != sid:
                    edges.add((sid, target))

    return sorted(edges), sorted(covered)


def _imported_top_levels(py_file: Path) -> set[str]:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return set()
    tops: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                tops.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            tops.add(node.module.split(".")[0])
    return tops
