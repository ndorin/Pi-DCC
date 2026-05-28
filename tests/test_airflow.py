"""Tests for airflow calculations."""

import pytest

from pi_dcc.airflow.calculator import (
    calculate_supplemental_gates_needed,
    gate_cfm,
    is_airflow_sufficient,
    required_cfm_for_tools,
    total_open_cfm,
)
from pi_dcc.config.schema import AirflowConfig, BlastGateConfig


@pytest.fixture
def airflow_config():
    return AirflowConfig(target_velocity_fpm=4000, minimum_cfm_ratio=0.8)


@pytest.fixture
def four_inch_gate():
    return BlastGateConfig(
        id="gate_4",
        diameter_inches=4,
        pwm_board=0,
        pwm_channel=0,
        led_index=0,
    )


@pytest.fixture
def six_inch_gate():
    return BlastGateConfig(
        id="gate_6",
        diameter_inches=6,
        pwm_board=0,
        pwm_channel=1,
        led_index=1,
    )


class TestGateCFM:
    def test_four_inch_gate(self, four_inch_gate):
        # 4" diameter = 2" radius = 1/6 ft radius
        # Area = pi * (1/6)^2 = pi/36 sq ft ≈ 0.0873 sq ft
        # CFM = 0.0873 * 4000 ≈ 349.1
        cfm = gate_cfm(four_inch_gate, 4000)
        assert abs(cfm - 349.07) < 1.0

    def test_six_inch_gate(self, six_inch_gate):
        # 6" diameter = 3" radius = 1/4 ft radius
        # Area = pi * (1/4)^2 = pi/16 sq ft ≈ 0.1963 sq ft
        # CFM = 0.1963 * 4000 ≈ 785.4
        cfm = gate_cfm(six_inch_gate, 4000)
        assert abs(cfm - 785.40) < 1.0


class TestTotalOpenCFM:
    def test_single_gate(self, four_inch_gate, airflow_config):
        cfm = total_open_cfm([four_inch_gate], airflow_config, 800)
        assert abs(cfm - 349.07) < 1.0

    def test_multiple_gates_under_max(self, four_inch_gate, airflow_config):
        cfm = total_open_cfm([four_inch_gate, four_inch_gate], airflow_config, 800)
        assert abs(cfm - 698.13) < 1.0

    def test_bounded_by_collector_max(self, six_inch_gate, airflow_config):
        # Two 6" gates would be ~1570 CFM, but collector max is 800
        cfm = total_open_cfm([six_inch_gate, six_inch_gate], airflow_config, 800)
        assert cfm == 800.0

    def test_no_gates(self, airflow_config):
        assert total_open_cfm([], airflow_config, 800) == 0.0


class TestAirflowSufficiency:
    def test_sufficient(self, four_inch_gate, airflow_config):
        # Gate provides ~349 CFM, tool needs 300, ratio is 0.8
        # Required: 300 * 0.8 = 240, Available: 349
        assert is_airflow_sufficient(
            [four_inch_gate], [300.0], airflow_config, 800
        )

    def test_insufficient(self, four_inch_gate, airflow_config):
        # Gate provides ~349 CFM, tool needs 500
        # Required: 500 * 0.8 = 400, Available: 349
        assert not is_airflow_sufficient(
            [four_inch_gate], [500.0], airflow_config, 800
        )

    def test_no_active_tools(self, four_inch_gate, airflow_config):
        assert is_airflow_sufficient([four_inch_gate], [], airflow_config, 800)


class TestSupplementalGates:
    def test_no_supplemental_needed(self, four_inch_gate, airflow_config):
        result = calculate_supplemental_gates_needed(
            current_gates=[four_inch_gate],
            active_tool_cfm_values=[200.0],
            available_supplemental=[],
            airflow_config=airflow_config,
            collector_max_cfm=800,
        )
        assert result == []

    def test_supplemental_added(self, airflow_config):
        gate1 = BlastGateConfig(
            id="g1", diameter_inches=4, pwm_board=0, pwm_channel=0, led_index=0
        )
        gate2 = BlastGateConfig(
            id="g2", diameter_inches=4, pwm_board=0, pwm_channel=1, led_index=1
        )
        # gate1 provides ~349 CFM, tool needs 500 (threshold: 400)
        result = calculate_supplemental_gates_needed(
            current_gates=[gate1],
            active_tool_cfm_values=[500.0],
            available_supplemental=[gate2],
            airflow_config=airflow_config,
            collector_max_cfm=800,
        )
        assert len(result) == 1
        assert result[0].id == "g2"
