"""Stress cases for every diagram type: 3-4 per type, deliberately varied.

``typed_samples`` holds one well-behaved example per type -- the showcase.
This holds the awkward ones. Each type gets a minimal case, a typical case, a
case at or past the density budget, and usually an edge case (long labels,
negative values, missing optional fields, structural collisions).

Rendered and checked by ``scripts/stress_test.py``.

Each entry is ``(slug, kind, payload)`` where kind is "spec" for typed
diagrams or "graph" for architecture/flowchart, which take nodes/connections.
"""

from __future__ import annotations

from typing import Any

Case = tuple[str, str, dict[str, Any]]

STRESS_CASES: dict[str, list[Case]] = {
    # ------------------------------------------------------------------
    # Graph types
    # ------------------------------------------------------------------
    "architecture": [
        (
            "01-minimal",
            "graph",
            {
                "nodes": [
                    {"id": "app", "label": "Web App"},
                    {"id": "db", "label": "PostgreSQL"},
                ],
                "connections": [{"from_id": "app", "to_id": "db"}],
            },
        ),
        (
            "02-microservices",
            "graph",
            {
                "nodes": [
                    {"id": "cdn", "label": "CloudFront"},
                    {"id": "gw", "label": "API Gateway"},
                    {"id": "auth", "label": "Auth Service"},
                    {"id": "catalog", "label": "Catalog Service"},
                    {"id": "cart", "label": "Cart Service"},
                    {"id": "redis", "label": "Redis"},
                    {"id": "pg", "label": "PostgreSQL"},
                    {"id": "kafka", "label": "Kafka"},
                    {"id": "search", "label": "Elasticsearch"},
                ],
                "connections": [
                    {"from_id": "cdn", "to_id": "gw"},
                    {"from_id": "gw", "to_id": "auth"},
                    {"from_id": "gw", "to_id": "catalog"},
                    {"from_id": "gw", "to_id": "cart"},
                    {"from_id": "auth", "to_id": "redis", "label": "sessions"},
                    {"from_id": "catalog", "to_id": "pg"},
                    {"from_id": "catalog", "to_id": "search", "label": "index"},
                    {"from_id": "cart", "to_id": "redis"},
                    {"from_id": "cart", "to_id": "kafka", "style": "dashed"},
                ],
            },
        ),
        (
            "03-dense-hub",
            "graph",
            {
                "nodes": [
                    {"id": "lb", "label": "Nginx"},
                    *[{"id": f"svc{i}", "label": f"Service {i}"} for i in range(1, 9)],
                    {"id": "pg", "label": "PostgreSQL"},
                    {"id": "redis", "label": "Redis"},
                    {"id": "kafka", "label": "Kafka"},
                    {"id": "s3", "label": "S3"},
                ],
                "connections": [
                    *[{"from_id": "lb", "to_id": f"svc{i}"} for i in range(1, 9)],
                    {"from_id": "svc1", "to_id": "pg"},
                    {"from_id": "svc2", "to_id": "pg"},
                    {"from_id": "svc3", "to_id": "redis"},
                    {"from_id": "svc4", "to_id": "kafka"},
                    {"from_id": "svc5", "to_id": "s3"},
                    {"from_id": "svc6", "to_id": "kafka"},
                ],
            },
        ),
        (
            "04-long-labels",
            "graph",
            {
                "nodes": [
                    {"id": "a", "label": "Customer Identity and Access Management"},
                    {"id": "b", "label": "Partner Reconciliation Batch Processor"},
                    {"id": "c", "label": "PostgreSQL"},
                ],
                "connections": [
                    {
                        "from_id": "a",
                        "to_id": "b",
                        "label": "nightly reconciliation handoff",
                    },
                    {"from_id": "b", "to_id": "c"},
                ],
            },
        ),
    ],
    "flowchart": [
        (
            "01-minimal",
            "graph",
            {
                "nodes": [
                    {"id": "s", "label": "Start", "shape": "stadium"},
                    {"id": "e", "label": "Done", "shape": "stadium"},
                ],
                "connections": [{"from_id": "s", "to_id": "e"}],
            },
        ),
        (
            "02-decision",
            "graph",
            {
                "nodes": [
                    {"id": "req", "label": "Request", "shape": "stadium"},
                    {"id": "cache", "label": "In cache?", "shape": "diamond"},
                    {"id": "hit", "label": "Return cached"},
                    {"id": "fetch", "label": "Query database"},
                    {"id": "store", "label": "Write cache"},
                    {"id": "resp", "label": "Respond", "shape": "stadium"},
                ],
                "connections": [
                    {"from_id": "req", "to_id": "cache"},
                    {"from_id": "cache", "to_id": "hit", "label": "yes"},
                    {"from_id": "cache", "to_id": "fetch", "label": "no"},
                    {"from_id": "fetch", "to_id": "store"},
                    {"from_id": "store", "to_id": "resp"},
                    {"from_id": "hit", "to_id": "resp"},
                ],
            },
        ),
        (
            "03-nested-branches",
            "graph",
            {
                "nodes": [
                    {"id": "in", "label": "Incoming webhook", "shape": "stadium"},
                    {"id": "sig", "label": "Signature valid?", "shape": "diamond"},
                    {"id": "drop", "label": "Reject 401"},
                    {"id": "dup", "label": "Duplicate?", "shape": "diamond"},
                    {"id": "ack", "label": "Ack 200"},
                    {"id": "kind", "label": "Event type?", "shape": "diamond"},
                    {"id": "pay", "label": "Handle payment"},
                    {"id": "ref", "label": "Handle refund"},
                    {"id": "unk", "label": "Log unknown"},
                    {"id": "done", "label": "Complete", "shape": "stadium"},
                ],
                "connections": [
                    {"from_id": "in", "to_id": "sig"},
                    {"from_id": "sig", "to_id": "drop", "label": "no"},
                    {"from_id": "sig", "to_id": "dup", "label": "yes"},
                    {"from_id": "dup", "to_id": "ack", "label": "yes"},
                    {"from_id": "dup", "to_id": "kind", "label": "no"},
                    {"from_id": "kind", "to_id": "pay", "label": "payment"},
                    {"from_id": "kind", "to_id": "ref", "label": "refund"},
                    {"from_id": "kind", "to_id": "unk", "label": "other"},
                    {"from_id": "pay", "to_id": "done"},
                    {"from_id": "ref", "to_id": "done"},
                    {"from_id": "unk", "to_id": "done"},
                ],
            },
        ),
    ],
    # ------------------------------------------------------------------
    # Flow
    # ------------------------------------------------------------------
    "dp_integration": [
        (
            "01-minimal",
            "spec",
            {
                "sources": [{"label": "Postgres CDC"}],
                "core": {"label": "Warehouse"},
                "consumers": [{"label": "Looker"}],
            },
        ),
        (
            "02-typical",
            "spec",
            {
                "title": "Customer data platform",
                "sources": [
                    {"label": "Salesforce"},
                    {"label": "Stripe"},
                    {"label": "Segment events"},
                ],
                "core": {
                    "label": "CDP",
                    "components": ["Ingest", "Identity resolution", "Warehouse"],
                },
                "consumers": [
                    {"label": "Braze", "focal": True},
                    {"label": "Looker"},
                ],
            },
        ),
        (
            "03-wide-fanout",
            "spec",
            {
                "title": "Enterprise integration topology",
                "sources": [{"label": f"Source system {i}"} for i in range(1, 9)],
                "core": {
                    "label": "Integration hub",
                    "components": ["Ingest", "Transform", "Serve", "Govern"],
                },
                "consumers": [{"label": f"Consumer {i}"} for i in range(1, 7)],
            },
        ),
        (
            "04-no-components",
            "spec",
            {
                "sources": [{"label": "Kafka"}, {"label": "S3 landing zone"}],
                "core": {"label": "Lakehouse"},
                "consumers": [{"label": "Notebooks"}, {"label": "Feature store"}],
            },
        ),
        (
            "05-long-labels",
            "spec",
            {
                "title": "Long source and consumer names",
                "sources": [{"label": "Salesforce Marketing Cloud"}],
                "core": {
                    "label": "Enterprise data platform",
                    "components": ["Ingestion and validation layer"],
                },
                "consumers": [{"label": "Executive reporting workspace"}],
            },
        ),
    ],
    "sequence": [
        (
            "01-minimal",
            "spec",
            {
                "actors": [
                    {"id": "c", "label": "Client"},
                    {"id": "s", "label": "Server"},
                ],
                "messages": [
                    {"from_id": "c", "to_id": "s", "label": "GET /health"},
                    {"from_id": "s", "to_id": "c", "label": "200 OK", "kind": "return"},
                ],
            },
        ),
        (
            "02-oauth",
            "spec",
            {
                "title": "OAuth authorization code flow",
                "actors": [
                    {"id": "ua", "label": "Browser"},
                    {"id": "app", "label": "Client App"},
                    {"id": "idp", "label": "Identity Provider"},
                    {"id": "api", "label": "Resource API"},
                ],
                "messages": [
                    {"from_id": "ua", "to_id": "app", "label": "click login"},
                    {"from_id": "app", "to_id": "ua", "label": "302 to IdP", "kind": "return"},
                    {"from_id": "ua", "to_id": "idp", "label": "authorize"},
                    {"from_id": "idp", "to_id": "idp", "label": "authenticate user"},
                    {"from_id": "idp", "to_id": "ua", "label": "302 + code", "kind": "return"},
                    {"from_id": "ua", "to_id": "app", "label": "code"},
                    {"from_id": "app", "to_id": "idp", "label": "exchange code"},
                    {
                        "from_id": "idp",
                        "to_id": "app",
                        "label": "access token",
                        "kind": "return",
                        "focal": True,
                    },
                    {"from_id": "app", "to_id": "api", "label": "Bearer request"},
                ],
            },
        ),
        (
            "03-dense",
            "spec",
            {
                "title": "Distributed transaction",
                "actors": [
                    {"id": "o", "label": "Orchestrator"},
                    {"id": "inv", "label": "Inventory"},
                    {"id": "pay", "label": "Payments"},
                    {"id": "ship", "label": "Shipping"},
                    {"id": "notify", "label": "Notifications"},
                ],
                "messages": [
                    {"from_id": "o", "to_id": "inv", "label": "reserve"},
                    {"from_id": "inv", "to_id": "o", "label": "reserved", "kind": "return"},
                    {"from_id": "o", "to_id": "pay", "label": "charge"},
                    {"from_id": "pay", "to_id": "pay", "label": "3DS check"},
                    {"from_id": "pay", "to_id": "o", "label": "declined", "kind": "return"},
                    {"from_id": "o", "to_id": "inv", "label": "release", "focal": True},
                    {"from_id": "inv", "to_id": "o", "label": "released", "kind": "return"},
                    {"from_id": "o", "to_id": "notify", "label": "payment failed"},
                    {"from_id": "notify", "to_id": "o", "label": "sent", "kind": "return"},
                    {"from_id": "o", "to_id": "ship", "label": "cancel draft"},
                ],
            },
        ),
        (
            "04-self-heavy",
            "spec",
            {
                "title": "Retry with backoff",
                "actors": [
                    {"id": "w", "label": "Worker"},
                    {"id": "q", "label": "Queue"},
                ],
                "messages": [
                    {"from_id": "w", "to_id": "q", "label": "poll"},
                    {"from_id": "w", "to_id": "w", "label": "attempt 1 fails"},
                    {"from_id": "w", "to_id": "w", "label": "backoff 2s"},
                    {"from_id": "w", "to_id": "w", "label": "attempt 2 fails"},
                    {"from_id": "w", "to_id": "q", "label": "nack + requeue"},
                ],
            },
        ),
    ],
    "swimlane": [
        (
            "01-minimal",
            "spec",
            {
                "lanes": ["Dev", "Ops"],
                "steps": [
                    {"id": "a", "label": "Merge", "lane": "Dev"},
                    {"id": "b", "label": "Deploy", "lane": "Ops"},
                ],
                "connections": [{"from_id": "a", "to_id": "b"}],
            },
        ),
        (
            "02-incident",
            "spec",
            {
                "title": "Sev-1 incident handling",
                "lanes": ["Detection", "On-call", "Comms", "Review"],
                "steps": [
                    {"id": "alert", "label": "Alert fires", "lane": "Detection"},
                    {"id": "ack", "label": "Acknowledge", "lane": "On-call"},
                    {"id": "sev", "label": "Set severity", "lane": "On-call"},
                    {"id": "status", "label": "Status page", "lane": "Comms"},
                    {"id": "fix", "label": "Mitigate", "lane": "On-call", "focal": True},
                    {"id": "allclear", "label": "All clear", "lane": "Comms"},
                    {"id": "pm", "label": "Postmortem", "lane": "Review"},
                ],
                "connections": [
                    {"from_id": "alert", "to_id": "ack"},
                    {"from_id": "ack", "to_id": "sev"},
                    {"from_id": "sev", "to_id": "status"},
                    {"from_id": "status", "to_id": "fix"},
                    {"from_id": "fix", "to_id": "allclear"},
                    {"from_id": "allclear", "to_id": "pm"},
                ],
            },
        ),
        (
            "03-same-lane-collisions",
            "spec",
            {
                "title": "Many steps per lane",
                "lanes": ["Author", "Reviewer"],
                "steps": [
                    {"id": f"a{i}", "label": f"Author step {i}", "lane": "Author"}
                    for i in range(1, 5)
                ]
                + [
                    {"id": f"r{i}", "label": f"Review step {i}", "lane": "Reviewer"}
                    for i in range(1, 5)
                ],
                "connections": [
                    {"from_id": "a1", "to_id": "r1"},
                    {"from_id": "r1", "to_id": "a2"},
                    {"from_id": "a2", "to_id": "r2"},
                    {"from_id": "r2", "to_id": "a3"},
                    {"from_id": "a3", "to_id": "r3"},
                    {"from_id": "r3", "to_id": "a4"},
                    {"from_id": "a4", "to_id": "r4"},
                ],
            },
        ),
        (
            "04-no-connections",
            "spec",
            {
                "title": "Responsibilities only",
                "lanes": ["Platform", "Product", "Security"],
                "steps": [
                    {"id": "p1", "label": "Runtime", "lane": "Platform"},
                    {"id": "p2", "label": "CI/CD", "lane": "Platform"},
                    {"id": "d1", "label": "Feature work", "lane": "Product"},
                    {"id": "s1", "label": "Threat model", "lane": "Security"},
                ],
            },
        ),
        (
            "05-long-labels",
            "spec",
            {
                "title": "Labels that exceed the fixed step width",
                "lanes": ["Platform engineering", "Security review"],
                "steps": [
                    {
                        "id": "a",
                        "label": "Provision isolated staging namespace",
                        "lane": "Platform engineering",
                    },
                    {
                        "id": "b",
                        "label": "Complete threat model sign-off",
                        "lane": "Security review",
                    },
                ],
                "connections": [{"from_id": "a", "to_id": "b"}],
            },
        ),
    ],
    "process": [
        (
            "01-minimal",
            "spec",
            {
                "actors": ["Requester", "Approver"],
                "steps": [
                    {"id": "r", "label": "Raise request", "lane": "Requester"},
                    {"id": "a", "label": "Approve", "lane": "Approver"},
                ],
                "connections": [{"from_id": "r", "to_id": "a"}],
            },
        ),
        (
            "02-onboarding",
            "spec",
            {
                "title": "Engineer onboarding",
                "actors": ["IT", "Manager", "New hire"],
                "steps": [
                    {"id": "acct", "label": "Create accounts", "lane": "IT"},
                    {"id": "laptop", "label": "Ship laptop", "lane": "IT"},
                    {"id": "buddy", "label": "Assign buddy", "lane": "Manager"},
                    {"id": "setup", "label": "Set up env", "lane": "New hire"},
                    {"id": "pr", "label": "First PR", "lane": "New hire", "focal": True},
                    {"id": "review", "label": "Review + merge", "lane": "Manager"},
                ],
                "connections": [
                    {"from_id": "acct", "to_id": "laptop"},
                    {"from_id": "laptop", "to_id": "buddy"},
                    {"from_id": "buddy", "to_id": "setup"},
                    {"from_id": "setup", "to_id": "pr"},
                    {"from_id": "pr", "to_id": "review"},
                ],
            },
        ),
        (
            "03-long-chain",
            "spec",
            {
                "title": "Change advisory flow",
                "actors": ["Engineer", "CAB", "Release"],
                "steps": [
                    {"id": "s1", "label": "Draft RFC", "lane": "Engineer"},
                    {"id": "s2", "label": "Impact analysis", "lane": "Engineer"},
                    {"id": "s3", "label": "Submit to CAB", "lane": "CAB"},
                    {"id": "s4", "label": "Risk review", "lane": "CAB"},
                    {"id": "s5", "label": "Approve window", "lane": "CAB"},
                    {"id": "s6", "label": "Schedule", "lane": "Release"},
                    {"id": "s7", "label": "Execute", "lane": "Release"},
                    {"id": "s8", "label": "Verify", "lane": "Engineer"},
                ],
                "connections": [{"from_id": f"s{i}", "to_id": f"s{i + 1}"} for i in range(1, 8)],
            },
        ),
        (
            "04-long-labels",
            "spec",
            {
                "title": "Long step labels",
                "actors": ["Requesting team", "Platform"],
                "steps": [
                    {
                        "id": "a",
                        "label": "Submit capacity increase request",
                        "lane": "Requesting team",
                    },
                    {"id": "b", "label": "Validate quota against budget", "lane": "Platform"},
                ],
                "connections": [{"from_id": "a", "to_id": "b"}],
            },
        ),
    ],
    "data_flow": [
        (
            "01-minimal",
            "spec",
            {"steps": [{"label": "Extract"}, {"label": "Load"}]},
        ),
        (
            "02-elt",
            "spec",
            {
                "title": "ELT pipeline ownership",
                "steps": [
                    {"label": "Extract", "role": "Data Eng", "note": "Fivetran"},
                    {"label": "Load", "role": "Data Eng", "note": "Snowflake"},
                    {"label": "Transform", "role": "Analytics Eng", "note": "dbt", "focal": True},
                    {"label": "Publish", "role": "Analytics Eng", "note": "marts"},
                    {"label": "Consume", "role": "Analyst", "note": "Looker"},
                ],
            },
        ),
        (
            "03-no-roles",
            "spec",
            {
                "steps": [
                    {"label": "Capture"},
                    {"label": "Validate"},
                    {"label": "Enrich"},
                    {"label": "Store"},
                ]
            },
        ),
        (
            "04-long-notes",
            "spec",
            {
                "title": "Notes that overflow",
                "steps": [
                    {
                        "label": "Ingestion",
                        "role": "Platform Engineering",
                        "note": "Kafka Connect with schema registry validation",
                    },
                    {
                        "label": "Curation",
                        "role": "Analytics Engineering",
                        "note": "dbt incremental models with freshness tests",
                    },
                ],
            },
        ),
        (
            "05-long-step-labels",
            "spec",
            {
                "title": "Stage names that overflow",
                "steps": [
                    {"label": "Change data capture ingestion", "role": "Platform"},
                    {"label": "Deduplication and conformance", "role": "Analytics"},
                ],
            },
        ),
    ],
    # ------------------------------------------------------------------
    # Geometric
    # ------------------------------------------------------------------
    "timeline": [
        (
            "01-minimal",
            "spec",
            {"events": [{"label": "Kickoff"}, {"label": "Launch"}]},
        ),
        (
            "02-roadmap",
            "spec",
            {
                "title": "Platform roadmap",
                "events": [
                    {"label": "Design review", "when": "Jan", "note": "RFC signed off"},
                    {"label": "Alpha", "when": "Mar"},
                    {"label": "Beta", "when": "Jun", "note": "10 design partners"},
                    {"label": "GA", "when": "Sep", "focal": True},
                ],
            },
        ),
        (
            "03-dense",
            "spec",
            {
                "title": "Incident chronology",
                "events": [
                    {"label": "Deploy v4.2", "when": "09:14"},
                    {"label": "Error rate spike", "when": "09:21"},
                    {"label": "Alert fires", "when": "09:23"},
                    {"label": "On-call ack", "when": "09:25"},
                    {"label": "Rollback started", "when": "09:31", "focal": True},
                    {"label": "Recovery", "when": "09:38"},
                    {"label": "All clear", "when": "09:52"},
                ],
            },
        ),
        (
            "04-long-labels",
            "spec",
            {
                "events": [
                    {
                        "label": "Migration cutover window opens",
                        "when": "Week 12",
                        "note": "read-only mode for 4 hours",
                    },
                    {"label": "Legacy decommission", "when": "Week 16"},
                    {"label": "Contract termination", "when": "Week 20"},
                ]
            },
        ),
        (
            "05-very-long-labels",
            "spec",
            {
                "events": [
                    {"label": "Regional failover rehearsal completed"},
                    {"label": "Primary datacentre decommissioned"},
                ]
            },
        ),
    ],
    "gantt": [
        (
            "01-minimal",
            "spec",
            {"tasks": [{"label": "Spike", "start": 0, "end": 2}]},
        ),
        (
            "02-quarter",
            "spec",
            {
                "title": "Q3 delivery plan",
                "unit_label": "Wk",
                "tick_every": 2,
                "marker": 6,
                "tasks": [
                    {"label": "Discovery", "start": 0, "end": 3, "phase": "Shape"},
                    {"label": "Design review", "start": 2, "end": 4, "phase": "Shape"},
                    {"label": "Backend", "start": 4, "end": 10, "phase": "Build", "focal": True},
                    {"label": "Frontend", "start": 6, "end": 11, "phase": "Build"},
                    {"label": "Hardening", "start": 10, "end": 12, "phase": "Ship"},
                    {"label": "Launch", "start": 12, "end": 13, "phase": "Ship"},
                ],
            },
        ),
        (
            "03-at-budget",
            "spec",
            {
                "title": "Twelve parallel tracks",
                "unit_label": "Sprint",
                "tick_every": 3,
                "tasks": [
                    {
                        "label": f"Workstream {i}",
                        "start": i - 1,
                        "end": i + 3,
                        "phase": "Phase A" if i <= 6 else "Phase B",
                    }
                    for i in range(1, 13)
                ],
            },
        ),
        (
            "04-fractional",
            "spec",
            {
                "title": "Half-week granularity",
                "unit_label": "Wk",
                "tasks": [
                    {"label": "Prep", "start": 0, "end": 0.5},
                    {"label": "Dual write", "start": 0.5, "end": 2.5, "focal": True},
                    {"label": "Backfill", "start": 1.5, "end": 4},
                    {"label": "Cutover", "start": 4, "end": 4.5},
                ],
            },
        ),
    ],
    "quadrant": [
        (
            "01-minimal",
            "spec",
            {
                "x_axis": {"label": "Cost"},
                "y_axis": {"label": "Value"},
                "items": [
                    {"label": "Option A", "x": 0.3, "y": 0.7},
                    {"label": "Option B", "x": 0.8, "y": 0.4},
                ],
            },
        ),
        (
            "02-consultant-2x2",
            "spec",
            {
                "title": "Build vs buy",
                "x_axis": {"label": "Differentiation", "low": "Commodity", "high": "Core"},
                "y_axis": {"label": "Maturity of vendors", "low": "Immature", "high": "Mature"},
                "quadrant_labels": ["Buy", "Partner", "Ignore", "Build"],
                "items": [
                    {"label": "Auth", "x": 0.2, "y": 0.85},
                    {"label": "Billing", "x": 0.35, "y": 0.7},
                    {"label": "Recommendations", "x": 0.85, "y": 0.25, "focal": True},
                    {"label": "Observability", "x": 0.25, "y": 0.6},
                ],
            },
        ),
        (
            "03-corners",
            "spec",
            {
                "title": "Extremes at the boundary",
                "x_axis": {"label": "Effort", "low": "0", "high": "1"},
                "y_axis": {"label": "Impact", "low": "0", "high": "1"},
                "items": [
                    {"label": "Bottom left", "x": 0.0, "y": 0.0},
                    {"label": "Top left", "x": 0.0, "y": 1.0},
                    {"label": "Bottom right", "x": 1.0, "y": 0.0},
                    {"label": "Top right", "x": 1.0, "y": 1.0},
                    {"label": "Dead centre", "x": 0.5, "y": 0.5},
                ],
            },
        ),
        (
            "04-crowded",
            "spec",
            {
                "title": "Ten services scored",
                "x_axis": {"label": "Migration effort"},
                "y_axis": {"label": "Business risk"},
                "items": [
                    {"label": f"svc-{i}", "x": (i * 0.09) % 1.0, "y": (i * 0.17) % 1.0}
                    for i in range(1, 11)
                ],
            },
        ),
    ],
    "pyramid": [
        (
            "01-minimal",
            "spec",
            {"tiers": [{"label": "Few"}, {"label": "Many"}]},
        ),
        (
            "02-maturity",
            "spec",
            {
                "title": "Observability maturity",
                "tiers": [
                    {"label": "Predictive", "note": "anomaly detection"},
                    {"label": "Proactive", "note": "SLOs + error budgets"},
                    {"label": "Reactive", "note": "alerting"},
                    {"label": "Foundational", "note": "logs + metrics", "focal": True},
                ],
            },
        ),
        (
            "03-funnel",
            "spec",
            {
                "title": "Signup conversion",
                "mode": "funnel",
                "tiers": [
                    {"label": "Visited", "value": 48000},
                    {"label": "Started signup", "value": 9200},
                    {"label": "Verified email", "value": 5100},
                    {"label": "Completed setup", "value": 2400, "focal": True},
                    {"label": "Activated", "value": 900},
                ],
            },
        ),
        (
            "04-six-tiers",
            "spec",
            {
                "title": "Deep hierarchy",
                "tiers": [{"label": f"Level {i}"} for i in range(1, 7)],
            },
        ),
    ],
    "venn": [
        (
            "01-two-sets",
            "spec",
            {
                "sets": [{"label": "Batch"}, {"label": "Streaming"}],
                "intersections": [{"between": ["Batch", "Streaming"], "label": "Lambda arch"}],
            },
        ),
        (
            "02-three-sets",
            "spec",
            {
                "title": "Skills on the platform team",
                "sets": [
                    {"label": "Infra"},
                    {"label": "Data"},
                    {"label": "Security", "focal": True},
                ],
                "intersections": [
                    {"between": ["Infra", "Data"], "label": "Pipelines"},
                    {"between": ["Infra", "Security"], "label": "Hardening"},
                    {"between": ["Data", "Security"], "label": "PII controls"},
                    {"between": ["Infra", "Data", "Security"], "label": "Compliance"},
                ],
            },
        ),
        (
            "03-no-intersections",
            "spec",
            {
                "title": "Sets without labelled overlap",
                "sets": [{"label": "Read path"}, {"label": "Write path"}],
            },
        ),
        (
            "04-long-labels",
            "spec",
            {
                "sets": [
                    {"label": "Customer facing services"},
                    {"label": "Internal tooling"},
                    {"label": "Regulated workloads"},
                ],
                "intersections": [
                    {
                        "between": ["Customer facing services", "Regulated workloads"],
                        "label": "PCI scope",
                    }
                ],
            },
        ),
    ],
    "loop": [
        (
            "01-minimal",
            "spec",
            {"stations": [{"label": "Plan"}, {"label": "Do"}, {"label": "Check"}]},
        ),
        (
            "02-hub",
            "spec",
            {
                "title": "Developer experience flywheel",
                "hub": "Internal platform",
                "hub_note": "each stage feeds the platform's backlog",
                "stations": [
                    {"label": "Onboard"},
                    {"label": "Build"},
                    {"label": "Ship"},
                    {"label": "Operate", "focal": True},
                    {"label": "Learn"},
                ],
            },
        ),
        (
            "03-eight-stations",
            "spec",
            {
                "title": "Long cycle",
                "hub": "Shared context",
                "stations": [{"label": f"Stage {i}"} for i in range(1, 9)],
            },
        ),
        (
            "04-no-hub",
            "spec",
            {
                "title": "Pure cycle",
                "stations": [
                    {"label": "Detect"},
                    {"label": "Triage"},
                    {"label": "Fix"},
                    {"label": "Verify"},
                ],
            },
        ),
        (
            "05-long-labels",
            "spec",
            {
                "title": "Station names that overflow",
                "hub": "Shared configuration store",
                "stations": [
                    {"label": "Provision infrastructure"},
                    {"label": "Deploy application bundle"},
                    {"label": "Collect production telemetry"},
                ],
            },
        ),
    ],
    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------
    "bar": [
        (
            "01-single-series",
            "spec",
            {
                "title": "Open PRs by repo",
                "categories": ["api", "web", "infra"],
                "series": [{"name": "Open", "values": [12, 7, 3]}],
            },
        ),
        (
            "02-grouped",
            "spec",
            {
                "title": "Test suite runtime",
                "y_label": "seconds",
                "categories": ["unit", "integration", "e2e"],
                "series": [
                    {"name": "Before", "values": [42, 310, 890]},
                    {"name": "After", "values": [38, 120, 410], "focal": True},
                ],
            },
        ),
        (
            "03-negatives",
            "spec",
            {
                "title": "Month-over-month change",
                "y_label": "% change",
                "categories": ["latency", "errors", "cost", "throughput"],
                "series": [{"name": "Delta", "values": [-18, -42, 7, 23], "focal": True}],
            },
        ),
        (
            "04-many-categories",
            "spec",
            {
                "title": "Ten services",
                "categories": [f"svc-{i}" for i in range(1, 11)],
                "series": [
                    {"name": "p99 ms", "values": [120, 340, 90, 610, 220, 150, 470, 80, 260, 330]}
                ],
            },
        ),
    ],
    "line": [
        (
            "01-single",
            "spec",
            {
                "title": "Weekly deploys",
                "x_labels": ["W1", "W2", "W3", "W4"],
                "series": [{"name": "Deploys", "values": [4, 9, 14, 21]}],
            },
        ),
        (
            "02-multi",
            "spec",
            {
                "title": "Error budget burn",
                "x_label": "Week",
                "y_label": "% consumed",
                "x_labels": ["W1", "W2", "W3", "W4", "W5", "W6"],
                "series": [
                    {"name": "checkout", "values": [5, 12, 26, 48, 71, 94], "focal": True},
                    {"name": "search", "values": [3, 6, 9, 13, 16, 20]},
                    {"name": "auth", "values": [1, 2, 4, 5, 7, 8]},
                ],
            },
        ),
        (
            "03-at-cap",
            "spec",
            {
                "title": "Fifteen points, the maximum",
                "x_labels": [f"D{i}" for i in range(1, 16)],
                "series": [
                    {
                        "name": "latency",
                        "values": [
                            120,
                            118,
                            125,
                            130,
                            128,
                            140,
                            155,
                            149,
                            138,
                            132,
                            126,
                            121,
                            119,
                            115,
                            110,
                        ],
                    }
                ],
            },
        ),
        (
            "04-negatives",
            "spec",
            {
                "title": "Net capacity headroom",
                "y_label": "cores",
                "x_labels": ["Q1", "Q2", "Q3", "Q4"],
                "series": [{"name": "headroom", "values": [40, 12, -8, -30], "focal": True}],
            },
        ),
    ],
    "scatter": [
        (
            "01-minimal",
            "spec",
            {"points": [{"x": 1, "y": 2}, {"x": 4, "y": 8}, {"x": 6, "y": 5}]},
        ),
        (
            "02-grouped",
            "spec",
            {
                "title": "Build time vs test count",
                "x_label": "Tests (hundreds)",
                "y_label": "Build minutes",
                "points": [
                    {"x": 2, "y": 4, "group": "monorepo"},
                    {"x": 5, "y": 9, "group": "monorepo"},
                    {"x": 9, "y": 17, "group": "monorepo", "label": "web", "focal": True},
                    {"x": 1, "y": 2, "group": "polyrepo"},
                    {"x": 3, "y": 4, "group": "polyrepo"},
                    {"x": 6, "y": 7, "group": "polyrepo"},
                ],
            },
        ),
        (
            "03-dense",
            "spec",
            {
                "title": "Thirty samples",
                "points": [{"x": (i * 7) % 40, "y": (i * 13) % 55} for i in range(1, 31)],
            },
        ),
        (
            "04-negative-quadrants",
            "spec",
            {
                "title": "Change in cost vs change in latency",
                "x_label": "Δ cost (%)",
                "y_label": "Δ p99 (%)",
                "points": [
                    {"x": -20, "y": -35, "label": "caching", "focal": True},
                    {"x": 15, "y": -40},
                    {"x": -5, "y": 12},
                    {"x": 30, "y": 25},
                ],
            },
        ),
    ],
    # ------------------------------------------------------------------
    # Structural
    # ------------------------------------------------------------------
    "nested": [
        (
            "01-flat",
            "spec",
            {
                "root": {
                    "label": "Monolith",
                    "children": [{"label": "Billing"}, {"label": "Users"}],
                }
            },
        ),
        (
            "02-two-levels",
            "spec",
            {
                "title": "Service decomposition",
                "root": {
                    "label": "Retail platform",
                    "children": [
                        {
                            "label": "Storefront",
                            "children": [{"label": "Catalog"}, {"label": "Search"}],
                        },
                        {
                            "label": "Checkout",
                            "focal": True,
                            "children": [{"label": "Cart"}, {"label": "Payments"}],
                        },
                    ],
                },
            },
        ),
        (
            "03-deep",
            "spec",
            {
                "title": "Four levels of containment",
                "root": {
                    "label": "Organisation",
                    "children": [
                        {
                            "label": "Platform group",
                            "children": [
                                {
                                    "label": "Runtime team",
                                    "children": [
                                        {"label": "Kubernetes"},
                                        {"label": "Service mesh"},
                                    ],
                                }
                            ],
                        }
                    ],
                },
            },
        ),
        (
            "04-wide",
            "spec",
            {
                "title": "Seven siblings",
                "root": {
                    "label": "Bounded contexts",
                    "children": [{"label": f"Context {i}"} for i in range(1, 8)],
                },
            },
        ),
    ],
    "layers": [
        ("01-minimal", "spec", {"layers": [{"label": "App"}, {"label": "Database"}]}),
        (
            "02-osi-ish",
            "spec",
            {
                "title": "Request lifecycle",
                "layers": [
                    {"label": "Browser", "note": "React SPA"},
                    {"label": "CDN", "note": "static + edge cache"},
                    {"label": "Load balancer", "note": "TLS termination"},
                    {"label": "Application", "note": "12 services", "focal": True},
                    {"label": "Data", "note": "Postgres + Redis"},
                ],
            },
        ),
        (
            "03-nine-layers",
            "spec",
            {
                "title": "Past the budget on purpose",
                "layers": [{"label": f"Layer {i}"} for i in range(1, 10)],
            },
        ),
    ],
    "medallion": [
        (
            "01-two-tier",
            "spec",
            {"tiers": [{"label": "Raw"}, {"label": "Curated"}]},
        ),
        (
            "02-classic",
            "spec",
            {
                "title": "Lakehouse",
                "tiers": [
                    {
                        "label": "Bronze",
                        "description": "raw ingest",
                        "datasets": ["events", "cdc_orders"],
                    },
                    {
                        "label": "Silver",
                        "description": "conformed",
                        "datasets": ["orders", "customers", "sessions"],
                    },
                    {
                        "label": "Gold",
                        "description": "serving",
                        "datasets": ["revenue_daily"],
                        "focal": True,
                    },
                ],
            },
        ),
        (
            "03-five-tier",
            "spec",
            {
                "title": "Extended tiers",
                "tiers": [
                    {"label": "Landing", "datasets": ["files"]},
                    {"label": "Bronze", "datasets": ["raw_events"]},
                    {"label": "Silver", "datasets": ["clean_events"]},
                    {"label": "Gold", "datasets": ["marts"]},
                    {"label": "Platinum", "datasets": ["ml_features"], "focal": True},
                ],
            },
        ),
        (
            "04-no-datasets",
            "spec",
            {
                "tiers": [
                    {"label": "Bronze", "description": "immutable"},
                    {"label": "Silver", "description": "deduplicated"},
                    {"label": "Gold", "description": "aggregated"},
                ]
            },
        ),
        (
            "05-long-labels",
            "spec",
            {
                "title": "Tier names and datasets that overflow",
                "tiers": [
                    {
                        "label": "Bronze landing zone",
                        "description": "immutable append-only capture",
                        "datasets": ["salesforce_opportunity_history"],
                    },
                    {
                        "label": "Gold serving layer",
                        "description": "business ready aggregates",
                        "datasets": ["daily_revenue_by_region"],
                    },
                ],
            },
        ),
    ],
    "er": [
        (
            "01-two-entities",
            "spec",
            {
                "entities": [
                    {"name": "User", "fields": ["id PK", "email"]},
                    {"name": "Session", "fields": ["id PK", "user_id FK"]},
                ],
                "relationships": [
                    {"from_entity": "User", "to_entity": "Session", "cardinality": "1..*"}
                ],
            },
        ),
        (
            "02-commerce",
            "spec",
            {
                "title": "Order model",
                "entities": [
                    {"name": "Customer", "fields": ["id PK", "email", "tier"]},
                    {
                        "name": "Order",
                        "fields": ["id PK", "customer_id FK", "status", "total"],
                        "focal": True,
                    },
                    {"name": "OrderLine", "fields": ["id PK", "order_id FK", "sku", "qty"]},
                    {"name": "Product", "fields": ["sku PK", "name", "price"]},
                ],
                "relationships": [
                    {"from_entity": "Customer", "to_entity": "Order", "cardinality": "1..*"},
                    {"from_entity": "Order", "to_entity": "OrderLine", "cardinality": "1..*"},
                    {"from_entity": "Product", "to_entity": "OrderLine", "cardinality": "0..*"},
                ],
            },
        ),
        (
            "03-many-fields",
            "spec",
            {
                "title": "Wide table",
                "entities": [
                    {
                        "name": "Account",
                        "fields": [
                            "id PK",
                            "external_id",
                            "email",
                            "phone",
                            "country",
                            "created_at",
                            "updated_at",
                            "deleted_at",
                            "tier",
                            "status",
                        ],
                    },
                    {"name": "AuditLog", "fields": ["id PK", "account_id FK", "action", "at"]},
                ],
                "relationships": [
                    {"from_entity": "Account", "to_entity": "AuditLog", "cardinality": "1..*"}
                ],
            },
        ),
        (
            "04-no-fields",
            "spec",
            {
                "title": "Entities only",
                "entities": [
                    {"name": "Tenant"},
                    {"name": "Workspace"},
                    {"name": "Project"},
                ],
                "relationships": [
                    {"from_entity": "Tenant", "to_entity": "Workspace"},
                    {"from_entity": "Workspace", "to_entity": "Project"},
                ],
            },
        ),
    ],
    "high_level": [
        (
            "01-minimal",
            "spec",
            {"cluster_label": "VPC", "rows": [{"label": "Compute", "items": ["EC2"]}]},
        ),
        (
            "02-cluster",
            "spec",
            {
                "title": "Staging environment",
                "cluster_label": "EKS / eu-central-1",
                "rows": [
                    {"label": "Edge", "items": ["ALB", "WAF"]},
                    {"label": "Services", "items": ["api", "worker", "cron"], "focal": True},
                    {"label": "Data", "items": ["RDS", "ElastiCache"]},
                ],
            },
        ),
        (
            "03-uneven-rows",
            "spec",
            {
                "title": "Ragged row widths",
                "cluster_label": "Production",
                "rows": [
                    {"label": "Ingress", "items": ["nginx"]},
                    {"label": "Application", "items": ["a", "b", "c", "d", "e"]},
                    {"label": "Storage", "items": ["postgres", "s3"]},
                ],
            },
        ),
        (
            "04-long-item-names",
            "spec",
            {
                "title": "Item names wider than the cell",
                "cluster_label": "Shared services account",
                "rows": [
                    {"label": "Networking", "items": ["Transit gateway attachment"]},
                    {"label": "Identity", "items": ["Cross-account role broker"]},
                ],
            },
        ),
    ],
    "it_state": [
        (
            "01-one-group",
            "spec",
            {"groups": [{"label": "Finance", "items": [{"id": "erp", "label": "Legacy ERP"}]}]},
        ),
        (
            "02-departments",
            "spec",
            {
                "title": "Current state",
                "subtitle": "Pre-modernization",
                "groups": [
                    {
                        "label": "Sales",
                        "items": [
                            {"id": "crm", "label": "On-prem CRM"},
                            {"id": "quotes", "label": "Access database", "focal": True},
                        ],
                    },
                    {
                        "label": "Finance",
                        "items": [
                            {"id": "erp", "label": "SAP ECC"},
                            {"id": "sheets", "label": "Excel close process"},
                        ],
                    },
                    {
                        "label": "Ops",
                        "items": [
                            {"id": "wms", "label": "Legacy WMS"},
                            {"id": "edi", "label": "EDI gateway"},
                        ],
                    },
                ],
                "connections": [
                    {"from_id": "crm", "to_id": "erp", "label": "nightly"},
                    {"from_id": "erp", "to_id": "wms", "label": "batch"},
                ],
            },
        ),
        (
            "03-six-groups",
            "spec",
            {
                "title": "Two rows of zones",
                "columns": 3,
                "groups": [
                    {
                        "label": f"Domain {i}",
                        "items": [
                            {"id": f"d{i}a", "label": f"System {i}A"},
                            {"id": f"d{i}b", "label": f"System {i}B"},
                        ],
                    }
                    for i in range(1, 7)
                ],
            },
        ),
    ],
    "tree": [
        (
            "01-minimal",
            "spec",
            {
                "nodes": [
                    {"id": "r", "label": "Root"},
                    {"id": "a", "label": "Child", "parent": "r"},
                ]
            },
        ),
        (
            "02-module-tree",
            "spec",
            {
                "title": "Package layout",
                "nodes": [
                    {"id": "src", "label": "src/"},
                    {"id": "core", "label": "core/", "parent": "src"},
                    {"id": "engine", "label": "engine/", "parent": "src", "focal": True},
                    {"id": "export", "label": "export/", "parent": "src"},
                    {"id": "models", "label": "models.py", "parent": "core"},
                    {"id": "layout", "label": "layout.py", "parent": "engine"},
                    {"id": "sketch", "label": "sketch.py", "parent": "export"},
                ],
            },
        ),
        (
            "03-deep-chain",
            "spec",
            {
                "title": "Five levels",
                "nodes": [
                    {"id": "l1", "label": "Level 1"},
                    {"id": "l2", "label": "Level 2", "parent": "l1"},
                    {"id": "l3", "label": "Level 3", "parent": "l2"},
                    {"id": "l4", "label": "Level 4", "parent": "l3"},
                    {"id": "l5", "label": "Level 5", "parent": "l4"},
                ],
            },
        ),
        (
            "04-wide-fanout",
            "spec",
            {
                "title": "One parent, eight children",
                "nodes": [{"id": "root", "label": "Config"}]
                + [{"id": f"c{i}", "label": f"Source {i}", "parent": "root"} for i in range(1, 9)],
            },
        ),
    ],
    "org_chart": [
        (
            "01-minimal",
            "spec",
            {
                "people": [
                    {"id": "a", "name": "Lead", "role": "Manager"},
                    {"id": "b", "name": "Dev", "role": "Engineer", "reports_to": "a"},
                ]
            },
        ),
        (
            "02-engineering",
            "spec",
            {
                "title": "Engineering org",
                "people": [
                    {"id": "cto", "name": "Priya Raman", "role": "CTO"},
                    {"id": "eng", "name": "Marcus Webb", "role": "VP Eng", "reports_to": "cto"},
                    {
                        "id": "sec",
                        "name": "Lena Fischer",
                        "role": "Head of Security",
                        "reports_to": "cto",
                        "focal": True,
                    },
                    {"id": "plat", "name": "Platform", "role": "6 engineers", "reports_to": "eng"},
                    {
                        "id": "prod",
                        "name": "Product Eng",
                        "role": "9 engineers",
                        "reports_to": "eng",
                    },
                    {"id": "appsec", "name": "AppSec", "role": "2 engineers", "reports_to": "sec"},
                ],
            },
        ),
        (
            "03-no-roles",
            "spec",
            {
                "title": "Names only",
                "people": [
                    {"id": "a", "name": "Alex"},
                    {"id": "b", "name": "Blair", "reports_to": "a"},
                    {"id": "c", "name": "Casey", "reports_to": "a"},
                    {"id": "d", "name": "Devon", "reports_to": "b"},
                ],
            },
        ),
    ],
    "state": [
        (
            "01-minimal",
            "spec",
            {
                "states": [{"id": "a", "label": "Idle"}, {"id": "b", "label": "Running"}],
                "transitions": [{"from_id": "a", "to_id": "b", "label": "start"}],
            },
        ),
        (
            "02-job-lifecycle",
            "spec",
            {
                "title": "Batch job lifecycle",
                "states": [
                    {"id": "s", "label": "start", "kind": "start"},
                    {"id": "queued", "label": "Queued"},
                    {"id": "running", "label": "Running", "focal": True},
                    {"id": "retry", "label": "Retrying"},
                    {"id": "failed", "label": "Failed"},
                    {"id": "done", "label": "Succeeded"},
                    {"id": "e", "label": "end", "kind": "end"},
                ],
                "transitions": [
                    {"from_id": "s", "to_id": "queued"},
                    {"from_id": "queued", "to_id": "running", "label": "worker picks up"},
                    {"from_id": "running", "to_id": "done", "label": "exit 0"},
                    {"from_id": "running", "to_id": "retry", "label": "exit != 0"},
                    {"from_id": "retry", "to_id": "running", "label": "attempt < 3"},
                    {"from_id": "retry", "to_id": "failed", "label": "attempt = 3"},
                    {"from_id": "done", "to_id": "e"},
                    {"from_id": "failed", "to_id": "e"},
                ],
            },
        ),
        (
            "03-self-loops",
            "spec",
            {
                "title": "Polling machine",
                "states": [
                    {"id": "idle", "label": "Idle"},
                    {"id": "poll", "label": "Polling"},
                    {"id": "work", "label": "Working"},
                ],
                "transitions": [
                    {"from_id": "idle", "to_id": "poll"},
                    {"from_id": "poll", "to_id": "poll", "label": "empty"},
                    {"from_id": "poll", "to_id": "work", "label": "message"},
                    {"from_id": "work", "to_id": "work", "label": "batch continues"},
                    {"from_id": "work", "to_id": "idle", "label": "drained"},
                ],
            },
        ),
        (
            "04-no-markers",
            "spec",
            {
                "title": "Circuit breaker",
                "states": [
                    {"id": "closed", "label": "Closed"},
                    {"id": "open", "label": "Open", "focal": True},
                    {"id": "half", "label": "Half-open"},
                ],
                "transitions": [
                    {"from_id": "closed", "to_id": "open", "label": "threshold exceeded"},
                    {"from_id": "open", "to_id": "half", "label": "cooldown elapsed"},
                    {"from_id": "half", "to_id": "closed", "label": "probe succeeds"},
                    {"from_id": "half", "to_id": "open", "label": "probe fails"},
                ],
            },
        ),
    ],
}


def case_count() -> int:
    return sum(len(v) for v in STRESS_CASES.values())
