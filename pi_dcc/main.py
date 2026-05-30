"""Pi-DCC: Main entry point for the Dust Collection Control application."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import threading

from pi_dcc.config.loader import load_config
from pi_dcc.controller.engine import ControlEngine
from pi_dcc.hardware.adc import ADCReader
from pi_dcc.hardware.buttons import ButtonController
from pi_dcc.hardware.display import DisplayController
from pi_dcc.hardware.leds import LEDController
from pi_dcc.hardware.relay import RelayController
from pi_dcc.hardware.servo import ServoController
from pi_dcc.network.model import PipingNetwork
from pi_dcc.web.app import init_app

logger = logging.getLogger("pi_dcc")


class GPIOServoWrapper:
    """Wraps ServoController to intercept specific gates and route to GPIO servo."""

    def __init__(self, pca_controller: ServoController, gpio_servo):
        self._pca = pca_controller
        self._gpio = gpio_servo
        self._gate_states: dict[str, bool] = {}

    def open_gate(self, gate):
        if self._gpio.has_gate(gate.id):
            self._gpio.set_angle(gate, gate.servo_open_angle)
        else:
            self._pca.open_gate(gate)
        self._gate_states[gate.id] = True

    def close_gate(self, gate):
        if self._gpio.has_gate(gate.id):
            self._gpio.set_angle(gate, gate.servo_close_angle)
        else:
            self._pca.close_gate(gate)
        self._gate_states[gate.id] = False

    def is_gate_open(self, gate_id: str) -> bool:
        return self._gate_states.get(gate_id, False)

    def get_all_gate_states(self) -> dict[str, bool]:
        return dict(self._gate_states)

    def close_all(self, all_gates):
        for gate in all_gates:
            self.close_gate(gate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pi-DCC: Dust Collection Control for Raspberry Pi"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Path to configuration file (default: config.json)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run in simulation mode (no hardware required)",
    )
    parser.add_argument(
        "--simulate-adc",
        action="store_true",
        help="Simulate only the ADC (CT sensors)",
    )
    parser.add_argument(
        "--simulate-buttons",
        action="store_true",
        help="Simulate only the button inputs",
    )
    parser.add_argument(
        "--simulate-servos",
        action="store_true",
        help="Simulate only the servo/PCA9685 outputs",
    )
    parser.add_argument(
        "--simulate-leds",
        action="store_true",
        help="Simulate only the NeoPixel LEDs",
    )
    parser.add_argument(
        "--simulate-relay",
        action="store_true",
        help="Simulate only the relay output",
    )
    parser.add_argument(
        "--simulate-display",
        action="store_true",
        help="Simulate only the 7-segment countdown display",
    )
    parser.add_argument(
        "--gpio-servo",
        type=str,
        action="append",
        default=[],
        metavar="GATE_ID:GPIO_PIN",
        help="Map a blast gate to a GPIO pin for direct servo control (e.g. gate_floor_sweep:12). Can be repeated.",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=5000,
        help="Port for the web dashboard (default: 5000)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    return parser.parse_args()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_web_server(engine: ControlEngine, port: int) -> None:
    """Run the Flask web server in a background thread."""
    flask_app = init_app(engine)
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)


async def main_async(args: argparse.Namespace) -> None:
    # Load configuration
    config = load_config(args.config)
    logger.info("Configuration loaded successfully")

    # Build piping network
    network = PipingNetwork.from_config(config.network)
    logger.info("Piping network built with %d total gates", len(network.get_all_gates()))

    # Initialize hardware
    simulate = args.simulate
    simulate_adc = simulate or args.simulate_adc
    simulate_buttons = simulate or args.simulate_buttons
    simulate_servos = simulate or args.simulate_servos
    simulate_leds = simulate or args.simulate_leds
    simulate_relay = simulate or args.simulate_relay
    adc = ADCReader(config.adc_boards, simulate=simulate_adc)
    servos = ServoController(config.pwm_boards, simulate=simulate_servos)
    relay = RelayController(config.dust_collector.relay_pin, simulate=simulate_relay)
    leds = LEDController(config.neopixel, simulate=simulate_leds)
    buttons = ButtonController(config.manual_triggers, simulate=simulate_buttons)

    # Initialize countdown display (optional)
    display = None
    simulate_display = simulate or args.simulate_display
    if config.display:
        display = DisplayController(
            data_pin=config.display.data_pin,
            clock_pin=config.display.clock_pin,
            latch_pin=config.display.latch_pin,
            simulate=simulate_display,
        )

    # Apply GPIO servo overrides for testing
    if args.gpio_servo:
        from pi_dcc.hardware.gpio_servo import GPIOServoController
        gpio_servo_map = {}
        for mapping in args.gpio_servo:
            gate_id, pin = mapping.rsplit(':', 1)
            gpio_servo_map[gate_id] = int(pin)
        gpio_servo = GPIOServoController(gpio_servo_map)
        servos = GPIOServoWrapper(servos, gpio_servo)

    # Create control engine
    engine = ControlEngine(
        config=config,
        network=network,
        adc=adc,
        servos=servos,
        relay=relay,
        leds=leds,
        buttons=buttons,
        display=display,
    )

    # Start web server in background thread
    web_thread = threading.Thread(
        target=run_web_server,
        args=(engine, args.web_port),
        daemon=True,
    )
    web_thread.start()
    logger.info("Web dashboard available at http://0.0.0.0:%d", args.web_port)

    # Handle shutdown signals
    loop = asyncio.get_running_loop()

    def shutdown_handler():
        logger.info("Shutdown signal received")
        asyncio.ensure_future(engine.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_handler)

    # Start the control loop
    try:
        await engine.start()
    except asyncio.CancelledError:
        pass
    finally:
        await engine.stop()


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    logger.info("Pi-DCC starting (simulate=%s)", args.simulate)

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
