"""Pathfinding utilities for the piping network."""

from __future__ import annotations

from pi_dcc.config.schema import BlastGateConfig

from .model import PipeNode, PipingNetwork


def find_path_to_node(network: PipingNetwork, target_node_id: str) -> list[PipeNode]:
    """Find the path from the collector (root) to a specific node.

    Args:
        network: The piping network tree.
        target_node_id: ID of the target node.

    Returns:
        Ordered list of nodes from root to target (inclusive).

    Raises:
        ValueError: If the target node doesn't exist in the network.
    """
    target = network.get_node(target_node_id)
    if target is None:
        raise ValueError(f"Node '{target_node_id}' not found in network")

    # Walk up from target to root
    path = []
    current = target
    while current is not None:
        path.append(current)
        current = current.parent

    # Reverse to get root → target order
    path.reverse()
    return path


def get_required_gates(network: PipingNetwork, target_node_id: str) -> list[BlastGateConfig]:
    """Get all blast gates that must be open to reach a target node from the collector.

    Args:
        network: The piping network tree.
        target_node_id: ID of the target node (tool connection point).

    Returns:
        List of BlastGateConfig for gates on the path from collector to target.
    """
    path = find_path_to_node(network, target_node_id)
    return [node.blast_gate for node in path if node.blast_gate is not None]


def get_gates_for_tools(
    network: PipingNetwork, tool_node_ids: list[str]
) -> list[BlastGateConfig]:
    """Get the union of all blast gates needed for a set of active tools.

    Args:
        network: The piping network tree.
        tool_node_ids: List of node IDs where active tools are connected.

    Returns:
        Deduplicated list of blast gates that must be open.
    """
    seen_gate_ids: set[str] = set()
    gates: list[BlastGateConfig] = []

    for node_id in tool_node_ids:
        for gate in get_required_gates(network, node_id):
            if gate.id not in seen_gate_ids:
                seen_gate_ids.add(gate.id)
                gates.append(gate)

    return gates


def get_supplemental_gates(
    network: PipingNetwork,
    currently_required_gate_ids: set[str],
) -> list[BlastGateConfig]:
    """Get available supplemental gates that could be opened for additional airflow.

    Returns gates NOT currently required, ordered by proximity to collector (shallowest first).

    Args:
        network: The piping network tree.
        currently_required_gate_ids: Set of gate IDs already required by active tools.

    Returns:
        List of available supplemental gates, closest to collector first.
    """
    supplemental: list[tuple[int, BlastGateConfig]] = []
    _find_supplemental(network.root, 0, currently_required_gate_ids, supplemental)

    # Sort by depth (closest to collector first)
    supplemental.sort(key=lambda x: x[0])
    return [gate for _, gate in supplemental]


def _find_supplemental(
    node: PipeNode,
    depth: int,
    excluded_ids: set[str],
    result: list[tuple[int, BlastGateConfig]],
) -> None:
    """Recursively find gates not in the excluded set."""
    if node.blast_gate and node.blast_gate.id not in excluded_ids:
        result.append((depth, node.blast_gate))
    for child in node.children:
        _find_supplemental(child, depth + 1, excluded_ids, result)
