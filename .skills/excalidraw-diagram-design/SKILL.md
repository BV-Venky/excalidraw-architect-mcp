---
name: excalidraw-diagram-design
description: Guide for structuring graph input (nodes and edges) for the Excalidraw Architect MCP tool to produce clean, readable diagrams. Use when generating architecture diagrams, flow diagrams, or any visual diagram via create_diagram or mermaid_to_excalidraw.
---

# Excalidraw Diagram Design Guide

This skill teaches you how to structure the `nodes` and `connections` input for the Excalidraw Architect MCP so the auto-layout engine produces clean, readable diagrams — not spaghetti.

## Core Principle

The layout engine (Sugiyama algorithm) works best with **tree-like, flow-oriented graphs**. Your job as the LLM is to model the *data flow story*, not the *import graph*.

## Graph Topology Rules

### 1. Keep it tree-like — avoid diamond dependencies

The #1 cause of messy diagrams is multiple nodes connecting to the same shared target.

```
BAD: 4 arrows all pointing to "models.py"
  mermaid → models
  state   → models
  layout  → models
  builder → models

GOOD: Drop shared infrastructure nodes or show them as a single grouped leaf
  layout → builder → output
```

**Rule**: If a node has 4+ incoming edges, either remove it or group it with related nodes.

### 2. Limit edges to primary data flow

Show how data moves through the system, not every `import` statement.

```
BAD (16 edges for 12 nodes — dependency graph):
  server → mermaid, state, layout, excalidraw
  mermaid → models
  state → models, excalidraw_file
  layout → models, grandalf, components
  excalidraw → models, components, themes, excalidraw_file

GOOD (9 edges for 9 nodes — data flow):
  ide → server → [mermaid, state, layout]
  layout → renderer → [styling, output]
```

**Rule**: Aim for roughly N-1 to N+2 edges for N nodes (tree + a few extra).

### 3. Hub nodes should have 3–5 fan-out, not more

The layout engine auto-stretches "hub" nodes (≥3 connections) into gate-like rectangles. This looks great for API gateways, load balancers, and message brokers. But a node with 6+ fan-out creates too many parallel arrows.

```
GOOD: API Gateway → [Auth, Users, Orders, Payments]  (4 fan-out)
BAD:  Server → [A, B, C, D, E, F, G, H]             (8 fan-out)
```

**Rule**: If a node has 6+ connections, split it into two logical stages or group downstream nodes.

### 4. Keep layers balanced

Each "column" (layer) in a left-right diagram should have 1–4 nodes. If one layer has 6+ nodes, the diagram becomes vertically sprawling.

```
GOOD layer distribution: [1] → [1] → [3] → [2] → [1]
BAD layer distribution:  [1] → [1] → [7] → [1]
```

### 5. Use concise edge labels (≤4 words)

Edge labels affect spacing. Long labels force adaptive gaps to push layers apart. They also increase node height, which makes the obstacle-detection engine more likely to trigger unnecessary detours.

```
GOOD: "LayoutResult", "DiagramGraph", "write JSON"
BAD:  "sends the computed layout result with positioned nodes and edges"
```

**Rule**: Max 4 words per edge label. If you need more context, put it in the node label or drop it.

## Node Design

### Choose the right abstraction level

- **Too granular**: Every function or class as a node → too many nodes
- **Too abstract**: "Frontend" and "Backend" → no useful detail
- **Right level**: One node per module, service, or logical component

### Use component_type for auto-styling

The tool auto-detects technology from labels, but explicit `component_type` is more reliable:

```json
{"id": "cache", "label": "Session Cache", "component_type": "redis"}
{"id": "db", "label": "Order Database", "component_type": "postgresql"}
{"id": "queue", "label": "Event Bus", "component_type": "kafka"}
{"id": "lb", "label": "API Gateway", "component_type": "api_gateway"}
```

### Node count guidelines

| Diagram type | Ideal node count |
|---|---|
| High-level architecture | 6–15 |
| Detailed service flow | 10–25 |
| Service deep-dive (internals, sub-components) | 15–30 |
| Simple sequence | 5–9 |

For diagrams with 20+ nodes, keep labels to **1–2 lines max** — long multi-line labels inflate node sizes and trigger unnecessary obstacle detours. Prefer short, scannable labels (e.g., `DynamoDB: orders` instead of `DynamoDB OrdersTable\n(partition: order_id)`).

## Edge Design

### Direction matters

Default is `LR` (left-to-right). Use this for:
- Architecture diagrams (request flows left to right)
- Data pipelines

Use `TD` (top-down) for:
- Org charts
- Class hierarchies
- Decision trees

### Edge styles

- `solid` (default): Primary data flow
- `dashed`: Optional, async, or metadata paths
- `dotted`: Monitoring, logging, observability
- `thick`: Critical path or high-throughput

## Common Diagram Patterns

### Pattern 1: Gateway Fan-out (architecture)

```
Client → Gateway → [Service A, Service B, Service C]
Each service → Database or Cache (1:1)
```

Produces a clean hub with parallel arrows.

### Pattern 2: Pipeline (data flow)

```
Input → Step 1 → Step 2 → Step 3 → Output
```

Linear chain, optionally with one fork-merge.

### Pattern 3: Pipeline with fork-merge

```
Input → Process → [Branch A, Branch B] → Merge → Output
```

Creates a diamond shape — keep it to ONE fork-merge per diagram.

### Pattern 4: Layered architecture

```
Client → Load Balancer → [Services] → [Databases]
                                     → [Caches]
Monitoring → [Prometheus, Grafana]  (disconnected — auto-stacked)
```

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| Every import as an edge | Spaghetti arrows | Show primary data flow only |
| Shared dependency node (4+ incoming) | Arrow crossings, overlaps | Remove or group the node |
| Long edge labels | Excessive spacing, detour triggers | Keep to ≤4 words |
| 30+ nodes without splitting | Unreadable, routing congestion | Split into multiple diagrams |
| Multi-line verbose labels at 20+ nodes | Inflated nodes, false detours | Use 1–2 line labels |
| Multiple fork-merges | Complex crossing patterns | Linearize or split |

## Quick Checklist

Before calling `create_diagram`:

- [ ] ≤15 nodes for architecture, ≤25 for detailed flows, ≤30 for deep-dives
- [ ] Edge count ≈ node count (tree-like, not a mesh)
- [ ] No node has 5+ incoming edges
- [ ] Hub fan-out is 3–5, not 6+
- [ ] Edge labels are ≤4 words each
- [ ] For 20+ nodes: labels are 1–2 lines max
- [ ] Used `component_type` for known technologies
- [ ] One primary flow direction, not a web
