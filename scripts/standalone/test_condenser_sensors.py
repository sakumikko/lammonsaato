#!/usr/bin/env python3
"""
Test Thermia Condenser Sensors via Home Assistant API

Verifies that the condenser temperature sensors exist and return sane values.

Usage:
    # Set environment variables first
    export HA_URL=http://homeassistant.local:8123
    export HA_TOKEN=your_token

    # Run test
    python scripts/standalone/test_condenser_sensors.py
"""

import os
import sys

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ha_client import HAClient

# Thermia condenser sensors (from thermiagenesis integration)
CONDENSER_OUT_SENSOR = "sensor.condenser_out_temperature"
CONDENSER_IN_SENSOR = "sensor.condenser_in_temperature"

# Additional sensors for reference (may not exist in all installations)
OUTDOOR_TEMP_SENSOR = "sensor.thermia_outdoor_temperature"
SYSTEM_SUPPLY_SENSOR = "sensor.thermia_supply_temperature"
COMPRESSOR_SPEED_SENSOR = "sensor.thermia_compressor_speed"


def test_sensor(client: HAClient, sensor_id: str, min_val: float, max_val: float, description: str) -> bool:
    """
    Test a single sensor.

    Args:
        client: HA client
        sensor_id: Entity ID
        min_val: Minimum expected value
        max_val: Maximum expected value
        description: Human-readable description

    Returns:
        True if sensor exists and has sane value
    """
    print(f"\nTesting: {description}")
    print(f"  Sensor: {sensor_id}")

    state = client.get_state(sensor_id)

    if state is None:
        print(f"  ❌ FAIL: Sensor not found")
        return False

    print(f"  State: {state.state}")
    print(f"  Last updated: {state.last_updated}")

    if not state.is_available:
        print(f"  ❌ FAIL: Sensor unavailable (state: {state.state})")
        return False

    try:
        value = float(state.state)
    except (ValueError, TypeError):
        print(f"  ❌ FAIL: Cannot convert '{state.state}' to number")
        return False

    if value < min_val or value > max_val:
        print(f"  ⚠️  WARNING: Value {value} outside expected range [{min_val}, {max_val}]")
        # Don't fail, just warn - values might be legitimately outside range
    else:
        print(f"  ✓ Value {value} is within expected range [{min_val}, {max_val}]")

    # Show unit if available
    unit = state.attributes.get("unit_of_measurement", "")
    if unit:
        print(f"  Unit: {unit}")

    return True


def test_delta_t(condenser_out: float, condenser_in: float) -> None:
    """Test delta-T calculation."""
    print(f"\n--- Delta-T Calculation ---")
    delta_t = condenser_out - condenser_in
    print(f"  Condenser Out (to pool): {condenser_out}°C")
    print(f"  Condenser In (from pool): {condenser_in}°C")
    print(f"  Delta-T: {delta_t:.1f}°C")

    if delta_t < 0:
        print(f"  ⚠️  WARNING: Negative delta-T suggests sensors may be swapped or heat pump is off")
    elif delta_t > 15:
        print(f"  ⚠️  WARNING: Very high delta-T (>15°C) - verify this is correct")
    elif delta_t > 0:
        print(f"  ✓ Positive delta-T indicates heat transfer to pool")
    else:
        print(f"  ℹ️  Zero delta-T - heat pump may be off or not heating pool")

    # Energy calculation example
    if delta_t > 0:
        flow_rate_l_per_min = 45
        flow_rate_l_per_s = flow_rate_l_per_min / 60
        specific_heat = 4.186  # kJ/(kg·°C)
        thermal_power_kw = delta_t * flow_rate_l_per_s * specific_heat
        cop = 3.0
        electrical_power_kw = thermal_power_kw / cop

        print(f"\n  --- Energy Estimate (at {flow_rate_l_per_min} L/min flow, COP={cop}) ---")
        print(f"  Thermal power to pool: {thermal_power_kw:.2f} kW")
        print(f"  Electrical consumption: {electrical_power_kw:.2f} kW")


def main():
    print("=" * 60)
    print("Thermia Condenser Sensor Test")
    print("=" * 60)

    # Check environment
    ha_url = os.environ.get("HA_URL")
    ha_token = os.environ.get("HA_TOKEN")

    if not ha_url or not ha_token:
        print("\n❌ ERROR: HA_URL and HA_TOKEN environment variables required")
        print("\nSet them with:")
        print("  export HA_URL=http://homeassistant.local:8123")
        print("  export HA_TOKEN=your_long_lived_access_token")
        sys.exit(1)

    print(f"\nConnecting to: {ha_url}")

    client = HAClient(ha_url, ha_token)

    if not client.check_connection(verbose=True):
        print("\n❌ ERROR: Cannot connect to Home Assistant")
        sys.exit(1)

    print("\n✓ Connected to Home Assistant")

    # Test condenser sensors (critical for energy calculation)
    print("\n" + "=" * 60)
    print("CRITICAL SENSORS (for energy calculation)")
    print("=" * 60)

    results = {}

    # Condenser out (hot water to pool) - expected 20-60°C
    results['condenser_out'] = test_sensor(
        client,
        CONDENSER_OUT_SENSOR,
        10, 70,
        "Condenser Out Temperature (hot water TO pool)"
    )

    # Condenser in (cool water from pool) - expected 15-50°C
    results['condenser_in'] = test_sensor(
        client,
        CONDENSER_IN_SENSOR,
        5, 60,
        "Condenser In Temperature (cool water FROM pool)"
    )

    # If both condenser sensors work, calculate delta-T
    if results['condenser_out'] and results['condenser_in']:
        out_state = client.get_state(CONDENSER_OUT_SENSOR)
        in_state = client.get_state(CONDENSER_IN_SENSOR)
        if out_state and in_state:
            try:
                test_delta_t(float(out_state.state), float(in_state.state))
            except (ValueError, TypeError):
                print("\n  Could not calculate delta-T")

    # Test reference sensors (nice to have)
    print("\n" + "=" * 60)
    print("REFERENCE SENSORS (for logging)")
    print("=" * 60)

    # Outdoor temperature - expected -30 to +40°C
    results['outdoor'] = test_sensor(
        client,
        OUTDOOR_TEMP_SENSOR,
        -30, 45,
        "Outdoor Temperature"
    )

    # System supply - expected 20-70°C
    results['system_supply'] = test_sensor(
        client,
        SYSTEM_SUPPLY_SENSOR,
        15, 75,
        "System Supply Line Temperature"
    )

    # Compressor speed - expected 0-100%
    results['compressor'] = test_sensor(
        client,
        COMPRESSOR_SPEED_SENSOR,
        0, 100,
        "Compressor Speed"
    )

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    critical_ok = results.get('condenser_out', False) and results.get('condenser_in', False)

    if critical_ok:
        print("\n✓ Critical sensors (condenser_out, condenser_in) are working")
        print("  Energy calculation will work correctly")
    else:
        print("\n❌ Critical sensors missing or unavailable")
        print("  Energy calculation will NOT work")
        print("\n  Check if:")
        print("  1. The thermiagenesis integration is installed and configured")
        print("  2. Your device name matches 'pannuhuone' (or update sensor IDs)")
        print("  3. The Thermia heat pump is connected and responding")

    all_ok = all(results.values())

    print(f"\nSensors found: {sum(results.values())}/{len(results)}")

    if all_ok:
        print("\n✓ All sensors working!")
        return 0
    else:
        missing = [k for k, v in results.items() if not v]
        print(f"\n⚠️  Missing/unavailable sensors: {', '.join(missing)}")
        return 1 if not critical_ok else 0


if __name__ == "__main__":
    sys.exit(main())
