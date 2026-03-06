# Contributing to Excalidraw Architect MCP

Thanks for your interest in contributing! This guide will help you get set up.

## Development Setup

### Prerequisites

- Python 3.10+
- [hatch](https://hatch.pypa.io/) (recommended) or pip

### Getting Started

```bash
git clone https://github.com/BV-Venky/excalidraw-architect-mcp.git
cd excalidraw-architect-mcp

# Hatch creates the virtual environment and installs dependencies automatically
hatch run test
```

No manual `pip install` or venv setup needed — hatch handles it all on first run.

### Available Commands

| Command | What it does |
|---|---|
| `hatch run test` | Run the test suite |
| `hatch run lint` | Check for linting issues |
| `hatch run format` | Auto-format all code |
| `hatch run check` | Run lint + format check (same as CI) |
| `hatch run fix` | Auto-fix lint issues + format |
| `hatch run serve` | Start the MCP server locally |

### Without Hatch

If you prefer pip/uv:

```bash
uv pip install -e ".[dev]"
pytest
ruff check src/ tests/
ruff format src/ tests/
```

## Project Structure

```
src/excalidraw_mcp/
├── server.py              # MCP tool definitions — start here for new tools
├── core/                  # Foundation: data models + styling
│   ├── models.py          # Pydantic models — the shared data contract
│   ├── components.py      # Technology → visual style registry
│   └── themes.py          # Color themes
├── engine/                # Computational core
│   ├── layout.py          # Sugiyama layout engine — the core algorithm
│   └── renderer.py        # Excalidraw JSON builder — shapes, arrows, bindings
└── parsers/               # Input adapters
    ├── mermaid.py          # Mermaid flowchart parser
    └── state.py            # Stateful editing for modify_diagram
```

### Data Flow

```
DiagramGraph (core/models.py)
  → compute_layout() (engine/layout.py)
    → LayoutResult (core/models.py)
      → build_excalidraw_file() (engine/renderer.py)
        → .excalidraw JSON
```

## How to Contribute

### Adding a New Component Style

To add a technology to the component library:

1. Open `src/excalidraw_mcp/core/components.py`
2. Add a new `ComponentStyle` entry to `_COMPONENTS` with:
   - `category`: The technology category (e.g., "Database", "Cache")
   - `badge`: Short badge text (e.g., "PG", "RD")
   - `background_color` / `stroke_color`: Hex colors
   - `aliases`: Tuple of lowercase strings that should match this component
3. Add a test case to verify detection

### Adding a New Theme

1. Open `src/excalidraw_mcp/core/themes.py`
2. Add a new `Theme` instance to `_THEMES`
3. Add the theme name to `ThemeName` enum in `core/models.py`

### Improving Layout

The layout engine lives in `engine/layout.py`. Key functions:

- `compute_layout()` — main entry point
- `_apply_adaptive_layer_gaps()` — spacing between layers
- `_stretch_hub_nodes()` — gate-like visualization for hubs
- `_route_edges()` / `_route_around_obstacles()` — arrow routing

### Adding a New MCP Tool

1. Define the tool function in `server.py` with the `@mcp.tool` decorator
2. Add any new Pydantic models to `core/models.py`
3. Add tests

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run `hatch run check` (lint + format check)
5. Run `hatch run test` and make sure all tests pass
6. Commit with a descriptive message
7. Open a pull request

### PR Guidelines

- Keep PRs focused — one feature or fix per PR
- Add tests for new functionality
- Update the README if adding user-facing features
- Follow existing code patterns and naming conventions

## Reporting Issues

When reporting bugs, please include:

- Python version (`python --version`)
- Steps to reproduce
- Expected vs actual behavior
- The `.excalidraw` output file if relevant

## Code Style

- Use `from __future__ import annotations` in all modules (required for Python 3.10 compat)
- Type hints on all public functions
- Docstrings on all public functions and classes
- Line length: 100 characters (configured in `pyproject.toml`)
