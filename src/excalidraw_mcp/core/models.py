"""Pydantic models for the diagram intermediate representation and Excalidraw output."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ShapeType(str, Enum):
    """Supported shape types for diagram nodes."""

    RECTANGLE = "rectangle"
    DIAMOND = "diamond"
    ELLIPSE = "ellipse"
    STADIUM = "stadium"
    PARALLELOGRAM = "parallelogram"
    CIRCLE = "circle"


class Direction(str, Enum):
    """Layout direction for the diagram."""

    TOP_DOWN = "TD"
    LEFT_RIGHT = "LR"
    BOTTOM_UP = "BT"
    RIGHT_LEFT = "RL"


class EdgeStyle(str, Enum):
    """Visual style for edges/arrows."""

    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    THICK = "thick"


class ThemeName(str, Enum):
    """Available color themes."""

    DEFAULT = "default"
    DARK = "dark"
    COLORFUL = "colorful"


# ---------------------------------------------------------------------------
# Diagram Graph (intermediate representation)
# ---------------------------------------------------------------------------


class Node(BaseModel):
    """A node in the diagram graph."""

    id: str
    label: str
    shape: ShapeType = ShapeType.RECTANGLE
    component_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    """A directed edge between two nodes."""

    from_id: str
    to_id: str
    label: str | None = None
    style: EdgeStyle = EdgeStyle.SOLID


class Subgraph(BaseModel):
    """A named group of nodes rendered as a bounding box."""

    id: str
    label: str
    node_ids: list[str] = Field(default_factory=list)


class DiagramGraph(BaseModel):
    """
    The intermediate representation shared across all tools.

    Produced by: create_diagram args, mermaid parser, or diagram state manager.
    Consumed by: layout engine -> excalidraw builder.
    """

    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    subgraphs: list[Subgraph] = Field(default_factory=list)
    direction: Direction = Direction.LEFT_RIGHT

    def node_by_id(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    @property
    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}


# ---------------------------------------------------------------------------
# Positioned elements (output of layout engine)
# ---------------------------------------------------------------------------


class PositionedNode(BaseModel):
    """A node with computed layout coordinates."""

    node: Node
    x: float
    y: float
    width: float
    height: float


class PositionedEdge(BaseModel):
    """An edge with routed waypoints."""

    edge: Edge
    points: list[tuple[float, float]] = Field(default_factory=list)


class LayoutResult(BaseModel):
    """Complete output of the layout engine."""

    nodes: list[PositionedNode] = Field(default_factory=list)
    edges: list[PositionedEdge] = Field(default_factory=list)
    subgraphs: list[Subgraph] = Field(default_factory=list)
    width: float = 0.0
    height: float = 0.0


# ---------------------------------------------------------------------------
# Diagram metadata (embedded in .excalidraw customData for stateful editing)
# ---------------------------------------------------------------------------


class NodeMetadata(BaseModel):
    """Metadata for a single node stored inside the .excalidraw file."""

    node_id: str
    label: str
    component_type: str | None = None
    element_ids: list[str] = Field(default_factory=list)


class ConnectionMetadata(BaseModel):
    """Metadata for a single connection stored inside the .excalidraw file."""

    from_id: str
    to_id: str
    label: str | None = None
    element_id: str | None = None


class DiagramMetadata(BaseModel):
    """
    Top-level metadata block embedded in appState for stateful editing.

    Stored at: .excalidraw -> appState -> customData -> excalidraw_mcp
    """

    version: int = 1
    direction: Direction = Direction.TOP_DOWN
    nodes: dict[str, NodeMetadata] = Field(default_factory=dict)
    connections: list[ConnectionMetadata] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Modification operations (for modify_diagram tool)
# ---------------------------------------------------------------------------


class AddNodeOp(BaseModel):
    """Operation to add a new node to an existing diagram."""

    op: str = "add_node"
    id: str
    label: str
    component_type: str | None = None
    shape: ShapeType = ShapeType.RECTANGLE
    near: str | None = None


class RemoveNodeOp(BaseModel):
    """Operation to remove a node and its connections."""

    op: str = "remove_node"
    id: str


class UpdateNodeOp(BaseModel):
    """Operation to update an existing node's properties."""

    op: str = "update_node"
    id: str
    label: str | None = None
    component_type: str | None = None


class AddConnectionOp(BaseModel):
    """Operation to add a new connection between existing nodes."""

    op: str = "add_connection"
    from_id: str
    to_id: str
    label: str | None = None


class RemoveConnectionOp(BaseModel):
    """Operation to remove a connection."""

    op: str = "remove_connection"
    from_id: str
    to_id: str


ModifyOperation = AddNodeOp | RemoveNodeOp | UpdateNodeOp | AddConnectionOp | RemoveConnectionOp
