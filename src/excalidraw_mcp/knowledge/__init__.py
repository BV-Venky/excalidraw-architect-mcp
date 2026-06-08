"""Knowledge graph layer.

A persistent, version-controlled architecture model that lives in the repo
(default ``.claude/architecture.md``) and acts as the single source of truth.

The knowledge graph is a *superset* of the diagram intermediate representation:
it carries richer per-service metadata (description, domain, owner, tags, links)
and projects *down* to a :class:`~excalidraw_mcp.core.models.DiagramGraph` for
rendering, so the entire layout/render/export engine is reused unchanged.

Diagrams are rendered *views* of the graph; rendering is one-directional
(``.md`` -> ``.excalidraw``).
"""

from __future__ import annotations

from excalidraw_mcp.knowledge.models import (
    Dependency,
    Domain,
    KnowledgeGraph,
    Service,
)

__all__ = [
    "Dependency",
    "Domain",
    "KnowledgeGraph",
    "Service",
]
