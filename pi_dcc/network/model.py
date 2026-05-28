"""Piping network tree model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pi_dcc.config.schema import BlastGateConfig, PipeNodeConfig


@dataclass
class PipeNode:
    """A node in the piping network tree."""

    id: str
    pipe_diameter_inches: float
    blast_gate: Optional[BlastGateConfig] = None
    children: List["PipeNode"] = field(default_factory=list)
    parent: Optional["PipeNode"] = field(default=None, repr=False)

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0


class PipingNetwork:
    """Represents the piping network as a tree structure.

    The root node is the dust collector. Tools connect at leaf nodes.
    Blast gates can exist at any node (branch points or tool ports).
    """

    def __init__(self, root: PipeNode):
        self.root = root
        self._node_index: dict[str, PipeNode] = {}
        self._build_index(root)

    def _build_index(self, node: PipeNode) -> None:
        """Build a lookup index of all nodes by ID."""
        self._node_index[node.id] = node
        for child in node.children:
            child.parent = node
            self._build_index(child)

    def get_node(self, node_id: str) -> Optional["PipeNode"]:
        """Get a node by its ID."""
        return self._node_index.get(node_id)

    def get_all_gates(self) -> list[BlastGateConfig]:
        """Get all blast gates in the network."""
        gates = []
        self._collect_gates(self.root, gates)
        return gates

    def _collect_gates(self, node: PipeNode, gates: list[BlastGateConfig]) -> None:
        if node.blast_gate:
            gates.append(node.blast_gate)
        for child in node.children:
            self._collect_gates(child, gates)

    @classmethod
    def from_config(cls, config_node: PipeNodeConfig) -> PipingNetwork:
        """Build a PipingNetwork from a configuration node tree."""
        root = cls._build_node(config_node)
        return cls(root)

    @classmethod
    def _build_node(cls, config_node: PipeNodeConfig) -> PipeNode:
        """Recursively build PipeNode tree from config."""
        node = PipeNode(
            id=config_node.id,
            pipe_diameter_inches=config_node.pipe_diameter_inches,
            blast_gate=config_node.blast_gate,
        )
        for child_config in config_node.children:
            child = cls._build_node(child_config)
            child.parent = node
            node.children.append(child)
        return node
