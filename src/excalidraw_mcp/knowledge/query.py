"""Pure graph queries over a KnowledgeGraph.

No I/O, no rendering — just deterministic graph algorithms that make the
architecture answerable: dependencies, impact analysis, paths, cycles, and
single points of failure. Every function here is straightforwardly unit-tested.

Terminology:
- ``dependencies(x)``  -> services x points to (x depends on / calls them): downstream.
- ``dependents(x)``    -> services that point to x (they depend on x): upstream.
"""

from __future__ import annotations

from collections import defaultdict, deque

from excalidraw_mcp.knowledge.models import KnowledgeGraph

Direction = str  # one of "downstream", "upstream", "both"


def _adjacency(kg: KnowledgeGraph) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build (out_adj, in_adj) over valid (non-dangling) dependencies, sorted."""
    ids = kg.service_ids
    out: dict[str, list[str]] = defaultdict(list)
    inc: dict[str, list[str]] = defaultdict(list)
    for d in kg.dependencies:
        if d.from_id in ids and d.to_id in ids:
            out[d.from_id].append(d.to_id)
            inc[d.to_id].append(d.from_id)
    return out, inc


# ---------------------------------------------------------------------------
# Direct relationships
# ---------------------------------------------------------------------------


def dependencies(kg: KnowledgeGraph, service_id: str) -> list[str]:
    """Services that ``service_id`` directly depends on (downstream)."""
    out, _ = _adjacency(kg)
    return sorted(set(out.get(service_id, [])))


def dependents(kg: KnowledgeGraph, service_id: str) -> list[str]:
    """Services that directly depend on ``service_id`` (upstream)."""
    _, inc = _adjacency(kg)
    return sorted(set(inc.get(service_id, [])))


def neighbors(kg: KnowledgeGraph, service_id: str) -> list[str]:
    """All directly connected services (either direction)."""
    return sorted(set(dependencies(kg, service_id)) | set(dependents(kg, service_id)))


# ---------------------------------------------------------------------------
# Transitive reachability / impact analysis
# ---------------------------------------------------------------------------


def connected(
    kg: KnowledgeGraph,
    service_id: str,
    depth: int | None = None,
    direction: Direction = "both",
) -> list[str]:
    """All services reachable from ``service_id`` within ``depth`` hops.

    Excludes the start node. ``depth=None`` means unbounded.
    ``direction``: "downstream" (what it depends on), "upstream" (what depends
    on it), or "both".
    """
    if not kg.has_service(service_id):
        return []
    out, inc = _adjacency(kg)

    def step(node: str) -> list[str]:
        if direction == "downstream":
            return out.get(node, [])
        if direction == "upstream":
            return inc.get(node, [])
        return out.get(node, []) + inc.get(node, [])

    seen: set[str] = {service_id}
    frontier: deque[tuple[str, int]] = deque([(service_id, 0)])
    result: set[str] = set()
    while frontier:
        node, dist = frontier.popleft()
        if depth is not None and dist >= depth:
            continue
        for nxt in step(node):
            if nxt not in seen:
                seen.add(nxt)
                result.add(nxt)
                frontier.append((nxt, dist + 1))
    return sorted(result)


def impact(kg: KnowledgeGraph, service_id: str) -> dict[str, list[str]]:
    """Blast radius of ``service_id`` failing.

    Returns ``{"directly_affected": [...], "transitively_affected": [...]}``
    — i.e. everything upstream that (transitively) depends on it.
    """
    direct = dependents(kg, service_id)
    transitive = connected(kg, service_id, depth=None, direction="upstream")
    return {
        "directly_affected": direct,
        "transitively_affected": transitive,
    }


def find_path(kg: KnowledgeGraph, from_id: str, to_id: str) -> list[str] | None:
    """Shortest directed path (following dependencies) from -> to, or None."""
    if not (kg.has_service(from_id) and kg.has_service(to_id)):
        return None
    out, _ = _adjacency(kg)
    prev: dict[str, str] = {}
    seen = {from_id}
    queue: deque[str] = deque([from_id])
    while queue:
        node = queue.popleft()
        if node == to_id:
            path = [to_id]
            while path[-1] != from_id:
                path.append(prev[path[-1]])
            return list(reversed(path))
        for nxt in out.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                prev[nxt] = node
                queue.append(nxt)
    return None


# ---------------------------------------------------------------------------
# Topology classification
# ---------------------------------------------------------------------------


def roots(kg: KnowledgeGraph) -> list[str]:
    """Entry points: services nothing depends on (no incoming edges)."""
    _, inc = _adjacency(kg)
    return sorted(s.id for s in kg.services if not inc.get(s.id))


def leaves(kg: KnowledgeGraph) -> list[str]:
    """Terminal services: depend on nothing (no outgoing edges)."""
    out, _ = _adjacency(kg)
    return sorted(s.id for s in kg.services if not out.get(s.id))


def orphans(kg: KnowledgeGraph) -> list[str]:
    """Services with no connections at all."""
    out, inc = _adjacency(kg)
    return sorted(s.id for s in kg.services if not out.get(s.id) and not inc.get(s.id))


def hubs(kg: KnowledgeGraph, min_degree: int = 3) -> list[tuple[str, int]]:
    """Services with total degree >= min_degree, sorted by degree desc."""
    out, inc = _adjacency(kg)
    scored = [
        (s.id, len(set(out.get(s.id, []))) + len(set(inc.get(s.id, [])))) for s in kg.services
    ]
    return sorted(
        [(sid, deg) for sid, deg in scored if deg >= min_degree],
        key=lambda t: (-t[1], t[0]),
    )


# ---------------------------------------------------------------------------
# Cycles (Tarjan SCC)
# ---------------------------------------------------------------------------


def strongly_connected_components(kg: KnowledgeGraph) -> list[list[str]]:
    """All SCCs (iterative Tarjan), each sorted; components in deterministic order."""
    out, _ = _adjacency(kg)
    ids = sorted(kg.service_ids)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    counter = 0
    result: list[list[str]] = []

    for start in ids:
        if start in index:
            continue
        # iterative DFS; work items are (node, neighbor_iterator_position)
        work: list[tuple[str, int]] = [(start, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            neigh = out.get(node, [])
            if pi < len(neigh):
                work[-1] = (node, pi + 1)
                nxt = neigh[pi]
                if nxt not in index:
                    work.append((nxt, 0))
                elif nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            else:
                if low[node] == index[node]:
                    comp: list[str] = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        comp.append(w)
                        if w == node:
                            break
                    result.append(sorted(comp))
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
    return result


def cycles(kg: KnowledgeGraph) -> list[list[str]]:
    """Cyclic groups: SCCs containing more than one service (sorted)."""
    return sorted(
        (c for c in strongly_connected_components(kg) if len(c) > 1),
        key=lambda c: (len(c), c),
    )


def has_cycle(kg: KnowledgeGraph) -> bool:
    return bool(cycles(kg))


# ---------------------------------------------------------------------------
# Single points of failure (articulation points, undirected)
# ---------------------------------------------------------------------------


def single_points_of_failure(kg: KnowledgeGraph) -> list[str]:
    """Articulation points of the underlying undirected graph.

    Removing one disconnects part of the architecture from the rest — a
    structural single point of failure. Computed with a Hopcroft-Tarjan DFS.
    """
    out, inc = _adjacency(kg)
    ids = sorted(kg.service_ids)
    adj: dict[str, set[str]] = {i: set() for i in ids}
    for u in ids:
        for v in out.get(u, []):
            adj[u].add(v)
            adj[v].add(u)
        for v in inc.get(u, []):
            adj[u].add(v)
            adj[v].add(u)

    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    timer = 0
    articulation: set[str] = set()

    for root in ids:
        if root in disc:
            continue
        root_children = 0
        # iterative DFS: (node, parent, neighbor_iter)
        stack: list[tuple[str, str | None, list[str], int]] = [(root, None, sorted(adj[root]), 0)]
        disc[root] = low[root] = timer
        timer += 1
        while stack:
            node, parent, neigh, pi = stack[-1]
            if pi < len(neigh):
                stack[-1] = (node, parent, neigh, pi + 1)
                nxt = neigh[pi]
                if nxt == parent:
                    continue
                if nxt in disc:
                    low[node] = min(low[node], disc[nxt])
                else:
                    disc[nxt] = low[nxt] = timer
                    timer += 1
                    if parent is None:
                        root_children += 1
                    stack.append((nxt, node, sorted(adj[nxt]), 0))
            else:
                stack.pop()
                if stack:
                    par = stack[-1][0]
                    low[par] = min(low[par], low[node])
                    par_parent = stack[-1][1]
                    if par_parent is not None and low[node] >= disc[par]:
                        articulation.add(par)
        if root_children > 1:
            articulation.add(root)

    return sorted(articulation)


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


def services_by_owner(kg: KnowledgeGraph) -> dict[str, list[str]]:
    by_owner: dict[str, list[str]] = defaultdict(list)
    for s in kg.services:
        by_owner[s.owner or "(unowned)"].append(s.id)
    return {k: sorted(v) for k, v in sorted(by_owner.items())}


def unowned_services(kg: KnowledgeGraph) -> list[str]:
    return sorted(s.id for s in kg.services if not s.owner)
