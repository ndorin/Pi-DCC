"""Relay controller for the dust collector."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO

    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False


class RelayController:
    """Controls the dust collector power via a GPIO relay."""

    def __init__(self, relay_pin: int, simulate: bool = False):
        self._pin = relay_pin
        self._simulate = simulate or not HAS_HARDWARE
        self._is_running = False

        if not self._simulate:
            self._init_hardware()
        else:
            logger.info("Relay controller running in simulation mode")

    def _init_hardware(self) -> None:
        """Initialize the GPIO relay pin."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._pin, GPIO.OUT)
        GPIO.output(self._pin, GPIO.LOW)  # Start with collector OFF
        logger.info("Initialized relay on GPIO pin %d", self._pin)

    def start_collector(self) -> None:
        """Turn on the dust collector."""
        if self._is_running:
            return

        if not self._simulate:
            GPIO.output(self._pin, GPIO.HIGH)
        else:
            logger.debug("SIM: Dust collector ON")

        self._is_running = True
        logger.info("Dust collector started")

    def stop_collector(self) -> None:
        """Turn off the dust collector."""
        if not self._is_running:
            return

        if not self._simulate:
            GPIO.output(self._pin, GPIO.LOW)
        else:
            logger.debug("SIM: Dust collector OFF")

        self._is_running = False
        logger.info("Dust collector stopped")

    @property
    def is_running(self) -> bool:
        """Whether the dust collector is currently running."""
        return self._is_running

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        if not self._simulate:
            GPIO.output(self._pin, GPIO.LOW)
            GPIO.cleanup(self._pin)
        self._is_running = False
