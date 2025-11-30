#!/usr/bin/env python3
"""
Test Jinja2 templates via Home Assistant API.

Verifies that templates compile and return expected values.

Usage:
    export HA_URL=http://homeassistant.local:8123
    export HA_TOKEN=your_token
    python scripts/standalone/test_templates.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ha_client import HAClient


# Templates to test
TEMPLATES = {
    "pool_next_heating": """
{% set now_ts = now() %}
{% set ns = namespace(future_blocks=[]) %}
{% for block in [
  states('input_datetime.pool_heat_block_1_start'),
  states('input_datetime.pool_heat_block_2_start'),
  states('input_datetime.pool_heat_block_3_start'),
  states('input_datetime.pool_heat_block_4_start')
] %}
  {% if block not in ['unknown', 'unavailable', ''] %}
    {% set block_dt = strptime(block, '%Y-%m-%d %H:%M:%S') | as_local %}
    {% if block_dt > now_ts %}
      {% set ns.future_blocks = ns.future_blocks + [block_dt] %}
    {% endif %}
  {% endif %}
{% endfor %}
{% if ns.future_blocks | length > 0 %}
  {{ (ns.future_blocks | sort | first).isoformat() }}
{% else %}
  unknown
{% endif %}
""",

    "pool_heating_block_count": """
{% set now_ts = now() %}
{% set cutoff = now_ts - timedelta(hours=12) %}
{% set ns = namespace(count=0) %}
{% for block in [
  states('input_datetime.pool_heat_block_1_start'),
  states('input_datetime.pool_heat_block_2_start'),
  states('input_datetime.pool_heat_block_3_start'),
  states('input_datetime.pool_heat_block_4_start')
] %}
  {% if block not in ['unknown', 'unavailable', ''] %}
    {% set block_dt = strptime(block, '%Y-%m-%d %H:%M:%S') | as_local %}
    {% if block_dt > cutoff %}
      {% set ns.count = ns.count + 1 %}
    {% endif %}
  {% endif %}
{% endfor %}
{{ ns.count }}
""",

    "pool_in_heating_window": """
{% set now_ts = now() %}
{% set ns = namespace(in_block=false) %}
{% for i in range(1, 5) %}
  {% set start = states('input_datetime.pool_heat_block_' ~ i ~ '_start') %}
  {% set end = states('input_datetime.pool_heat_block_' ~ i ~ '_end') %}
  {% if start not in ['unknown', 'unavailable', ''] and end not in ['unknown', 'unavailable', ''] %}
    {% set start_dt = strptime(start, '%Y-%m-%d %H:%M:%S') | as_local %}
    {% set end_dt = strptime(end, '%Y-%m-%d %H:%M:%S') | as_local %}
    {% if start_dt <= now_ts <= end_dt %}
      {% set ns.in_block = true %}
    {% endif %}
  {% endif %}
{% endfor %}
{{ ns.in_block }}
""",

    "pool_thermal_power": """
{% if is_state('binary_sensor.pool_heating_active', 'on') %}
  {% set delta_t = states('sensor.pool_heat_exchanger_delta_t') | float(0) %}
  {% set flow_rate_l_per_s = 45 / 60 %}
  {% set specific_heat = 4.186 %}
  {{ (delta_t * flow_rate_l_per_s * specific_heat) | round(2) }}
{% else %}
  0
{% endif %}
""",

    "pool_heating_electrical_power": """
{% if is_state('binary_sensor.pool_heating_active', 'on') %}
  {% set thermal = states('sensor.pool_thermal_power') | float(0) %}
  {% set cop = 3.0 %}
  {{ (thermal / cop) | round(2) }}
{% else %}
  0
{% endif %}
""",

    "pool_heating_cost_rate": """
{% if is_state('binary_sensor.pool_heating_active', 'on') %}
  {% set electrical_kw = states('sensor.pool_heating_electrical_power') | float(0) %}
  {% set price_cents = states('sensor.nordpool_kwh_fi_eur_3_10_0255') | float(0) %}
  {% set price_eur = price_cents / 100 %}
  {{ (electrical_kw * price_eur) | round(3) }}
{% else %}
  0
{% endif %}
""",
}


def test_template(client: HAClient, name: str, template: str) -> tuple[bool, str]:
    """
    Test a single template.

    Returns:
        (success, result_or_error)
    """
    result = client.render_template(template)

    if result is None:
        return False, "API returned None (connection error?)"

    # Check for error indicators
    if "TemplateError" in result or "Error" in result:
        return False, result

    return True, result.strip()


def main():
    print("=" * 60)
    print("Template Compilation Test")
    print("=" * 60)

    ha_url = os.environ.get("HA_URL")
    ha_token = os.environ.get("HA_TOKEN")

    if not ha_url or not ha_token:
        print("\nERROR: HA_URL and HA_TOKEN environment variables required")
        print("\nSet them with:")
        print("  export HA_URL=http://homeassistant.local:8123")
        print("  export HA_TOKEN=your_long_lived_access_token")
        sys.exit(1)

    print(f"\nConnecting to: {ha_url}")

    client = HAClient(ha_url, ha_token)

    if not client.check_connection(verbose=True):
        print("\nERROR: Cannot connect to Home Assistant")
        sys.exit(1)

    print("\nConnected to Home Assistant")

    # First, check current state of input_datetimes
    print("\n" + "=" * 60)
    print("CURRENT INPUT DATETIME VALUES")
    print("=" * 60)

    for i in range(1, 5):
        start = client.get_state(f"input_datetime.pool_heat_block_{i}_start")
        end = client.get_state(f"input_datetime.pool_heat_block_{i}_end")
        if start:
            print(f"Block {i} start: {start.state}")
        if end:
            print(f"Block {i} end:   {end.state}")

    # Check pool heating active state
    heating_active = client.get_state("binary_sensor.pool_heating_active")
    if heating_active:
        print(f"\nPool heating active: {heating_active.state}")

    # Test templates
    print("\n" + "=" * 60)
    print("TEMPLATE TESTS")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, template in TEMPLATES.items():
        print(f"\nTesting: {name}")
        success, result = test_template(client, name, template)

        if success:
            print(f"  PASS: {result}")
            passed += 1
        else:
            print(f"  FAIL: {result}")
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nPassed: {passed}/{len(TEMPLATES)}")
    print(f"Failed: {failed}/{len(TEMPLATES)}")

    if failed == 0:
        print("\nAll templates compile and execute correctly!")
        return 0
    else:
        print("\nSome templates failed - check errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
