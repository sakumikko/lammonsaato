#!/usr/bin/env python3
"""
Validate that all graphable entities from config files are in entityPresets.ts

This script extracts entity IDs from:
1. scripts/config/thermia_required_entities.yaml (sensors only)
2. homeassistant/packages/pool_heating.yaml (template sensors)

And checks they are all present in:
- web-ui/src/constants/entityPresets.ts

Run: python scripts/standalone/validate_graph_entities.py
Or:  make validate-entities
"""

import re
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent.parent

# Entities that are known to be unavailable (from thermia config)
UNAVAILABLE_ENTITIES = {
    "binary_sensor.alarm_active_class_e",
    "binary_sensor.surplus_heat_temperature_deviation_alarm",
    "number.desired_cooling_temperature_setpoint_mixing_valve_3",
    "sensor.hot_water_directional_valve_position",
    "sensor.queued_demand_second_priority",
}

# Entities that don't make sense to graph (binary, status, etc.)
NON_GRAPHABLE_ENTITIES = {
    "sensor.nordpool_tomorrow_available",  # binary-like
    "sensor.pool_heating_active",  # binary sensor
    "sensor.pool_in_heating_window",  # binary sensor
    "sensor.pool_heating_cost_limit_active",  # binary sensor
    "sensor.pool_heating_block_count",  # integer count
    "sensor.pool_heating_enabled_block_count",  # integer count
    "sensor.pool_next_heating",  # datetime
    "sensor.pool_heating_15min_energy",  # aggregation
    "sensor.pool_heating_night_summary",  # aggregation
}


def extract_thermia_sensors(yaml_path: Path) -> set[str]:
    """Extract sensor entity IDs from thermia_required_entities.yaml"""
    entities = set()
    content = yaml_path.read_text()

    # Match lines like "      - sensor.foo" or "      - number.bar"
    # Only include sensors and numbers (graphable entities)
    pattern = r"^\s*-\s+(sensor\.[a-z0-9_]+|number\.[a-z0-9_]+)"
    for match in re.finditer(pattern, content, re.MULTILINE):
        entity = match.group(1)
        if entity not in UNAVAILABLE_ENTITIES:
            entities.add(entity)

    return entities


def extract_pool_heating_sensors(yaml_path: Path) -> set[str]:
    """Extract template sensor entity IDs from pool_heating.yaml"""
    entities = set()
    content = yaml_path.read_text()

    # Match unique_id definitions in sensor blocks
    # The actual entity_id is based on the name, not unique_id
    # So we need to extract both and use the actual entity names

    # For template sensors, extract unique_id and map to known entity names
    # The unique_id -> entity_id mapping:
    unique_id_to_entity = {
        "pool_return_line_temperature_corrected": "sensor.pool_return_line_temperature_corrected",
        "pool_heat_exchanger_delta_t": "sensor.pool_heat_exchanger_delta_t",
        "pool_thermal_power": "sensor.pool_thermal_power",
        "pool_heating_electrical_power": "sensor.pool_heating_electrical_power",
        "pool_heating_cost_rate": "sensor.pool_heating_cost_rate",
        "external_heater_pid_sum": "sensor.external_heater_pid_sum",
        "supply_line_temp_difference": "sensor.supply_line_temperature_difference",
        "pool_next_heating": "sensor.pool_next_heating",  # non-graphable
        "current_nordpool_price": "sensor.current_nordpool_price",
        "pool_heating_avg_price": "sensor.pool_heating_avg_price",
        "pool_heating_block_count": "sensor.pool_heating_block_count",  # non-graphable
        "pool_heating_enabled_block_count": "sensor.pool_heating_enabled_block_count",  # non-graphable
        "pool_heating_active": "sensor.pool_heating_active",  # non-graphable (binary)
        "nordpool_tomorrow_available": "sensor.nordpool_tomorrow_available",  # non-graphable
        "pool_heating_15min_energy": "sensor.pool_heating_15min_energy",  # non-graphable
        "pool_heating_night_summary": "sensor.pool_heating_night_summary",  # non-graphable
        "pool_in_heating_window": "sensor.pool_in_heating_window",  # non-graphable (binary)
        "pool_heating_cost_limit_active": "sensor.pool_heating_cost_limit_active",  # non-graphable
        "pool_true_temp": "sensor.pool_true_temperature",
        # Integration sensors (not templates but defined in yaml)
        "pool_heating_electricity": "sensor.pool_heating_electricity",
        "pool_heating_cumulative_cost": "sensor.pool_heating_cumulative_cost",
    }

    # Extract unique_id values from template sensor definitions
    pattern = r'unique_id:\s*([a-z0-9_]+)'
    for match in re.finditer(pattern, content):
        unique_id = match.group(1)
        # Skip block-related unique_ids
        if unique_id.startswith('pool_heat_block_'):
            continue
        if unique_id in unique_id_to_entity:
            entity = unique_id_to_entity[unique_id]
            if entity not in NON_GRAPHABLE_ENTITIES:
                entities.add(entity)
        else:
            # Fallback: assume sensor.{unique_id}
            entity = f"sensor.{unique_id}"
            if entity not in NON_GRAPHABLE_ENTITIES:
                entities.add(entity)

    return entities


def extract_preset_entities(ts_path: Path) -> set[str]:
    """Extract entity IDs from entityPresets.ts"""
    entities = set()
    content = ts_path.read_text()

    # Match entityId definitions like: entityId: 'sensor.foo',
    pattern = r"entityId:\s*['\"]([^'\"]+)['\"]"
    for match in re.finditer(pattern, content):
        entities.add(match.group(1))

    return entities


def main():
    # Paths
    thermia_yaml = ROOT / "scripts/config/thermia_required_entities.yaml"
    pool_yaml = ROOT / "homeassistant/packages/pool_heating.yaml"
    presets_ts = ROOT / "web-ui/src/constants/entityPresets.ts"

    # Check files exist
    for path in [thermia_yaml, pool_yaml, presets_ts]:
        if not path.exists():
            print(f"ERROR: File not found: {path}")
            sys.exit(1)

    # Extract entities
    thermia_entities = extract_thermia_sensors(thermia_yaml)
    pool_entities = extract_pool_heating_sensors(pool_yaml)
    preset_entities = extract_preset_entities(presets_ts)

    # Combine expected entities (exclude unavailable and non-graphable)
    expected = (thermia_entities | pool_entities) - UNAVAILABLE_ENTITIES - NON_GRAPHABLE_ENTITIES

    # Find missing
    missing = expected - preset_entities

    # Find extra (in presets but not in config - this is OK, just informational)
    extra = preset_entities - expected

    # Report
    print(f"Thermia entities: {len(thermia_entities)}")
    print(f"Pool heating entities: {len(pool_entities)}")
    print(f"Total expected: {len(expected)}")
    print(f"In entityPresets.ts: {len(preset_entities)}")
    print()

    if missing:
        print("MISSING from entityPresets.ts:")
        for entity in sorted(missing):
            print(f"  - {entity}")
        print()
        print("Add these to web-ui/src/constants/entityPresets.ts")
        sys.exit(1)
    else:
        print("All graphable entities from config files are in entityPresets.ts")

    if extra:
        print()
        print(f"Additional entities in presets (not in config): {len(extra)}")
        # Don't list them all, just count

    sys.exit(0)


if __name__ == "__main__":
    main()
