"""Build the Amazon-like demo via the real MCP tool layer.

Generates two associated artifacts in demo/tmp/:
  - architecture.md          (the knowledge graph — source of truth)
  - amazon-architecture.excalidraw  (a diagram rendered FROM that graph)

Run:  uv run python demo/build_amazon_demo.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from excalidraw_mcp import server

HERE = Path(__file__).resolve().parent
TMP = HERE / "tmp"
GRAPH = str(TMP / "architecture.md")
DIAGRAM = str(TMP / "amazon-architecture.excalidraw")


async def call(name: str, args: dict) -> str:
    res = await server.mcp.call_tool(name, args)
    content = getattr(res, "content", None)
    if isinstance(content, list) and content:
        return getattr(content[0], "text", str(content[0]))
    return str(getattr(res, "data", res))


# (id, label, component_type, domain, owner, description)
SERVICES = [
    ("web-app", "Storefront Web App", "react", "client", "@web", "Customer-facing storefront"),
    ("api-gateway", "API Gateway", "nginx", "edge", "@platform", "Edge routing + auth"),
    ("user-service", "User Service", "service", "accounts", "@accounts", "Profiles & sessions"),
    ("user-db", "User DB", "postgresql", "accounts", "@accounts", "Users, addresses"),
    ("catalog-service", "Catalog Service", "service", "catalog", "@catalog", "Products & pricing"),
    ("catalog-db", "Catalog DB", "postgresql", "catalog", "@catalog", "Product records"),
    ("search", "Search", "elasticsearch", "catalog", "@catalog", "Product search index"),
    ("cart-service", "Cart Service", "service", "shopping", "@shopping", "Shopping carts"),
    ("cart-cache", "Cart Cache", "redis", "shopping", "@shopping", "Hot cart state"),
    ("order-service", "Order Service", "service", "orders", "@orders", "Checkout & orders"),
    ("order-db", "Order DB", "postgresql", "orders", "@orders", "Order records"),
    ("inventory-service", "Inventory Service", "service", "inventory", "@inventory", "Stock levels"),
    ("inventory-db", "Inventory DB", "postgresql", "inventory", "@inventory", "Stock counts"),
    ("payment-service", "Payment Service", "service", "payments", "@payments", "Charges & refunds"),
    ("kafka", "Event Bus", "kafka", "platform", "@platform", "Async event backbone"),
    ("notification-service", "Notification Service", "service", "platform", "@platform",
     "Emails & push"),
]

# (from, to, label, style)
LINKS = [
    ("web-app", "api-gateway", "HTTPS", "solid"),
    ("api-gateway", "user-service", "REST", "solid"),
    ("api-gateway", "catalog-service", "REST", "solid"),
    ("api-gateway", "cart-service", "REST", "solid"),
    ("api-gateway", "order-service", "REST", "solid"),
    ("user-service", "user-db", "SQL", "solid"),
    ("catalog-service", "catalog-db", "SQL", "solid"),
    ("catalog-service", "search", "index", "dashed"),
    ("cart-service", "cart-cache", "Redis", "solid"),
    ("cart-service", "catalog-service", "price/stock", "solid"),
    ("order-service", "cart-service", "checkout", "solid"),
    ("order-service", "order-db", "SQL", "solid"),
    ("order-service", "inventory-service", "reserve", "solid"),
    # --- parallel edges: two communication modes between the same pair ---
    ("order-service", "payment-service", "REST /charge", "solid"),
    ("order-service", "payment-service", "Kafka payment.requested", "dashed"),
    # ---------------------------------------------------------------------
    ("inventory-service", "inventory-db", "SQL", "solid"),
    ("inventory-service", "kafka", "inventory.updated", "dashed"),
    ("payment-service", "kafka", "payment.settled", "dashed"),
    ("order-service", "kafka", "order.created", "dashed"),
    ("kafka", "notification-service", "order.* / payment.*", "dashed"),
]


async def main() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    print(await call("kg_init", {
        "graph_path": GRAPH,
        "title": "ShopZon — Amazon-like Commerce Platform",
        "direction": "LR",
        "overwrite": True,
    }))

    for sid, label, ctype, domain, owner, desc in SERVICES:
        await call("kg_add_service", {
            "id": sid, "label": label, "component_type": ctype,
            "domain": domain, "owner": owner, "description": desc, "graph_path": GRAPH,
        })
    print(f"Added {len(SERVICES)} services.")

    for frm, to, label, style in LINKS:
        msg = await call("kg_link", {
            "from_id": frm, "to_id": to, "label": label, "style": style, "graph_path": GRAPH,
        })
        if "parallel" in msg or "Error" in msg:
            print("  ", msg)
    print(f"Linked {len(LINKS)} dependencies.")

    print(await call("kg_render", {"output_path": DIAGRAM, "graph_path": GRAPH, "theme": "colorful"}))
    print(await call("kg_lint", {"check_owners": False, "graph_path": GRAPH}))


if __name__ == "__main__":
    asyncio.run(main())
