# Excalidraw Architect MCP
<!-- mcp-name: io.github.BV-Venky/excalidraw-architect-mcp -->
[![PyPI](https://img.shields.io/pypi/v/excalidraw-architect-mcp)](https://pypi.org/project/excalidraw-architect-mcp/)
[![Cursor Directory](https://img.shields.io/badge/Cursor-Directory-purple)](https://cursor.directory/mcp/excalidraw-architect-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)


It's been a constant struggle trying to understand unfamiliar and complex codebases - managing cognitive overload and trying to imagine how everything fits together.

## The Problem

When you're onboarding onto a codebase, designing a new system, or documenting existing architecture, a visual diagram communicates in seconds what pages of text can't. But the options today aren't great. Mermaid diagrams are quick to generate but have limited capabilities - you can't drag a node to reposition it, group components visually. Excalidraw solves these problems, but when LLMs try to generate Excalidraw directly, they hallucinate coordinates - boxes overlap, arrows tangle, and you end up fixing the diagram manually.

## The Solution

**excalidraw-architect-mcp** separates the *what* from the *where* - the AI focuses on structure, the engine handles the pixel math.

Your LLM describes the components and connections, and the MCP handles layout, styling, and rendering using a proper graph layout algorithm. 50+ technologies (Kafka, PostgreSQL, Redis, etc.) get auto-styled, you can iteratively edit diagrams with natural language ("add a cache in front of the DB"), and it runs fully offline in Cursor/Windsurf - no API keys needed.

- **Perfect layouts every time** - Sugiyama algorithm with adaptive spacing; no overlapping boxes
- **Architecture-aware styling** - say "Kafka" and get a stream-styled node, not a generic rectangle
- **Talk to your diagrams** - add, remove, or rewire components on an existing diagram with natural language
- **Hub node visualization** - gateways and load balancers auto-stretch to span their connected services
- **Export to SVG & PNG** - convert any `.excalidraw` file to a portable image, no browser needed

## See It In Action

> Every frame below is generated entirely by AI using this MCP - zero manual positioning.

### E-Commerce Platform Architecture

![E-Commerce Platform Demo](showcase/demo_ecommerce.gif)

### Payment Processing Flow

![Payment Processing Flow Demo](showcase/demo_payment.gif)

## Use Cases

- **Onboarding onto a new codebase** - point it at a microservice and get a high-level architecture diagram without reading a single line of code. Point it to a set of classes for a low-level flow diagram when you need the details.
- **Brainstorming and system design** - when you're whiteboarding a new service or debating trade-offs, ask it to visualize the architecture as you go. Iterate by saying "add a cache here" or "swap Kafka for SQS" instead of redrawing from scratch.
- **Documentation that stays alive** - drop the `.excalidraw` file into your repo and update it with natural language as the system evolves. No more stale diagrams from six sprints ago.

## Quick Start

### Install

```bash
pip install excalidraw-architect-mcp
```

For **PNG export** support (SVG works out of the box):

```bash
pip install excalidraw-architect-mcp[png]
```

Or run without installing (requires [uv](https://docs.astral.sh/uv/)):

```bash
uvx excalidraw-architect-mcp
```

### Configure MCP in Your IDE

**Cursor** - Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "excalidraw-architect": {
      "command": "excalidraw-architect-mcp",
      "transport": "stdio"
    }
  }
}
```

**Claude Code** - Run this one-liner:

```bash
claude mcp add-json excalidraw-architect '{"type":"stdio","command":"excalidraw-architect-mcp"}' --scope user
```

Or add manually to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "excalidraw-architect": {
      "type": "stdio",
      "command": "excalidraw-architect-mcp"
    }
  }
}
```

**Windsurf / Other IDEs** - Same pattern; point to the `excalidraw-architect-mcp` command over stdio.

### Install the Diagram Design Skill (recommended)

This repo includes a [Diagram Design Skill](.skills/excalidraw-diagram-design/SKILL.md) that teaches the AI how to structure diagrams for the best results - node count limits, topology rules, edge label guidelines, and common patterns.

**For Cursor users:**

```bash
mkdir -p ~/.cursor/skills/excalidraw-diagram-design && \
curl -o ~/.cursor/skills/excalidraw-diagram-design/SKILL.md \
  https://raw.githubusercontent.com/BV-Venky/excalidraw-architect-mcp/main/.skills/excalidraw-diagram-design/SKILL.md
```

**For other IDEs:** Download the [SKILL.md](.skills/excalidraw-diagram-design/SKILL.md) file and add it to your IDE's prompt context or system instructions.

The AI will automatically pick up the skill and apply it when generating diagrams. Feel free to modify the rules to suit your preferences - tweak node limits, add your own patterns, or adjust styling guidelines.

> **A note on diagram complexity:** As the number of components and connections grows, diagrams inevitably become harder to read - this is true for humans drawing by hand too, not just automated layout. For best results, aim for **6-15 nodes** in architecture diagrams and **10-25 nodes** in detailed flows. If your system is larger, split it into multiple focused diagrams rather than cramming everything into one.

### Use It

Just ask your AI IDE naturally:

> "Create a high-level architecture diagram of this codebase"

> "Create an architecture diagram for a microservices system with an API Gateway, Auth Service, User Service, Order Service, PostgreSQL, Redis cache, and Kafka event bus"

> "Convert this mermaid diagram to excalidraw diagram"

> "Add a Caching layer to the Order Service in the High Level architecture diagram"

> "Export the architecture diagram to SVG"

> "Export the diagram as a PNG at 3x resolution"

The AI calls the MCP tool with the relationship map. The MCP handles layout, styling, and output. Open the resulting `.excalidraw` file with the [Excalidraw VS Code extension](https://marketplace.visualstudio.com/items?itemName=pomdtr.excalidraw-editor) or drag it into [excalidraw.com](https://excalidraw.com).

## Features

### Auto Layout Engine

Uses the Sugiyama hierarchical layout algorithm with:

- **Adaptive layer gaps** - spacing adjusts based on edge label length
- **Hub node stretching** - gateways/load balancers stretch to span connected services
- **Obstacle-aware edge routing** - arrows curve around intermediate nodes instead of cutting through them
- **Disconnected component stacking** - separate subgraphs (e.g., monitoring stack) are placed without overlap

### Component Library

50+ technology mappings with automatic visual styling:

| Category | Technologies |
|---|---|
| Database | PostgreSQL, MySQL, MongoDB, DynamoDB, Cassandra, ClickHouse, SQLite, CockroachDB |
| Message Queue | Kafka, RabbitMQ, SQS, Redis Streams, NATS |
| Cache | Redis, Memcached, Varnish |
| Load Balancer | Nginx, HAProxy, ALB/ELB, Traefik, Envoy |
| Compute | Docker, Kubernetes, Lambda, ECS, Fargate |
| Storage | S3, GCS, Azure Blob, MinIO |
| API | REST, GraphQL, gRPC, WebSocket |
| CDN | CloudFront, Cloudflare |
| Monitoring | Prometheus, Grafana, Datadog, ELK |
| Client | Browser, Mobile, Desktop, CLI |

### Stateful Editing

Diagram metadata is embedded in the `.excalidraw` file. Ask the AI:

> "Add a Redis cache in front of the database in the existing diagram"

The MCP reads the current state, applies the modification, and re-renders with proper layout.

### Mermaid Conversion

Already have a Mermaid flowchart? Convert it:

> "Convert this Mermaid diagram to Excalidraw" (paste your Mermaid syntax)

### Image Export

Export any `.excalidraw` diagram to a portable image — no browser, Excalidraw app, or Node.js required.

- **SVG** - zero extra dependencies; uses a pure-Python renderer that handles rectangles, ellipses, diamonds, text (including multiline), and arrows with arrowheads
- **PNG** - requires the optional `cairosvg` package (`pip install excalidraw-architect-mcp[png]`); supports a configurable resolution multiplier (default 2×)

> "Export the architecture diagram as an SVG"

## MCP Tools

| Tool | Description |
|---|---|
| `create_diagram` | Create a new diagram from structured node/connection data |
| `mermaid_to_excalidraw` | Convert Mermaid flowchart syntax to `.excalidraw` |
| `modify_diagram` | Add/remove/update nodes and connections on an existing diagram |
| `get_diagram_info` | Read current diagram state (call before modifying) |
| `export_diagram` | Export `.excalidraw` to SVG or PNG image |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

MIT - see [LICENSE](LICENSE).
