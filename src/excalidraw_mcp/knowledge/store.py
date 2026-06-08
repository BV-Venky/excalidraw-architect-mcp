"""File I/O and high-level CRUD orchestration for the knowledge graph.

This is the only module that knows where the knowledge file lives. It mirrors
the ``parsers/state.py`` pattern: load -> mutate -> save -> return a summary
string suitable for an MCP tool response.
"""

from __future__ import annotations

from pathlib import Path

from excalidraw_mcp.core.models import EdgeStyle, ShapeType
from excalidraw_mcp.knowledge.models import (
    Dependency,
    KnowledgeGraph,
    KnowledgeGraphError,
    Service,
)
from excalidraw_mcp.knowledge.parser import parse, serialize

DEFAULT_KG_PATH = ".claude/architecture.md"


# ---------------------------------------------------------------------------
# Low-level I/O
# ---------------------------------------------------------------------------


def load_graph(path: str | Path = DEFAULT_KG_PATH) -> KnowledgeGraph:
    """Load and parse the knowledge file. Empty graph if the file is absent."""
    p = Path(path)
    if not p.exists():
        return KnowledgeGraph()
    return parse(p.read_text(encoding="utf-8"))


def save_graph(kg: KnowledgeGraph, path: str | Path = DEFAULT_KG_PATH) -> Path:
    """Serialize and write the knowledge file (creates parent dirs)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(serialize(kg), encoding="utf-8")
    return p


def graph_exists(path: str | Path = DEFAULT_KG_PATH) -> bool:
    return Path(path).exists()


def _n_deps(kg: KnowledgeGraph) -> str:
    n = len(kg.dependencies)
    return f"{n} dependency" if n == 1 else f"{n} dependencies"


# ---------------------------------------------------------------------------
# High-level operations (load -> mutate -> save -> summary)
# ---------------------------------------------------------------------------


def init_graph(
    path: str | Path = DEFAULT_KG_PATH,
    title: str = "System Architecture",
    direction: str = "LR",
    *,
    overwrite: bool = False,
) -> str:
    """Create a new (empty) knowledge file."""
    p = Path(path)
    if p.exists() and not overwrite:
        return (
            f"Knowledge graph already exists at {p}. "
            f"It has {len(load_graph(p).services)} service(s). "
            "Pass overwrite=True to replace it."
        )
    kg = KnowledgeGraph(title=title)
    kg.direction = _coerce_direction(direction)
    save_graph(kg, p)
    return f"Initialized empty knowledge graph at {p} (title: {title!r}, direction: {direction})."


def add_service(
    path: str | Path = DEFAULT_KG_PATH,
    *,
    id: str,
    label: str | None = None,
    component_type: str | None = None,
    shape: str | None = None,
    description: str | None = None,
    domain: str | None = None,
    owner: str | None = None,
    tags: list[str] | None = None,
    links: list[str] | None = None,
) -> str:
    kg = load_graph(path)
    existed = kg.has_service(id)
    service = Service(
        id=id,
        label=label or id,
        component_type=component_type,
        shape=_coerce_shape(shape),
        description=description,
        domain=domain,
        owner=owner,
        tags=tags or [],
        links=links or [],
    )
    kg.add_service(service)
    save_graph(kg, path)
    verb = "Updated" if existed else "Added"
    extra = f" [{component_type}]" if component_type else ""
    return f"{verb} service '{id}'{extra}. Graph now has {len(kg.services)} service(s)."


def remove_service(path: str | Path = DEFAULT_KG_PATH, *, id: str) -> str:
    kg = load_graph(path)
    n_before = len(kg.dependencies)
    removed = kg.remove_service(id)
    if not removed:
        return f"Service '{id}' not found."
    dropped = n_before - len(kg.dependencies)
    save_graph(kg, path)
    return (
        f"Removed service '{id}' and {dropped} dependency/dependencies. "
        f"Graph now has {len(kg.services)} service(s)."
    )


def link(
    path: str | Path = DEFAULT_KG_PATH,
    *,
    from_id: str,
    to_id: str,
    label: str | None = None,
    style: str | None = None,
) -> str:
    kg = load_graph(path)
    existed = kg.dependency(from_id, to_id, label) is not None
    parallel = kg.dependencies_between(from_id, to_id)
    try:
        kg.add_dependency(
            Dependency(
                from_id=from_id,
                to_id=to_id,
                label=label,
                style=_coerce_style(style),
            )
        )
    except KnowledgeGraphError as exc:
        return f"Error: {exc}. Add the service(s) first with add_service."
    save_graph(kg, path)
    label_str = f' labelled "{label}"' if label else ""
    if existed:
        verb = f"Updated link {from_id} -> {to_id}{label_str}"
    elif parallel:
        # adding a second, differently-labelled edge between the same services
        verb = f"Added parallel link {from_id} -> {to_id}{label_str}"
    else:
        verb = f"Linked {from_id} -> {to_id}{label_str}"
    return f"{verb}. Graph now has {_n_deps(kg)}."


def unlink(
    path: str | Path = DEFAULT_KG_PATH,
    *,
    from_id: str,
    to_id: str,
    label: str | None = None,
) -> str:
    kg = load_graph(path)
    removed = kg.remove_dependency(from_id, to_id, label)
    if not removed:
        which = f' labelled "{label}"' if label else ""
        return f"No dependency {from_id} -> {to_id}{which} found."
    save_graph(kg, path)
    suffix = f" ({removed} edges)" if removed > 1 else ""
    return f"Unlinked {from_id} -> {to_id}{suffix}. Graph now has {_n_deps(kg)}."


def set_domain(
    path: str | Path = DEFAULT_KG_PATH,
    *,
    service_id: str,
    domain: str,
    label: str | None = None,
) -> str:
    kg = load_graph(path)
    svc = kg.service_by_id(service_id)
    if svc is None:
        return f"Service '{service_id}' not found."
    svc.domain = domain
    if label:
        kg.set_domain_label(domain, label)
    save_graph(kg, path)
    return f"Assigned '{service_id}' to domain '{domain}'."


# ---------------------------------------------------------------------------
# Summary (analogous to get_diagram_summary)
# ---------------------------------------------------------------------------


def graph_summary(path: str | Path = DEFAULT_KG_PATH) -> str:
    """Human-readable overview of the whole knowledge graph."""
    p = Path(path)
    if not p.exists():
        return (
            f"No knowledge graph at {p}. Create one with kg_init, or import an "
            "existing .excalidraw diagram with kg_import."
        )
    kg = load_graph(p)
    lines: list[str] = [
        f"Knowledge graph: {kg.title} ({p})",
        f"{len(kg.services)} service(s), {len(kg.dependencies)} dependency/dependencies, "
        f"{len(kg.domain_ids)} domain(s) · direction {kg.direction.value}",
        "",
    ]

    if kg.domain_ids:
        lines.append("Domains:")
        for did in kg.domain_ids:
            members = kg.domain_members(did)
            lines.append(f"  - {kg.domain_label(did)} [{did}]: {', '.join(members)}")
        lines.append("")

    if kg.services:
        lines.append("Services:")
        for s in kg.services:
            out = [d.to_id for d in kg.dependencies if d.from_id == s.id]
            inc = [d.from_id for d in kg.dependencies if d.to_id == s.id]
            bits: list[str] = []
            if s.component_type:
                bits.append(s.component_type)
            if s.owner:
                bits.append(f"owner {s.owner}")
            meta = f" ({', '.join(bits)})" if bits else ""
            conn: list[str] = []
            if inc:
                conn.append(f"<- {', '.join(inc)}")
            if out:
                conn.append(f"-> {', '.join(out)}")
            conn_str = f"  [{'; '.join(conn)}]" if conn else ""
            lines.append(f'  - {s.id}: "{s.label}"{meta}{conn_str}')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def _coerce_shape(value: str | None) -> ShapeType:
    if not value:
        return ShapeType.RECTANGLE
    try:
        return ShapeType(value.strip().lower())
    except ValueError:
        return ShapeType.RECTANGLE


def _coerce_style(value: str | None) -> EdgeStyle:
    if not value:
        return EdgeStyle.SOLID
    try:
        return EdgeStyle(value.strip().lower())
    except ValueError:
        return EdgeStyle.SOLID


def _coerce_direction(value: str | None):
    from excalidraw_mcp.core.models import Direction

    if not value:
        return Direction.LEFT_RIGHT
    try:
        return Direction(value.strip().upper())
    except ValueError:
        return Direction.LEFT_RIGHT
