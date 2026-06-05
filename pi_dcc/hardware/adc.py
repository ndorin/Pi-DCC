"""ADC reader for CT current sensors via ADS1115."""

from __future__ import annotations

import logging
import math
import time

from pi_dcc.config.schema import ADCBoardConfig

logger = logging.getLogger(__name__)

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn

    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False


class ADCReader:
    """Reads CT current sensors via ADS1115 ADC boards."""

    # Number of samples for RMS calculation
    RMS_SAMPLES = 20

    # Max I2C retries for transient bus errors
    I2C_RETRIES = 3
    I2C_RETRY_DELAY = 0.05  # 50ms between retries

    # Reference voltage for CT sensor calibration
    # SCT-013-030: 30A/1V, with burden resistor producing voltage proportional to current
    CT_CALIBRATION_FACTOR = 300

    def __init__(self, boards_config: list[ADCBoardConfig], simulate: bool = False):
        self._simulate = simulate or not HAS_HARDWARE
        self._boards: list = []
        self._simulated_values: dict[tuple[int, int], float] = {}

        if not self._simulate:
            self._init_hardware(boards_config)
        else:
            logger.info("ADC reader running in simulation mode")

    def _init_hardware(self, boards_config: list[ADCBoardConfig]) -> None:
        """Initialize ADS1115 hardware boards."""
        i2c = busio.I2C(board.SCL, board.SDA)
        for cfg in boards_config:
            address = int(cfg.address, 16)
            ads = ADS.ADS1115(i2c, address=address)
            self._boards.append(ads)
            logger.info("Initialized ADS1115 at address %s on bus %d", cfg.address, cfg.bus)

    def read_current_amps(self, board_index: int, channel: int) -> float:
        """Read the RMS current from a CT sensor.

        Args:
            board_index: Index of the ADS1115 board.
            channel: ADC channel (0-3).

        Returns:
            RMS current in amps.
        """
        if self._simulate:
            return self._simulated_values.get((board_index, channel), 0.0)

        ads = self._boards[board_index]
        chan = AnalogIn(ads, channel)

        for attempt in range(self.I2C_RETRIES):
            try:
                # Sample the waveform
                samples = []
                for _ in range(self.RMS_SAMPLES):
                    samples.append(chan.voltage)

                # Subtract DC bias (mean) to isolate AC component
                dc_offset = sum(samples) / len(samples)
                sum_squares = sum((s - dc_offset) ** 2 for s in samples)

                rms_voltage = math.sqrt(sum_squares / self.RMS_SAMPLES)
                return rms_voltage * self.CT_CALIBRATION_FACTOR
            except OSError as e:
                if attempt < self.I2C_RETRIES - 1:
                    logger.warning("I2C read error (attempt %d/%d): %s", attempt + 1, self.I2C_RETRIES, e)
                    time.sleep(self.I2C_RETRY_DELAY)
                else:
                    logger.error("I2C read failed after %d attempts: %s", self.I2C_RETRIES, e)
                    return 0.0

    def is_tool_running(
        self, board_index: int, channel: int, threshold_amps: float
    ) -> bool:
        """Check if a tool is drawing current above its threshold.

        Args:
            board_index: Index of the ADS1115 board.
            channel: ADC channel (0-3).
            threshold_amps: Current threshold for tool detection.

        Returns:
            True if measured current exceeds threshold.
        """
        current = self.read_current_amps(board_index, channel)
        running = current > threshold_amps
        if running:
            logger.debug("Tool on board %d ch %d: %.2f A (threshold %.2f)", board_index, channel, current, threshold_amps)
        return running

    def set_simulated_current(
        self, board_index: int, channel: int, amps: float
    ) -> None:
        """Set a simulated current value for testing.

        Only works in simulation mode.
        """
        if self._simulate:
            self._simulated_values[(board_index, channel)] = amps
