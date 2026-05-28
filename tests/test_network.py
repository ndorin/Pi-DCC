"""Tests for the piping network model and pathfinder."""

import pytest

from pi_dcc.config.schema import BlastGateConfig, PipeNodeConfig
from pi_dcc.network.model import PipingNetwork
from pi_dcc.network.pathfinder import (
    find_path_to_node,
    get_gates_for_tools,
    get_required_gates,
    get_supplemental_gates,
)


@pytest.fixture
def sample_network_config():
    """Create a sample network tree config for testing.

    Tree structure:
        collector
        └── main_trunk
            ├── left_branch (gate_left)
            │   ├── saw_port (gate_saw)
            │   └── jointer_port (gate_jointer)
            └── right_branch (gate_right)
                └── bandsaw_port (gate_bandsaw)
    """
    return PipeNodeConfig(
        id="collector",
        pipe_diameter_inches=6,
        children=[
            PipeNodeConfig(
                id="main_trunk",
                pipe_diameter_inches=6,
                children=[
                    PipeNodeConfig(
                        id="left_branch",
                        pipe_diameter_inches=4,
                        blast_gate=BlastGateConfig(
                            id="gate_left",
                            diameter_inches=4,
                            pwm_board=0,
                            pwm_channel=0,
                            led_index=0,
                        ),
                        children=[
                            PipeNodeConfig(
                                id="saw_port",
                                pipe_diameter_inches=4,
                                blast_gate=BlastGateConfig(
                                    id="gate_saw",
                                    diameter_inches=4,
                                    pwm_board=0,
                                    pwm_channel=1,
                                    led_index=1,
                                ),
                            ),
                            PipeNodeConfig(
                                id="jointer_port",
                                pipe_diameter_inches=4,
                                blast_gate=BlastGateConfig(
                                    id="gate_jointer",
                                    diameter_inches=4,
                                    pwm_board=0,
                                    pwm_channel=2,
                                    led_index=2,
                                ),
                            ),
                        ],
                    ),
                    PipeNodeConfig(
                        id="right_branch",
                        pipe_diameter_inches=4,
                        blast_gate=BlastGateConfig(
                            id="gate_right",
                            diameter_inches=4,
                            pwm_board=0,
                            pwm_channel=3,
                            led_index=3,
                        ),
                        children=[
                            PipeNodeConfig(
                                id="bandsaw_port",
                                pipe_diameter_inches=4,
                                blast_gate=BlastGateConfig(
                                    id="gate_bandsaw",
                                    diameter_inches=4,
                                    pwm_board=0,
                                    pwm_channel=4,
                                    led_index=4,
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def network(sample_network_config):
    return PipingNetwork.from_config(sample_network_config)


class TestPipingNetwork:
    def test_build_from_config(self, network):
        assert network.root.id == "collector"
        assert len(network.get_all_gates()) == 5

    def test_get_node(self, network):
        node = network.get_node("saw_port")
        assert node is not None
        assert node.id == "saw_port"
        assert node.blast_gate.id == "gate_saw"

    def test_get_node_not_found(self, network):
        assert network.get_node("nonexistent") is None

    def test_parent_references(self, network):
        saw = network.get_node("saw_port")
        assert saw.parent.id == "left_branch"
        assert saw.parent.parent.id == "main_trunk"
        assert saw.parent.parent.parent.id == "collector"


class TestPathfinder:
    def test_find_path_to_leaf(self, network):
        path = find_path_to_node(network, "saw_port")
        ids = [n.id for n in path]
        assert ids == ["collector", "main_trunk", "left_branch", "saw_port"]

    def test_find_path_to_branch(self, network):
        path = find_path_to_node(network, "left_branch")
        ids = [n.id for n in path]
        assert ids == ["collector", "main_trunk", "left_branch"]

    def test_find_path_invalid_node(self, network):
        with pytest.raises(ValueError):
            find_path_to_node(network, "nonexistent")

    def test_get_required_gates_for_saw(self, network):
        gates = get_required_gates(network, "saw_port")
        gate_ids = [g.id for g in gates]
        assert gate_ids == ["gate_left", "gate_saw"]

    def test_get_required_gates_for_bandsaw(self, network):
        gates = get_required_gates(network, "bandsaw_port")
        gate_ids = [g.id for g in gates]
        assert gate_ids == ["gate_right", "gate_bandsaw"]

    def test_get_gates_for_multiple_tools(self, network):
        gates = get_gates_for_tools(network, ["saw_port", "jointer_port"])
        gate_ids = {g.id for g in gates}
        # Both are on the left branch, so they share gate_left
        assert gate_ids == {"gate_left", "gate_saw", "gate_jointer"}

    def test_get_gates_for_tools_different_branches(self, network):
        gates = get_gates_for_tools(network, ["saw_port", "bandsaw_port"])
        gate_ids = {g.id for g in gates}
        assert gate_ids == {"gate_left", "gate_saw", "gate_right", "gate_bandsaw"}

    def test_get_supplemental_gates(self, network):
        # If saw is active, supplemental gates are on the right branch
        required = {"gate_left", "gate_saw"}
        supplemental = get_supplemental_gates(network, required)
        supplemental_ids = [g.id for g in supplemental]
        # Should include gates not in required set, sorted by depth
        assert "gate_right" in supplemental_ids
        assert "gate_bandsaw" in supplemental_ids
        assert "gate_jointer" in supplemental_ids
        assert "gate_left" not in supplemental_ids
        assert "gate_saw" not in supplemental_ids
