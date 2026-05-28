"""Airflow calculations for the dust collection system."""

from __future__ import annotations

import math

from pi_dcc.config.schema import AirflowConfig, BlastGateConfig


def gate_cfm(gate: BlastGateConfig, target_velocity_fpm: float) -> float:
    """Calculate the CFM capacity of a single blast gate.

    CFM = Area (sq ft) × Velocity (FPM)

    Args:
        gate: Blast gate configuration.
        target_velocity_fpm: Target air velocity in feet per minute.

    Returns:
        CFM capacity of the gate.
    """
    radius_ft = (gate.diameter_inches / 2.0) / 12.0
    area_sq_ft = math.pi * radius_ft * radius_ft
    return area_sq_ft * target_velocity_fpm


def total_open_cfm(
    open_gates: list[BlastGateConfig],
    airflow_config: AirflowConfig,
    collector_max_cfm: float,
) -> float:
    """Calculate the total CFM flowing through all open gates.

    The total is bounded by the dust collector's maximum CFM capacity.

    Args:
        open_gates: List of currently open blast gates.
        airflow_config: Airflow configuration parameters.
        collector_max_cfm: Maximum CFM the dust collector can provide.

    Returns:
        Effective total CFM through the system.
    """
    if not open_gates:
        return 0.0

    raw_total = sum(
        gate_cfm(g, airflow_config.target_velocity_fpm) for g in open_gates
    )
    return min(raw_total, collector_max_cfm)


def required_cfm_for_tools(tool_cfm_values: list[float]) -> float:
    """Calculate the total CFM required by all active tools.

    Args:
        tool_cfm_values: List of required CFM values for each active tool.

    Returns:
        Total required CFM.
    """
    return sum(tool_cfm_values)


def is_airflow_sufficient(
    open_gates: list[BlastGateConfig],
    active_tool_cfm_values: list[float],
    airflow_config: AirflowConfig,
    collector_max_cfm: float,
) -> bool:
    """Check if the current open gates provide sufficient airflow for active tools.

    Args:
        open_gates: List of currently open blast gates.
        active_tool_cfm_values: CFM requirements of each active tool.
        airflow_config: Airflow configuration.
        collector_max_cfm: Maximum CFM of the dust collector.

    Returns:
        True if airflow is sufficient.
    """
    available = total_open_cfm(open_gates, airflow_config, collector_max_cfm)
    required = required_cfm_for_tools(active_tool_cfm_values)

    if required == 0:
        return True

    return available >= (required * airflow_config.minimum_cfm_ratio)


def calculate_supplemental_gates_needed(
    current_gates: list[BlastGateConfig],
    active_tool_cfm_values: list[float],
    available_supplemental: list[BlastGateConfig],
    airflow_config: AirflowConfig,
    collector_max_cfm: float,
) -> list[BlastGateConfig]:
    """Determine which supplemental gates to open for adequate airflow.

    Opens gates from the available list (ordered by priority) until
    airflow is sufficient or no more gates are available.

    Args:
        current_gates: Gates already required by active tools.
        active_tool_cfm_values: CFM requirements of active tools.
        available_supplemental: Available supplemental gates (priority-ordered).
        airflow_config: Airflow configuration.
        collector_max_cfm: Maximum CFM of the dust collector.

    Returns:
        List of supplemental gates that should be opened.
    """
    if is_airflow_sufficient(
        current_gates, active_tool_cfm_values, airflow_config, collector_max_cfm
    ):
        return []

    supplemental_to_open: list[BlastGateConfig] = []
    test_gates = list(current_gates)

    for gate in available_supplemental:
        test_gates.append(gate)
        supplemental_to_open.append(gate)

        if is_airflow_sufficient(
            test_gates, active_tool_cfm_values, airflow_config, collector_max_cfm
        ):
            break

    return supplemental_to_open
