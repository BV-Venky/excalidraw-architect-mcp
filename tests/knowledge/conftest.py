"""Shared fixtures for knowledge-graph tests."""

from __future__ import annotations

import pytest

from excalidraw_mcp.core.models import Direction, EdgeStyle, ShapeType
from excalidraw_mcp.knowledge.models import Dependency, KnowledgeGraph, Service


@pytest.fixture
def sample_graph() -> KnowledgeGraph:
    """A small e-commerce-ish architecture with a domain and a data store.

    gateway -> orders -> orders-db
    gateway -> payments
    orders  -> payments
    """
    kg = KnowledgeGraph(title="Shop", direction=Direction.TOP_DOWN)
    kg.add_service(
        Service(id="gateway", label="API Gateway", component_type="nginx", domain="edge")
    )
    kg.add_service(
        Service(
            id="orders",
            label="Orders Service",
            component_type="service",
            domain="core",
            owner="@orders",
            tags=["http"],
            description="Order lifecycle",
        )
    )
    kg.add_service(
        Service(id="payments", label="Payments", component_type="service", domain="core")
    )
    kg.add_service(
        Service(
            id="orders-db",
            label="Orders DB",
            component_type="postgresql",
            domain="core",
            shape=ShapeType.ELLIPSE,
        )
    )
    kg.add_dependency(Dependency(from_id="gateway", to_id="orders", label="REST"))
    kg.add_dependency(Dependency(from_id="gateway", to_id="payments"))
    kg.add_dependency(Dependency(from_id="orders", to_id="orders-db", style=EdgeStyle.THICK))
    kg.add_dependency(Dependency(from_id="orders", to_id="payments", label="charge"))
    kg.set_domain_label("core", "Core Services")
    kg.set_domain_label("edge", "Edge")
    return kg
