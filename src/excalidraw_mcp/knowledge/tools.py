"""MCP tool definitions for the knowledge graph layer.

Kept separate from ``server.py`` so the knowledge feature is self-contained.
``register(mcp)`` attaches every ``kg_*`` tool to the FastMCP instance. Tools
are thin wrappers over ``store`` / ``views`` / ``query`` / etc.
"""

from __future__ import annotations

from excalidraw_mcp.knowledge import (
    diff as diff_mod,
)
from excalidraw_mcp.knowledge import (
    docgen,
    exporters,
    migrate,
    query,
    store,
    views,
)
from excalidraw_mcp.knowledge import (
    drift as drift_mod,
)
from excalidraw_mcp.knowledge import (
    lint as lint_mod,
)

DEFAULT = store.DEFAULT_KG_PATH


def register(mcp) -> None:  # noqa: ANN001 (FastMCP instance)
    """Register all knowledge-graph tools on the given FastMCP server."""

    # -- Phase 1: build & maintain the graph -------------------------------

    @mcp.tool
    def kg_init(
        graph_path: str = DEFAULT,
        title: str = "System Architecture",
        direction: str = "LR",
        overwrite: bool = False,
    ) -> str:
        """Create a new architecture knowledge graph file (markdown).

        The knowledge graph is the persistent source of truth for your system's
        services and dependencies. Diagrams are rendered *from* it.

        Args:
            graph_path: Where to store the knowledge file. Default ``.claude/architecture.md``.
            title: Human title for the architecture.
            direction: Default layout direction for rendered views (LR/TD/BT/RL).
            overwrite: Replace an existing file if present.
        """
        return store.init_graph(graph_path, title=title, direction=direction, overwrite=overwrite)

    @mcp.tool
    def kg_add_service(
        id: str,
        label: str | None = None,
        component_type: str | None = None,
        description: str | None = None,
        domain: str | None = None,
        owner: str | None = None,
        tags: list[str] | None = None,
        links: list[str] | None = None,
        shape: str | None = None,
        graph_path: str = DEFAULT,
    ) -> str:
        """Add or update a service in the knowledge graph.

        Args:
            id: Unique service identifier (stable; reused across diagrams).
            label: Display name (defaults to id).
            component_type: Technology for auto-styling (e.g. "postgresql", "kafka").
            description: Free-text description.
            domain: Bounded-context / team / tier this service belongs to.
            owner: Owning team or person (e.g. "@payments").
            tags: Arbitrary tags.
            links: Related URLs (ADRs, runbooks, dashboards).
            shape: Shape override (rectangle/diamond/ellipse/circle/stadium/parallelogram).
            graph_path: Knowledge file path.
        """
        return store.add_service(
            graph_path,
            id=id,
            label=label,
            component_type=component_type,
            shape=shape,
            description=description,
            domain=domain,
            owner=owner,
            tags=tags,
            links=links,
        )

    @mcp.tool
    def kg_remove_service(id: str, graph_path: str = DEFAULT) -> str:
        """Remove a service and all dependencies touching it."""
        return store.remove_service(graph_path, id=id)

    @mcp.tool
    def kg_link(
        from_id: str,
        to_id: str,
        label: str | None = None,
        style: str | None = None,
        graph_path: str = DEFAULT,
    ) -> str:
        """Add a directed dependency: ``from_id`` depends on / calls ``to_id``.

        Both services must already exist (add them with kg_add_service first).
        ``style`` is one of solid/dashed/dotted/thick.
        """
        return store.link(graph_path, from_id=from_id, to_id=to_id, label=label, style=style)

    @mcp.tool
    def kg_unlink(from_id: str, to_id: str, graph_path: str = DEFAULT) -> str:
        """Remove the dependency ``from_id`` -> ``to_id``."""
        return store.unlink(graph_path, from_id=from_id, to_id=to_id)

    @mcp.tool
    def kg_set_domain(
        service_id: str,
        domain: str,
        label: str | None = None,
        graph_path: str = DEFAULT,
    ) -> str:
        """Assign a service to a domain (optionally set the domain's display label)."""
        return store.set_domain(graph_path, service_id=service_id, domain=domain, label=label)

    @mcp.tool
    def kg_info(graph_path: str = DEFAULT) -> str:
        """Summarize the whole knowledge graph: services, domains, and topology.

        Call this before mutating the graph to reason about current state.
        """
        return store.graph_summary(graph_path)

    # -- Rendering (projections to .excalidraw) ----------------------------

    @mcp.tool
    def kg_render(output_path: str, theme: str = "default", graph_path: str = DEFAULT) -> str:
        """Render the entire architecture to an .excalidraw file."""
        return views.render(store.load_graph(graph_path), output_path, theme=theme)

    @mcp.tool
    def kg_render_view(
        node_ids: list[str],
        output_path: str,
        theme: str = "default",
        graph_path: str = DEFAULT,
    ) -> str:
        """Render a focused diagram of just the given services (induced subgraph)."""
        return views.render_view(store.load_graph(graph_path), node_ids, output_path, theme=theme)

    @mcp.tool
    def kg_render_around(
        service_id: str,
        depth: int,
        output_path: str,
        direction: str = "both",
        theme: str = "default",
        graph_path: str = DEFAULT,
    ) -> str:
        """Render a service plus everything within ``depth`` hops of it.

        ``direction``: "downstream" (its dependencies), "upstream" (its
        dependents), or "both".
        """
        return views.render_around(
            store.load_graph(graph_path),
            service_id,
            depth,
            output_path,
            theme=theme,
            direction=direction,
        )

    @mcp.tool
    def kg_render_domain(
        domain: str,
        output_path: str,
        theme: str = "default",
        graph_path: str = DEFAULT,
    ) -> str:
        """Render only the services belonging to one domain."""
        return views.render_domain(store.load_graph(graph_path), domain, output_path, theme=theme)

    # -- Phase 2: knowledge & queries --------------------------------------

    @mcp.tool
    def kg_import(excalidraw_path: str, graph_path: str = DEFAULT) -> str:
        """Import an existing .excalidraw diagram's services into the knowledge graph.

        Bootstraps the graph from diagrams you already created with this tool.
        """
        kg = store.load_graph(graph_path)
        try:
            added_s, added_d = migrate.merge_excalidraw(kg, excalidraw_path)
        except ValueError as exc:
            return f"Error: {exc}"
        store.save_graph(kg, graph_path)
        return (
            f"Imported {added_s} new service(s) and {added_d} new dependency/dependencies "
            f"from {excalidraw_path}. Graph now has {len(kg.services)} service(s)."
        )

    @mcp.tool
    def whats_connected_to(
        service_id: str,
        graph_path: str = DEFAULT,
    ) -> str:
        """Impact analysis: what breaks if ``service_id`` fails?

        Reports direct dependents, the full transitive upstream blast radius,
        and what the service itself depends on.
        """
        kg = store.load_graph(graph_path)
        if not kg.has_service(service_id):
            return f"Service '{service_id}' not found."
        imp = query.impact(kg, service_id)
        deps = query.dependencies(kg, service_id)
        lines = [
            f"Impact analysis for '{service_id}':",
            f"  Directly affected if it fails: {', '.join(imp['directly_affected']) or '(none)'}",
            f"  Transitive blast radius: {', '.join(imp['transitively_affected']) or '(none)'}",
            f"  It depends on: {', '.join(deps) or '(none)'}",
        ]
        return "\n".join(lines)

    @mcp.tool
    def kg_path(from_id: str, to_id: str, graph_path: str = DEFAULT) -> str:
        """Trace the shortest dependency path between two services."""
        kg = store.load_graph(graph_path)
        path = query.find_path(kg, from_id, to_id)
        if path is None:
            return f"No dependency path from '{from_id}' to '{to_id}'."
        return " -> ".join(path)

    # -- Phase 3: health, export, diff, docs, drift ------------------------

    @mcp.tool
    def kg_lint(check_owners: bool = False, graph_path: str = DEFAULT) -> str:
        """Architecture health check: cycles, single points of failure, orphans,
        dangling references, and (optionally) unowned services.
        """
        return lint_mod.lint(store.load_graph(graph_path), check_owners=check_owners).to_text()

    @mcp.tool
    def kg_export(
        format: str = "mermaid", output_path: str | None = None, graph_path: str = DEFAULT
    ) -> str:
        """Export the knowledge graph to another format.

        Args:
            format: "mermaid", "dot" (Graphviz), or "json".
            output_path: If given, write to this file; otherwise return the text.
        """
        kg = store.load_graph(graph_path)
        fmt = format.lower().strip()
        renderers = {
            "mermaid": exporters.to_mermaid,
            "dot": exporters.to_dot,
            "json": exporters.to_json,
        }
        if fmt not in renderers:
            return f"Error: unsupported format '{format}'. Choose mermaid, dot, or json."
        text = renderers[fmt](kg)
        if output_path:
            from pathlib import Path

            Path(output_path).write_text(text, encoding="utf-8")
            return f"Exported {fmt} to {output_path}."
        return text

    @mcp.tool
    def kg_diff(ref: str = "HEAD", graph_path: str = DEFAULT) -> str:
        """Show how the architecture changed since a git ref (default HEAD).

        Compares the current knowledge file against its version at ``ref``.
        """
        try:
            old = diff_mod.load_from_git_ref(graph_path, ref)
        except (RuntimeError, OSError) as exc:
            return f"Error reading {ref}: {exc}"
        new = store.load_graph(graph_path)
        return diff_mod.diff_graphs(old, new).to_text()

    @mcp.tool
    def kg_onboarding_doc(output_path: str | None = None, graph_path: str = DEFAULT) -> str:
        """Generate a human onboarding guide (entry points, hubs, domains) from the graph."""
        kg = store.load_graph(graph_path)
        text = docgen.to_onboarding_markdown(kg)
        if output_path:
            from pathlib import Path

            Path(output_path).write_text(text, encoding="utf-8")
            return f"Wrote onboarding guide to {output_path}."
        return text

    @mcp.tool
    def kg_drift(code_root: str, graph_path: str = DEFAULT) -> str:
        """Detect drift between the declared architecture and Python imports under ``code_root``.

        Best-effort: treats each top-level package as a service and infers edges
        from imports. Reports undocumented and possibly-stale dependencies.
        """
        kg = store.load_graph(graph_path)
        edges, covered = drift_mod.scan_python_imports(code_root)
        return drift_mod.compute_drift(kg, edges, covered).to_text()
