"""Diff two knowledge graphs — the basis for "what changed in the architecture".

Because the knowledge file is version-controlled, diffing the working copy
against a git ref answers "what did this PR change architecturally?". The core
``diff_graphs`` is pure and fully testable; ``load_from_git_ref`` is a thin,
best-effort git helper used by the MCP tool.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from excalidraw_mcp.knowledge.models import KnowledgeGraph
from excalidraw_mcp.knowledge.parser import parse


class ServiceChange(BaseModel):
    id: str
    fields: list[str] = Field(default_factory=list)


class GraphDiff(BaseModel):
    added_services: list[str] = Field(default_factory=list)
    removed_services: list[str] = Field(default_factory=list)
    changed_services: list[ServiceChange] = Field(default_factory=list)
    # (from_id, to_id, label) — label distinguishes parallel edges
    added_dependencies: list[tuple[str, str, str]] = Field(default_factory=list)
    removed_dependencies: list[tuple[str, str, str]] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (
            self.added_services
            or self.removed_services
            or self.changed_services
            or self.added_dependencies
            or self.removed_dependencies
        )

    def to_text(self) -> str:
        if self.is_empty:
            return "No architectural changes."
        lines = ["Architecture changes:"]
        for sid in self.added_services:
            lines.append(f"  + service {sid}")
        for sid in self.removed_services:
            lines.append(f"  - service {sid}")
        for ch in self.changed_services:
            lines.append(f"  ~ service {ch.id} ({', '.join(ch.fields)})")
        for f, t, lbl in self.added_dependencies:
            lines.append(f"  + dependency {f} -> {t}{f' ({lbl})' if lbl else ''}")
        for f, t, lbl in self.removed_dependencies:
            lines.append(f"  - dependency {f} -> {t}{f' ({lbl})' if lbl else ''}")
        return "\n".join(lines)


_COMPARED_FIELDS = ("label", "component_type", "domain", "owner", "description", "tags")


def diff_graphs(old: KnowledgeGraph, new: KnowledgeGraph) -> GraphDiff:
    """Compute the structural diff from ``old`` to ``new``."""
    old_ids = old.service_ids
    new_ids = new.service_ids

    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)

    changed: list[ServiceChange] = []
    for sid in sorted(old_ids & new_ids):
        os_, ns_ = old.service_by_id(sid), new.service_by_id(sid)
        diff_fields = [f for f in _COMPARED_FIELDS if getattr(os_, f) != getattr(ns_, f)]
        if diff_fields:
            changed.append(ServiceChange(id=sid, fields=diff_fields))

    old_deps = {(d.from_id, d.to_id, d.label or "") for d in old.dependencies}
    new_deps = {(d.from_id, d.to_id, d.label or "") for d in new.dependencies}
    added_deps = sorted(new_deps - old_deps)
    removed_deps = sorted(old_deps - new_deps)

    return GraphDiff(
        added_services=added,
        removed_services=removed,
        changed_services=changed,
        added_dependencies=added_deps,
        removed_dependencies=removed_deps,
    )


def load_from_git_ref(path: str | Path, ref: str = "HEAD") -> KnowledgeGraph:
    """Load the knowledge file as it existed at a git ref. Raises on git error."""
    p = Path(path)
    # Resolve the path relative to the repo root for `git show`.
    rel = _repo_relative(p)
    out = subprocess.run(
        ["git", "show", f"{ref}:{rel}"],
        capture_output=True,
        text=True,
        cwd=p.resolve().parent,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"git show {ref}:{rel} failed")
    return parse(out.stdout)


def _repo_relative(path: Path) -> str:
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=path.resolve().parent,
        )
        if root.returncode == 0:
            top = Path(root.stdout.strip())
            return str(path.resolve().relative_to(top))
    except (subprocess.SubprocessError, ValueError):
        pass
    return path.name
