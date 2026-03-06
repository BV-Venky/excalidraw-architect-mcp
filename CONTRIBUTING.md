# Contributing to Excalidraw Architect MCP

Thanks for your interest in this project!

We're currently keeping the scope limited while we stabilize the core layout engine and component library. **We plan to accept external contributions in the future** -- stay tuned.

In the meantime, you're welcome to:

- **Report bugs** -- open an issue with steps to reproduce and the `.excalidraw` output file
- **Request features** -- open an issue describing your use case
- **Star the repo** -- helps others discover the project

## Development Setup (for maintainers)

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) or [hatch](https://hatch.pypa.io/)

### Getting Started

```bash
git clone https://github.com/BV-Venky/excalidraw-architect-mcp.git
cd excalidraw-architect-mcp
hatch run test
```

### Available Commands

| Command | What it does |
|---|---|
| `hatch run test` | Run the test suite |
| `hatch run lint` | Check for linting issues |
| `hatch run format` | Auto-format all code |
| `hatch run check` | Run lint + format check (same as CI) |
| `hatch run fix` | Auto-fix lint issues + format |
| `hatch run serve` | Start the MCP server locally |

## Architecture

```
AI IDE ──MCP──▶ server.py ──▶ engine/layout.py ──▶ engine/renderer.py ──▶ .excalidraw
                   │              │                       │
                   ├─ parsers/    ├─ grandalf              ├─ core/components.py
                   │  mermaid.py  │  (Sugiyama)            ├─ core/themes.py
                   └─ parsers/    └─ Adaptive gaps,        └─ JSON + metadata
                      state.py      hub stretch,
                                    obstacle routing
```

The AI IDE's LLM provides the *what* (nodes and connections). The MCP server handles the *how* (layout, styling, rendering). No AI inference happens in the MCP -- all reasoning is done by the IDE's built-in model.

## Project Structure

```
src/excalidraw_mcp/
├── server.py              # FastMCP server - exposes 4 MCP tools
├── core/                  # Foundation: data models + styling
│   ├── models.py          # Pydantic models (DiagramGraph, LayoutResult, etc.)
│   ├── components.py      # Technology → visual style mapping (50+ components)
│   └── themes.py          # Color themes (default, dark, colorful)
├── engine/                # Computational core
│   ├── layout.py          # Sugiyama layout with adaptive gaps & obstacle routing
│   └── renderer.py        # Excalidraw JSON builder (shapes, arrows, bindings)
└── parsers/               # Input adapters
    ├── mermaid.py          # Mermaid flowchart → DiagramGraph parser
    └── state.py            # Stateful editing (read/modify existing diagrams)
```
