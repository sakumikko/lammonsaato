#!/usr/bin/env python3
"""
Fix historical cost data in Home Assistant that was calculated 100x too small.

The bug: Nordpool prices are in EUR/kWh but code divided by 100 assuming cents.

This script shows affected Home Assistant statistics and provides fix options.

Usage:
    python fix_historical_costs.py --ha-url http://homeassistant.local:8123 --ha-token YOUR_TOKEN
"""

import argparse
from datetime import datetime, timedelta

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def fix_ha_statistics(ha_url: str, ha_token: str) -> dict:
    """
    Check Home Assistant statistics for cost sensors and provide fix options.
    """
    if not HAS_REQUESTS:
        print("ERROR: requests library not installed")
        print("Run: pip install requests")
        return {"error": "requests not installed"}

    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json"
    }

    # Entities with accumulated cost data that need fixing
    cost_entities = [
        "sensor.pool_heating_cumulative_cost",
        "sensor.pool_heating_cost_daily",
        "sensor.pool_heating_cost_monthly"
    ]

    print(f"\nChecking Home Assistant statistics at {ha_url}")
    print("-" * 60)

    # Get statistics for the past week
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)

    for entity_id in cost_entities:
        # Get current statistics
        stats_url = f"{ha_url}/api/history/period/{start_time.isoformat()}"
        params = {
            "filter_entity_id": entity_id,
            "end_time": end_time.isoformat()
        }

        try:
            response = requests.get(stats_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            history = response.json()

            if not history or not history[0]:
                print(f"  {entity_id}: No history data found")
                continue

            states = history[0]
            print(f"\n  {entity_id}")
            print(f"    History records: {len(states)}")

            # Filter out unknown/unavailable states and get valid numeric values
            valid_states = []
            for s in states:
                state_val = s.get('state', '')
                if state_val not in ('unknown', 'unavailable', '', None):
                    try:
                        valid_states.append((s, float(state_val)))
                    except (ValueError, TypeError):
                        pass

            if valid_states:
                first_state, first_val = valid_states[0]
                last_state, last_val = valid_states[-1]
                print(f"    Valid records: {len(valid_states)}")
                print(f"    First value: {first_val:.6f} EUR")
                print(f"    Last value:  {last_val:.6f} EUR")
                print(f"    Corrected:   {last_val * 100:.4f} EUR")
            else:
                print(f"    No valid numeric values found")

        except requests.exceptions.RequestException as e:
            print(f"  {entity_id}: API error: {e}")
            continue

    print("\n" + "=" * 60)
    print("How to fix Home Assistant accumulated values:")
    print("=" * 60)
    print("""
Option 1: Calibrate utility meters (recommended)
------------------------------------------------
In Home Assistant Developer Tools > Services, call:

  Service: utility_meter.calibrate
  Entity: sensor.pool_heating_cost_daily
  Value: <current_value * 100>

Repeat for each cost entity.

Option 2: Purge and rebuild (loses history)
-------------------------------------------
In Developer Tools > Services, call:

  Service: recorder.purge_entities
  Entity IDs:
    - sensor.pool_heating_cumulative_cost
    - sensor.pool_heating_cost_daily
    - sensor.pool_heating_cost_monthly

This deletes history; values will accumulate correctly going forward.

Option 3: Direct database fix (advanced)
----------------------------------------
1. Stop Home Assistant
2. Backup home-assistant_v2.db
3. Run:

   sqlite3 home-assistant_v2.db

   -- Find the metadata IDs for cost entities
   SELECT id, statistic_id FROM statistics_meta
   WHERE statistic_id LIKE '%cost%';

   -- Multiply the sum values by 100 (replace X,Y,Z with IDs from above)
   UPDATE statistics
   SET sum = sum * 100, state = state * 100
   WHERE metadata_id IN (X, Y, Z);

   UPDATE statistics_short_term
   SET sum = sum * 100, state = state * 100
   WHERE metadata_id IN (X, Y, Z);

4. Restart Home Assistant
""")


def main():
    parser = argparse.ArgumentParser(
        description="Fix historical cost data in Home Assistant (100x too small)"
    )
    parser.add_argument(
        "--ha-url",
        default="http://192.168.50.11:8123",
        help="Home Assistant URL (default: http://192.168.50.11:8123)"
    )
    parser.add_argument(
        "--ha-token",
        required=True,
        help="Home Assistant long-lived access token"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Pool Heating Cost Fix - Home Assistant Statistics")
    print("=" * 60)

    fix_ha_statistics(args.ha_url, args.ha_token)

    print("\nDone!")


if __name__ == "__main__":
    main()
