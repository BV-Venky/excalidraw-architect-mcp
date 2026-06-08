"""Data model for the persistent architecture knowledge graph.

``KnowledgeGraph`` is the source-of-truth model. It is a superset of the
rendering IR (:class:`~excalidraw_mcp.core.models.DiagramGraph`) and projects
down to it via :meth:`KnowledgeGraph.to_diagram_graph`.

All mutation helpers here are *pure* in-memory operations and validate their
inputs (e.g. linking unknown services raises). File I/O lives in
``knowledge/store.py``; this module never touches the filesystem.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from excalidraw_mcp.core.models import (
    DiagramGraph,
    Direction,
    Edge,
    EdgeStyle,
    Node,
    ShapeType,
    Subgraph,
)


class KnowledgeGraphError(ValueError):
    """Raised on invalid mutations (unknown ids, duplicates, etc.)."""


class Service(BaseModel):
    """A service / component in the architecture knowledge graph.

    Superset of :class:`~excalidraw_mcp.core.models.Node` with the extra
    metadata that makes the graph queryable and team-useful.
    """

    id: str
    label: str
    component_type: str | None = None
    shape: ShapeType = ShapeType.RECTANGLE
    description: str | None = None
    domain: str | None = None
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_node(self) -> Node:
        """Project this service to a diagram node (drops knowledge-only fields)."""
        return Node(
            id=self.id,
            label=self.label,
            shape=self.shape,
            component_type=self.component_type,
            metadata=dict(self.metadata),
        )


class Dependency(BaseModel):
    """A directed dependency between two services.

    ``from_id`` depends on / calls / sends to ``to_id``.
    """

    from_id: str
    to_id: str
    label: str | None = None
    style: EdgeStyle = EdgeStyle.SOLID
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_edge(self) -> Edge:
        return Edge(from_id=self.from_id, to_id=self.to_id, label=self.label, style=self.style)

    @property
    def key(self) -> tuple[str, str]:
        return (self.from_id, self.to_id)


class Domain(BaseModel):
    """A named grouping of services (bounded context / team / tier).

    Membership is derived from each service's ``domain`` field; this record
    only carries the optional human-readable label for a domain id.
    """

    id: str
    label: str


class KnowledgeGraph(BaseModel):
    """The persistent architecture model — single source of truth."""

    version: int = 1
    title: str = "System Architecture"
    direction: Direction = Direction.LEFT_RIGHT
    services: list[Service] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    domains: list[Domain] = Field(default_factory=list)

    # -- lookups ------------------------------------------------------------

    @property
    def service_ids(self) -> set[str]:
        return {s.id for s in self.services}

    def service_by_id(self, service_id: str) -> Service | None:
        return next((s for s in self.services if s.id == service_id), None)

    def has_service(self, service_id: str) -> bool:
        return any(s.id == service_id for s in self.services)

    def dependency(self, from_id: str, to_id: str, label: str | None = None) -> Dependency | None:
        """Find a dependency. With ``label`` given, matches the exact edge;
        otherwise returns the first edge between the two services."""
        for d in self.dependencies:
            if d.from_id == from_id and d.to_id == to_id:
                if label is None or d.label == label:
                    return d
        return None

    def dependencies_between(self, from_id: str, to_id: str) -> list[Dependency]:
        """All (parallel) dependencies from ``from_id`` to ``to_id``."""
        return [d for d in self.dependencies if d.from_id == from_id and d.to_id == to_id]

    def domain_label(self, domain_id: str) -> str:
        match = next((d for d in self.domains if d.id == domain_id), None)
        return match.label if match else domain_id

    def domain_members(self, domain_id: str) -> list[str]:
        return [s.id for s in self.services if s.domain == domain_id]

    @property
    def domain_ids(self) -> list[str]:
        """All domain ids referenced by services, in first-seen order."""
        seen: list[str] = []
        for s in self.services:
            if s.domain and s.domain not in seen:
                seen.append(s.domain)
        return seen

    # -- mutations (pure, validating) ---------------------------------------

    def add_service(self, service: Service, *, upsert: bool = True) -> Service:
        """Add a service, or update it in place when it already exists.

        With ``upsert=False`` a duplicate id raises.
        """
        existing = self.service_by_id(service.id)
        if existing is not None:
            if not upsert:
                raise KnowledgeGraphError(f"service '{service.id}' already exists")
            idx = self.services.index(existing)
            self.services[idx] = service
            return service
        self.services.append(service)
        return service

    def remove_service(self, service_id: str) -> bool:
        """Remove a service and every dependency touching it. Returns True if removed."""
        existing = self.service_by_id(service_id)
        if existing is None:
            return False
        self.services.remove(existing)
        self.dependencies = [
            d for d in self.dependencies if d.from_id != service_id and d.to_id != service_id
        ]
        return True

    def add_dependency(self, dependency: Dependency, *, upsert: bool = True) -> Dependency:
        """Add a dependency between two existing services.

        Parallel edges are supported: two dependencies between the same pair of
        services coexist as long as their labels differ (e.g. a REST call and a
        Kafka topic between the same services). An edge is identified by
        ``(from_id, to_id, label)`` — adding one with an identical triple
        upserts (updating style) rather than duplicating.

        Raises if either endpoint is unknown.
        """
        for endpoint in (dependency.from_id, dependency.to_id):
            if not self.has_service(endpoint):
                raise KnowledgeGraphError(f"unknown service '{endpoint}'")
        if dependency.from_id == dependency.to_id:
            raise KnowledgeGraphError("a service cannot depend on itself")
        existing = self.dependency(dependency.from_id, dependency.to_id, dependency.label)
        if existing is not None:
            if not upsert:
                raise KnowledgeGraphError(
                    f"dependency {dependency.from_id} -> {dependency.to_id} "
                    f"({dependency.label or 'unlabelled'}) already exists"
                )
            idx = self.dependencies.index(existing)
            self.dependencies[idx] = dependency
            return dependency
        self.dependencies.append(dependency)
        return dependency

    def remove_dependency(self, from_id: str, to_id: str, label: str | None = None) -> int:
        """Remove dependencies between two services. Returns the count removed.

        With ``label`` given, removes only the matching parallel edge; otherwise
        removes every edge between the two services.
        """
        if label is None:
            victims = self.dependencies_between(from_id, to_id)
        else:
            victims = [
                d
                for d in self.dependencies
                if d.from_id == from_id and d.to_id == to_id and d.label == label
            ]
        for d in victims:
            self.dependencies.remove(d)
        return len(victims)

    def set_domain_label(self, domain_id: str, label: str) -> None:
        match = next((d for d in self.domains if d.id == domain_id), None)
        if match is None:
            self.domains.append(Domain(id=domain_id, label=label))
        else:
            match.label = label

    # -- validation ---------------------------------------------------------

    def dangling_dependencies(self) -> list[Dependency]:
        """Dependencies whose endpoints are not declared services.

        Mutation helpers prevent these, but hand-edits to the file can
        introduce them; lint surfaces them.
        """
        ids = self.service_ids
        return [d for d in self.dependencies if d.from_id not in ids or d.to_id not in ids]

    # -- projection to the rendering IR -------------------------------------

    def to_diagram_graph(
        self,
        node_ids: list[str] | set[str] | None = None,
        *,
        include_domains: bool = True,
    ) -> DiagramGraph:
        """Project the knowledge graph (or a subset) to a renderable DiagramGraph.

        Args:
            node_ids: If given, restrict to these services; only dependencies
                whose *both* endpoints are in the set are kept (induced subgraph).
                Unknown ids are ignored.
            include_domains: Emit a Subgraph per domain that has >= 1 included
                service.
        """
        if node_ids is None:
            selected = list(self.services)
        else:
            wanted = set(node_ids)
            selected = [s for s in self.services if s.id in wanted]

        selected_ids = {s.id for s in selected}
        nodes = [s.to_node() for s in selected]
        edges = [
            d.to_edge()
            for d in self.dependencies
            if d.from_id in selected_ids and d.to_id in selected_ids
        ]

        subgraphs: list[Subgraph] = []
        if include_domains:
            for domain_id in self.domain_ids:
                members = [sid for sid in self.domain_members(domain_id) if sid in selected_ids]
                if members:
                    subgraphs.append(
                        Subgraph(
                            id=domain_id,
                            label=self.domain_label(domain_id),
                            node_ids=members,
                        )
                    )

        return DiagramGraph(
            nodes=nodes,
            edges=edges,
            subgraphs=subgraphs,
            direction=self.direction,
        )
