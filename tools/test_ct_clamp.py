#!/usr/bin/env python3
"""Test script for CT clamp on ADS1115 channel A0.

Reads the CT sensor continuously and displays raw voltage,
RMS voltage, and estimated current in amps.
"""

import math
import time
import sys

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.ads1x15 import Mode
    from adafruit_ads1x15.analog_in import AnalogIn
except ImportError:
    print("ERROR: Required libraries not found.")
    print("Install with: pip install adafruit-circuitpython-ads1x15")
    sys.exit(1)

# Configuration
I2C_ADDRESS = 0x48
ADC_CHANNEL = 0  # A0 (channel index)
RMS_SAMPLES = 50
SAMPLE_DELAY = 0.001  # 1ms between samples
CT_CALIBRATION_FACTOR = 30.0  # SCT-013-030: 30A/1V
READ_INTERVAL = 1.0  # seconds between readings


def main():
    print("CT Clamp Test - ADS1115 Channel A0")
    print("=" * 50)
    print(f"I2C Address: {hex(I2C_ADDRESS)}")
    print(f"CT Calibration Factor: {CT_CALIBRATION_FACTOR} A/V")
    print(f"RMS Samples per reading: {RMS_SAMPLES}")
    print("=" * 50)
    print()

    # Initialize I2C and ADC
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=I2C_ADDRESS)
        ads.gain = 1  # +/- 4.096V range
        chan = AnalogIn(ads, ADS.P0)
        print("ADS1115 initialized successfully.")
    except Exception as e:
        print(f"ERROR: Failed to initialize ADS1115: {e}")
        sys.exit(1)

    print()
    print(f"{'Reading':<8} {'Raw':<8} {'Voltage':<10} {'RMS V':<10} {'Current':<10}")
    print("-" * 50)

    reading_num = 0
    try:
        while True:
            reading_num += 1

            # Collect samples for RMS calculation
            samples = []
            for _ in range(RMS_SAMPLES):
                samples.append(chan.voltage)
                time.sleep(SAMPLE_DELAY)

            # Calculate DC offset (mean) and RMS of AC component
            dc_offset = sum(samples) / len(samples)
            sum_squares = sum((s - dc_offset) ** 2 for s in samples)
            rms_voltage = math.sqrt(sum_squares / RMS_SAMPLES)

            # Convert to current
            current_amps = rms_voltage * CT_CALIBRATION_FACTOR

            # Get a single instantaneous reading for display
            raw_value = chan.value
            instant_voltage = chan.voltage

            print(
                f"{reading_num:<8} "
                f"{raw_value:<8} "
                f"{instant_voltage:<10.4f} "
                f"{rms_voltage:<10.4f} "
                f"{current_amps:<10.2f} A"
            )

            time.sleep(READ_INTERVAL)

    except KeyboardInterrupt:
        print("\n\nTest stopped by user.")


if __name__ == "__main__":
    main()
