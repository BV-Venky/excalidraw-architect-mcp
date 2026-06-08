---
name: architecture-knowledge-graph
description: Guide for reading a codebase and building a high-quality, persistent architecture knowledge graph via the Excalidraw Architect MCP kg_* tools. Use when creating or updating the knowledge graph (.claude/architecture.md), mapping services and their dependencies, or analyzing one or more repos to capture how services communicate.
---

# Architecture Knowledge Graph Guide

This skill teaches you how to turn a codebase into a clean, durable knowledge
graph using the `kg_*` MCP tools. The graph (default `.claude/architecture.md`)
is the **single source of truth**; diagrams are rendered views of it.

Graph quality depends almost entirely on how well you read the code. The MCP
preserves, validates, and renders whatever you put in — it does not analyze the
codebase. That analysis is your job.

## Core Principle

Model **services/components and how they communicate**, not classes, functions,
or every `import`. A "service" is a deployable unit / bounded context — one
repo, one container, one logical responsibility.

## Workflow (do the passes in order — don't interleave)

1. **`kg_init`** once (or `kg_import` to bootstrap from an existing `.excalidraw`).
2. **Discovery pass** — identify every service first. Add each with
   `kg_add_service`, setting `component_type`, `domain`, and `owner` while the
   info is in front of you (Dockerfiles, `CODEOWNERS`, READMEs, manifests).
3. **Linking pass** — only after all services exist, add edges with `kg_link`.
   Linking before a target exists fails; that's why discovery comes first.
4. **`kg_lint`** — catch dangling references, cycles, and single points of
   failure. Fix them before rendering.
5. **`kg_render`** (whole graph) or **`kg_render_view` / `kg_render_around` /
   `kg_render_domain`** for focused diagrams.

## How to find the edges (where services talk)

Look for these signals and translate each into a labelled `kg_link`:

| Signal in code | Link | Label / style |
|---|---|---|
| HTTP client, base URL, OpenAPI/Swagger spec | sync call | `"REST /orders"`, `style: solid` |
| gRPC stub / proto service | sync call | `"gRPC GetOrder"`, `style: solid` |
| Kafka/SQS/RabbitMQ **producer** | async event | `"Kafka order.created"`, `style: dashed` |
| Kafka/SQS/RabbitMQ **consumer** | async event (incoming) | label with the same topic |
| DB connection string / ORM config | datastore | `"reads/writes"`, `style: solid` |
| Service-discovery / env var (`PAYMENTS_URL`) | dependency | name the protocol |

### Cross-repo detection (multiple repos)

To connect services across repos, match a **producer** in repo A to a
**consumer** in repo B using the shared join key:

- **Async:** topic / queue name (A publishes `order.created`, B subscribes
  `order.created` → `kg_link order-svc -> fulfilment-svc "Kafka order.created" style=dashed`).
- **Sync:** the called service's route/host (A calls `https://payments/charge`
  → link A → payments).

Do a producer/consumer inventory across all repos *before* linking, so you
don't miss an edge whose two ends live in different codebases.

## Conventions (keep the graph consistent across sessions)

- **Stable kebab-case ids**, reused everywhere: `order-service` — never
  `OrderService` one session and `orders` the next. Id drift silently corrupts a
  cumulative graph.
- **Every edge is labelled with the mechanism.** No bare arrows between services.
- **Style encodes transport:** `solid` = sync (REST/gRPC/DB), `dashed` =
  async (events/queues). Consistency makes diagrams instantly readable.
- **Set `domain`** to group services (team / bounded context / tier) so you can
  render one domain at a time.

## Granularity

The full graph may be large, but any single rendered view should stay readable
(~6–15 services). If a domain has 20 services, render it per sub-domain with
`kg_render_domain` / `kg_render_view` rather than one giant picture. Resist
decomposing a service into its internal classes — that's a different diagram.

## Known limitation: parallel edges

A dependency is keyed on `(from_id, to_id)`, so a second `kg_link` between the
same pair **replaces** the first. If A talks to B two ways (REST *and* Kafka),
combine them into one label — `"REST /orders · Kafka order.created"` — or link
the primary transport. Don't issue two `kg_link` calls expecting two arrows.

## Verify

Unlike diagrams, the graph is deterministically checkable. After building, run
`whats_connected_to <service>` and `kg_lint` to sanity-check the topology
matches your understanding of the system before sharing rendered views.
