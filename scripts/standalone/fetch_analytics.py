#!/usr/bin/env python3
"""
Fetch and display analytics-related sensors from Home Assistant.

Helps diagnose why analytics dashboards may not show data by checking:
- Raw sensors (temperatures, power, prices)
- 15-minute aggregated data
- Heating block data
- Daily/nightly summary sensors

Usage:
    ./scripts/standalone/fetch_analytics.py
    ./scripts/standalone/fetch_analytics.py --section raw
    ./scripts/standalone/fetch_analytics.py --section 15min
    ./scripts/standalone/fetch_analytics.py --section blocks
    ./scripts/standalone/fetch_analytics.py --section daily

Or with custom host/token:
    HA_HOST=192.168.50.11 HA_TOKEN=xxx ./scripts/standalone/fetch_analytics.py
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timedelta

HA_HOST = os.environ.get("HA_HOST", "192.168.50.11")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
HA_URL = f"http://{HA_HOST}:8123"

if not HA_TOKEN:
    print("Error: HA_TOKEN environment variable not set", file=sys.stderr)
    print("Set it with: export HA_TOKEN=your_token_here", file=sys.stderr)
    sys.exit(1)


def fetch_state(entity_id: str) -> dict | None:
    """Fetch a single entity state from HA."""
    url = f"{HA_URL}/api/states/{entity_id}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"{e.code} {e.reason}", "entity_id": entity_id}
    except Exception as e:
        return {"error": str(e), "entity_id": entity_id}


def fetch_all_states() -> list:
    """Fetch all entity states from HA."""
    url = f"{HA_URL}/api/states"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"ERROR fetching all states: {e}")
        return []


def fetch_history(entity_id: str, hours: int = 24) -> list:
    """Fetch history for an entity."""
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    url = f"{HA_URL}/api/history/period/{start_time.isoformat()}?filter_entity_id={entity_id}&end_time={end_time.isoformat()}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data[0] if data else []
    except Exception as e:
        return []


def print_entity(entity_id: str, label: str = None, show_attrs: bool = False):
    """Print entity state with optional attributes."""
    state = fetch_state(entity_id)
    label = label or entity_id
    if state and "error" not in state:
        val = state["state"]
        if show_attrs:
            attrs = state.get("attributes", {})
            print(f"  {label}: {val}")
            for k, v in attrs.items():
                if k not in ["friendly_name", "icon", "unit_of_measurement"]:
                    # Truncate long values
                    v_str = str(v)
                    if len(v_str) > 100:
                        v_str = v_str[:100] + "..."
                    print(f"    {k}: {v_str}")
        else:
            print(f"  {label}: {val}")
    else:
        error = state.get("error", "unknown") if state else "no response"
        print(f"  {label}: [ERROR: {error}]")


def section_raw():
    """Display raw sensor values used for analytics."""
    print("\n" + "=" * 60)
    print("RAW SENSORS")
    print("=" * 60)

    print("\n--- Pool Temperatures ---")
    temps = [
        ("sensor.pool_return_line_temperature_corrected", "Pool Return Line Temp"),
        ("sensor.pool_estimated_true_temp", "Pool Estimated True Temp"),
        ("sensor.pool_heat_exchanger_delta_t", "Heat Exchanger Delta-T"),
        ("input_number.pool_true_temp_daytime", "Daytime Calibration Temp"),
    ]
    for entity_id, label in temps:
        print_entity(entity_id, label)

    print("\n--- Power/Energy ---")
    power = [
        ("sensor.pool_thermal_power", "Thermal Power (kW)"),
        ("sensor.pool_heating_electrical_power", "Electrical Power (W)"),
        ("sensor.pool_heating_electricity", "Cumulative Electricity (kWh)"),
    ]
    for entity_id, label in power:
        print_entity(entity_id, label)

    print("\n--- Daily/Monthly Totals ---")
    totals = [
        ("sensor.pool_heating_electricity_daily", "Electricity Daily (kWh)"),
        ("sensor.pool_heating_electricity_monthly", "Electricity Monthly (kWh)"),
        ("sensor.pool_heating_cost_daily", "Cost Daily (€)"),
        ("sensor.pool_heating_cost_monthly", "Cost Monthly (€)"),
        ("sensor.pool_heating_cumulative_cost", "Cumulative Cost (€)"),
    ]
    for entity_id, label in totals:
        print_entity(entity_id, label)

    print("\n--- Electricity Prices ---")
    nordpool = fetch_state("sensor.nordpool_kwh_fi_eur_3_10_0255")
    if nordpool and "error" not in nordpool:
        print(f"  Current Price: {float(nordpool['state'])*100:.2f} c/kWh")
        attrs = nordpool.get("attributes", {})
        today = attrs.get("today", [])
        tomorrow = attrs.get("tomorrow", [])
        print(f"  Today prices: {len(today)} values")
        print(f"  Tomorrow prices: {len(tomorrow) if tomorrow else 'Not available'}")
        if today:
            print(f"  Today range: {min(today)*100:.2f} - {max(today)*100:.2f} c/kWh")
    else:
        print("  Nordpool: [NOT AVAILABLE]")

    print("\n--- Schedule Stats ---")
    schedule_stats = [
        ("sensor.pool_heating_block_count", "Total Blocks"),
        ("sensor.pool_heating_enabled_block_count", "Enabled Blocks"),
        ("sensor.pool_heating_average_price", "Average Price (c/kWh)"),
        ("sensor.pool_heating_cost_rate", "Cost Rate"),
        ("sensor.pool_next_heating", "Next Heating"),
    ]
    for entity_id, label in schedule_stats:
        print_entity(entity_id, label)


def section_15min():
    """Display 15-minute aggregated sensors."""
    print("\n" + "=" * 60)
    print("15-MINUTE AGGREGATED SENSORS")
    print("=" * 60)

    # Check for 15min sensors
    all_states = fetch_all_states()
    sensors_15min = [
        s for s in all_states if "15min" in s.get("entity_id", "").lower()
    ]

    if sensors_15min:
        print(f"\nFound {len(sensors_15min)} 15-minute sensors:")
        for s in sensors_15min:
            entity_id = s["entity_id"]
            state = s["state"]
            last_changed = s.get("last_changed", "")
            print(f"  {entity_id}: {state} (changed: {last_changed[:19] if last_changed else 'N/A'})")
    else:
        print("\n[!] No 15-minute sensors found!")
        print("    Expected sensors like: sensor.pool_heating_15min_*")

    # Check for utility meter sensors (often used for 15min aggregation)
    utility_meters = [
        s for s in all_states if "utility_meter" in s.get("entity_id", "").lower()
    ]
    if utility_meters:
        print(f"\nFound {len(utility_meters)} utility meter sensors:")
        for s in utility_meters[:10]:  # Limit to first 10
            print(f"  {s['entity_id']}: {s['state']}")

    # Check for statistics sensors
    stats_sensors = [
        s
        for s in all_states
        if "statistics" in s.get("entity_id", "").lower()
        or "average" in s.get("entity_id", "").lower()
    ]
    if stats_sensors:
        print(f"\nFound {len(stats_sensors)} statistics sensors:")
        for s in stats_sensors[:10]:
            print(f"  {s['entity_id']}: {s['state']}")


def section_blocks():
    """Display heating block data."""
    print("\n" + "=" * 60)
    print("HEATING BLOCKS")
    print("=" * 60)

    NUM_BLOCKS = 5

    print("\n--- Schedule Parameters ---")
    params = [
        ("input_number.pool_heating_total_hours", "Total Hours"),
        ("input_number.pool_heating_max_cost_eur", "Max Cost EUR"),
        ("input_number.pool_heating_min_block_duration", "Min Block Duration"),
        ("input_number.pool_heating_max_block_duration", "Max Block Duration"),
        ("input_boolean.pool_heating_cost_limit_applied", "Cost Limit Applied"),
    ]
    for entity_id, label in params:
        print_entity(entity_id, label)

    print("\n--- Block Details ---")
    print(
        f"{'Block':<6} {'Enabled':<8} {'CostExc':<8} {'Start':<6} {'End':<6} {'Price':<8} {'Cost':<10}"
    )
    print("-" * 60)

    for i in range(1, NUM_BLOCKS + 1):
        enabled = fetch_state(f"input_boolean.pool_heat_block_{i}_enabled")
        cost_exceeded = fetch_state(f"input_boolean.pool_heat_block_{i}_cost_exceeded")
        start = fetch_state(f"input_datetime.pool_heat_block_{i}_start")
        end = fetch_state(f"input_datetime.pool_heat_block_{i}_end")
        price = fetch_state(f"input_number.pool_heat_block_{i}_price")
        cost = fetch_state(f"input_number.pool_heat_block_{i}_cost")

        enabled_val = enabled["state"] if enabled and "error" not in enabled else "?"
        cost_exc_val = (
            cost_exceeded["state"]
            if cost_exceeded and "error" not in cost_exceeded
            else "?"
        )

        start_val = "—"
        if start and "error" not in start and start["state"] not in ["unknown", "unavailable"]:
            s = start["state"]
            if "T" in s or " " in s:
                start_val = s.split("T")[-1].split(" ")[-1][:5]
            else:
                start_val = s[:5]

        end_val = "—"
        if end and "error" not in end and end["state"] not in ["unknown", "unavailable"]:
            e = end["state"]
            if "T" in e or " " in e:
                end_val = e.split("T")[-1].split(" ")[-1][:5]
            else:
                end_val = e[:5]

        price_val = (
            f"{float(price['state']):.2f}c"
            if price and "error" not in price and price["state"] not in ["unknown", "unavailable"]
            else "—"
        )
        cost_val = (
            f"€{float(cost['state']):.3f}"
            if cost and "error" not in cost and cost["state"] not in ["unknown", "unavailable"]
            else "—"
        )

        print(
            f"{i:<6} {enabled_val:<8} {cost_exc_val:<8} {start_val:<6} {end_val:<6} {price_val:<8} {cost_val:<10}"
        )

    print("\n--- Schedule Info ---")
    print_entity("input_text.pool_heating_schedule_info", "Schedule Info", show_attrs=True)


def section_daily():
    """Display daily/nightly summary sensors."""
    print("\n" + "=" * 60)
    print("DAILY/NIGHTLY SUMMARIES")
    print("=" * 60)

    # Check for night summary data and sensor
    print("\n--- Night Summary (Persistent Storage) ---")
    # input_text stores the raw JSON data (persists across restarts)
    print_entity("input_text.pool_heating_night_summary_data", "Night Summary Data (JSON)", show_attrs=False)

    # Template sensor parses the JSON for convenient access
    print("\n--- Night Summary Sensor ---")
    print_entity("sensor.pool_heating_night_summary", "Night Summary", show_attrs=True)

    # Check all states for any daily/night sensors
    all_states = fetch_all_states()

    daily_sensors = [
        s
        for s in all_states
        if any(
            x in s.get("entity_id", "").lower()
            for x in ["daily", "night", "day_", "_day", "today", "yesterday"]
        )
        and "pool" in s.get("entity_id", "").lower()
    ]

    if daily_sensors:
        print(f"\nFound {len(daily_sensors)} daily/night pool sensors:")
        for s in daily_sensors:
            entity_id = s["entity_id"]
            state = s["state"]
            attrs = s.get("attributes", {})
            print(f"\n  {entity_id}: {state}")
            for k, v in attrs.items():
                if k not in ["friendly_name", "icon", "unit_of_measurement"]:
                    v_str = str(v)
                    if len(v_str) > 80:
                        v_str = v_str[:80] + "..."
                    print(f"    {k}: {v_str}")
    else:
        print("\n[!] No daily/night pool sensors found in Home Assistant")

    # Check for SQL sensors that might store analytics
    sql_sensors = [s for s in all_states if "sql" in s.get("entity_id", "").lower()]
    if sql_sensors:
        print(f"\nFound {len(sql_sensors)} SQL sensors:")
        for s in sql_sensors[:5]:
            print(f"  {s['entity_id']}: {s['state']}")


def section_history():
    """Display recent history for key sensors."""
    print("\n" + "=" * 60)
    print("RECENT HISTORY (last 24h)")
    print("=" * 60)

    key_sensors = [
        "sensor.pool_thermal_power",
        "sensor.pool_return_line_temperature_corrected",
        "sensor.pool_heating_electricity",
        "sensor.nordpool_kwh_fi_eur_3_10_0255",
    ]

    for entity_id in key_sensors:
        history = fetch_history(entity_id, hours=24)
        if history:
            # Count state changes
            changes = len(history)
            # Get first and last values
            first = history[0] if history else {}
            last = history[-1] if history else {}
            print(f"\n{entity_id}:")
            print(f"  Data points: {changes}")
            print(f"  First: {first.get('state', 'N/A')} at {first.get('last_changed', 'N/A')[:19]}")
            print(f"  Last: {last.get('state', 'N/A')} at {last.get('last_changed', 'N/A')[:19]}")
        else:
            print(f"\n{entity_id}: [NO HISTORY DATA]")


def section_diagnostics():
    """Run diagnostics to identify potential issues."""
    print("\n" + "=" * 60)
    print("DIAGNOSTICS")
    print("=" * 60)

    issues = []

    # Check HA connection
    print("\n--- Connection ---")
    all_states = fetch_all_states()
    if all_states:
        print(f"  HA Connection: OK ({len(all_states)} entities)")
    else:
        print("  HA Connection: FAILED")
        issues.append("Cannot connect to Home Assistant")

    # Check for required sensors
    print("\n--- Required Sensors ---")
    required = [
        ("sensor.pool_thermal_power", "Pool Thermal Power"),
        ("sensor.pool_heating_electrical_power", "Pool Electrical Power"),
        ("sensor.pool_return_line_temperature_corrected", "Pool Return Temp"),
        ("sensor.pool_heating_electricity", "Cumulative Electricity"),
        ("sensor.nordpool_kwh_fi_eur_3_10_0255", "Nordpool Price"),
    ]
    for entity_id, label in required:
        state = fetch_state(entity_id)
        if state and "error" not in state and state["state"] not in ["unavailable", "unknown"]:
            print(f"  {label}: OK ({state['state']})")
        elif state and "error" not in state:
            print(f"  {label}: {state['state'].upper()}")
            issues.append(f"Sensor unavailable: {entity_id}")
        else:
            print(f"  {label}: MISSING")
            issues.append(f"Required sensor missing: {entity_id}")

    # Check recorder
    print("\n--- Recorder/History ---")
    recorder_check = fetch_history("sensor.pool_return_line_temperature_corrected", hours=1)
    if recorder_check:
        print(f"  Recorder: OK ({len(recorder_check)} entries in last hour)")
    else:
        print("  Recorder: NO DATA (check recorder config)")
        issues.append("No history data - check Home Assistant recorder configuration")

    # Check for analytics sensors
    print("\n--- Analytics Sensors ---")
    analytics_patterns = ["night_summary", "daily", "15min", "statistics"]
    found_analytics = []
    for s in all_states:
        entity_id = s.get("entity_id", "")
        if any(p in entity_id.lower() for p in analytics_patterns):
            found_analytics.append(entity_id)

    if found_analytics:
        print(f"  Found {len(found_analytics)} analytics-related sensors")
        for e in found_analytics[:5]:
            print(f"    - {e}")
    else:
        print("  No analytics sensors found")
        issues.append("No analytics sensors created - check pyscript/automations")

    # Summary
    print("\n" + "-" * 60)
    if issues:
        print("ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("No obvious issues found")


def main():
    parser = argparse.ArgumentParser(description="Fetch analytics data from Home Assistant")
    parser.add_argument(
        "--section",
        "-s",
        choices=["raw", "15min", "blocks", "daily", "history", "diag", "all"],
        default="all",
        help="Which section to display",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"Analytics Data Fetch - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Host: {HA_HOST}")
    print("=" * 60)

    if args.section == "all":
        section_diagnostics()
        section_raw()
        section_blocks()
        section_15min()
        section_daily()
    elif args.section == "raw":
        section_raw()
    elif args.section == "15min":
        section_15min()
    elif args.section == "blocks":
        section_blocks()
    elif args.section == "daily":
        section_daily()
    elif args.section == "history":
        section_history()
    elif args.section == "diag":
        section_diagnostics()

    print("\n")


if __name__ == "__main__":
    main()
