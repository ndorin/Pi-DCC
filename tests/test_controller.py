"""Tests for the control engine."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pi_dcc.config.schema import (
    ADCBoardConfig,
    AirflowConfig,
    AppConfig,
    BlastGateConfig,
    DustCollectorConfig,
    ManualTriggerConfig,
    NeoPixelConfig,
    PipeNodeConfig,
    PWMBoardConfig,
    ToolConfig,
)
from pi_dcc.controller.engine import ControlEngine, SystemState
from pi_dcc.hardware.adc import ADCReader
from pi_dcc.hardware.buttons import ButtonController
from pi_dcc.hardware.leds import LEDController
from pi_dcc.hardware.relay import RelayController
from pi_dcc.hardware.servo import ServoController
from pi_dcc.network.model import PipingNetwork


@pytest.fixture
def app_config():
    return AppConfig(
        dust_collector=DustCollectorConfig(
            relay_pin=17,
            shutdown_delay_seconds=2,
            max_cfm=800,
            motor_hp=2.0,
            filter_clean_interval_hours=50,
        ),
        airflow=AirflowConfig(target_velocity_fpm=4000, minimum_cfm_ratio=0.8),
        adc_boards=[ADCBoardConfig(address="0x48", bus=1)],
        pwm_boards=[PWMBoardConfig(address="0x40", bus=1)],
        neopixel=NeoPixelConfig(gpio_pin=18, led_count=3, brightness=0.5),
        polling_interval_ms=50,
        network=PipeNodeConfig(
            id="collector",
            pipe_diameter_inches=6,
            children=[
                PipeNodeConfig(
                    id="tool_port",
                    pipe_diameter_inches=4,
                    blast_gate=BlastGateConfig(
                        id="gate_1",
                        diameter_inches=4,
                        pwm_board=0,
                        pwm_channel=0,
                        led_index=0,
                    ),
                    children=[],
                ),
                PipeNodeConfig(
                    id="tool_port_2",
                    pipe_diameter_inches=4,
                    blast_gate=BlastGateConfig(
                        id="gate_2",
                        diameter_inches=4,
                        pwm_board=0,
                        pwm_channel=1,
                        led_index=1,
                    ),
                    children=[],
                ),
                PipeNodeConfig(
                    id="manual_port",
                    pipe_diameter_inches=4,
                    blast_gate=BlastGateConfig(
                        id="gate_manual",
                        diameter_inches=4,
                        pwm_board=0,
                        pwm_channel=2,
                        led_index=2,
                    ),
                    children=[],
                ),
            ],
        ),
        tools=[
            ToolConfig(
                id="saw",
                name="Table Saw",
                adc_board=0,
                adc_channel=0,
                current_threshold_amps=2.0,
                required_cfm=300,
                node_ids=["tool_port"],
            ),
            ToolConfig(
                id="drill",
                name="Drill Press",
                adc_board=0,
                adc_channel=1,
                current_threshold_amps=1.5,
                required_cfm=200,
                node_ids=["tool_port_2"],
            ),
        ],
        manual_triggers=[
            ManualTriggerConfig(
                id="floor_sweep",
                name="Floor Sweep",
                gpio_pin=22,
                node_ids=["manual_port"],
                required_cfm=200,
            ),
        ],
    )


@pytest.fixture
def engine(app_config, tmp_path):
    network = PipingNetwork.from_config(app_config.network)
    adc = ADCReader(app_config.adc_boards, simulate=True)
    servos = ServoController(app_config.pwm_boards, simulate=True)
    relay = RelayController(app_config.dust_collector.relay_pin, simulate=True)
    leds = LEDController(app_config.neopixel, simulate=True)
    buttons = ButtonController(app_config.manual_triggers, simulate=True)

    state_file = tmp_path / "state.json"
    return ControlEngine(
        config=app_config,
        network=network,
        adc=adc,
        servos=servos,
        relay=relay,
        leds=leds,
        buttons=buttons,
        state_file_path=state_file,
    )


class TestSystemState:
    def test_to_dict(self):
        state = SystemState()
        state.cumulative_runtime_hours = 25.0
        state.filter_clean_interval_hours = 50.0
        d = state.to_dict()
        assert d["filter_status_pct"] == 50.0

    def test_filter_status_at_limit(self):
        state = SystemState()
        state.cumulative_runtime_hours = 50.0
        state.filter_clean_interval_hours = 50.0
        d = state.to_dict()
        assert d["filter_status_pct"] == 100.0


class TestControlEngine:
    def test_initial_state(self, engine):
        assert engine.state.collector_running is False
        assert engine.state.active_tools == []
        assert engine.state.open_gates == []

    def test_reset_filter_runtime(self, engine):
        engine._state.cumulative_runtime_hours = 30.0
        engine.reset_filter_runtime()
        assert engine.state.cumulative_runtime_hours == 0.0

    def test_state_persistence(self, engine, tmp_path):
        engine._state.cumulative_runtime_hours = 15.5
        engine._save_persisted_state()

        # Verify file was written
        state_file = tmp_path / "state.json"
        data = json.loads(state_file.read_text())
        assert data["cumulative_runtime_hours"] == 15.5

    @pytest.mark.asyncio
    async def test_control_cycle_no_tools(self, engine):
        await engine._control_cycle()
        assert engine.state.active_tools == []
        assert engine.state.collector_running is False

    @pytest.mark.asyncio
    async def test_control_cycle_tool_active(self, engine):
        # Simulate tool drawing current
        engine._adc.set_simulated_current(0, 0, 5.0)
        await engine._control_cycle()
        assert "saw" in engine.state.active_tools
        assert engine.state.collector_running is True
        assert "gate_1" in engine.state.open_gates

    @pytest.mark.asyncio
    async def test_control_cycle_multiple_tools(self, engine):
        engine._adc.set_simulated_current(0, 0, 5.0)
        engine._adc.set_simulated_current(0, 1, 3.0)
        await engine._control_cycle()
        assert "saw" in engine.state.active_tools
        assert "drill" in engine.state.active_tools
        assert "gate_1" in engine.state.open_gates
        assert "gate_2" in engine.state.open_gates

    @pytest.mark.asyncio
    async def test_graceful_stop(self, engine):
        engine._adc.set_simulated_current(0, 0, 5.0)
        await engine._control_cycle()
        assert engine.state.collector_running is True

        await engine.stop()
        assert engine._relay.is_running is False

    @pytest.mark.asyncio
    async def test_manual_trigger_opens_gate(self, engine):
        # Simulate pressing the floor sweep button
        engine._buttons.simulate_press("floor_sweep")
        await engine._control_cycle()
        assert "floor_sweep" in engine.state.active_triggers
        assert "gate_manual" in engine.state.open_gates
        assert engine.state.collector_running is True

    @pytest.mark.asyncio
    async def test_manual_trigger_toggle_off(self, engine):
        # Press to activate
        engine._buttons.simulate_press("floor_sweep")
        await engine._control_cycle()
        assert engine.state.collector_running is True

        # Press again to deactivate
        engine._buttons.simulate_press("floor_sweep")
        await engine._control_cycle()
        assert "floor_sweep" not in engine.state.active_triggers
        assert "gate_manual" not in engine.state.open_gates

    @pytest.mark.asyncio
    async def test_tool_and_trigger_simultaneously(self, engine):
        engine._adc.set_simulated_current(0, 0, 5.0)
        engine._buttons.simulate_press("floor_sweep")
        await engine._control_cycle()
        assert "saw" in engine.state.active_tools
        assert "floor_sweep" in engine.state.active_triggers
        assert "gate_1" in engine.state.open_gates
        assert "gate_manual" in engine.state.open_gates
        assert engine.state.collector_running is True
