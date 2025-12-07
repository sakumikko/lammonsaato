#!/usr/bin/env python3
"""
Pull thermal calibration data from Home Assistant.

Queries:
- input_number.pool_true_temp_pre_heating
- input_number.pool_true_temp_post_heating
- input_number.pool_true_temp_daytime
- input_datetime.pool_last_calibration_time

Usage:
    export HA_TOKEN="your_token"
    python pull_thermal_data.py

    # Or specify days to look back
    python pull_thermal_data.py --days 14
"""

import argparse
import json
import os
from datetime import datetime, timedelta

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


HA_URL = os.environ.get("HA_URL", "http://192.168.50.11:8123")
HA_TOKEN = os.environ.get("HA_TOKEN")

THERMAL_ENTITIES = [
    "input_number.pool_true_temp_pre_heating",
    "input_number.pool_true_temp_post_heating",
    "input_number.pool_true_temp_daytime",
    "input_datetime.pool_last_calibration_time",
]


def get_history(entity_id: str, start_time: datetime, end_time: datetime) -> list:
    """Fetch history for an entity from HA API."""
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }

    url = f"{HA_URL}/api/history/period/{start_time.isoformat()}"
    params = {
        "filter_entity_id": entity_id,
        "end_time": end_time.isoformat(),
        "minimal_response": "false"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data and len(data) > 0:
            return data[0]
        return []
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching {entity_id}: {e}")
        return []


def get_current_state(entity_id: str) -> dict:
    """Get current state of an entity."""
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }

    url = f"{HA_URL}/api/states/{entity_id}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching {entity_id}: {e}")
        return {}


def parse_state_changes(history: list) -> list:
    """Extract meaningful state changes from history."""
    changes = []
    last_value = None

    for entry in history:
        state = entry.get("state", "")
        if state in ("unknown", "unavailable", "", None):
            continue

        try:
            value = float(state)
        except (ValueError, TypeError):
            # For datetime entities, keep as string
            value = state

        # Only record if value changed
        if value != last_value:
            timestamp = entry.get("last_changed", entry.get("last_updated", ""))
            changes.append({
                "timestamp": timestamp,
                "value": value
            })
            last_value = value

    return changes


def format_timestamp(ts_str: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return ts_str[:16] if ts_str else "N/A"


def main():
    parser = argparse.ArgumentParser(description="Pull thermal calibration data from HA")
    parser.add_argument("--days", type=int, default=7, help="Days of history to fetch")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not HAS_REQUESTS:
        print("ERROR: requests library required")
        print("Run: pip install requests")
        return

    if not HA_TOKEN:
        print("ERROR: HA_TOKEN environment variable not set")
        print("Export your Home Assistant long-lived access token:")
        print('  export HA_TOKEN="your_token_here"')
        return

    end_time = datetime.now()
    start_time = end_time - timedelta(days=args.days)

    print("=" * 70)
    print("Pool Thermal Calibration Data")
    print("=" * 70)
    print(f"HA URL: {HA_URL}")
    print(f"Period: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
    print()

    # Collect all data
    all_data = {}

    print("Fetching current states...")
    print("-" * 70)
    for entity_id in THERMAL_ENTITIES:
        state = get_current_state(entity_id)
        if state:
            name = entity_id.split(".")[-1]
            value = state.get("state", "N/A")
            updated = format_timestamp(state.get("last_updated", ""))
            print(f"  {name}: {value} (updated: {updated})")
            all_data[f"current_{name}"] = {
                "value": value,
                "last_updated": state.get("last_updated")
            }

    print()
    print("Fetching history...")
    print("-" * 70)

    calibration_records = []

    for entity_id in THERMAL_ENTITIES:
        name = entity_id.split(".")[-1]
        print(f"\n  {name}:")

        history = get_history(entity_id, start_time, end_time)
        changes = parse_state_changes(history)

        all_data[f"history_{name}"] = changes

        if not changes:
            print("    No data recorded")
            continue

        print(f"    {len(changes)} state changes recorded:")
        for change in changes[-10:]:  # Show last 10
            ts = format_timestamp(change["timestamp"])
            val = change["value"]
            if isinstance(val, float):
                print(f"      {ts}: {val:.1f}°C")
            else:
                print(f"      {ts}: {val}")

        if len(changes) > 10:
            print(f"      ... ({len(changes) - 10} earlier records)")

    # Try to correlate readings into daily records
    print()
    print("=" * 70)
    print("Daily Calibration Summary")
    print("=" * 70)

    pre_heat_history = all_data.get("history_pool_true_temp_pre_heating", [])
    post_heat_history = all_data.get("history_pool_true_temp_post_heating", [])
    daytime_history = all_data.get("history_pool_true_temp_daytime", [])

    # Group by date
    daily_data = {}

    for record in pre_heat_history:
        try:
            dt = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
            date_key = dt.strftime("%Y-%m-%d")
            if date_key not in daily_data:
                daily_data[date_key] = {}
            daily_data[date_key]["pre_heating"] = record["value"]
            daily_data[date_key]["pre_heating_time"] = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            pass

    for record in post_heat_history:
        try:
            dt = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
            date_key = dt.strftime("%Y-%m-%d")
            if date_key not in daily_data:
                daily_data[date_key] = {}
            daily_data[date_key]["post_heating"] = record["value"]
            daily_data[date_key]["post_heating_time"] = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            pass

    for record in daytime_history:
        try:
            dt = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
            date_key = dt.strftime("%Y-%m-%d")
            if date_key not in daily_data:
                daily_data[date_key] = {}
            daily_data[date_key]["daytime"] = record["value"]
            daily_data[date_key]["daytime_time"] = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            pass

    if daily_data:
        print(f"\n{'Date':<12} {'Pre-Heat':<12} {'Post-Heat':<12} {'Daytime':<12} {'Heating Δ':<10}")
        print("-" * 70)

        for date in sorted(daily_data.keys()):
            data = daily_data[date]
            pre = data.get("pre_heating")
            post = data.get("post_heating")
            day = data.get("daytime")

            pre_str = f"{pre:.1f}°C" if pre else "-"
            post_str = f"{post:.1f}°C" if post else "-"
            day_str = f"{day:.1f}°C" if day else "-"

            # Calculate heating delta if both pre and post exist
            if pre and post:
                delta = post - pre
                delta_str = f"{delta:+.1f}°C"
            else:
                delta_str = "-"

            print(f"{date:<12} {pre_str:<12} {post_str:<12} {day_str:<12} {delta_str:<10}")

        # Calculate cooling rate if we have consecutive days
        print()
        print("Cooling Analysis:")
        print("-" * 70)

        sorted_dates = sorted(daily_data.keys())
        for i in range(len(sorted_dates) - 1):
            today = sorted_dates[i]
            tomorrow = sorted_dates[i + 1]

            post_today = daily_data[today].get("post_heating")
            pre_tomorrow = daily_data[tomorrow].get("pre_heating")

            if post_today and pre_tomorrow:
                # Calculate cooling from post-heating to next pre-heating
                # Typically ~12.5 hours (08:00 to 20:30)
                cooling = post_today - pre_tomorrow
                print(f"  {today} post → {tomorrow} pre: {post_today:.1f}°C → {pre_tomorrow:.1f}°C (Δ = {-cooling:+.1f}°C)")
    else:
        print("\nNo daily calibration data found yet.")
        print("The calibration automations run at:")
        print("  - 20:30 (pre-heating)")
        print("  - 07:30 (post-heating)")
        print("  - 14:00 (daytime)")

    if args.json:
        print()
        print("=" * 70)
        print("JSON Output")
        print("=" * 70)
        output = {
            "query_time": datetime.now().isoformat(),
            "period_days": args.days,
            "current_states": {k: v for k, v in all_data.items() if k.startswith("current_")},
            "history": {k: v for k, v in all_data.items() if k.startswith("history_")},
            "daily_summary": daily_data
        }
        print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
