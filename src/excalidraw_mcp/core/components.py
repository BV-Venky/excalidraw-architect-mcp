"""Architecture-aware component library.

Maps technology names to distinctive visual styles so diagrams are instantly
readable -- a Kafka node looks different from a PostgreSQL node at a glance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from excalidraw_mcp.core.models import ShapeType


@dataclass(frozen=True)
class ComponentStyle:
    """Visual style applied to a diagram node based on its technology/role."""

    category: str
    badge: str
    background_color: str
    stroke_color: str
    shape: ShapeType = ShapeType.RECTANGLE
    aliases: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Component registry
# ---------------------------------------------------------------------------

_COMPONENTS: dict[str, ComponentStyle] = {}


def _register(*names: str, **kwargs) -> ComponentStyle:
    style = ComponentStyle(aliases=names, **kwargs)
    for name in names:
        _COMPONENTS[name.lower()] = style
    return style


# -- Databases ---------------------------------------------------------------
_register(
    "postgresql",
    "postgres",
    "pg",
    category="Database",
    badge="DB",
    background_color="#dbe4ff",
    stroke_color="#364fc7",
    shape=ShapeType.RECTANGLE,
)
_register(
    "mysql",
    "mariadb",
    category="Database",
    badge="DB",
    background_color="#d0ebff",
    stroke_color="#1864ab",
    shape=ShapeType.RECTANGLE,
)
_register(
    "mongodb",
    "mongo",
    category="Database",
    badge="DB",
    background_color="#d3f9d8",
    stroke_color="#2b8a3e",
    shape=ShapeType.RECTANGLE,
)
_register(
    "dynamodb",
    "dynamo",
    category="Database",
    badge="DB",
    background_color="#fff3bf",
    stroke_color="#e67700",
    shape=ShapeType.RECTANGLE,
)
_register(
    "clickhouse",
    category="Database",
    badge="DB",
    background_color="#fff9db",
    stroke_color="#f08c00",
    shape=ShapeType.RECTANGLE,
)
_register(
    "cassandra",
    category="Database",
    badge="DB",
    background_color="#e5dbff",
    stroke_color="#6741d9",
    shape=ShapeType.RECTANGLE,
)
_register(
    "sqlite",
    category="Database",
    badge="DB",
    background_color="#e7f5ff",
    stroke_color="#1971c2",
    shape=ShapeType.RECTANGLE,
)
_register(
    "elasticsearch",
    "elastic",
    "opensearch",
    category="Database",
    badge="Search",
    background_color="#c3fae8",
    stroke_color="#087f5b",
    shape=ShapeType.RECTANGLE,
)

# -- Message Queues ----------------------------------------------------------
_register(
    "kafka",
    category="Message Queue",
    badge="Queue",
    background_color="#ffe8cc",
    stroke_color="#d9480f",
    shape=ShapeType.RECTANGLE,
)
_register(
    "rabbitmq",
    "rabbit",
    category="Message Queue",
    badge="Queue",
    background_color="#fff4e6",
    stroke_color="#e8590c",
    shape=ShapeType.RECTANGLE,
)
_register(
    "sqs",
    category="Message Queue",
    badge="Queue",
    background_color="#fff4e6",
    stroke_color="#e8590c",
    shape=ShapeType.RECTANGLE,
)
_register(
    "nats",
    category="Message Queue",
    badge="Queue",
    background_color="#ffe3e3",
    stroke_color="#c92a2a",
    shape=ShapeType.RECTANGLE,
)
_register(
    "pulsar",
    category="Message Queue",
    badge="Queue",
    background_color="#ffe8cc",
    stroke_color="#d9480f",
    shape=ShapeType.RECTANGLE,
)

# -- Caches ------------------------------------------------------------------
_register(
    "redis",
    category="Cache",
    badge="Cache",
    background_color="#ffe3e3",
    stroke_color="#c92a2a",
    shape=ShapeType.RECTANGLE,
)
_register(
    "memcached",
    "memcache",
    category="Cache",
    badge="Cache",
    background_color="#ffc9c9",
    stroke_color="#e03131",
    shape=ShapeType.RECTANGLE,
)
_register(
    "varnish",
    category="Cache",
    badge="Cache",
    background_color="#ffe3e3",
    stroke_color="#c92a2a",
    shape=ShapeType.RECTANGLE,
)

# -- Load Balancers ----------------------------------------------------------
_register(
    "nginx",
    category="Load Balancer",
    badge="LB",
    background_color="#e5dbff",
    stroke_color="#6741d9",
    shape=ShapeType.RECTANGLE,
)
_register(
    "haproxy",
    category="Load Balancer",
    badge="LB",
    background_color="#d0bfff",
    stroke_color="#5f3dc4",
    shape=ShapeType.RECTANGLE,
)
_register(
    "alb",
    "elb",
    "load balancer",
    category="Load Balancer",
    badge="LB",
    background_color="#e5dbff",
    stroke_color="#6741d9",
    shape=ShapeType.RECTANGLE,
)
_register(
    "envoy",
    category="Load Balancer",
    badge="Proxy",
    background_color="#d0bfff",
    stroke_color="#5f3dc4",
    shape=ShapeType.RECTANGLE,
)
_register(
    "traefik",
    category="Load Balancer",
    badge="Proxy",
    background_color="#e5dbff",
    stroke_color="#6741d9",
    shape=ShapeType.RECTANGLE,
)

# -- Compute / Services ------------------------------------------------------
_register(
    "lambda",
    "aws lambda",
    category="Compute",
    badge="FaaS",
    background_color="#c3fae8",
    stroke_color="#087f5b",
    shape=ShapeType.RECTANGLE,
)
_register(
    "ecs",
    "fargate",
    category="Compute",
    badge="Container",
    background_color="#c3fae8",
    stroke_color="#087f5b",
    shape=ShapeType.RECTANGLE,
)
_register(
    "kubernetes",
    "k8s",
    category="Compute",
    badge="K8s",
    background_color="#d0ebff",
    stroke_color="#1864ab",
    shape=ShapeType.RECTANGLE,
)
_register(
    "docker",
    category="Compute",
    badge="Container",
    background_color="#d0ebff",
    stroke_color="#1864ab",
    shape=ShapeType.RECTANGLE,
)
_register(
    "ec2",
    category="Compute",
    badge="VM",
    background_color="#c3fae8",
    stroke_color="#087f5b",
    shape=ShapeType.RECTANGLE,
)

# -- Storage -----------------------------------------------------------------
_register(
    "s3",
    "aws s3",
    category="Storage",
    badge="Storage",
    background_color="#d3f9d8",
    stroke_color="#2b8a3e",
    shape=ShapeType.RECTANGLE,
)
_register(
    "gcs",
    "google cloud storage",
    category="Storage",
    badge="Storage",
    background_color="#d3f9d8",
    stroke_color="#2b8a3e",
    shape=ShapeType.RECTANGLE,
)
_register(
    "minio",
    category="Storage",
    badge="Storage",
    background_color="#d3f9d8",
    stroke_color="#2b8a3e",
    shape=ShapeType.RECTANGLE,
)

# -- API / Gateway -----------------------------------------------------------
_register(
    "api gateway",
    "apigateway",
    "api gw",
    category="API",
    badge="API",
    background_color="#edf2ff",
    stroke_color="#3b5bdb",
    shape=ShapeType.RECTANGLE,
)
_register(
    "graphql",
    category="API",
    badge="GraphQL",
    background_color="#f3d9fa",
    stroke_color="#9c36b5",
    shape=ShapeType.RECTANGLE,
)
_register(
    "rest",
    "rest api",
    category="API",
    badge="REST",
    background_color="#edf2ff",
    stroke_color="#3b5bdb",
    shape=ShapeType.RECTANGLE,
)
_register(
    "grpc",
    category="API",
    badge="gRPC",
    background_color="#edf2ff",
    stroke_color="#3b5bdb",
    shape=ShapeType.RECTANGLE,
)

# -- CDN / Edge --------------------------------------------------------------
_register(
    "cloudfront",
    "cdn",
    category="CDN",
    badge="CDN",
    background_color="#c5f6fa",
    stroke_color="#0b7285",
    shape=ShapeType.RECTANGLE,
)
_register(
    "cloudflare",
    category="CDN",
    badge="CDN",
    background_color="#c5f6fa",
    stroke_color="#0b7285",
    shape=ShapeType.RECTANGLE,
)

# -- Monitoring / Observability ----------------------------------------------
_register(
    "prometheus",
    category="Monitoring",
    badge="Monitor",
    background_color="#fff9db",
    stroke_color="#e67700",
    shape=ShapeType.RECTANGLE,
)
_register(
    "grafana",
    category="Monitoring",
    badge="Monitor",
    background_color="#fff3bf",
    stroke_color="#f08c00",
    shape=ShapeType.RECTANGLE,
)
_register(
    "datadog",
    category="Monitoring",
    badge="Monitor",
    background_color="#e5dbff",
    stroke_color="#6741d9",
    shape=ShapeType.RECTANGLE,
)
_register(
    "jaeger",
    category="Monitoring",
    badge="Tracing",
    background_color="#fff9db",
    stroke_color="#e67700",
    shape=ShapeType.RECTANGLE,
)

# -- Clients -----------------------------------------------------------------
_register(
    "browser",
    "web",
    "frontend",
    category="Client",
    badge="",
    background_color="#f1f3f5",
    stroke_color="#495057",
    shape=ShapeType.RECTANGLE,
)
_register(
    "mobile",
    "ios",
    "android",
    category="Client",
    badge="",
    background_color="#f1f3f5",
    stroke_color="#495057",
    shape=ShapeType.RECTANGLE,
)
_register(
    "desktop",
    category="Client",
    badge="",
    background_color="#f1f3f5",
    stroke_color="#495057",
    shape=ShapeType.RECTANGLE,
)
_register(
    "user",
    "client",
    category="Client",
    badge="",
    background_color="#f8f9fa",
    stroke_color="#495057",
    shape=ShapeType.RECTANGLE,
)

# -- Generic service (fallback for "service" keyword) -----------------------
_register(
    "service",
    "microservice",
    category="Service",
    badge="",
    background_color="#e7f5ff",
    stroke_color="#1971c2",
    shape=ShapeType.RECTANGLE,
)


# ---------------------------------------------------------------------------
# Default style (for nodes that don't match any component)
# ---------------------------------------------------------------------------

DEFAULT_STYLE = ComponentStyle(
    category="",
    badge="",
    background_color="#f8f9fa",
    stroke_color="#495057",
    shape=ShapeType.RECTANGLE,
)


# ---------------------------------------------------------------------------
# Lookup / detection
# ---------------------------------------------------------------------------

_WORD_BOUNDARY = re.compile(r"[^a-z0-9]+")


def _normalize(text: str) -> list[str]:
    """Split text into lowercase tokens for matching."""
    return _WORD_BOUNDARY.split(text.lower().strip())


def detect_component(label: str, explicit_type: str | None = None) -> ComponentStyle:
    """Return the best matching ComponentStyle for a node label.

    Priority:
      1. Explicit component_type (exact match)
      2. Exact token match against the label
      3. Substring match against the label
      4. DEFAULT_STYLE
    """
    if explicit_type:
        key = explicit_type.lower().strip()
        if key in _COMPONENTS:
            return _COMPONENTS[key]

    label_lower = label.lower()
    tokens = _normalize(label)

    for token in tokens:
        if token in _COMPONENTS:
            return _COMPONENTS[token]

    for key, style in _COMPONENTS.items():
        if key in label_lower:
            return style

    return DEFAULT_STYLE


def list_components() -> dict[str, list[str]]:
    """Return all registered components grouped by category."""
    by_category: dict[str, list[str]] = {}
    seen: set[int] = set()
    for name, style in _COMPONENTS.items():
        if id(style) in seen:
            continue
        seen.add(id(style))
        by_category.setdefault(style.category, []).append(name)
    return by_category
