"""Direct GPIO servo control for testing without PCA9685."""

from __future__ import annotations

import logging

from pi_dcc.config.schema import BlastGateConfig

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO

    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False


class GPIOServoController:
    """Controls servos directly via Pi GPIO hardware PWM pins."""

    def __init__(self, gate_pin_map: dict[str, int]):
        """Initialize with a mapping of gate_id -> GPIO pin number."""
        self._pin_map = gate_pin_map
        self._pwms: dict[str, object] = {}

        if not HAS_GPIO:
            logger.warning("RPi.GPIO not available, GPIO servo will be simulated")
            return

        GPIO.setmode(GPIO.BCM)
        for gate_id, pin in gate_pin_map.items():
            GPIO.setup(pin, GPIO.OUT)
            pwm = GPIO.PWM(pin, 50)  # 50Hz for servos
            pwm.start(0)
            self._pwms[gate_id] = pwm
            logger.info("GPIO servo for '%s' on pin %d", gate_id, pin)

    def has_gate(self, gate_id: str) -> bool:
        """Check if this controller handles the given gate."""
        return gate_id in self._pin_map

    def set_angle(self, gate: BlastGateConfig, angle: int) -> None:
        """Set a servo to a specific angle via GPIO PWM."""
        pwm = self._pwms.get(gate.id)
        if pwm is None:
            logger.debug("SIM GPIO: Set %s to %d°", gate.id, angle)
            return

        # Map angle (0-180) to duty cycle (2.5% - 12.5%)
        duty = 2.5 + (angle / 180.0) * 10.0
        pwm.ChangeDutyCycle(duty)
        logger.debug("GPIO servo %s -> %d° (duty=%.1f%%)", gate.id, angle, duty)

    def cleanup(self) -> None:
        """Stop all PWM and clean up GPIO."""
        for pwm in self._pwms.values():
            pwm.ChangeDutyCycle(0)
            pwm.stop()
        # Don't call GPIO.cleanup() here as other modules may use GPIO
