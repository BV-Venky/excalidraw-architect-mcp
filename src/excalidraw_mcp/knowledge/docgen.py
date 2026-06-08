"""Generate human onboarding docs from the knowledge graph.

Turns the structured graph into a narrated "start here" markdown document:
entry points, domains, key hubs, data stores, and per-service detail with
ownership — the thing a new hire actually wants.
"""

from __future__ import annotations

from excalidraw_mcp.knowledge import query
from excalidraw_mcp.knowledge.models import KnowledgeGraph


def to_onboarding_markdown(kg: KnowledgeGraph) -> str:
    """Render an onboarding guide for the architecture."""
    lines: list[str] = [f"# {kg.title} — Onboarding Guide", ""]
    lines.append(
        f"This system has **{len(kg.services)} services** with "
        f"**{len(kg.dependencies)} dependencies** across "
        f"**{len(kg.domain_ids)} domain(s)**."
    )
    lines.append("")

    entry_points = query.roots(kg)
    if entry_points:
        lines.append("## Entry points")
        lines.append("Nothing depends on these — they are where requests enter:")
        for sid in entry_points:
            lines.append(f"- {_svc_ref(kg, sid)}")
        lines.append("")

    hubs = query.hubs(kg, min_degree=3)
    if hubs:
        lines.append("## Key hubs")
        lines.append("Most-connected services — learn these first:")
        for sid, degree in hubs:
            lines.append(f"- {_svc_ref(kg, sid)} — {degree} connections")
        lines.append("")

    data_stores = [s.id for s in kg.services if (s.component_type or "").lower() in _STORE_TYPES]
    if data_stores:
        lines.append("## Data stores")
        for sid in sorted(data_stores):
            lines.append(f"- {_svc_ref(kg, sid)}")
        lines.append("")

    if kg.domain_ids:
        lines.append("## Domains")
        for domain_id in kg.domain_ids:
            lines.append(f"### {kg.domain_label(domain_id)}")
            for sid in kg.domain_members(domain_id):
                lines.append(f"- {_svc_detail(kg, sid)}")
            lines.append("")

    ungrouped = [s for s in kg.services if not s.domain]
    if ungrouped:
        lines.append("## Other services")
        for s in ungrouped:
            lines.append(f"- {_svc_detail(kg, s.id)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


_STORE_TYPES = {
    "postgresql",
    "postgres",
    "mysql",
    "mariadb",
    "mongodb",
    "redis",
    "cassandra",
    "dynamodb",
    "elasticsearch",
    "s3",
}


def _svc_ref(kg: KnowledgeGraph, sid: str) -> str:
    svc = kg.service_by_id(sid)
    if svc is None:
        return f"`{sid}`"
    return f"**{svc.label}** (`{sid}`)"


def _svc_detail(kg: KnowledgeGraph, sid: str) -> str:
    svc = kg.service_by_id(sid)
    if svc is None:
        return f"`{sid}`"
    parts = [f"**{svc.label}** (`{sid}`)"]
    extras: list[str] = []
    if svc.component_type:
        extras.append(svc.component_type)
    if svc.owner:
        extras.append(f"owner {svc.owner}")
    if extras:
        parts.append(f"_{', '.join(extras)}_")
    if svc.description:
        parts.append(f"— {svc.description}")
    deps = query.dependencies(kg, sid)
    if deps:
        parts.append(f"→ depends on {', '.join(deps)}")
    return " ".join(parts)
