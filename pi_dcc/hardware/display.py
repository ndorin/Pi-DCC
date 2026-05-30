"""7-segment display driver via 74HC595 shift register.

Drives a single-digit common-anode 7-segment display (5011AS) using a 74HC595
shift register. Only requires 3 GPIO pins (data, clock, latch).

Display encoding for countdown:
  - 15 = "5." (dot = tens digit)
  - 10 = "0."
  - 9 = "9" (no dot)
  - 1 = "1"
  - 0 or off = blank
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO

    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False


# Segment bit positions in shift register: QA=a, QB=b, QC=c, QD=d, QE=e, QF=f, QG=g, QH=dp
# For common anode: 0 = segment ON, 1 = segment OFF
# Bit order (MSB first into shift register): DP, g, f, e, d, c, b, a

#        a
#       ---
#    f |   | b
#       -g-
#    e |   | c
#       ---
#        d    .DP

# Common anode digit patterns (0 = ON, 1 = OFF)
# Bits: DP g f e d c b a
_DIGITS_CA = {
    0: 0b11000000,  # a,b,c,d,e,f on
    1: 0b11111001,  # b,c on
    2: 0b10100100,  # a,b,d,e,g on
    3: 0b10110000,  # a,b,c,d,g on
    4: 0b10011001,  # b,c,f,g on
    5: 0b10010010,  # a,c,d,f,g on
    6: 0b10000010,  # a,c,d,e,f,g on
    7: 0b11111000,  # a,b,c on
    8: 0b10000000,  # all on
    9: 0b10010000,  # a,b,c,d,f,g on
}

# Blank display (all segments off for common anode = all bits high)
_BLANK = 0b11111111

# Decimal point mask: clear DP bit (bit 7) to turn it on
_DP_MASK = 0b01111111


class DisplayController:
    """Controls a 7-segment display via 74HC595 shift register."""

    def __init__(
        self,
        data_pin: int,
        clock_pin: int,
        latch_pin: int,
        simulate: bool = False,
    ):
        self._data_pin = data_pin
        self._clock_pin = clock_pin
        self._latch_pin = latch_pin
        self._simulate = simulate or not HAS_HARDWARE
        self._current_value: int | None = None

        if not self._simulate:
            self._init_hardware()
        else:
            logger.info("Display controller running in simulation mode")

    def _init_hardware(self) -> None:
        """Initialize GPIO pins for the shift register."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._data_pin, GPIO.OUT)
        GPIO.setup(self._clock_pin, GPIO.OUT)
        GPIO.setup(self._latch_pin, GPIO.OUT)
        GPIO.output(self._data_pin, GPIO.LOW)
        GPIO.output(self._clock_pin, GPIO.LOW)
        GPIO.output(self._latch_pin, GPIO.LOW)
        # Start with display blank
        self._shift_out(_BLANK)
        logger.info(
            "Initialized 7-segment display (data=%d, clock=%d, latch=%d)",
            self._data_pin, self._clock_pin, self._latch_pin,
        )

    def _shift_out(self, data: int) -> None:
        """Shift 8 bits out to the 74HC595 (MSB first)."""
        if self._simulate:
            return

        GPIO.output(self._latch_pin, GPIO.LOW)
        for i in range(7, -1, -1):
            bit = (data >> i) & 1
            GPIO.output(self._data_pin, bit)
            GPIO.output(self._clock_pin, GPIO.HIGH)
            GPIO.output(self._clock_pin, GPIO.LOW)
        GPIO.output(self._latch_pin, GPIO.HIGH)

    def show_countdown(self, seconds: int) -> None:
        """Display a countdown value (0-19 seconds).

        For values >= 10: shows ones digit with decimal point (dot = tens)
        For values 1-9: shows digit without decimal point
        For 0: shows blank
        """
        if seconds <= 0:
            self.blank()
            return

        if seconds >= 10:
            digit = seconds % 10
            pattern = _DIGITS_CA[digit] & _DP_MASK  # Add decimal point
        else:
            digit = seconds
            pattern = _DIGITS_CA[digit]

        if self._current_value != seconds:
            self._current_value = seconds
            self._shift_out(pattern)
            if self._simulate:
                dp = "." if seconds >= 10 else ""
                logger.debug("SIM: Display showing %d%s", digit, dp)

    def blank(self) -> None:
        """Turn off all segments."""
        if self._current_value is not None:
            self._current_value = None
            self._shift_out(_BLANK)
            if self._simulate:
                logger.debug("SIM: Display blank")

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        self.blank()
        if not self._simulate:
            GPIO.cleanup(self._data_pin)
            GPIO.cleanup(self._clock_pin)
            GPIO.cleanup(self._latch_pin)
