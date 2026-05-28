"""Configuration file loader and validator."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .schema import AppConfig

logger = logging.getLogger(__name__)


def load_config(config_path: str | Path) -> AppConfig:
    """Load and validate the application configuration from a JSON file.

    Args:
        config_path: Path to the JSON configuration file.

    Returns:
        Validated AppConfig instance.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        json.JSONDecodeError: If the file contains invalid JSON.
        pydantic.ValidationError: If the config doesn't match the schema.
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    logger.info("Loading configuration from %s", config_path)
    raw = config_path.read_text(encoding="utf-8")
    data = json.loads(raw)

    config = AppConfig.model_validate(data)
    logger.info(
        "Configuration loaded: %d tools, %d ADC boards, %d PWM boards",
        len(config.tools),
        len(config.adc_boards),
        len(config.pwm_boards),
    )

    _validate_references(config)

    return config


def _validate_references(config: AppConfig) -> None:
    """Validate cross-references within the configuration.

    Ensures that tool node_ids exist in the network tree,
    ADC/PWM board indices are valid, and LED indices are within range.
    """
    # Collect all node IDs from the network tree
    node_ids = set()
    _collect_node_ids(config.network, node_ids)

    # Collect all blast gate IDs and LED indices
    gate_ids = set()
    led_indices = set()
    _collect_gate_info(config.network, gate_ids, led_indices)

    # Validate tool references
    for tool in config.tools:
        for node_id in tool.node_ids:
            if node_id not in node_ids:
                raise ValueError(
                    f"Tool '{tool.id}' references node_id '{node_id}' "
                    f"which does not exist in the network tree"
                )
        if tool.adc_board >= len(config.adc_boards):
            raise ValueError(
                f"Tool '{tool.id}' references adc_board index {tool.adc_board} "
                f"but only {len(config.adc_boards)} ADC boards are configured"
            )

    # Validate manual trigger references
    for trigger in config.manual_triggers:
        for node_id in trigger.node_ids:
            if node_id not in node_ids:
                raise ValueError(
                    f"Manual trigger '{trigger.id}' references node_id '{node_id}' "
                    f"which does not exist in the network tree"
                )

    # Validate LED indices are within NeoPixel strip range
    for idx in led_indices:
        if idx >= config.neopixel.led_count:
            raise ValueError(
                f"Blast gate LED index {idx} exceeds neopixel led_count "
                f"({config.neopixel.led_count})"
            )

    # Validate PWM board references in blast gates
    max_pwm_board = len(config.pwm_boards) - 1
    _validate_pwm_references(config.network, max_pwm_board)


def _collect_node_ids(node, node_ids: set) -> None:
    """Recursively collect all node IDs from the network tree."""
    node_ids.add(node.id)
    for child in node.children:
        _collect_node_ids(child, node_ids)


def _collect_gate_info(node, gate_ids: set, led_indices: set) -> None:
    """Recursively collect blast gate IDs and LED indices."""
    if node.blast_gate:
        gate_ids.add(node.blast_gate.id)
        led_indices.add(node.blast_gate.led_index)
    for child in node.children:
        _collect_gate_info(child, gate_ids, led_indices)


def _validate_pwm_references(node, max_pwm_board: int) -> None:
    """Recursively validate PWM board references in blast gates."""
    if node.blast_gate:
        if node.blast_gate.pwm_board > max_pwm_board:
            raise ValueError(
                f"Blast gate '{node.blast_gate.id}' references pwm_board "
                f"index {node.blast_gate.pwm_board} but only "
                f"{max_pwm_board + 1} PWM boards are configured"
            )
    for child in node.children:
        _validate_pwm_references(child, max_pwm_board)
