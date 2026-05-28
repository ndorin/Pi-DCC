"""Servo controller for blast gates via PCA9685 PWM driver."""

from __future__ import annotations

import logging

from pi_dcc.config.schema import BlastGateConfig, PWMBoardConfig

logger = logging.getLogger(__name__)

try:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    from adafruit_motor import servo as servo_module

    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False


class ServoController:
    """Controls blast gate servos via PCA9685 PWM driver boards."""

    def __init__(self, boards_config: list[PWMBoardConfig], simulate: bool = False):
        self._simulate = simulate or not HAS_HARDWARE
        self._boards: list = []
        self._gate_states: dict[str, bool] = {}  # gate_id -> is_open

        if not self._simulate:
            self._init_hardware(boards_config)
        else:
            logger.info("Servo controller running in simulation mode")

    def _init_hardware(self, boards_config: list[PWMBoardConfig]) -> None:
        """Initialize PCA9685 hardware boards."""
        i2c = busio.I2C(board.SCL, board.SDA)
        for cfg in boards_config:
            address = int(cfg.address, 16)
            pca = PCA9685(i2c, address=address)
            pca.frequency = 50  # Standard servo frequency
            self._boards.append(pca)
            logger.info("Initialized PCA9685 at address %s on bus %d", cfg.address, cfg.bus)

    def open_gate(self, gate: BlastGateConfig) -> None:
        """Open a blast gate by moving its servo to the open position."""
        self._set_servo_angle(gate, gate.servo_open_angle)
        self._gate_states[gate.id] = True
        logger.debug("Opened gate %s", gate.id)

    def close_gate(self, gate: BlastGateConfig) -> None:
        """Close a blast gate by moving its servo to the closed position."""
        self._set_servo_angle(gate, gate.servo_close_angle)
        self._gate_states[gate.id] = False
        logger.debug("Closed gate %s", gate.id)

    def is_gate_open(self, gate_id: str) -> bool:
        """Check if a gate is currently open."""
        return self._gate_states.get(gate_id, False)

    def get_all_gate_states(self) -> dict[str, bool]:
        """Get the current state of all gates."""
        return dict(self._gate_states)

    def close_all(self, all_gates: list[BlastGateConfig]) -> None:
        """Close all blast gates."""
        for gate in all_gates:
            self.close_gate(gate)

    def _set_servo_angle(self, gate: BlastGateConfig, angle: int) -> None:
        """Set a servo to a specific angle."""
        if self._simulate:
            logger.debug(
                "SIM: Set servo board=%d ch=%d to %d°",
                gate.pwm_board, gate.pwm_channel, angle,
            )
            return

        pca = self._boards[gate.pwm_board]
        srv = servo_module.Servo(pca.channels[gate.pwm_channel])
        srv.angle = angle
