#!/usr/bin/env python3
"""Test script for CT clamp on ADS1115 channel A0.

Reads the CT sensor continuously and displays raw voltage,
RMS voltage, and estimated current in amps.

Includes a calibration mode: run with --calibrate <known_amps> to
calculate the correction factor for your setup.
"""

import math
import time
import sys
import argparse

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
except ImportError:
    print("ERROR: Required libraries not found.")
    print("Install with: pip install adafruit-circuitpython-ads1x15")
    sys.exit(1)

# Configuration
I2C_ADDRESS = 0x48
ADC_CHANNEL = 0  # A0 (channel index)
RMS_SAMPLES = 200  # More samples for better accuracy over multiple AC cycles
SAMPLE_DELAY = 0.0005  # 0.5ms between samples (~100ms total capture window)
CT_CALIBRATION_FACTOR = 111.0  # SCT-013-000: 100A/50mA, turns ratio 2000:1
# Formula: turns_ratio / burden_ohms = 2000 / R_burden
# With 2x 10Ω bias resistors, effective burden depends on wiring.
# Use --calibrate <known_amps> to find the exact value for your setup.
READ_INTERVAL = 1.0  # seconds between readings

# Correction multiplier. Set to 1.0 with a DC bias circuit (full waveform visible).
# Adjust via --calibrate mode if readings don't match known load.
HALF_WAVE_CORRECTION = 1.0


def read_rms(chan, num_samples, sample_delay):
    """Read RMS voltage from the CT sensor."""
    samples = []
    for _ in range(num_samples):
        samples.append(chan.voltage)
        time.sleep(sample_delay)

    dc_offset = sum(samples) / len(samples)
    sum_squares = sum((s - dc_offset) ** 2 for s in samples)
    rms_voltage = math.sqrt(sum_squares / num_samples)
    return rms_voltage, dc_offset, samples


def calibrate_mode(chan, known_amps):
    """Run calibration to find the correction factor."""
    print(f"\nCALIBRATION MODE - Known load: {known_amps} A")
    print("=" * 50)
    print("Turn ON the tool now. Taking 10 readings...")
    print()
    time.sleep(2)

    readings = []
    for i in range(10):
        rms_voltage, dc_offset, _ = read_rms(chan, RMS_SAMPLES, SAMPLE_DELAY)
        raw_current = rms_voltage * CT_CALIBRATION_FACTOR
        readings.append(raw_current)
        print(f"  Reading {i+1}: RMS V={rms_voltage:.4f}, Raw current={raw_current:.2f} A")
        time.sleep(0.5)

    avg_raw = sum(readings) / len(readings)
    correction_factor = known_amps / avg_raw if avg_raw > 0 else 0

    print()
    print("=" * 50)
    print(f"Average raw current reading: {avg_raw:.3f} A")
    print(f"Known actual current:        {known_amps:.1f} A")
    print(f"Correction factor:           {correction_factor:.4f}")
    print()
    print(f"Effective calibration = CT_CALIBRATION_FACTOR * correction")
    print(f"                      = {CT_CALIBRATION_FACTOR} * {correction_factor:.4f}")
    print(f"                      = {CT_CALIBRATION_FACTOR * correction_factor:.2f}")
    print()
    print("Update CT_CALIBRATION_FACTOR in this script and in")
    print("pi_dcc/hardware/adc.py to use the corrected value.")


def monitor_mode(chan, correction):
    """Continuous monitoring mode."""
    print(f"{'Reading':<8} {'DC Bias':<10} {'RMS V':<10} {'Current':<10}")
    print("-" * 50)

    reading_num = 0
    try:
        while True:
            reading_num += 1
            rms_voltage, dc_offset, _ = read_rms(chan, RMS_SAMPLES, SAMPLE_DELAY)
            current_amps = rms_voltage * CT_CALIBRATION_FACTOR * correction

            print(
                f"{reading_num:<8} "
                f"{dc_offset:<10.4f} "
                f"{rms_voltage:<10.4f} "
                f"{current_amps:<10.2f} A"
            )

            time.sleep(READ_INTERVAL)

    except KeyboardInterrupt:
        print("\n\nTest stopped by user.")


def main():
    parser = argparse.ArgumentParser(description="CT Clamp Test & Calibration")
    parser.add_argument(
        "--calibrate", type=float, metavar="AMPS",
        help="Run calibration mode with a known current draw (in amps)"
    )
    parser.add_argument(
        "--correction", type=float, default=HALF_WAVE_CORRECTION,
        help=f"Correction multiplier (default: {HALF_WAVE_CORRECTION:.4f} for half-wave)"
    )
    parser.add_argument(
        "--gain", type=int, choices=[1, 2, 4, 8, 16], default=1,
        help="ADS1115 gain (1=±4.096V, 2=±2.048V, 4=±1.024V, 8=±0.512V, 16=±0.256V)"
    )
    args = parser.parse_args()

    print("CT Clamp Test - ADS1115 Channel A0")
    print("=" * 50)
    print(f"I2C Address: {hex(I2C_ADDRESS)}")
    print(f"CT Factor: {CT_CALIBRATION_FACTOR} A/V")
    print(f"Correction: {args.correction:.4f}x")
    print(f"Effective: {CT_CALIBRATION_FACTOR * args.correction:.2f} A/V")
    print(f"ADC Gain: {args.gain}")
    print(f"Samples: {RMS_SAMPLES} @ {SAMPLE_DELAY*1000:.1f}ms interval")
    print("=" * 50)

    # Initialize I2C and ADC
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=I2C_ADDRESS)
        ads.gain = args.gain
        chan = AnalogIn(ads, ADC_CHANNEL)
        print("ADS1115 initialized successfully.\n")
    except Exception as e:
        print(f"ERROR: Failed to initialize ADS1115: {e}")
        sys.exit(1)

    if args.calibrate:
        calibrate_mode(chan, args.calibrate)
    else:
        monitor_mode(chan, args.correction)


if __name__ == "__main__":
    main()
