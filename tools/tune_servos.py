"""Interactive servo tuning tool for blast gate calibration.

Connects to the PCA9685 and lets you adjust servo angles in real-time
to find the correct open/close positions for each gate.

Usage:
  sudo /home/neildorin/Pi-DCC/.venv/bin/python tools/tune_servos.py

Controls:
  - Select a channel (0-15)
  - Type an angle (0-180) to move the servo
  - Use +/- to adjust by 1 degree
  - Type 'save' to print the current angles for config.json
"""

import sys

try:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    from adafruit_motor import servo
except ImportError:
    print("ERROR: Adafruit libraries not available. Run on the Raspberry Pi.")
    sys.exit(1)


def main():
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50

    print("=== Pi-DCC Servo Tuning Tool ===")
    print()
    print("Commands:")
    print("  ch <n>        - Select PCA9685 channel (0-15)")
    print("  <angle>       - Move to angle (0-180)")
    print("  +             - Increase angle by 1")
    print("  -             - Decrease angle by 1")
    print("  +5 / -5       - Increase/decrease by 5")
    print("  +10 / -10     - Increase/decrease by 10")
    print("  min <us>      - Set min pulse width (default 500)")
    print("  max <us>      - Set max pulse width (default 2500)")
    print("  sweep         - Sweep 0 → 180 → 0")
    print("  off           - Disable servo (stop sending pulses)")
    print("  q             - Quit")
    print()

    channel = 0
    current_angle = 90
    min_pulse = 500
    max_pulse = 2500
    srv = None

    def make_servo():
        nonlocal srv
        srv = servo.Servo(pca.channels[channel], min_pulse=min_pulse, max_pulse=max_pulse)
        return srv

    def move_to(angle):
        nonlocal current_angle
        angle = max(0, min(180, angle))
        current_angle = angle
        s = make_servo()
        s.angle = angle
        print(f"  Channel {channel}: {angle}° (pulse {min_pulse}-{max_pulse}µs)")

    make_servo()
    print(f"Selected channel {channel}, pulse range {min_pulse}-{max_pulse}µs")
    print()

    while True:
        try:
            cmd = input(f"[ch{channel} @ {current_angle}°] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not cmd:
            continue

        if cmd == "q":
            break

        if cmd.startswith("ch"):
            try:
                channel = int(cmd.split()[1])
                current_angle = 90
                print(f"  Switched to channel {channel}")
                move_to(current_angle)
            except (IndexError, ValueError):
                print("  Usage: ch <0-15>")

        elif cmd.startswith("min"):
            try:
                min_pulse = int(cmd.split()[1])
                print(f"  Min pulse set to {min_pulse}µs")
                move_to(current_angle)
            except (IndexError, ValueError):
                print("  Usage: min <microseconds>")

        elif cmd.startswith("max"):
            try:
                max_pulse = int(cmd.split()[1])
                print(f"  Max pulse set to {max_pulse}µs")
                move_to(current_angle)
            except (IndexError, ValueError):
                print("  Usage: max <microseconds>")

        elif cmd == "sweep":
            import time
            print("  Sweeping 0 → 180 → 0...")
            for a in range(0, 181, 5):
                move_to(a)
                time.sleep(0.1)
            for a in range(180, -1, -5):
                move_to(a)
                time.sleep(0.1)

        elif cmd == "off":
            pca.channels[channel].duty_cycle = 0
            print(f"  Channel {channel} disabled")

        elif cmd.startswith("+") or cmd.startswith("-"):
            try:
                delta = int(cmd)
            except ValueError:
                delta = 1 if cmd == "+" else -1
            move_to(current_angle + delta)

        else:
            try:
                angle = int(cmd)
                move_to(angle)
            except ValueError:
                print(f"  Unknown command: {cmd}")

    pca.deinit()
    print("Done.")


if __name__ == "__main__":
    main()
