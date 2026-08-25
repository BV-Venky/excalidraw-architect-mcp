# Contributing to Excalidraw Architect MCP

Thanks for your interest — **contributions are welcome!** 🎉

Whether it's a bug fix, a new feature, more component styles, better docs, or a new graph query, we'd love your help.

## Ways to contribute

- **Report bugs** — open an issue with steps to reproduce and, if relevant, the `.excalidraw` output or `.claude/architecture.md` file
- **Request features** — open an issue describing your use case
- **Submit a pull request** — fixes, features, components, docs, tests
- **Improve docs** — README, examples, or this guide
- **Star the repo** — helps others discover the project

If you're planning something non-trivial, please open an issue first so we can align on the approach before you invest the time.

## Good first contributions

- **New component styles** — add a technology to `core/components.py` (e.g. a database, queue, or cloud service we don't style yet)
- **New graph queries** — add a pure query to `knowledge/query.py` (e.g. "longest dependency chain", "fan-in ranking") with tests
- **New export formats** — extend `knowledge/exporters.py`
- **Mermaid coverage** — handle more flowchart syntax in `parsers/mermaid.py`
- **Docs & examples** — show a real architecture modelled end-to-end

## Pull request workflow

1. **Fork** the repo and create a branch from `main`:
   ```bash
   git checkout -b feature/my-change
   ```
2. **Make your change** with tests (see below).
3. **Run the checks** — they must pass (CI runs the same):
   ```bash
   hatch run check   # lint + format check
   hatch run test    # full test suite
   ```
4. **Commit** with a clear message (we loosely follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, `test:`).
5. **Open a PR** against `main`, describe what and why, and link any related issue.

A maintainer will review; we aim to respond quickly. Be ready for a round or two of feedback.

### What we look for

- **Tests** for any behavior change. The graph layer is deterministic and fully unit-testable — new logic should come with assertions, not manual diagram inspection.
- **Green CI** — lint, format, and tests across Python 3.10–3.13.
- **Focused PRs** — one logical change per PR is easier to review than a grab-bag.
- **Backward compatibility** — existing MCP tools and the `.excalidraw` / `.claude/architecture.md` formats shouldn't break without discussion.

## Development setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) or [hatch](https://hatch.pypa.io/)

### Getting started

```bash
git clone https://github.com/BV-Venky/excalidraw-architect-mcp.git
cd excalidraw-architect-mcp
hatch run test
```

(Equivalently with uv: `uv run pytest`, `uv run ruff check src/ tests/`.)

### Available commands

| Command | What it does |
|---|---|
| `hatch run test` | Run the test suite |
| `hatch run lint` | Check for linting issues |
| `hatch run format` | Auto-format all code |
| `hatch run check` | Run lint + format check (same as CI) |
| `hatch run fix` | Auto-fix lint issues + format |
| `hatch run serve` | Start the MCP server locally |

## Architecture

The project has two layers. The **knowledge graph** is the persistent source of truth; **diagrams are rendered views** of it. The graph is a superset of the diagram IR and projects *down* to it, so the layout/render engine is shared.

```
                          ┌──────────────────────────────┐
AI IDE ──MCP──▶ server.py │  knowledge/ (source of truth) │
                   │      │   models → parser ⇄ .claude/   │
                   │      │   architecture.md              │
                   │      │   query · lint · views · diff  │
                   │      └───────────────┬────────────────┘
                   │           projects down to
                   ▼                      ▼
            parsers/ (mermaid,    DiagramGraph (IR)
            stateful editing)            │
                                         ▼
                   engine/layout.py ──▶ engine/renderer.py ──▶ .excalidraw
                     (grandalf /          (shapes, arrows,
                      Sugiyama)            bindings, metadata)
```

The AI IDE's LLM provides the *what* (services and connections). The MCP server handles the *how* (storage, queries, layout, styling, rendering). **No AI inference happens in the MCP** — all reasoning is done by the IDE's built-in model.

## Project structure

```
src/excalidraw_mcp/
├── server.py              # FastMCP server — registers all MCP tools
├── core/                  # Foundation: data models + styling
│   ├── models.py          # Pydantic models (DiagramGraph, LayoutResult, etc.)
│   ├── components.py      # Technology → visual style mapping (50+ components)
│   └── themes.py          # Color themes (default, dark, colorful)
├── engine/                # Computational core
│   ├── layout.py          # Sugiyama layout: adaptive gaps, hub stretch, routing
│   └── renderer.py        # Excalidraw JSON builder (shapes, arrows, bindings)
├── parsers/               # Input adapters
│   ├── mermaid.py         # Mermaid flowchart → DiagramGraph parser
│   └── state.py           # Stateful editing (read/modify existing diagrams)
├── export/                # SVG / PNG export (browserless)
│   └── svg_exporter.py
└── knowledge/             # Architecture knowledge graph (source of truth)
    ├── models.py          # KnowledgeGraph / Service / Dependency (+ projection)
    ├── parser.py          # Markdown DSL ⇄ KnowledgeGraph (round-trip safe)
    ├── store.py           # File I/O + CRUD orchestration (.claude/architecture.md)
    ├── query.py           # Pure graph queries (impact, cycles, SPOF, paths)
    ├── views.py           # Render full / focused / domain / N-hop projections
    ├── migrate.py         # Import existing .excalidraw diagrams
    ├── lint.py            # Health checks (cycles, SPOF, orphans, dangling refs)
    ├── exporters.py       # Mermaid / DOT / JSON export
    ├── diff.py            # Git-aware architecture diffs
    ├── docgen.py          # Onboarding-doc generation
    ├── drift.py           # Drift detection vs. code imports
    └── tools.py           # MCP tool definitions (kg_*)

tests/                     # pytest suite (mirrors the package layout)
```

## Code style

- Type hints throughout; `from __future__ import annotations` at the top of modules.
- Formatting and linting are enforced by [ruff](https://docs.astral.sh/ruff/) (config in `pyproject.toml`). Run `hatch run fix` before committing.
- Match the surrounding code's naming, docstring, and comment conventions.

## Releasing

Releases are cut by maintainers — see [RELEASE.md](RELEASE.md). You don't need to bump versions in your PR.

## License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
