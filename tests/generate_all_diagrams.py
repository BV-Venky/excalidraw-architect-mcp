"""Regenerate all sample diagrams using the layout engine directly."""

from __future__ import annotations

import os

from excalidraw_mcp.core.models import (
    DiagramGraph,
    Direction,
    Edge,
    Node,
)
from excalidraw_mcp.engine.layout import compute_layout
from excalidraw_mcp.engine.renderer import build_excalidraw_file, save_excalidraw

OUT = os.path.join(os.path.dirname(__file__), "sample_diagrams")


def _build(name: str, nodes: list[Node], edges: list[Edge],
           direction: Direction = Direction.LEFT_RIGHT,
           theme: str = "default") -> None:
    graph = DiagramGraph(nodes=nodes, edges=edges, direction=direction)
    layout = compute_layout(graph)
    doc = build_excalidraw_file(layout, theme_name=theme, direction=direction)
    path = save_excalidraw(doc, os.path.join(OUT, name))
    print(f"  -> {path}")


def diagram_01():
    nodes = [
        Node(id="browser", label="Browser", component_type="browser"),
        Node(id="cdn", label="CloudFront CDN", component_type="cloudfront"),
        Node(id="nginx", label="Nginx", component_type="nginx"),
        Node(id="gateway", label="API Gateway", component_type="api_gateway"),
        Node(id="auth", label="Auth Service"),
        Node(id="user", label="User Service"),
        Node(id="order", label="Order Service"),
        Node(id="pg", label="PostgreSQL", component_type="postgresql"),
        Node(id="redis", label="Redis Cache", component_type="redis"),
        Node(id="kafka", label="Kafka", component_type="kafka"),
        Node(id="s3", label="S3 Storage", component_type="s3"),
        Node(id="prom", label="Prometheus", component_type="prometheus"),
        Node(id="grafana", label="Grafana", component_type="grafana"),
    ]
    edges = [
        Edge(from_id="browser", to_id="cdn", label="HTTPS"),
        Edge(from_id="cdn", to_id="nginx", label="origin"),
        Edge(from_id="nginx", to_id="gateway", label="reverse proxy"),
        Edge(from_id="gateway", to_id="auth", label="authenticate"),
        Edge(from_id="gateway", to_id="user", label="user data"),
        Edge(from_id="gateway", to_id="order", label="orders"),
        Edge(from_id="auth", to_id="redis", label="sessions"),
        Edge(from_id="user", to_id="pg", label="query"),
        Edge(from_id="user", to_id="s3", label="avatars"),
        Edge(from_id="order", to_id="pg", label="query"),
        Edge(from_id="order", to_id="kafka", label="events"),
        Edge(from_id="prom", to_id="grafana", label="metrics"),
    ]
    _build("01_system_architecture.excalidraw", nodes, edges)


def diagram_02():
    nodes = [
        Node(id="client", label="Client App", component_type="browser"),
        Node(id="gateway", label="API Gateway", component_type="api_gateway"),
        Node(id="auth", label="Auth Service"),
        Node(id="jwt", label="JWT Validator"),
        Node(id="user_db", label="User Database", component_type="postgresql"),
        Node(id="cache", label="Token Cache", component_type="redis"),
        Node(id="protected", label="Protected Resource"),
    ]
    edges = [
        Edge(from_id="client", to_id="gateway", label="request + token"),
        Edge(from_id="gateway", to_id="auth", label="validate"),
        Edge(from_id="auth", to_id="jwt", label="verify JWT"),
        Edge(from_id="jwt", to_id="cache", label="check cache"),
        Edge(from_id="jwt", to_id="user_db", label="lookup user"),
        Edge(from_id="auth", to_id="protected", label="authorized"),
        Edge(from_id="cache", to_id="auth", label="cached result"),
    ]
    _build("02_auth_flow.excalidraw", nodes, edges)


def diagram_03():
    nodes = [
        Node(id="client", label="Mobile Client", component_type="mobile"),
        Node(id="lb", label="Load Balancer", component_type="nginx"),
        Node(id="gateway", label="API Gateway", component_type="api_gateway"),
        Node(id="svc_a", label="Product Service"),
        Node(id="svc_b", label="Cart Service"),
        Node(id="svc_c", label="Payment Service"),
        Node(id="db_a", label="Product DB", component_type="postgresql"),
        Node(id="db_b", label="Cart Store", component_type="redis"),
        Node(id="db_c", label="Payment DB", component_type="postgresql"),
        Node(id="kafka", label="Event Bus", component_type="kafka"),
    ]
    edges = [
        Edge(from_id="client", to_id="lb", label="HTTPS"),
        Edge(from_id="lb", to_id="gateway", label="route"),
        Edge(from_id="gateway", to_id="svc_a", label="products"),
        Edge(from_id="gateway", to_id="svc_b", label="cart"),
        Edge(from_id="gateway", to_id="svc_c", label="payments"),
        Edge(from_id="svc_a", to_id="db_a", label="query"),
        Edge(from_id="svc_b", to_id="db_b", label="read/write"),
        Edge(from_id="svc_c", to_id="db_c", label="transactions"),
        Edge(from_id="svc_b", to_id="kafka", label="cart events"),
        Edge(from_id="svc_c", to_id="kafka", label="payment events"),
    ]
    _build("03_microservices_dark.excalidraw", nodes, edges, theme="dark")


def diagram_05():
    nodes = [
        Node(id="client", label="Customer App", component_type="mobile"),
        Node(id="alb", label="ALB", component_type="alb"),
        Node(id="avail_svc", label="Availability\nService"),
        Node(id="order_svc", label="Order Service"),
        Node(id="fulfill_svc", label="Fulfillment\nService"),
        Node(id="notif_svc", label="Notification\nService"),
        Node(id="avail_cache", label="Redis\nAvailability Cache", component_type="redis"),
        Node(id="inventory_db", label="PostgreSQL\nInventory DB", component_type="postgresql"),
        Node(id="order_db", label="PostgreSQL\nOrder DB", component_type="postgresql"),
        Node(id="kafka", label="Kafka\nEvent Bus", component_type="kafka"),
        Node(id="cache_rebuild", label="Cache Rebuild\nWorker"),
        Node(id="prom", label="Prometheus", component_type="prometheus"),
        Node(id="grafana", label="Grafana", component_type="grafana"),
    ]
    edges = [
        Edge(from_id="client", to_id="alb", label="HTTPS"),
        Edge(from_id="alb", to_id="avail_svc", label="availability"),
        Edge(from_id="alb", to_id="order_svc", label="place order"),
        Edge(from_id="avail_svc", to_id="avail_cache", label="<100ms lookup"),
        Edge(from_id="order_svc", to_id="order_db", label="strong consistency"),
        Edge(from_id="order_svc", to_id="inventory_db", label="reserve stock"),
        Edge(from_id="order_svc", to_id="kafka", label="order events"),
        Edge(from_id="kafka", to_id="fulfill_svc", label="dispatch"),
        Edge(from_id="kafka", to_id="notif_svc", label="notify"),
        Edge(from_id="kafka", to_id="cache_rebuild", label="rebuild"),
        Edge(from_id="cache_rebuild", to_id="inventory_db", label="read inventory"),
        Edge(from_id="cache_rebuild", to_id="avail_cache", label="update cache"),
        Edge(from_id="prom", to_id="grafana", label="dashboards"),
    ]
    _build("05_local_delivery_service.excalidraw", nodes, edges)


def diagram_06():
    nodes = [
        Node(id="ide", label="AI IDE\n(Cursor / Antigravity)", component_type="client"),
        Node(id="server", label="server.py\nMCP Server", component_type="api_gateway"),
        Node(id="mermaid", label="Mermaid Parser"),
        Node(id="state", label="Diagram State\nManager"),
        Node(id="layout", label="Layout Engine\n(Sugiyama)"),
        Node(id="renderer", label="Excalidraw\nRenderer"),
        Node(id="grandalf", label="grandalf\nLayout Library"),
        Node(id="styling", label="Component Library\n& Themes"),
        Node(id="output", label=".excalidraw\nFile", component_type="storage"),
    ]
    edges = [
        Edge(from_id="ide", to_id="server", label="MCP protocol"),
        Edge(from_id="server", to_id="mermaid", label="Mermaid syntax"),
        Edge(from_id="server", to_id="state", label="modify operations"),
        Edge(from_id="server", to_id="layout", label="DiagramGraph"),
        Edge(from_id="layout", to_id="grandalf", label="Sugiyama"),
        Edge(from_id="layout", to_id="renderer", label="LayoutResult"),
        Edge(from_id="renderer", to_id="styling", label="styling lookup"),
        Edge(from_id="renderer", to_id="output", label="JSON output"),
        Edge(from_id="state", to_id="output", label="read metadata"),
    ]
    _build("06_repo_architecture.excalidraw", nodes, edges)


def diagram_07():
    nodes = [
        Node(id="start", label="LLM Invokes\nMCP Tool", component_type="client"),
        Node(id="parse", label="Parse Input\nnodes + connections"),
        Node(id="components", label="Auto-detect\nComponent Styles"),
        Node(id="sugiyama", label="Sugiyama Layout\nLayer Assignment"),
        Node(id="gaps", label="Adaptive Spacing\n+ Hub Stretching"),
        Node(id="routing", label="Edge Routing\n+ Obstacle Avoidance"),
        Node(id="build", label="Build Excalidraw\nShapes + Arrows"),
        Node(id="theme", label="Apply Theme\n+ Embed Metadata"),
        Node(id="save", label="Save .excalidraw\nFile", component_type="storage"),
    ]
    edges = [
        Edge(from_id="start", to_id="parse", label="tool params"),
        Edge(from_id="parse", to_id="components", label="DiagramGraph"),
        Edge(from_id="components", to_id="sugiyama", label="styled nodes"),
        Edge(from_id="sugiyama", to_id="gaps", label="raw positions"),
        Edge(from_id="gaps", to_id="routing", label="spaced layout"),
        Edge(from_id="routing", to_id="build", label="final layout"),
        Edge(from_id="build", to_id="theme", label="elements"),
        Edge(from_id="theme", to_id="save", label=".excalidraw JSON"),
    ]
    _build("07_logic_flow.excalidraw", nodes, edges)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in [
        ("01 System Architecture", diagram_01),
        ("02 Auth Flow", diagram_02),
        ("03 Microservices Dark", diagram_03),
        ("05 Local Delivery Service", diagram_05),
        ("06 Repo Architecture", diagram_06),
        ("07 Logic Flow", diagram_07),
    ]:
        print(f"Generating {name}...")
        fn()
    print("\nDone! All sample diagrams regenerated.")
