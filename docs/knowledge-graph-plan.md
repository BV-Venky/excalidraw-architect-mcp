# Knowledge Graph — Design & Implementation Plan

> Status: proposal · Target: `v0.4.0 "Knowledge Graph"`

## 1. Core idea

Every diagram is already backed by a structured graph (`DiagramGraph`), and we already
persist a per-file copy in `appState.customData.excalidraw_mcp` (`DiagramMetadata`).
This feature lifts that graph out of individual `.excalidraw` files into a **single,
cumulative, version-controlled architecture model** stored in the repo
(default `.claude/architecture.md`).

- The knowledge file is the **source of truth**.
- `.excalidraw` files become **projections** (views) rendered from it — full system or a focused slice.
- Rendering is **one-directional** (`.md` → `.excalidraw`). If both are hand-edited, `.md` wins.

This turns the project from a *diagram generator* into a *living architecture layer*.

## 2. Architectural fit (what we reuse vs. add)

```
            ┌─────────────────────────────┐
            │  .claude/architecture.md     │  ← NEW: source of truth
            └─────────────┬───────────────┘
              parse/serialize (NEW)
            ┌─────────────▼───────────────┐
            │  KnowledgeGraph (NEW model)  │  superset of DiagramGraph
            └─────────────┬───────────────┘
              project + select (NEW)        ── query (NEW) ──▶ answers
            ┌─────────────▼───────────────┐
            │  DiagramGraph (EXISTING IR)  │
            └─────────────┬───────────────┘
              compute_layout → build_excalidraw_file → save   (EXISTING, untouched)
            ┌─────────────▼───────────────┐
            │  .excalidraw (rendered view) │
            └──────────────────────────────┘
```

**Principle:** the new layer only ever produces a `DiagramGraph` and hands it to the
existing engine. We do not modify `engine/`, `core/components.py`, or the renderer.

## 3. Module layout (new `knowledge/` subpackage)

Keep it isolated and single-responsibility, mirroring the existing `core/ engine/ parsers/` split:

| Module | Responsibility |
|--------|----------------|
| `knowledge/models.py` | `KnowledgeGraph`, `Service` (superset of `Node`: + description, tags, domain, owner, links). Pure data. |
| `knowledge/store.py` | Locate / load / save the knowledge file; CRUD on the in-memory model. The only module that touches the file path. |
| `knowledge/parser.py` | Markdown DSL ⇄ `KnowledgeGraph`. Tolerant read, normalize-on-write (round-trip safe). |
| `knowledge/views.py` | `KnowledgeGraph` + selector → `DiagramGraph`. Selectors: explicit ids, by domain/tag, N-hops-from-X. Domains map to `Subgraph`. |
| `knowledge/query.py` | Pure graph queries: neighbors, dependents/dependencies, paths, orphans, cycles. No I/O. |
| `knowledge/migrate.py` | Import existing `.excalidraw` `DiagramMetadata` → merge into the store. |
| `server.py` | Thin MCP tool wrappers calling into `knowledge/*`. No logic. |

`KnowledgeGraph` exposes a `.to_diagram_graph(selector)` method so `views.py` stays tiny
and the projection is testable in isolation.

## 4. File format (the DSL)

Human-readable, machine-parseable, git-diff-friendly. Parses into `KnowledgeGraph`.

```markdown
# System Architecture
<!-- excalidraw-architect: v1 · do not delete this marker -->

## Services
- gateway    [type: nginx]       (domain: edge)     — API gateway
- payments   [type: service]     (domain: core)     — Stripe integration · owner: @payments-team
- orders-db  [type: postgresql]  (domain: core)

## Links
- gateway -> payments    : "REST /pay"
- payments -> orders-db  : "writes"   [style: thick]

## Domains
- edge: [gateway]
- core: [payments, orders-db]
```

- `Services` → `Service` nodes (`[type: …]` = `component_type` for auto-styling).
- `Links` → `Edge` (label + optional style).
- `Domains` → `Subgraph` on render.
- Unknown fields are preserved on round-trip (forward-compat).

## 5. Tool surface

Prefixed for discoverability by the LLM. (A typed `/`-command skill layer can wrap these later.)

### Phase 1 — MVP (the wedge)
| Tool | Purpose |
|------|---------|
| `kg_init(path?)` | Create an empty knowledge file (or import — see migrate). |
| `kg_add_service(id, type?, description?, domain?, file?)` | Add/update a service. |
| `kg_link(from_id, to_id, label?, style?)` | Add an edge between services. |
| `kg_unlink(from_id, to_id)` | Remove an edge. |
| `kg_remove_service(id)` | Remove a service + its links. |
| `kg_render(output_path, theme?, direction?)` | Render the whole graph to `.excalidraw`. |
| `kg_render_view(node_ids[], output_path, …)` | Render a focused slice. |
| `kg_info()` | Human-readable summary (reuse `get_diagram_summary` style). |

### Phase 2 — the "knowledge" payoff
| Tool | Purpose |
|------|---------|
| `kg_import(excalidraw_path)` | Migrate an existing diagram's metadata into the store. |
| `whats_connected_to(id, depth?, direction?)` | Impact analysis — upstream/downstream blast radius. |
| `kg_render_around(id, depth, output_path)` | Render N hops around a service (auto-slice). |
| `kg_render_domain(domain, output_path)` | Render one domain/bounded-context. |

### Phase 3 — delight / stickiness
| Tool | Purpose |
|------|---------|
| `kg_lint()` | Health check: orphans, cycles, dangling links, single points of failure. |
| `kg_path(from_id, to_id)` | Trace request/data flow between two services. |
| `kg_export(format)` | Export to mermaid / dot / json (future-proofs the `excalidraw-` name). |
| `kg_diff(ref?)` | Architecture changelog via git (the `.md` is versioned). |

## 6. Phasing & scope

- **Phase 1 (ship as `v0.4.0`):** models + store + parser (round-trip safe) + CRUD tools + render/render_view + info. This alone is launch-worthy.
- **Phase 2 (`v0.4.x`):** migration + `whats_connected_to` + focused auto-slices + domains. **This is the launch GIF** — query → impact map, or explode a subsystem out of a 40-node graph.
- **Phase 3 (`v0.5.0+`):** lint/health, path tracing, multi-format export, git-diff architecture.

Keep `create_diagram` / `modify_diagram` / `mermaid_to_excalidraw` **fully working and
untouched**. Knowledge tools are purely additive. (Optional later: `create_diagram` gains
an `upsert_to_knowledge=True` flag so one-off diagrams can feed the model.)

## 7. "Cool features" users would actually love

Ranked by wow-per-effort:

1. **Impact analysis (`whats_connected_to`)** — "if payments goes down, what breaks?" Blast-radius is hard to eyeball, trivial on a graph. *This is the headline demo.*
2. **Focused-view / explode** — pull a clean subsystem out of a huge model on demand. Directly serves the README's "split into focused diagrams" advice.
3. **Architecture lint** — flag orphans, cycles, single points of failure, dangling links. Cheap, feels magical, gives a recurring reason to run the tool.
4. **Ownership / on-call metadata** — `owner:` per service → "who owns checkout?" Makes it a team tool, not just an individual one (widens the audience → stars).
5. **Git-aware architecture diff** — because the `.md` is versioned: "what changed in the architecture in this PR?" Strong CI/PR-bot story.
6. **Codebase drift detection (bigger)** — scan repo imports, compare to the declared graph, flag undocumented dependencies. The "docs that can't go stale" promise, enforced.
7. **Onboarding doc generation** — turn the graph into a narrated "start here" markdown for new hires.
8. **ADR linking** — link services to Architecture Decision Records / runbooks.

## 8. Design considerations / risks

- **Single source of truth:** `.md` canonical; rendered `.excalidraw` disposable and regenerable. Document the conflict rule (`.md` wins) prominently.
- **Round-trip safety:** normalize-on-write + preserve unknown fields, so hand edits survive and diffs stay small. Cover with parser round-trip tests.
- **ID stability:** reuse ids across renders so views are consistent and `modify_diagram` interop stays sane.
- **Backward compatibility:** no changes to existing tools or engine; new subpackage only.
- **Determinism:** keep parser/serializer ordering stable for clean git diffs and reproducible tests.
- **Name ceiling:** if multi-target export (Phase 3) becomes core, lead positioning with "architecture knowledge graph"; keep the published package name.

## 9. Testing

Mirror the existing `tests/` layout:
- `parser` round-trip: model → markdown → model is identity (+ tolerant of hand edits).
- `store` CRUD: add/link/unlink/remove mutate and persist correctly.
- `views` projection: selector subsets produce expected `DiagramGraph` (nodes + induced edges only).
- `query`: neighbors / dependents / cycles / orphans on fixture graphs.
- `migrate`: a sample `.excalidraw` imports to the expected model.

## 10. Suggested first PR

`knowledge/models.py` + `knowledge/parser.py` + round-trip tests only — no tools yet.
Nail the format and round-trip safety first; everything else builds on it.
