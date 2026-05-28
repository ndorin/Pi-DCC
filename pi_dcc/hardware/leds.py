"""NeoPixel LED controller for blast gate status indicators."""

from __future__ import annotations

import logging

from pi_dcc.config.schema import NeoPixelConfig

logger = logging.getLogger(__name__)

try:
    from rpi_ws281x import PixelStrip, Color

    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False

# LED colors
COLOR_RED = (255, 0, 0)    # Gate closed
COLOR_GREEN = (0, 255, 0)  # Gate open
COLOR_OFF = (0, 0, 0)      # LED off


class LEDController:
    """Controls NeoPixel LEDs indicating blast gate status."""

    def __init__(self, config: NeoPixelConfig, simulate: bool = False):
        self._simulate = simulate or not HAS_HARDWARE
        self._config = config
        self._states: list[tuple[int, int, int]] = [COLOR_OFF] * config.led_count
        self._strip = None

        if not self._simulate:
            self._init_hardware()
        else:
            logger.info("LED controller running in simulation mode")

    def _init_hardware(self) -> None:
        """Initialize the NeoPixel strip."""
        self._strip = PixelStrip(
            self._config.led_count,
            self._config.gpio_pin,
            brightness=int(self._config.brightness * 255),
        )
        self._strip.begin()
        logger.info(
            "Initialized NeoPixel strip: %d LEDs on GPIO %d",
            self._config.led_count,
            self._config.gpio_pin,
        )

    def set_gate_open(self, led_index: int) -> None:
        """Set a gate's LED to green (open)."""
        self._set_color(led_index, COLOR_GREEN)

    def set_gate_closed(self, led_index: int) -> None:
        """Set a gate's LED to red (closed)."""
        self._set_color(led_index, COLOR_RED)

    def set_all_closed(self) -> None:
        """Set all LEDs to red (all gates closed)."""
        for i in range(self._config.led_count):
            self._set_color(i, COLOR_RED)
        self._show()

    def set_all_off(self) -> None:
        """Turn off all LEDs."""
        for i in range(self._config.led_count):
            self._set_color(i, COLOR_OFF)
        self._show()

    def update_gate(self, led_index: int, is_open: bool) -> None:
        """Update a gate LED based on its state."""
        if is_open:
            self.set_gate_open(led_index)
        else:
            self.set_gate_closed(led_index)
        self._show()

    def get_states(self) -> list[tuple[int, int, int]]:
        """Get the current color state of all LEDs."""
        return list(self._states)

    def _set_color(self, index: int, color: tuple[int, int, int]) -> None:
        """Set the color of a specific LED."""
        if index < 0 or index >= self._config.led_count:
            return

        self._states[index] = color

        if not self._simulate and self._strip:
            r, g, b = color
            self._strip.setPixelColor(index, Color(r, g, b))

    def _show(self) -> None:
        """Push LED state to hardware."""
        if not self._simulate and self._strip:
            self._strip.show()

    def cleanup(self) -> None:
        """Turn off all LEDs and clean up."""
        self.set_all_off()
