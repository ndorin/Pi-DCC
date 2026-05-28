"""Main control engine for the dust collection system."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from pi_dcc.airflow.calculator import (
    calculate_supplemental_gates_needed,
    is_airflow_sufficient,
    total_open_cfm,
    required_cfm_for_tools,
)
from pi_dcc.config.schema import AppConfig, BlastGateConfig
from pi_dcc.hardware.adc import ADCReader
from pi_dcc.hardware.buttons import ButtonController
from pi_dcc.hardware.leds import LEDController
from pi_dcc.hardware.relay import RelayController
from pi_dcc.hardware.servo import ServoController
from pi_dcc.network.model import PipingNetwork
from pi_dcc.network.pathfinder import get_gates_for_tools, get_supplemental_gates

logger = logging.getLogger(__name__)

STATE_FILE = "state.json"


class SystemState:
    """Current state of the dust collection system."""

    def __init__(self):
        self.active_tools: list[str] = []
        self.active_triggers: list[str] = []
        self.open_gates: list[str] = []
        self.supplemental_gates: list[str] = []
        self.collector_running: bool = False
        self.current_cfm: float = 0.0
        self.required_cfm: float = 0.0
        self.cumulative_runtime_hours: float = 0.0
        self.filter_clean_interval_hours: float = 50.0
        self.last_filter_reset_timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "active_tools": self.active_tools,
            "active_triggers": self.active_triggers,
            "open_gates": self.open_gates,
            "supplemental_gates": self.supplemental_gates,
            "collector_running": self.collector_running,
            "current_cfm": round(self.current_cfm, 1),
            "required_cfm": round(self.required_cfm, 1),
            "cumulative_runtime_hours": round(self.cumulative_runtime_hours, 2),
            "filter_clean_interval_hours": self.filter_clean_interval_hours,
            "filter_status_pct": round(
                min(
                    self.cumulative_runtime_hours / self.filter_clean_interval_hours * 100,
                    100.0,
                ),
                1,
            )
            if self.filter_clean_interval_hours > 0
            else 0.0,
        }


class ControlEngine:
    """Main control loop for the dust collection system."""

    def __init__(
        self,
        config: AppConfig,
        network: PipingNetwork,
        adc: ADCReader,
        servos: ServoController,
        relay: RelayController,
        leds: LEDController,
        buttons: ButtonController,
        state_file_path: str | Path = STATE_FILE,
    ):
        self._config = config
        self._network = network
        self._adc = adc
        self._servos = servos
        self._relay = relay
        self._leds = leds
        self._buttons = buttons
        self._state_file = Path(state_file_path)

        self._state = SystemState()
        self._state.filter_clean_interval_hours = (
            config.dust_collector.filter_clean_interval_hours
        )

        self._shutdown_task: asyncio.Task | None = None
        self._collector_start_time: float | None = None
        self._running = False

        # Web-triggered overrides: node IDs toggled from the web UI
        self._web_override_nodes: set[str] = set()

        # Load persisted state
        self._load_persisted_state()

    def _load_persisted_state(self) -> None:
        """Load cumulative runtime from state file."""
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                self._state.cumulative_runtime_hours = data.get(
                    "cumulative_runtime_hours", 0.0
                )
                self._state.last_filter_reset_timestamp = data.get(
                    "last_filter_reset_timestamp", 0.0
                )
                logger.info(
                    "Loaded persisted state: %.2f cumulative hours",
                    self._state.cumulative_runtime_hours,
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load state file: %s", e)

    def _save_persisted_state(self) -> None:
        """Save cumulative runtime to state file."""
        data = {
            "cumulative_runtime_hours": self._state.cumulative_runtime_hours,
            "last_filter_reset_timestamp": self._state.last_filter_reset_timestamp,
        }
        try:
            self._state_file.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except OSError as e:
            logger.error("Failed to save state file: %s", e)

    def reset_filter_runtime(self) -> None:
        """Reset the cumulative runtime counter (after filter cleaning)."""
        self._state.cumulative_runtime_hours = 0.0
        self._state.last_filter_reset_timestamp = time.time()
        self._save_persisted_state()
        logger.info("Filter runtime counter reset")

    def toggle_web_override(self, node_id: str) -> bool:
        """Toggle a node from the web UI. Returns True if now active."""
        if node_id in self._web_override_nodes:
            self._web_override_nodes.discard(node_id)
            logger.info("Web override removed for node: %s", node_id)
            return False
        else:
            self._web_override_nodes.add(node_id)
            logger.info("Web override added for node: %s", node_id)
            return True

    def get_web_overrides(self) -> list[str]:
        """Get list of currently active web override node IDs."""
        return list(self._web_override_nodes)

    def stop_all(self) -> None:
        """Clear all web overrides, effectively requesting system shutdown."""
        self._web_override_nodes.clear()
        logger.info("All web overrides cleared (stop all)")

    @property
    def state(self) -> SystemState:
        """Get the current system state."""
        return self._state

    async def start(self) -> None:
        """Start the control loop."""
        logger.info("Starting control engine")
        self._running = True

        # Initialize: close all gates, set LEDs to red
        all_gates = self._network.get_all_gates()
        self._servos.close_all(all_gates)
        self._leds.set_all_closed()

        # Main polling loop
        poll_interval = self._config.polling_interval_ms / 1000.0
        while self._running:
            await self._control_cycle()
            await asyncio.sleep(poll_interval)

    async def stop(self) -> None:
        """Stop the control loop and shut down gracefully."""
        logger.info("Stopping control engine")
        self._running = False

        # Cancel any pending shutdown timer
        if self._shutdown_task and not self._shutdown_task.done():
            self._shutdown_task.cancel()

        # Update runtime before stopping
        self._update_runtime()

        # Close all gates, stop collector, turn off LEDs
        all_gates = self._network.get_all_gates()
        self._servos.close_all(all_gates)
        self._relay.stop_collector()
        self._leds.set_all_off()
        self._relay.cleanup()
        self._leds.cleanup()
        self._buttons.cleanup()

        self._save_persisted_state()

    async def _control_cycle(self) -> None:
        """Execute one control cycle: poll, decide, actuate."""
        # 1. Poll CT sensors - determine active tools
        active_tools = self._poll_tools()

        # 2. Get active manual triggers
        active_trigger_ids = self._buttons.get_active_triggers()

        # 3. Determine required gates from tools (multi-node support)
        active_node_ids: list[str] = []
        for tool in self._config.tools:
            if tool.id in active_tools:
                active_node_ids.extend(tool.node_ids)

        # Add nodes from active manual triggers
        for trigger in self._config.manual_triggers:
            if trigger.id in active_trigger_ids:
                active_node_ids.extend(trigger.node_ids)

        # Add nodes from web overrides
        active_node_ids.extend(self._web_override_nodes)

        required_gates = get_gates_for_tools(self._network, active_node_ids)
        required_gate_ids = {g.id for g in required_gates}

        # 4. Check airflow and add supplemental gates if needed
        active_cfm_values = [
            tool.required_cfm
            for tool in self._config.tools
            if tool.id in active_tools
        ]
        # Include CFM from active manual triggers
        for trigger in self._config.manual_triggers:
            if trigger.id in active_trigger_ids:
                active_cfm_values.append(trigger.required_cfm)

        # Determine if anything is active (tools, triggers, or web overrides)
        anything_active = bool(active_tools) or bool(active_trigger_ids) or bool(self._web_override_nodes)

        supplemental_gates: list[BlastGateConfig] = []
        if anything_active and not is_airflow_sufficient(
            required_gates,
            active_cfm_values,
            self._config.airflow,
            self._config.dust_collector.max_cfm,
        ):
            available = get_supplemental_gates(self._network, required_gate_ids)
            supplemental_gates = calculate_supplemental_gates_needed(
                required_gates,
                active_cfm_values,
                available,
                self._config.airflow,
                self._config.dust_collector.max_cfm,
            )

        # 5. Compute desired gate state
        desired_open_ids = required_gate_ids | {g.id for g in supplemental_gates}
        all_gates = self._network.get_all_gates()

        # 6. Actuate gates (open/close as needed)
        for gate in all_gates:
            currently_open = self._servos.is_gate_open(gate.id)
            should_be_open = gate.id in desired_open_ids

            if should_be_open and not currently_open:
                self._servos.open_gate(gate)
                self._leds.update_gate(gate.led_index, True)
            elif not should_be_open and currently_open:
                self._servos.close_gate(gate)
                self._leds.update_gate(gate.led_index, False)

        # 7. Manage dust collector
        await self._manage_collector(anything_active)

        # 8. Update state
        self._state.active_tools = active_tools
        self._state.active_triggers = active_trigger_ids
        self._state.open_gates = [g.id for g in required_gates]
        self._state.supplemental_gates = [g.id for g in supplemental_gates]
        self._state.collector_running = self._relay.is_running
        self._state.required_cfm = required_cfm_for_tools(active_cfm_values)

        open_gate_configs = [g for g in all_gates if g.id in desired_open_ids]
        self._state.current_cfm = total_open_cfm(
            open_gate_configs,
            self._config.airflow,
            self._config.dust_collector.max_cfm,
        )

    def _poll_tools(self) -> list[str]:
        """Poll all CT sensors and return list of active tool IDs."""
        active = []
        for tool in self._config.tools:
            if self._adc.is_tool_running(
                tool.adc_board, tool.adc_channel, tool.current_threshold_amps
            ):
                active.append(tool.id)
        return active

    async def _manage_collector(self, anything_active: bool) -> None:
        """Manage dust collector start/stop with shutdown delay."""
        if anything_active:
            # Tools/triggers are active - cancel any pending shutdown and ensure collector is on
            if self._shutdown_task and not self._shutdown_task.done():
                self._shutdown_task.cancel()
                self._shutdown_task = None

            if not self._relay.is_running:
                self._relay.start_collector()
                self._collector_start_time = time.time()
        else:
            # Nothing active - schedule shutdown if not already scheduled
            if self._relay.is_running and (
                self._shutdown_task is None or self._shutdown_task.done()
            ):
                self._shutdown_task = asyncio.create_task(
                    self._shutdown_after_delay()
                )

    async def _shutdown_after_delay(self) -> None:
        """Wait for shutdown delay then stop collector and close gates."""
        delay = self._config.dust_collector.shutdown_delay_seconds
        logger.info("Scheduling collector shutdown in %d seconds", delay)

        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            logger.debug("Shutdown timer cancelled (tool started)")
            return

        logger.info("Shutdown delay elapsed, stopping collector")
        self._update_runtime()

        # Close all gates and stop collector
        all_gates = self._network.get_all_gates()
        self._servos.close_all(all_gates)
        self._relay.stop_collector()

        # Update LEDs
        self._leds.set_all_closed()

        # Save state
        self._save_persisted_state()

    def _update_runtime(self) -> None:
        """Update cumulative runtime based on collector activity."""
        if self._collector_start_time is not None and self._relay.is_running:
            elapsed = time.time() - self._collector_start_time
            self._state.cumulative_runtime_hours += elapsed / 3600.0
            self._collector_start_time = time.time()

            if (
                self._state.cumulative_runtime_hours
                >= self._state.filter_clean_interval_hours
            ):
                logger.warning(
                    "Filter cleaning recommended! Runtime: %.1f hours (threshold: %.1f)",
                    self._state.cumulative_runtime_hours,
                    self._state.filter_clean_interval_hours,
                )
