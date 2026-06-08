"""Markdown DSL <-> KnowledgeGraph.

The knowledge file is human-readable *and* machine-parseable. ``serialize``
produces a deterministic canonical form; ``parse`` reads it back (and tolerates
hand edits). For any graph built through the model API,
``parse(serialize(kg)) == kg`` (excluding the in-memory-only ``metadata`` field,
which is intentionally not persisted to markdown).

Canonical form::

    # System Architecture
    <!-- excalidraw-architect: knowledge-graph v1 -->
    <!-- direction: LR -->

    ## Services
    - gateway: API Gateway [type: nginx] [domain: edge] — public entrypoint
    - payments [type: service] [domain: core] [owner: @pay] [tags: pci, money]

    ## Dependencies
    - gateway -> payments : "REST /pay" [style: thick]

    ## Domains
    - edge — Edge Tier
    - core — Core Services

Line grammar:
- Service: ``- <id>[: <label>] [<k>: <v>]... [— <description>]``
- Dependency: ``- <from> -> <to> [: "<label>"] [[style: <s>]]``
- Domain: ``- <id> — <label>``
"""

from __future__ import annotations

import re

from excalidraw_mcp.core.models import Direction, EdgeStyle, ShapeType
from excalidraw_mcp.knowledge.models import (
    Dependency,
    Domain,
    KnowledgeGraph,
    Service,
)

_MARKER = "excalidraw-architect: knowledge-graph"

# Em dash or "--" used as the description separator.
_DESC_SPLIT = re.compile(r"\s+(?:—|--)\s+")
_ATTR = re.compile(r"\[([a-zA-Z_]+):\s*([^\]]*)\]")
_VERSION_COMMENT = re.compile(rf"<!--\s*{re.escape(_MARKER)}\s*v(\d+)\s*-->")
_DIRECTION_COMMENT = re.compile(r"<!--\s*direction:\s*([A-Za-z]+)\s*-->")
_LIST_ITEM = re.compile(r"^-\s+(.*)$")
_ARROW = re.compile(r"\s*->\s*")
_QUOTED = re.compile(r'^"(.*)"$')

_SECTIONS = {
    "services": "services",
    "dependencies": "dependencies",
    "links": "dependencies",  # alias
    "domains": "domains",
}


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def parse(text: str) -> KnowledgeGraph:
    """Parse the markdown knowledge file into a KnowledgeGraph (tolerant)."""
    kg = KnowledgeGraph(services=[], dependencies=[], domains=[])

    section: str | None = None
    title_set = False

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        vm = _VERSION_COMMENT.search(stripped)
        if vm:
            kg.version = int(vm.group(1))
            continue
        dm = _DIRECTION_COMMENT.search(stripped)
        if dm:
            kg.direction = _parse_direction(dm.group(1))
            continue
        if stripped.startswith("<!--"):
            continue

        if stripped.startswith("## "):
            section = _SECTIONS.get(stripped[3:].strip().lower())
            continue
        if stripped.startswith("# "):
            if not title_set:
                kg.title = stripped[2:].strip()
                title_set = True
            continue

        item = _LIST_ITEM.match(stripped)
        if not item or section is None:
            continue
        body = item.group(1).strip()

        if section == "services":
            svc = _parse_service(body)
            if svc is not None:
                kg.services.append(svc)
        elif section == "dependencies":
            dep = _parse_dependency(body)
            if dep is not None:
                kg.dependencies.append(dep)
        elif section == "domains":
            dom = _parse_domain(body)
            if dom is not None:
                kg.domains.append(dom)

    return kg


def _split_description(body: str) -> tuple[str, str | None]:
    parts = _DESC_SPLIT.split(body, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return body.strip(), None


def _extract_attrs(text: str) -> tuple[str, dict[str, list[str]]]:
    """Return (text with [k: v] groups removed, {key: [values...]})."""
    attrs: dict[str, list[str]] = {}
    for m in _ATTR.finditer(text):
        attrs.setdefault(m.group(1).lower(), []).append(m.group(2).strip())
    cleaned = _ATTR.sub("", text).strip()
    return cleaned, attrs


def _parse_service(body: str) -> Service | None:
    head, description = _split_description(body)
    head, attrs = _extract_attrs(head)
    head = head.strip()
    if not head:
        return None

    if ":" in head:
        sid, label = head.split(":", 1)
        sid, label = sid.strip(), label.strip()
    else:
        sid, label = head.strip(), head.strip()
    if not sid:
        return None
    if not label:
        label = sid

    tags: list[str] = []
    if "tags" in attrs:
        for chunk in attrs["tags"]:
            tags.extend(t.strip() for t in chunk.split(",") if t.strip())

    shape = ShapeType.RECTANGLE
    if "shape" in attrs:
        shape = _parse_shape(attrs["shape"][0])

    return Service(
        id=sid,
        label=label,
        component_type=_first(attrs.get("type")),
        shape=shape,
        description=description,
        domain=_first(attrs.get("domain")),
        owner=_first(attrs.get("owner")),
        tags=tags,
        links=attrs.get("link", []),
    )


def _parse_dependency(body: str) -> Dependency | None:
    body, attrs = _extract_attrs(body)
    if "->" not in body:
        return None
    left, right = _ARROW.split(body, maxsplit=1)
    from_id = left.strip()

    label: str | None = None
    if ":" in right:
        to_part, label_part = right.split(":", 1)
        to_id = to_part.strip()
        label = _unquote(label_part.strip())
    else:
        to_id = right.strip()

    if not from_id or not to_id:
        return None

    style = EdgeStyle.SOLID
    if "style" in attrs:
        style = _parse_style(attrs["style"][0])

    return Dependency(from_id=from_id, to_id=to_id, label=label or None, style=style)


def _parse_domain(body: str) -> Domain | None:
    head, label = _split_description(body)
    head = head.strip()
    if not head:
        return None
    return Domain(id=head, label=(label or head).strip())


# ---------------------------------------------------------------------------
# Serialize (deterministic, canonical)
# ---------------------------------------------------------------------------


def serialize(kg: KnowledgeGraph) -> str:
    """Render a KnowledgeGraph to the canonical markdown form."""
    lines: list[str] = [
        f"# {kg.title}",
        f"<!-- {_MARKER} v{kg.version} -->",
        f"<!-- direction: {kg.direction.value} -->",
        "",
        "## Services",
    ]
    for s in kg.services:
        lines.append(_service_line(s))

    lines.append("")
    lines.append("## Dependencies")
    for d in kg.dependencies:
        lines.append(_dependency_line(d))

    # Only emit a Domains section for domains that have a label distinct from
    # their id (membership lives on the services themselves).
    labelled = [d for d in kg.domains if d.label and d.label != d.id]
    if labelled:
        lines.append("")
        lines.append("## Domains")
        for d in labelled:
            lines.append(f"- {d.id} — {d.label}")

    return "\n".join(lines) + "\n"


def _service_line(s: Service) -> str:
    head = s.id if (s.label == s.id) else f"{s.id}: {s.label}"
    attrs: list[str] = []
    if s.component_type:
        attrs.append(f"[type: {s.component_type}]")
    if s.shape != ShapeType.RECTANGLE:
        attrs.append(f"[shape: {s.shape.value}]")
    if s.domain:
        attrs.append(f"[domain: {s.domain}]")
    if s.owner:
        attrs.append(f"[owner: {s.owner}]")
    if s.tags:
        attrs.append(f"[tags: {', '.join(s.tags)}]")
    for link in s.links:
        attrs.append(f"[link: {link}]")

    parts = [f"- {head}"]
    if attrs:
        parts.append(" ".join(attrs))
    if s.description:
        parts.append(f"— {s.description}")
    return " ".join(parts)


def _dependency_line(d: Dependency) -> str:
    line = f"- {d.from_id} -> {d.to_id}"
    if d.label:
        line += f' : "{d.label}"'
    if d.style != EdgeStyle.SOLID:
        line += f" [style: {d.style.value}]"
    return line


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_knowledge_graph(text: str) -> bool:
    """True if the text looks like a knowledge-graph file (has the marker)."""
    return _MARKER in text


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0] or None


def _unquote(text: str) -> str:
    m = _QUOTED.match(text)
    return m.group(1) if m else text


def _parse_direction(value: str) -> Direction:
    try:
        return Direction(value.strip().upper())
    except ValueError:
        return Direction.LEFT_RIGHT


def _parse_style(value: str) -> EdgeStyle:
    try:
        return EdgeStyle(value.strip().lower())
    except ValueError:
        return EdgeStyle.SOLID


def _parse_shape(value: str) -> ShapeType:
    try:
        return ShapeType(value.strip().lower())
    except ValueError:
        return ShapeType.RECTANGLE
