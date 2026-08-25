"""Typed diagram families: spec models, layout strategies, and the registry.

Each diagram type owns a Pydantic spec and a layout function that turns that
spec into ``Drawable`` primitives. Types are independent -- adding one touches
only its own module plus a registry entry.
"""

from excalidraw_mcp.diagrams.registry import (
    DIAGRAM_TYPES,
    DiagramNotFoundError,
    build_typed_diagram,
    describe_type,
    list_types,
)

__all__ = [
    "DIAGRAM_TYPES",
    "DiagramNotFoundError",
    "build_typed_diagram",
    "describe_type",
    "list_types",
]
