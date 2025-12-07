#!/usr/bin/env python3
"""
Fetch and display pool heating blocks from Home Assistant.

Usage:
    ./scripts/standalone/fetch_blocks.py

Or with custom host/token:
    HA_HOST=192.168.50.11 HA_TOKEN=xxx ./scripts/standalone/fetch_blocks.py

Currency/Price Convention:
--------------------------
- Nordpool sensor: EUR/kWh (e.g., 0.026 = 2.6 cents)
- Block prices (input_number.pool_heat_block_N_price): CENTS/kWh (stored as cents)
- Block costs (input_number.pool_heat_block_N_cost): EUR
- max_cost_eur: EUR
- All displays: prices in "c/kWh", costs in "€X.XX"
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

HA_HOST = os.environ.get("HA_HOST", "192.168.50.11")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
HA_URL = f"http://{HA_HOST}:8123"

if not HA_TOKEN:
    print("Error: HA_TOKEN environment variable not set", file=sys.stderr)
    print("Set it with: export HA_TOKEN=your_token_here", file=sys.stderr)
    sys.exit(1)

NUM_BLOCKS = 5


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
        print(f"  ERROR fetching {entity_id}: {e.code} {e.reason}")
        return None
    except Exception as e:
        print(f"  ERROR fetching {entity_id}: {e}")
        return None


def main():
    print(f"{'='*60}")
    print(f"Pool Heating Blocks - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Host: {HA_HOST}")
    print(f"{'='*60}\n")

    # Fetch schedule parameters
    print("=== Schedule Parameters ===")
    params = [
        ("input_number.pool_heating_total_hours", "Total Hours"),
        ("input_number.pool_heating_max_cost_eur", "Max Cost EUR"),
        ("input_number.pool_heating_min_block_duration", "Min Block Duration"),
        ("input_number.pool_heating_max_block_duration", "Max Block Duration"),
        ("input_boolean.pool_heating_cost_limit_applied", "Cost Limit Applied"),
    ]
    for entity_id, label in params:
        state = fetch_state(entity_id)
        if state:
            print(f"  {label}: {state['state']}")
    print()

    # Fetch Nordpool price
    print("=== Nordpool ===")
    nordpool = fetch_state("sensor.nordpool_kwh_fi_eur_3_10_0255")
    if nordpool:
        print(f"  Current price: {float(nordpool['state'])*100:.2f} c/kWh")
        attrs = nordpool.get("attributes", {})
        if "today" in attrs:
            print(f"  Today prices available: {len(attrs['today'])} hours")
        if "tomorrow" in attrs:
            tomorrow = attrs["tomorrow"]
            if tomorrow:
                print(f"  Tomorrow prices available: {len(tomorrow)} hours")
            else:
                print(f"  Tomorrow prices: Not yet available")
    print()

    # Fetch blocks
    print("=== Heating Blocks ===")
    print(f"{'Block':<6} {'Enabled':<8} {'CostExc':<8} {'Start':<6} {'End':<6} {'Price':<8} {'Cost EUR':<10}")
    print("-" * 60)

    total_enabled_mins = 0
    total_cost = 0.0

    for i in range(1, NUM_BLOCKS + 1):
        enabled = fetch_state(f"input_boolean.pool_heat_block_{i}_enabled")
        cost_exceeded = fetch_state(f"input_boolean.pool_heat_block_{i}_cost_exceeded")
        start = fetch_state(f"input_datetime.pool_heat_block_{i}_start")
        end = fetch_state(f"input_datetime.pool_heat_block_{i}_end")
        price = fetch_state(f"input_number.pool_heat_block_{i}_price")
        cost = fetch_state(f"input_number.pool_heat_block_{i}_cost")

        enabled_val = enabled["state"] if enabled else "?"
        cost_exc_val = cost_exceeded["state"] if cost_exceeded else "?"

        # Handle datetime - could be "HH:MM" or "YYYY-MM-DD HH:MM:SS"
        start_val = "—"
        end_val = "—"
        if start and start["state"] not in ["unknown", "unavailable"]:
            s = start["state"]
            if "T" in s or " " in s:  # ISO format
                start_val = s.split("T")[-1].split(" ")[-1][:5]
            else:
                start_val = s[:5]
        if end and end["state"] not in ["unknown", "unavailable"]:
            e = end["state"]
            if "T" in e or " " in e:  # ISO format
                end_val = e.split("T")[-1].split(" ")[-1][:5]
            else:
                end_val = e[:5]

        # Price is stored in CENTS/kWh, display directly
        price_val = f"{float(price['state']):.2f}c" if price and price["state"] not in ["unknown", "unavailable"] else "—"
        # Cost is stored in EUR
        cost_val = f"€{float(cost['state']):.3f}" if cost and cost["state"] not in ["unknown", "unavailable"] else "—"

        # Calculate duration if we have start and end
        duration = ""
        if start_val != "—" and end_val != "—":
            try:
                s = datetime.strptime(start_val, "%H:%M")
                e = datetime.strptime(end_val, "%H:%M")
                if e < s:  # crosses midnight
                    mins = (24 * 60 - (s.hour * 60 + s.minute)) + (e.hour * 60 + e.minute)
                else:
                    mins = (e.hour * 60 + e.minute) - (s.hour * 60 + s.minute)
                duration = f"({mins}m)"

                # Track totals for enabled blocks
                if enabled_val == "on" and cost_exc_val == "off":
                    total_enabled_mins += mins
                    if cost and cost["state"] not in ["unknown", "unavailable"]:
                        total_cost += float(cost["state"])
            except:
                pass

        # Color coding via symbols
        status = ""
        if enabled_val == "off":
            status = "[DISABLED]"
        elif cost_exc_val == "on":
            status = "[COST_EXCEEDED]"
        else:
            status = "[ACTIVE]"

        print(f"{i:<6} {enabled_val:<8} {cost_exc_val:<8} {start_val:<6} {end_val:<6} {price_val:<8} {cost_val:<10} {duration} {status}")

    print("-" * 60)
    print(f"Total enabled: {total_enabled_mins} min ({total_enabled_mins/60:.1f}h), Cost: €{total_cost:.3f}")
    print()

    # Fetch schedule info (input_text entity)
    print("=== Schedule Info ===")
    info = fetch_state("input_text.pool_heating_schedule_info")
    if info:
        print(f"  State: {info['state']}")
        attrs = info.get("attributes", {})
        for key in ["scheduled_minutes", "total_cost_eur", "blocks_enabled", "last_updated"]:
            if key in attrs:
                print(f"  {key}: {attrs[key]}")
    print()


if __name__ == "__main__":
    main()
