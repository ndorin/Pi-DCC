"""Tests for configuration loading and validation."""

import json
import tempfile
from pathlib import Path

import pytest

from pi_dcc.config.loader import load_config
from pi_dcc.config.schema import AppConfig


@pytest.fixture
def valid_config_data():
    """Minimal valid configuration."""
    return {
        "dust_collector": {
            "relay_pin": 17,
            "shutdown_delay_seconds": 10,
            "max_cfm": 800,
            "motor_hp": 2.0,
            "filter_clean_interval_hours": 50,
        },
        "adc_boards": [{"address": "0x48", "bus": 1}],
        "pwm_boards": [{"address": "0x40", "bus": 1}],
        "neopixel": {"gpio_pin": 18, "led_count": 2, "brightness": 0.5},
        "network": {
            "id": "collector",
            "pipe_diameter_inches": 6,
            "children": [
                {
                    "id": "tool_port",
                    "pipe_diameter_inches": 4,
                    "blast_gate": {
                        "id": "gate_1",
                        "diameter_inches": 4,
                        "pwm_board": 0,
                        "pwm_channel": 0,
                        "led_index": 0,
                        "servo_open_angle": 90,
                        "servo_close_angle": 0,
                    },
                    "children": [],
                }
            ],
        },
        "tools": [
            {
                "id": "saw",
                "name": "Table Saw",
                "adc_board": 0,
                "adc_channel": 0,
                "current_threshold_amps": 2.0,
                "required_cfm": 350,
                "node_ids": ["tool_port"],
            }
        ],
    }


@pytest.fixture
def config_file(valid_config_data, tmp_path):
    """Write config data to a temporary file."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps(valid_config_data))
    return path


def test_load_valid_config(config_file):
    config = load_config(config_file)
    assert isinstance(config, AppConfig)
    assert config.dust_collector.max_cfm == 800
    assert config.dust_collector.motor_hp == 2.0
    assert config.dust_collector.filter_clean_interval_hours == 50
    assert len(config.tools) == 1
    assert config.tools[0].id == "saw"


def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.json")


def test_load_config_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not valid json {{{")
    with pytest.raises(json.JSONDecodeError):
        load_config(path)


def test_load_config_missing_required_field(valid_config_data, tmp_path):
    del valid_config_data["dust_collector"]["relay_pin"]
    path = tmp_path / "config.json"
    path.write_text(json.dumps(valid_config_data))
    with pytest.raises(Exception):  # pydantic.ValidationError
        load_config(path)


def test_load_config_invalid_tool_node_id(valid_config_data, tmp_path):
    valid_config_data["tools"][0]["node_ids"] = ["nonexistent_node"]
    path = tmp_path / "config.json"
    path.write_text(json.dumps(valid_config_data))
    with pytest.raises(ValueError, match="does not exist in the network tree"):
        load_config(path)


def test_load_config_invalid_adc_board_index(valid_config_data, tmp_path):
    valid_config_data["tools"][0]["adc_board"] = 5
    path = tmp_path / "config.json"
    path.write_text(json.dumps(valid_config_data))
    with pytest.raises(ValueError, match="ADC boards are configured"):
        load_config(path)


def test_load_config_invalid_led_index(valid_config_data, tmp_path):
    valid_config_data["network"]["children"][0]["blast_gate"]["led_index"] = 99
    path = tmp_path / "config.json"
    path.write_text(json.dumps(valid_config_data))
    with pytest.raises(ValueError, match="exceeds neopixel led_count"):
        load_config(path)
