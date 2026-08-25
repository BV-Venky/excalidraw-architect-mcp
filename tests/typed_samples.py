"""Realistic sample specs for every typed diagram.

Shared by the test suite (which renders all of them) and by the gallery
generator. Each sample is written the way the docs say to write one: a small
number of nodes, and one or two elements marked focal.
"""

from __future__ import annotations

from typing import Any

SAMPLES: dict[str, dict[str, Any]] = {
    # -- structural ---------------------------------------------------------
    "tree": {
        "title": "Config resolution order",
        "nodes": [
            {"id": "root", "label": "Effective config"},
            {"id": "cli", "label": "CLI flags", "parent": "root", "focal": True},
            {"id": "env", "label": "Environment", "parent": "root"},
            {"id": "file", "label": "config.toml", "parent": "root"},
            {"id": "proj", "label": "Project", "parent": "file"},
            {"id": "user", "label": "User home", "parent": "file"},
            {"id": "defaults", "label": "Built-in defaults", "parent": "root"},
        ],
    },
    "org_chart": {
        "title": "Platform group",
        "people": [
            {"id": "vp", "name": "Ada Whitfield", "role": "VP Engineering"},
            {"id": "plat", "name": "Ravi Menon", "role": "Platform Lead", "reports_to": "vp"},
            {"id": "data", "name": "Sofia Lindqvist", "role": "Data Lead", "reports_to": "vp"},
            {
                "id": "sre",
                "name": "On-call rotation",
                "role": "Shared",
                "reports_to": "plat",
                "focal": True,
            },
            {"id": "api", "name": "API team", "role": "4 engineers", "reports_to": "plat"},
            {"id": "pipe", "name": "Pipelines", "role": "3 engineers", "reports_to": "data"},
        ],
    },
    "state": {
        "title": "Order lifecycle",
        "states": [
            {"id": "s", "label": "start", "kind": "start"},
            {"id": "pending", "label": "Pending"},
            {"id": "paid", "label": "Paid", "focal": True},
            {"id": "shipped", "label": "Shipped"},
            {"id": "cancelled", "label": "Cancelled"},
            {"id": "e", "label": "end", "kind": "end"},
        ],
        "transitions": [
            {"from_id": "s", "to_id": "pending"},
            {"from_id": "pending", "to_id": "paid", "label": "payment ok"},
            {"from_id": "pending", "to_id": "cancelled", "label": "timeout"},
            {"from_id": "pending", "to_id": "pending", "label": "retry"},
            {"from_id": "paid", "to_id": "shipped", "label": "picked"},
            {"from_id": "shipped", "to_id": "e"},
            {"from_id": "cancelled", "to_id": "e"},
        ],
    },
    "nested": {
        "title": "Bounded contexts",
        "root": {
            "label": "Commerce platform",
            "children": [
                {
                    "label": "Ordering",
                    "focal": True,
                    "children": [{"label": "Cart"}, {"label": "Checkout"}, {"label": "Pricing"}],
                },
                {
                    "label": "Fulfilment",
                    "children": [{"label": "Inventory"}, {"label": "Shipping"}],
                },
                {"label": "Identity", "children": [{"label": "Accounts"}, {"label": "Sessions"}]},
            ],
        },
    },
    "layers": {
        "title": "Request path",
        "layers": [
            {"label": "Client", "note": "web + mobile"},
            {"label": "Edge / CDN", "note": "TLS termination"},
            {"label": "API Gateway", "focal": True, "note": "auth, rate limits"},
            {"label": "Services", "note": "12 deployments"},
            {"label": "Data stores", "note": "Postgres, Redis"},
        ],
    },
    "medallion": {
        "title": "Lakehouse tiers",
        "tiers": [
            {
                "label": "Bronze",
                "description": "raw, append-only",
                "datasets": ["events_raw", "cdc_orders", "clickstream"],
            },
            {
                "label": "Silver",
                "description": "cleaned, conformed",
                "datasets": ["orders", "customers", "sessions"],
            },
            {
                "label": "Gold",
                "description": "business-ready",
                "datasets": ["daily_revenue", "cohort_ltv"],
                "focal": True,
            },
        ],
    },
    "er": {
        "title": "Billing model",
        "entities": [
            {"name": "Customer", "fields": ["id  PK", "email", "created_at"]},
            {
                "name": "Subscription",
                "fields": ["id  PK", "customer_id  FK", "plan", "status"],
                "focal": True,
            },
            {"name": "Invoice", "fields": ["id  PK", "subscription_id  FK", "total", "issued_at"]},
            {"name": "Payment", "fields": ["id  PK", "invoice_id  FK", "amount", "method"]},
        ],
        "relationships": [
            {"from_entity": "Customer", "to_entity": "Subscription", "cardinality": "1..*"},
            {"from_entity": "Subscription", "to_entity": "Invoice", "cardinality": "1..*"},
            {"from_entity": "Invoice", "to_entity": "Payment", "cardinality": "0..*"},
        ],
    },
    "high_level": {
        "title": "Production cluster",
        "cluster_label": "Kubernetes / eu-west-1",
        "rows": [
            {"label": "Ingress", "items": ["ALB", "nginx"]},
            {"label": "Services", "items": ["api", "worker", "scheduler"], "focal": True},
            {"label": "Data", "items": ["Postgres", "Redis"]},
            {"label": "Observability", "items": ["Prometheus", "Loki"]},
        ],
    },
    "it_state": {
        "title": "Current-state landscape",
        "subtitle": "Before the 2026 modernization",
        "groups": [
            {
                "label": "Finance",
                "items": [
                    {"id": "sap", "label": "SAP ECC 6.0"},
                    {"id": "excel", "label": "Excel reconciliation", "focal": True},
                ],
            },
            {
                "label": "Operations",
                "items": [
                    {"id": "wms", "label": "Legacy WMS"},
                    {"id": "ftp", "label": "Nightly FTP drop"},
                ],
            },
            {
                "label": "Customer",
                "items": [
                    {"id": "crm", "label": "On-prem CRM"},
                    {"id": "portal", "label": "Customer portal"},
                ],
            },
        ],
        "connections": [
            {"from_id": "sap", "to_id": "wms", "label": "batch"},
            {"from_id": "ftp", "to_id": "crm", "label": "nightly"},
        ],
    },
    # -- flow ---------------------------------------------------------------
    "swimlane": {
        "title": "Pull request lifecycle",
        "lanes": ["Author", "CI", "Reviewer"],
        "steps": [
            {"id": "open", "label": "Open PR", "lane": "Author"},
            {"id": "checks", "label": "Run checks", "lane": "CI"},
            {"id": "review", "label": "Review", "lane": "Reviewer"},
            {"id": "fixes", "label": "Push fixes", "lane": "Author"},
            {"id": "approve", "label": "Approve", "lane": "Reviewer", "focal": True},
            {"id": "merge", "label": "Squash + merge", "lane": "CI"},
        ],
        "connections": [
            {"from_id": "open", "to_id": "checks"},
            {"from_id": "checks", "to_id": "review", "label": "green"},
            {"from_id": "review", "to_id": "fixes", "label": "changes requested"},
            {"from_id": "fixes", "to_id": "approve"},
            {"from_id": "approve", "to_id": "merge", "focal": True},
        ],
    },
    "process": {
        "title": "Incident response",
        "actors": ["Reporter", "On-call", "Comms"],
        "steps": [
            {"id": "page", "label": "File incident", "lane": "Reporter"},
            {"id": "ack", "label": "Acknowledge", "lane": "On-call"},
            {"id": "triage", "label": "Triage severity", "lane": "On-call", "focal": True},
            {"id": "status", "label": "Post status page", "lane": "Comms"},
            {"id": "fix", "label": "Mitigate", "lane": "On-call"},
            {"id": "resolve", "label": "Resolve + notify", "lane": "Comms"},
        ],
        "connections": [
            {"from_id": "page", "to_id": "ack"},
            {"from_id": "ack", "to_id": "triage"},
            {"from_id": "triage", "to_id": "status"},
            {"from_id": "status", "to_id": "fix"},
            {"from_id": "fix", "to_id": "resolve"},
        ],
    },
    "data_flow": {
        "title": "Analytics pipeline",
        "steps": [
            {"label": "Capture", "role": "Product", "note": "SDK events"},
            {"label": "Ingest", "role": "Data Eng", "note": "Kafka -> S3"},
            {"label": "Model", "role": "Analytics Eng", "note": "dbt", "focal": True},
            {"label": "Serve", "role": "Analyst", "note": "BI layer"},
        ],
    },
    "dp_integration": {
        "title": "Platform integration",
        "sources": [
            {"label": "Salesforce"},
            {"label": "Stripe"},
            {"label": "App events"},
            {"label": "Support desk"},
        ],
        "core": {
            "label": "Data Platform",
            "components": ["Ingestion", "Warehouse", "Semantic layer"],
        },
        "consumers": [
            {"label": "Executive BI", "focal": True},
            {"label": "Growth models"},
            {"label": "Reverse ETL"},
        ],
    },
    "sequence": {
        "title": "Checkout authorization",
        "actors": [
            {"id": "web", "label": "Web app"},
            {"id": "api", "label": "Orders API"},
            {"id": "psp", "label": "Payment PSP"},
            {"id": "db", "label": "Postgres"},
        ],
        "messages": [
            {"from_id": "web", "to_id": "api", "label": "POST /checkout"},
            {"from_id": "api", "to_id": "db", "label": "reserve stock"},
            {"from_id": "db", "to_id": "api", "label": "ok", "kind": "return"},
            {"from_id": "api", "to_id": "psp", "label": "authorize"},
            {"from_id": "psp", "to_id": "psp", "label": "risk check"},
            {
                "from_id": "psp",
                "to_id": "api",
                "label": "approved",
                "kind": "return",
                "focal": True,
            },
            {"from_id": "api", "to_id": "web", "label": "201 Created", "kind": "return"},
        ],
    },
    # -- geometric ----------------------------------------------------------
    "timeline": {
        "title": "Migration milestones",
        "events": [
            {"label": "Audit complete", "when": "Q1", "note": "42 services"},
            {"label": "Pilot service", "when": "Q2"},
            {"label": "Bulk migration", "when": "Q3", "focal": True, "note": "the risky one"},
            {"label": "Legacy shutdown", "when": "Q4"},
        ],
    },
    "quadrant": {
        "title": "Migration priorities",
        "x_axis": {"label": "Effort", "low": "Low", "high": "High"},
        "y_axis": {"label": "Impact", "low": "Low", "high": "High"},
        "quadrant_labels": ["Quick wins", "Big bets", "Ignore", "Money pits"],
        "items": [
            {"label": "Auth service", "x": 0.25, "y": 0.82, "focal": True},
            {"label": "Search", "x": 0.72, "y": 0.75},
            {"label": "Admin UI", "x": 0.22, "y": 0.24},
            {"label": "Legacy reports", "x": 0.80, "y": 0.20},
            {"label": "Billing", "x": 0.55, "y": 0.60},
        ],
    },
    "pyramid": {
        "title": "Test strategy",
        "tiers": [
            {"label": "E2E", "note": "~40 specs"},
            {"label": "Integration", "note": "~400 tests"},
            {"label": "Unit", "note": "~6,000 tests", "focal": True},
        ],
    },
    "venn": {
        "title": "Where the work sits",
        "sets": [
            {"label": "Platform"},
            {"label": "Product"},
            {"label": "Security", "focal": True},
        ],
        "intersections": [
            {"between": ["Platform", "Product"], "label": "SDKs"},
            {"between": ["Platform", "Security"], "label": "IAM"},
            {"between": ["Product", "Security"], "label": "Consent"},
            {"between": ["Platform", "Product", "Security"], "label": "Audit log"},
        ],
    },
    "loop": {
        "title": "Observability flywheel",
        "hub": "Telemetry store",
        "hub_note": "every stage reads from and writes back to it",
        "stations": [
            {"label": "Ship"},
            {"label": "Instrument"},
            {"label": "Observe"},
            {"label": "Diagnose", "focal": True},
            {"label": "Prioritise"},
        ],
    },
    "gantt": {
        "title": "Platform migration plan",
        "unit_label": "Wk",
        "tick_every": 2,
        "marker": 5,
        "tasks": [
            {"label": "Discovery", "start": 0, "end": 3, "phase": "Assess"},
            {"label": "Dependency audit", "start": 2, "end": 5, "phase": "Assess"},
            {"label": "Pilot service", "start": 5, "end": 9, "phase": "Build"},
            {"label": "Bulk migration", "start": 8, "end": 16, "phase": "Build", "focal": True},
            {"label": "Cutover", "start": 15, "end": 18, "phase": "Land"},
            {"label": "Decommission", "start": 17, "end": 20, "phase": "Land"},
        ],
    },
    # -- charts -------------------------------------------------------------
    "bar": {
        "title": "p99 latency by service",
        "y_label": "milliseconds",
        "categories": ["auth", "orders", "search", "billing", "media"],
        "series": [
            {"name": "Before", "values": [220, 480, 310, 190, 640]},
            {"name": "After", "values": [140, 210, 260, 150, 300], "focal": True},
        ],
    },
    "line": {
        "title": "Weekly build time",
        "x_label": "Week",
        "y_label": "minutes",
        "x_labels": ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"],
        "series": [
            {"name": "CI total", "values": [42, 44, 41, 38, 30, 26, 22, 19], "focal": True},
            {"name": "Test suite", "values": [28, 29, 27, 25, 20, 17, 15, 13]},
        ],
    },
    "scatter": {
        "title": "Service size vs. change failure rate",
        "x_label": "Lines of code (thousands)",
        "y_label": "Change failure rate (%)",
        "points": [
            {"x": 2.1, "y": 3.0, "group": "core"},
            {"x": 4.5, "y": 4.2, "group": "core"},
            {"x": 9.8, "y": 7.5, "group": "core"},
            {"x": 14.2, "y": 11.0, "group": "core", "label": "billing", "focal": True},
            {"x": 3.3, "y": 5.5, "group": "edge"},
            {"x": 6.0, "y": 6.1, "group": "edge"},
            {"x": 11.5, "y": 9.4, "group": "edge"},
            {"x": 1.2, "y": 2.0, "group": "edge"},
        ],
    },
}
