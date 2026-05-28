"""Configuration schema definitions using Pydantic models."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DustCollectorConfig(BaseModel):
    """Configuration for the dust collector unit."""

    relay_pin: int = Field(description="GPIO pin controlling the dust collector relay")
    shutdown_delay_seconds: int = Field(
        default=10,
        description="Seconds to keep collector running after last tool stops",
    )
    max_cfm: float = Field(description="Maximum CFM rating of the dust collector")
    motor_hp: float = Field(description="Horsepower of the dust collector motor")
    filter_clean_interval_hours: float = Field(
        default=50.0,
        description="Cumulative runtime hours before filter cleaning is recommended",
    )


class ADCBoardConfig(BaseModel):
    """Configuration for an ADS1115 ADC board."""

    address: str = Field(
        default="0x48", description="I2C address of the ADS1115 board"
    )
    bus: int = Field(default=1, description="I2C bus number")


class PWMBoardConfig(BaseModel):
    """Configuration for a PCA9685 PWM driver board."""

    address: str = Field(
        default="0x40", description="I2C address of the PCA9685 board"
    )
    bus: int = Field(default=1, description="I2C bus number")


class NeoPixelConfig(BaseModel):
    """Configuration for the NeoPixel LED strip."""

    gpio_pin: int = Field(default=18, description="GPIO pin for NeoPixel data line")
    led_count: int = Field(description="Total number of LEDs in the strip")
    brightness: float = Field(
        default=0.5, ge=0.0, le=1.0, description="LED brightness (0.0 to 1.0)"
    )


class AirflowConfig(BaseModel):
    """Configuration for airflow calculations."""

    target_velocity_fpm: float = Field(
        default=4000.0,
        description="Target air velocity in feet per minute for dust collection",
    )
    minimum_cfm_ratio: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum ratio of required CFM that must be met before opening supplemental gates",
    )


class BlastGateConfig(BaseModel):
    """Configuration for a single blast gate."""

    id: str = Field(description="Unique identifier for this blast gate")
    diameter_inches: float = Field(description="Diameter of the blast gate in inches")
    pwm_board: int = Field(description="Index of the PCA9685 board controlling this gate's servo")
    pwm_channel: int = Field(description="PWM channel on the board for this gate's servo")
    led_index: int = Field(description="Index of this gate's LED in the NeoPixel strip")
    servo_open_angle: int = Field(default=90, description="Servo angle for gate open position")
    servo_close_angle: int = Field(default=0, description="Servo angle for gate closed position")


class PipeNodeConfig(BaseModel):
    """Configuration for a node in the piping network tree."""

    id: str = Field(description="Unique identifier for this pipe node")
    pipe_diameter_inches: float = Field(description="Diameter of the pipe at this node in inches")
    blast_gate: Optional[BlastGateConfig] = Field(
        default=None, description="Blast gate at this node, if any"
    )
    children: List["PipeNodeConfig"] = Field(
        default_factory=list, description="Child nodes in the piping tree"
    )


class ToolConfig(BaseModel):
    """Configuration for a tool connected to the dust collection system."""

    id: str = Field(description="Unique identifier for this tool")
    name: str = Field(description="Human-readable name of the tool")
    adc_board: int = Field(description="Index of the ADS1115 board for this tool's CT sensor")
    adc_channel: int = Field(description="ADC channel for this tool's CT sensor")
    current_threshold_amps: float = Field(
        default=2.0,
        description="Current threshold in amps above which the tool is considered running",
    )
    required_cfm: float = Field(
        description="CFM required by this tool for proper dust collection"
    )
    node_ids: List[str] = Field(
        description="IDs of the pipe nodes where this tool connects to the network. "
        "A tool with multiple dust ports (e.g. table saw with blade guard and bottom port) "
        "will have multiple node_ids — all gates on all paths will be opened."
    )


class ManualTriggerConfig(BaseModel):
    """Configuration for a manually-triggered gate (button toggle).

    Used for gates without CT-sensor-detected tools, such as a floor sweep
    vacuum hose or a lathe where current detection is not desirable.
    Pressing the button toggles the associated gates open/closed and
    starts/stops the dust collector.
    """

    id: str = Field(description="Unique identifier for this trigger")
    name: str = Field(description="Human-readable name")
    gpio_pin: int = Field(description="GPIO pin connected to the trigger button")
    node_ids: List[str] = Field(
        description="IDs of pipe nodes whose gates should open when triggered"
    )
    required_cfm: float = Field(
        description="CFM required when this trigger is active"
    )


class AppConfig(BaseModel):
    """Top-level application configuration."""

    dust_collector: DustCollectorConfig
    airflow: AirflowConfig = Field(default_factory=AirflowConfig)
    adc_boards: List[ADCBoardConfig] = Field(default_factory=list)
    pwm_boards: List[PWMBoardConfig] = Field(default_factory=list)
    neopixel: NeoPixelConfig
    polling_interval_ms: int = Field(
        default=100, description="Sensor polling interval in milliseconds"
    )
    network: PipeNodeConfig = Field(description="Root node of the piping network tree")
    tools: List[ToolConfig] = Field(default_factory=list)
    manual_triggers: List[ManualTriggerConfig] = Field(default_factory=list)
