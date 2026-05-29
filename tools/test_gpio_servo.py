"""Test a servo directly from the Pi's hardware PWM GPIO pin.

Wiring:
  - Servo signal (orange/white) -> GPIO 12 (pin 32 on the header)
  - Servo power (red)           -> External 5V supply (NOT the Pi's 5V unless it's a micro servo)
  - Servo ground (brown/black)  -> GND (shared between Pi and external supply)

GPIO 12 supports hardware PWM (PWM0) which gives a clean 50Hz signal.

Usage:
  sudo $(which python) tools/test_gpio_servo.py
"""

import time

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("ERROR: RPi.GPIO not available. Run this on the Raspberry Pi.")
    raise SystemExit(1)

SERVO_PIN = 12  # GPIO 12 = physical pin 32 (hardware PWM0)

GPIO.setmode(GPIO.BCM)
GPIO.setup(SERVO_PIN, GPIO.OUT)

# 50Hz = 20ms period, standard for servos
pwm = GPIO.PWM(SERVO_PIN, 50)
pwm.start(0)


def set_angle(angle: float) -> None:
    """Convert angle (0-180) to duty cycle and set it.
    
    At 50Hz (20ms period):
      - 1ms pulse = 5% duty  = ~0 degrees
      - 1.5ms pulse = 7.5% duty = ~90 degrees
      - 2ms pulse = 10% duty = ~180 degrees
    """
    duty = 2.5 + (angle / 180.0) * 10.0  # Maps 0-180 to 2.5%-12.5%
    pwm.ChangeDutyCycle(duty)


try:
    print(f"Testing servo on GPIO {SERVO_PIN} (physical pin 32)")
    print("=" * 40)

    print("Moving to 0 degrees...")
    set_angle(0)
    time.sleep(1)

    print("Moving to 45 degrees...")
    set_angle(45)
    time.sleep(1)

    print("Moving to 90 degrees...")
    set_angle(90)
    time.sleep(1)

    print("Moving to 135 degrees...")
    set_angle(135)
    time.sleep(1)

    print("Moving to 180 degrees...")
    set_angle(180)
    time.sleep(1)

    print("Returning to 0 degrees...")
    set_angle(0)
    time.sleep(1)

    print("\nSweep test (0 -> 180 -> 0)...")
    for a in range(0, 181, 5):
        set_angle(a)
        time.sleep(0.03)
    for a in range(180, -1, -5):
        set_angle(a)
        time.sleep(0.03)

    print("\nDone! Servo test complete.")
    print("If the servo moved, your servo is fine and the issue is with the PCA9685 board.")

finally:
    pwm.ChangeDutyCycle(0)
    pwm.stop()
    GPIO.cleanup()
