# Diagram type reference

Generated from the registry by `scripts/sync_skill_docs.py`. Do not
edit by hand — edit `src/excalidraw_mcp/diagrams/registry.py` and the
type's spec model, then re-run the script.

Every spec also accepts `title` and `subtitle`. Mark one or two
elements `"focal": true` — no more.

## Structural — hierarchy, containment, entities

### `tree`

**Use when:** Parent -> children: taxonomies, file hierarchies, decision breakdowns.

**Avoid when:** Use org_chart for people or teams; use nested when containment is the point.

**Spec fields**

- `nodes`
- `direction` (optional)

**Example**

```json
{
  "title": "Config resolution order",
  "nodes": [
    {
      "id": "root",
      "label": "Effective config"
    },
    {
      "id": "cli",
      "label": "CLI flags",
      "parent": "root",
      "focal": true
    },
    {
      "id": "env",
      "label": "Environment",
      "parent": "root"
    },
    {
      "id": "file",
      "label": "config.toml",
      "parent": "root"
    },
    {
      "id": "proj",
      "label": "Project",
      "parent": "file"
    },
    {
      "id": "user",
      "label": "User home",
      "parent": "file"
    },
    {
      "id": "defaults",
      "label": "Built-in defaults",
      "parent": "root"
    }
  ]
}
```

### `org_chart`

**Use when:** Human, team, or agent ownership: reporting lines, escalation, routing.

**Avoid when:** Not for system components -- that is architecture.

**Spec fields**

- `people`

**Example**

```json
{
  "title": "Platform group",
  "people": [
    {
      "id": "vp",
      "name": "Ada Whitfield",
      "role": "VP Engineering"
    },
    {
      "id": "plat",
      "name": "Ravi Menon",
      "role": "Platform Lead",
      "reports_to": "vp"
    },
    {
      "id": "data",
      "name": "Sofia Lindqvist",
      "role": "Data Lead",
      "reports_to": "vp"
    },
    {
      "id": "sre",
      "name": "On-call rotation",
      "role": "Shared",
      "reports_to": "plat",
      "focal": true
    },
    {
      "id": "api",
      "name": "API team",
      "role": "4 engineers",
      "reports_to": "plat"
    },
    {
      "id": "pipe",
      "name": "Pipelines",
      "role": "3 engineers",
      "reports_to": "data"
    }
  ]
}
```

### `state`

**Use when:** States, transitions, and guards. Order lifecycles, retry machines, approval flows.

**Avoid when:** Not for time-ordered messages between actors -- that is sequence.

**Spec fields**

- `states`
- `transitions` (optional)
- `direction` (optional)

**Example**

```json
{
  "title": "Order lifecycle",
  "states": [
    {
      "id": "s",
      "label": "start",
      "kind": "start"
    },
    {
      "id": "pending",
      "label": "Pending"
    },
    {
      "id": "paid",
      "label": "Paid",
      "focal": true
    },
    {
      "id": "shipped",
      "label": "Shipped"
    },
    {
      "id": "cancelled",
      "label": "Cancelled"
    },
    {
      "id": "e",
      "label": "end",
      "kind": "end"
    }
  ],
  "transitions": [
    {
      "from_id": "s",
      "to_id": "pending"
    },
    {
      "from_id": "pending",
      "to_id": "paid",
      "label": "payment ok"
    },
    {
      "from_id": "pending",
      "to_id": "cancelled",
      "label": "timeout"
    },
    {
      "from_id": "pending",
      "to_id": "pending",
      "label": "retry"
    },
    {
      "from_id": "paid",
      "to_id": "shipped",
      "label": "picked"
    },
    {
      "from_id": "shipped",
      "to_id": "e"
    },
    {
      "from_id": "cancelled",
      "to_id": "e"
    }
  ]
}
```

### `nested`

**Use when:** Hierarchy by containment or scope: bounded contexts, module trees, org scopes.

**Avoid when:** Beyond three levels of nesting, split into an overview plus a detail diagram.

**Spec fields**

- `root`

**Example**

```json
{
  "title": "Bounded contexts",
  "root": {
    "label": "Commerce platform",
    "children": [
      {
        "label": "Ordering",
        "focal": true,
        "children": [
          {
            "label": "Cart"
          },
          {
            "label": "Checkout"
          },
          {
            "label": "Pricing"
          }
        ]
      },
      {
        "label": "Fulfilment",
        "children": [
          {
            "label": "Inventory"
          },
          {
            "label": "Shipping"
          }
        ]
      },
      {
        "label": "Identity",
        "children": [
          {
            "label": "Accounts"
          },
          {
            "label": "Sessions"
          }
        ]
      }
    ]
  }
}
```

### `layers`

**Use when:** Stacked abstraction levels where each layer sits on the one below.

**Avoid when:** If the layers exchange traffic in both directions, use architecture instead.

**Spec fields**

- `layers`
- `width` (optional)
- `show_dividers` (optional)

**Example**

```json
{
  "title": "Request path",
  "layers": [
    {
      "label": "Client",
      "note": "web + mobile"
    },
    {
      "label": "Edge / CDN",
      "note": "TLS termination"
    },
    {
      "label": "API Gateway",
      "focal": true,
      "note": "auth, rate limits"
    },
    {
      "label": "Services",
      "note": "12 deployments"
    },
    {
      "label": "Data stores",
      "note": "Postgres, Redis"
    }
  ]
}
```

### `medallion`

**Use when:** Multi-tier data storage with quality levels: bronze/silver/gold, raw/curated/serving.

**Avoid when:** Use data_flow when the emphasis is who does what rather than where data rests.

**Spec fields**

- `tiers`

**Example**

```json
{
  "title": "Lakehouse tiers",
  "tiers": [
    {
      "label": "Bronze",
      "description": "raw, append-only",
      "datasets": [
        "events_raw",
        "cdc_orders",
        "clickstream"
      ]
    },
    {
      "label": "Silver",
      "description": "cleaned, conformed",
      "datasets": [
        "orders",
        "customers",
        "sessions"
      ]
    },
    {
      "label": "Gold",
      "description": "business-ready",
      "datasets": [
        "daily_revenue",
        "cohort_ltv"
      ],
      "focal": true
    }
  ]
}
```

### `er`

**Use when:** Entities, their fields, and relationships. Data models and schema documentation.

**Avoid when:** Above ~8 entities, split by bounded context.

**Spec fields**

- `entities`
- `relationships` (optional)

**Example**

```json
{
  "title": "Billing model",
  "entities": [
    {
      "name": "Customer",
      "fields": [
        "id  PK",
        "email",
        "created_at"
      ]
    },
    {
      "name": "Subscription",
      "fields": [
        "id  PK",
        "customer_id  FK",
        "plan",
        "status"
      ],
      "focal": true
    },
    {
      "name": "Invoice",
      "fields": [
        "id  PK",
        "subscription_id  FK",
        "total",
        "issued_at"
      ]
    },
    {
      "name": "Payment",
      "fields": [
        "id  PK",
        "invoice_id  FK",
        "amount",
        "method"
      ]
    }
  ],
  "relationships": [
    {
      "from_entity": "Customer",
      "to_entity": "Subscription",
      "cardinality": "1..*"
    },
    {
      "from_entity": "Subscription",
      "to_entity": "Invoice",
      "cardinality": "1..*"
    },
    {
      "from_entity": "Invoice",
      "to_entity": "Payment",
      "cardinality": "0..*"
    }
  ]
}
```

### `high_level`

**Use when:** End-to-end stack drawn inside one named boundary (a cluster, an account, a VPC).

**Avoid when:** Use architecture when the boundary is not the point.

**Spec fields**

- `cluster_label` (optional)
- `rows`

**Example**

```json
{
  "title": "Production cluster",
  "cluster_label": "Kubernetes / eu-west-1",
  "rows": [
    {
      "label": "Ingress",
      "items": [
        "ALB",
        "nginx"
      ]
    },
    {
      "label": "Services",
      "items": [
        "api",
        "worker",
        "scheduler"
      ],
      "focal": true
    },
    {
      "label": "Data",
      "items": [
        "Postgres",
        "Redis"
      ]
    },
    {
      "label": "Observability",
      "items": [
        "Prometheus",
        "Loki"
      ]
    }
  ]
}
```

### `it_state`

**Use when:** Legacy landscape grouped by phase or department; the 'before' state.

**Avoid when:** Use architecture for a target-state design.

**Spec fields**

- `groups`
- `connections` (optional)
- `columns` (optional)

**Example**

```json
{
  "title": "Current-state landscape",
  "subtitle": "Before the 2026 modernization",
  "groups": [
    {
      "label": "Finance",
      "items": [
        {
          "id": "sap",
          "label": "SAP ECC 6.0"
        },
        {
          "id": "excel",
          "label": "Excel reconciliation",
          "focal": true
        }
      ]
    },
    {
      "label": "Operations",
      "items": [
        {
          "id": "wms",
          "label": "Legacy WMS"
        },
        {
          "id": "ftp",
          "label": "Nightly FTP drop"
        }
      ]
    },
    {
      "label": "Customer",
      "items": [
        {
          "id": "crm",
          "label": "On-prem CRM"
        },
        {
          "id": "portal",
          "label": "Customer portal"
        }
      ]
    }
  ],
  "connections": [
    {
      "from_id": "sap",
      "to_id": "wms",
      "label": "batch"
    },
    {
      "from_id": "ftp",
      "to_id": "crm",
      "label": "nightly"
    }
  ]
}
```

## Flow — work moving across actors and time

### `swimlane`

**Use when:** Cross-functional process where step ownership matters. Handoffs are the story.

**Avoid when:** If every step has the same owner, use flowchart.

**Spec fields**

- `lanes`
- `steps`
- `connections` (optional)

**Example**

```json
{
  "title": "Pull request lifecycle",
  "lanes": [
    "Author",
    "CI",
    "Reviewer"
  ],
  "steps": [
    {
      "id": "open",
      "label": "Open PR",
      "lane": "Author"
    },
    {
      "id": "checks",
      "label": "Run checks",
      "lane": "CI"
    },
    {
      "id": "review",
      "label": "Review",
      "lane": "Reviewer"
    },
    {
      "id": "fixes",
      "label": "Push fixes",
      "lane": "Author"
    },
    {
      "id": "approve",
      "label": "Approve",
      "lane": "Reviewer",
      "focal": true
    },
    {
      "id": "merge",
      "label": "Squash + merge",
      "lane": "CI"
    }
  ],
  "connections": [
    {
      "from_id": "open",
      "to_id": "checks"
    },
    {
      "from_id": "checks",
      "to_id": "review",
      "label": "green"
    },
    {
      "from_id": "review",
      "to_id": "fixes",
      "label": "changes requested"
    },
    {
      "from_id": "fixes",
      "to_id": "approve"
    },
    {
      "from_id": "approve",
      "to_id": "merge",
      "focal": true
    }
  ]
}
```

### `process`

**Use when:** Multi-actor sequential workflow drawn as vertical actor columns with data handoffs.

**Avoid when:** Use swimlane for horizontal lanes and a wider flow.

**Spec fields**

- `actors`
- `steps`
- `connections` (optional)

**Example**

```json
{
  "title": "Incident response",
  "actors": [
    "Reporter",
    "On-call",
    "Comms"
  ],
  "steps": [
    {
      "id": "page",
      "label": "File incident",
      "lane": "Reporter"
    },
    {
      "id": "ack",
      "label": "Acknowledge",
      "lane": "On-call"
    },
    {
      "id": "triage",
      "label": "Triage severity",
      "lane": "On-call",
      "focal": true
    },
    {
      "id": "status",
      "label": "Post status page",
      "lane": "Comms"
    },
    {
      "id": "fix",
      "label": "Mitigate",
      "lane": "On-call"
    },
    {
      "id": "resolve",
      "label": "Resolve + notify",
      "lane": "Comms"
    }
  ],
  "connections": [
    {
      "from_id": "page",
      "to_id": "ack"
    },
    {
      "from_id": "ack",
      "to_id": "triage"
    },
    {
      "from_id": "triage",
      "to_id": "status"
    },
    {
      "from_id": "status",
      "to_id": "fix"
    },
    {
      "from_id": "fix",
      "to_id": "resolve"
    }
  ]
}
```

### `data_flow`

**Use when:** A pipeline where each stage is tagged with the role that owns it.

**Avoid when:** Use medallion when storage tiers, not roles, are the subject.

**Spec fields**

- `steps`

**Example**

```json
{
  "title": "Analytics pipeline",
  "steps": [
    {
      "label": "Capture",
      "role": "Product",
      "note": "SDK events"
    },
    {
      "label": "Ingest",
      "role": "Data Eng",
      "note": "Kafka -> S3"
    },
    {
      "label": "Model",
      "role": "Analytics Eng",
      "note": "dbt",
      "focal": true
    },
    {
      "label": "Serve",
      "role": "Analyst",
      "note": "BI layer"
    }
  ]
}
```

### `dp_integration`

**Use when:** Integration topology of a platform: sources -> core -> consumers.

**Avoid when:** Use architecture when the core needs to be decomposed in detail.

**Spec fields**

- `sources`
- `core` (optional)
- `consumers`

**Example**

```json
{
  "title": "Platform integration",
  "sources": [
    {
      "label": "Salesforce"
    },
    {
      "label": "Stripe"
    },
    {
      "label": "App events"
    },
    {
      "label": "Support desk"
    }
  ],
  "core": {
    "label": "Data Platform",
    "components": [
      "Ingestion",
      "Warehouse",
      "Semantic layer"
    ]
  },
  "consumers": [
    {
      "label": "Executive BI",
      "focal": true
    },
    {
      "label": "Growth models"
    },
    {
      "label": "Reverse ETL"
    }
  ]
}
```

### `sequence`

**Use when:** Time-ordered messages between actors: API traces, protocols, incident replays.

**Avoid when:** Never draw a message arrow that points backwards in time; use state for lifecycles.

**Spec fields**

- `actors`
- `messages`

**Example**

```json
{
  "title": "Checkout authorization",
  "actors": [
    {
      "id": "web",
      "label": "Web app"
    },
    {
      "id": "api",
      "label": "Orders API"
    },
    {
      "id": "psp",
      "label": "Payment PSP"
    },
    {
      "id": "db",
      "label": "Postgres"
    }
  ],
  "messages": [
    {
      "from_id": "web",
      "to_id": "api",
      "label": "POST /checkout"
    },
    {
      "from_id": "api",
      "to_id": "db",
      "label": "reserve stock"
    },
    {
      "from_id": "db",
      "to_id": "api",
      "label": "ok",
      "kind": "return"
    },
    {
      "from_id": "api",
      "to_id": "psp",
      "label": "authorize"
    },
    {
      "from_id": "psp",
      "to_id": "psp",
      "label": "risk check"
    },
    {
      "from_id": "psp",
      "to_id": "api",
      "label": "approved",
      "kind": "return",
      "focal": true
    },
    {
      "from_id": "api",
      "to_id": "web",
      "label": "201 Created",
      "kind": "return"
    }
  ]
}
```

## Geometric — position carries the meaning

### `timeline`

**Use when:** Events positioned in time along a single axis. Roadmaps, incident chronologies.

**Avoid when:** Use gantt when items have duration rather than a single instant.

**Spec fields**

- `events`

**Example**

```json
{
  "title": "Migration milestones",
  "events": [
    {
      "label": "Audit complete",
      "when": "Q1",
      "note": "42 services"
    },
    {
      "label": "Pilot service",
      "when": "Q2"
    },
    {
      "label": "Bulk migration",
      "when": "Q3",
      "focal": true,
      "note": "the risky one"
    },
    {
      "label": "Legacy shutdown",
      "when": "Q4"
    }
  ]
}
```

### `quadrant`

**Use when:** Two-axis positioning and prioritization. Add quadrant_labels for a consultant 2x2.

**Avoid when:** Use scatter when the axes carry real units rather than relative position.

**Spec fields**

- `x_axis`
- `y_axis`
- `items` (optional)
- `quadrant_labels` (optional)

**Example**

```json
{
  "title": "Migration priorities",
  "x_axis": {
    "label": "Effort",
    "low": "Low",
    "high": "High"
  },
  "y_axis": {
    "label": "Impact",
    "low": "Low",
    "high": "High"
  },
  "quadrant_labels": [
    "Quick wins",
    "Big bets",
    "Ignore",
    "Money pits"
  ],
  "items": [
    {
      "label": "Auth service",
      "x": 0.25,
      "y": 0.82,
      "focal": true
    },
    {
      "label": "Search",
      "x": 0.72,
      "y": 0.75
    },
    {
      "label": "Admin UI",
      "x": 0.22,
      "y": 0.24
    },
    {
      "label": "Legacy reports",
      "x": 0.8,
      "y": 0.2
    },
    {
      "label": "Billing",
      "x": 0.55,
      "y": 0.6
    }
  ]
}
```

### `pyramid`

**Use when:** Ranked hierarchy (mode='pyramid') or conversion drop-off (mode='funnel').

**Avoid when:** Use bar when the values matter more than the ranking.

**Spec fields**

- `tiers`
- `mode` (optional)

**Example**

```json
{
  "title": "Test strategy",
  "tiers": [
    {
      "label": "E2E",
      "note": "~40 specs"
    },
    {
      "label": "Integration",
      "note": "~400 tests"
    },
    {
      "label": "Unit",
      "note": "~6,000 tests",
      "focal": true
    }
  ]
}
```

### `venn`

**Use when:** Overlap between two or three sets, where the intersection is the insight.

**Avoid when:** Four or more sets is unreadable -- use a table.

**Spec fields**

- `sets`
- `intersections` (optional)

**Example**

```json
{
  "title": "Where the work sits",
  "sets": [
    {
      "label": "Platform"
    },
    {
      "label": "Product"
    },
    {
      "label": "Security",
      "focal": true
    }
  ],
  "intersections": [
    {
      "between": [
        "Platform",
        "Product"
      ],
      "label": "SDKs"
    },
    {
      "between": [
        "Platform",
        "Security"
      ],
      "label": "IAM"
    },
    {
      "between": [
        "Product",
        "Security"
      ],
      "label": "Consent"
    },
    {
      "between": [
        "Platform",
        "Product",
        "Security"
      ],
      "label": "Audit log"
    }
  ]
}
```

### `loop`

**Use when:** A reinforcing cycle; add a hub for shared state the stations write back to.

**Avoid when:** Use process when the flow has a real beginning and end.

**Spec fields**

- `stations`
- `hub` (optional)
- `hub_note` (optional)

**Example**

```json
{
  "title": "Observability flywheel",
  "hub": "Telemetry store",
  "hub_note": "every stage reads from and writes back to it",
  "stations": [
    {
      "label": "Ship"
    },
    {
      "label": "Instrument"
    },
    {
      "label": "Observe"
    },
    {
      "label": "Diagnose",
      "focal": true
    },
    {
      "label": "Prioritise"
    }
  ]
}
```

### `gantt`

**Use when:** Tasks and phases with duration on a timeline. Shows overlap and parallel tracks.

**Avoid when:** Above ~12 tasks, collapse to a phase-level view.

**Spec fields**

- `tasks`
- `unit_label` (optional)
- `tick_every` (optional)
- `marker` (optional)

**Example**

```json
{
  "title": "Platform migration plan",
  "unit_label": "Wk",
  "tick_every": 2,
  "marker": 5,
  "tasks": [
    {
      "label": "Discovery",
      "start": 0,
      "end": 3,
      "phase": "Assess"
    },
    {
      "label": "Dependency audit",
      "start": 2,
      "end": 5,
      "phase": "Assess"
    },
    {
      "label": "Pilot service",
      "start": 5,
      "end": 9,
      "phase": "Build"
    },
    {
      "label": "Bulk migration",
      "start": 8,
      "end": 16,
      "phase": "Build",
      "focal": true
    },
    {
      "label": "Cutover",
      "start": 15,
      "end": 18,
      "phase": "Land"
    },
    {
      "label": "Decommission",
      "start": 17,
      "end": 20,
      "phase": "Land"
    }
  ]
}
```

## Charts — quantitative, drawn hand-sketched

### `bar`

**Use when:** Quantitative comparison across categories. Multiple series render as grouped bars.

**Avoid when:** Use line when the x axis is continuous time.

**Spec fields**

- `categories`
- `series`
- `x_label` (optional)
- `y_label` (optional)

**Example**

```json
{
  "title": "p99 latency by service",
  "y_label": "milliseconds",
  "categories": [
    "auth",
    "orders",
    "search",
    "billing",
    "media"
  ],
  "series": [
    {
      "name": "Before",
      "values": [
        220,
        480,
        310,
        190,
        640
      ]
    },
    {
      "name": "After",
      "values": [
        140,
        210,
        260,
        150,
        300
      ],
      "focal": true
    }
  ]
}
```

### `line`

**Use when:** Continuous trends over an ordered axis. Capped at 15 points per series.

**Avoid when:** Use bar for a handful of discrete categories.

**Spec fields**

- `x_labels`
- `series`
- `x_label` (optional)
- `y_label` (optional)
- `show_points` (optional)

**Example**

```json
{
  "title": "Weekly build time",
  "x_label": "Week",
  "y_label": "minutes",
  "x_labels": [
    "W1",
    "W2",
    "W3",
    "W4",
    "W5",
    "W6",
    "W7",
    "W8"
  ],
  "series": [
    {
      "name": "CI total",
      "values": [
        42,
        44,
        41,
        38,
        30,
        26,
        22,
        19
      ],
      "focal": true
    },
    {
      "name": "Test suite",
      "values": [
        28,
        29,
        27,
        25,
        20,
        17,
        15,
        13
      ]
    }
  ]
}
```

### `scatter`

**Use when:** Distribution and correlation between two continuous variables.

**Avoid when:** Use quadrant when position is relative judgement rather than measurement.

**Spec fields**

- `points`
- `x_label` (optional)
- `y_label` (optional)

**Example**

```json
{
  "title": "Service size vs. change failure rate",
  "x_label": "Lines of code (thousands)",
  "y_label": "Change failure rate (%)",
  "points": [
    {
      "x": 2.1,
      "y": 3.0,
      "group": "core"
    },
    {
      "x": 4.5,
      "y": 4.2,
      "group": "core"
    },
    {
      "x": 9.8,
      "y": 7.5,
      "group": "core"
    },
    {
      "x": 14.2,
      "y": 11.0,
      "group": "core",
      "label": "billing",
      "focal": true
    },
    {
      "x": 3.3,
      "y": 5.5,
      "group": "edge"
    },
    {
      "x": 6.0,
      "y": 6.1,
      "group": "edge"
    },
    {
      "x": 11.5,
      "y": 9.4,
      "group": "edge"
    },
    {
      "x": 1.2,
      "y": 2.0,
      "group": "edge"
    }
  ]
}
```
