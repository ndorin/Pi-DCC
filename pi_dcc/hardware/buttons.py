"""GPIO button input handler for manual triggers."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List

from pi_dcc.config.schema import ManualTriggerConfig

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO

    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False


class ButtonController:
    """Handles GPIO button inputs for manual trigger toggles.

    Each button press toggles its associated trigger between active/inactive.
    Uses edge detection with software debounce.
    """

    DEBOUNCE_MS = 300

    def __init__(
        self,
        triggers: List[ManualTriggerConfig],
        simulate: bool = False,
    ):
        self._simulate = simulate or not HAS_HARDWARE
        self._triggers = {t.id: t for t in triggers}
        self._active_triggers: Dict[str, bool] = {t.id: False for t in triggers}
        self._callbacks: List[Callable[[str, bool], None]] = []

        if not self._simulate:
            self._init_hardware(triggers)
        else:
            logger.info("Button controller running in simulation mode")

    def _init_hardware(self, triggers: List[ManualTriggerConfig]) -> None:
        """Initialize GPIO pins for button inputs with pull-up resistors."""
        GPIO.setmode(GPIO.BCM)
        for trigger in triggers:
            GPIO.setup(trigger.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                trigger.gpio_pin,
                GPIO.FALLING,
                callback=lambda pin, t=trigger: self._handle_press(t),
                bouncetime=self.DEBOUNCE_MS,
            )
            logger.info(
                "Initialized button on GPIO %d for trigger '%s'",
                trigger.gpio_pin,
                trigger.id,
            )

    def _handle_press(self, trigger: ManualTriggerConfig) -> None:
        """Handle a button press — toggle the trigger state."""
        new_state = not self._active_triggers[trigger.id]
        self._active_triggers[trigger.id] = new_state
        logger.info(
            "Manual trigger '%s' toggled to %s",
            trigger.id,
            "ACTIVE" if new_state else "INACTIVE",
        )
        for callback in self._callbacks:
            callback(trigger.id, new_state)

    def on_toggle(self, callback: Callable[[str, bool], None]) -> None:
        """Register a callback for trigger state changes.

        Callback receives (trigger_id, is_active).
        """
        self._callbacks.append(callback)

    def get_active_triggers(self) -> List[str]:
        """Get list of currently active trigger IDs."""
        return [tid for tid, active in self._active_triggers.items() if active]

    def is_active(self, trigger_id: str) -> bool:
        """Check if a specific trigger is currently active."""
        return self._active_triggers.get(trigger_id, False)

    def simulate_press(self, trigger_id: str) -> None:
        """Simulate a button press (for testing/simulation mode)."""
        if trigger_id in self._triggers:
            self._handle_press(self._triggers[trigger_id])

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        if not self._simulate:
            for trigger in self._triggers.values():
                GPIO.remove_event_detect(trigger.gpio_pin)
                GPIO.cleanup(trigger.gpio_pin)
