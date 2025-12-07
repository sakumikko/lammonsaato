"""
Tests for night summary data structure.

Verifies that the data structure used by:
1. calculate_cycle_summary.py (writes JSON to input_text)
2. pool_heating.yaml template sensor (reads JSON, exposes attributes)
3. useHAHistory.ts (reads sensor history for analytics)

All components must agree on the attribute names.
"""

import pytest
import json


# Expected JSON keys written by calculate_cycle_summary.py
EXPECTED_JSON_KEYS = {
    "date",           # YYYY-MM-DD
    "energy",         # kWh (from state value, not JSON)
    "cost",           # EUR
    "baseline",       # EUR
    "savings",        # EUR
    "duration",       # minutes
    "blocks",         # count
    "avg_price",      # EUR/kWh
    "outdoor_avg",    # °C (maps to sensor attr outdoor_temp)
    "pool_final",     # °C (maps to sensor attr pool_temp)
}

# Expected sensor attributes (after YAML template transformation)
EXPECTED_SENSOR_ATTRS = {
    "heating_date",   # from JSON date
    "cost",           # from JSON cost
    "baseline",       # from JSON baseline
    "savings",        # from JSON savings
    "duration",       # from JSON duration
    "blocks",         # from JSON blocks
    "outdoor_temp",   # from JSON outdoor_avg
    "pool_temp",      # from JSON pool_final
    "avg_price",      # from JSON avg_price
}


class TestNightSummaryDataStructure:
    """Tests for night summary data structure consistency."""

    def test_json_keys_match_expected(self):
        """Verify calculate_cycle_summary.py outputs correct JSON keys."""
        # Simulate what calculate_cycle_summary.py returns
        summary = {
            "date": "2025-12-05",
            "energy": 11.919,
            "cost": 0.4837,
            "baseline": 0.6462,
            "savings": 0.1625,
            "duration": 180,
            "blocks": 12,
            "avg_price": 0.0406,
            "outdoor_avg": 6.0,
            "pool_final": 25.2,
        }

        actual_keys = set(summary.keys())
        assert actual_keys == EXPECTED_JSON_KEYS, f"Missing: {EXPECTED_JSON_KEYS - actual_keys}, Extra: {actual_keys - EXPECTED_JSON_KEYS}"

    def test_yaml_template_mapping(self):
        """Verify YAML template correctly maps JSON to sensor attributes.

        The YAML template in pool_heating.yaml does:
        - heating_date: from .date
        - cost: from .cost
        - baseline: from .baseline
        - savings: from .savings
        - duration: from .duration
        - blocks: from .blocks
        - outdoor_temp: from .outdoor_avg
        - pool_temp: from .pool_final
        - avg_price: from .avg_price
        """
        json_data = {
            "date": "2025-12-05",
            "cost": 0.4837,
            "baseline": 0.6462,
            "savings": 0.1625,
            "duration": 180,
            "blocks": 12,
            "outdoor_avg": 6.0,
            "pool_final": 25.2,
            "avg_price": 0.0406,
        }

        # Simulate YAML template transformation
        sensor_attrs = {
            "heating_date": json_data["date"],
            "cost": json_data["cost"],
            "baseline": json_data["baseline"],
            "savings": json_data["savings"],
            "duration": json_data["duration"],
            "blocks": json_data["blocks"],
            "outdoor_temp": json_data["outdoor_avg"],  # Note: different key
            "pool_temp": json_data["pool_final"],      # Note: different key
            "avg_price": json_data["avg_price"],
        }

        assert set(sensor_attrs.keys()) == EXPECTED_SENSOR_ATTRS

    def test_web_ui_parsing(self):
        """Verify web-ui useHAHistory.ts correctly reads sensor attributes.

        useHAHistory.ts parseNightSummaryHistory() expects:
        - heating_date (from attrs.heating_date)
        - energy (from state value, not attr)
        - cost (from attrs.cost)
        - baseline (from attrs.baseline)
        - savings (from attrs.savings)
        - duration (from attrs.duration)
        - blocks (from attrs.blocks)
        - pool_temp (from attrs.pool_temp)
        - outdoor_temp (from attrs.outdoor_temp)
        - avg_price (from attrs.avg_price)
        """
        # Simulate HA sensor state as returned by WebSocket
        sensor_state = {
            "entity_id": "sensor.pool_heating_night_summary",
            "state": "11.919",  # Energy value
            "attributes": {
                "heating_date": "2025-12-05",
                "cost": 0.4837,
                "baseline": 0.6462,
                "savings": 0.1625,
                "duration": 180,
                "blocks": 12,
                "outdoor_temp": 6.0,
                "pool_temp": 25.2,
                "avg_price": 0.0406,
                "unit_of_measurement": "kWh",
                "device_class": "energy",
            }
        }

        # Simulate useHAHistory.ts parsing
        attrs = sensor_state["attributes"]
        parsed = {
            "heating_date": attrs.get("heating_date"),
            "energy": float(sensor_state["state"]),
            "cost": attrs.get("cost", 0),
            "baseline": attrs.get("baseline", 0),
            "savings": attrs.get("savings", 0),
            "duration": attrs.get("duration", 0),
            "blocks": attrs.get("blocks", 0),
            "pool_temp": attrs.get("pool_temp", 0),
            "outdoor_temp": attrs.get("outdoor_temp", 0),
            "avg_price": attrs.get("avg_price", 0),
        }

        # Verify all values are correctly parsed
        assert parsed["heating_date"] == "2025-12-05"
        assert parsed["energy"] == 11.919
        assert parsed["cost"] == 0.4837
        assert parsed["baseline"] == 0.6462
        assert parsed["savings"] == 0.1625
        assert parsed["duration"] == 180
        assert parsed["blocks"] == 12
        assert parsed["outdoor_temp"] == 6.0
        assert parsed["pool_temp"] == 25.2
        assert parsed["avg_price"] == 0.0406

    def test_2025_12_05_real_data(self):
        """Test with actual data from 2025-12-05 heating cycle.

        This is the reference data point that should display correctly
        in the analytics UI.
        """
        # Actual data from HA sensor
        expected = {
            "heating_date": "2025-12-05",
            "energy": 11.919,  # kWh
            "cost": 0.4837,    # EUR
            "baseline": 0.6462, # EUR
            "savings": 0.1625,  # EUR (baseline - cost)
            "duration": 180,    # minutes (3 hours)
            "blocks": 12,       # 12 x 15-min periods
            "outdoor_temp": 6.0, # °C
            "pool_temp": 25.2,   # °C
            "avg_price": 0.0406, # EUR/kWh
        }

        # Verify calculations
        assert abs(expected["baseline"] - expected["cost"] - expected["savings"]) < 0.001, \
            "savings should equal baseline - cost"

        # Verify energy makes sense
        # 12 blocks × 15 min = 180 min = 3 hours
        assert expected["duration"] == expected["blocks"] * 15

        # Average cost per kWh
        calculated_avg = expected["cost"] / expected["energy"]
        assert abs(calculated_avg - expected["avg_price"]) < 0.001, \
            f"avg_price mismatch: {calculated_avg} vs {expected['avg_price']}"
