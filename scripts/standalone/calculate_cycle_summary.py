#!/usr/bin/env python3
"""
Calculate cycle summary by aggregating 15-minute energy data.

Data Aggregation Hierarchy:
  raw → 15min → block → cycle

This script queries HA history for sensor.pool_heating_15min_energy
during the 21:00→21:00 cycle window and calculates totals.

Cycle Window:
  - Start: 21:00 on heating_date (inclusive)
  - End: 21:00 on heating_date + 1 day (exclusive)

Usage:
  ./calculate_cycle_summary.py [heating_date]

  If heating_date is not specified, calculates for the cycle that just ended.
  heating_date format: YYYY-MM-DD
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from typing import Optional

# Configuration
HA_HOST = os.getenv("HA_HOST", "192.168.50.11")
HA_PORT = os.getenv("HA_PORT", "8123")
HA_TOKEN = os.getenv("HA_TOKEN", "")

BASE_URL = f"http://{HA_HOST}:{HA_PORT}/api"


def get_heating_date(dt: datetime) -> str:
    """Get the heating date for a given datetime.

    Heating cycle runs from 21:00 to 21:00 next day.
    If before 21:00, heating_date is previous day.
    """
    if dt.hour < 21:
        return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d")


def get_cycle_window(heating_date: str) -> tuple[datetime, datetime]:
    """Get the cycle window start and end times.

    Args:
        heating_date: YYYY-MM-DD string

    Returns:
        (cycle_start, cycle_end) as datetime objects
    """
    date_obj = datetime.strptime(heating_date, "%Y-%m-%d")
    cycle_start = date_obj.replace(hour=21, minute=0, second=0, microsecond=0)
    cycle_end = (date_obj + timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)
    return cycle_start, cycle_end


def fetch_history(entity_id: str, start_time: datetime, end_time: datetime) -> list:
    """Fetch entity history from HA REST API.

    Args:
        entity_id: The entity to query
        start_time: Start of history window
        end_time: End of history window

    Returns:
        List of state records
    """
    if not HA_TOKEN:
        print("Error: HA_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }

    # Format times for API (ISO format with timezone)
    start_str = start_time.isoformat()
    end_str = end_time.isoformat()

    url = f"{BASE_URL}/history/period/{start_str}"
    params = {
        "filter_entity_id": entity_id,
        "end_time": end_str,
        # Don't use minimal_response to ensure attributes are included
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data and len(data) > 0:
            return data[0]  # History API returns list of lists
        return []

    except requests.exceptions.RequestException as e:
        print(f"Error fetching history: {e}", file=sys.stderr)
        return []


def calculate_cycle_totals(heating_date: str) -> dict:
    """Calculate cycle totals from 15-minute sensor history.

    Aggregates:
    - Total energy (kWh) from sensor state values
    - Total cost (EUR) from period_cost_eur attributes
    - Count of 15-min periods with heating

    Args:
        heating_date: YYYY-MM-DD string for the cycle start

    Returns:
        Dictionary with cycle totals
    """
    cycle_start, cycle_end = get_cycle_window(heating_date)

    print(f"Calculating cycle summary for {heating_date}")
    print(f"  Window: {cycle_start.isoformat()} → {cycle_end.isoformat()}")

    # Fetch 15-minute sensor history
    history = fetch_history("sensor.pool_heating_15min_energy", cycle_start, cycle_end)

    if not history:
        print("  No history data found")
        return {
            "date": heating_date,
            "energy": 0,
            "cost": 0,
            "periods": 0,
            "error": "No history data"
        }

    print(f"  Found {len(history)} history records")

    # Aggregate values
    total_energy = 0.0
    total_cost = 0.0
    periods_with_energy = 0
    prices = []

    # Maximum reasonable energy per 15-min period
    # 5kW heat pump = max 1.25 kWh per 15 min
    # Use 5 kWh as threshold to filter out erroneous cumulative values
    MAX_ENERGY_PER_PERIOD = 5.0

    for record in history:
        state = record.get("state", "0")
        attributes = record.get("attributes", {})

        # Skip unavailable states
        if state in ["unknown", "unavailable", None]:
            continue

        try:
            energy = float(state)
            cost = float(attributes.get("period_cost_eur", 0) or 0)
            price = float(attributes.get("period_price_eur", 0) or 0)

            # Filter out erroneous values (e.g., cumulative accidentally stored as state)
            if energy > MAX_ENERGY_PER_PERIOD:
                print(f"  Skipping erroneous value: {energy:.3f} kWh (> {MAX_ENERGY_PER_PERIOD})")
                continue

            if energy > 0:
                total_energy += energy
                total_cost += cost
                periods_with_energy += 1
                if price > 0:
                    prices.append(price)

        except (ValueError, TypeError):
            continue

    # Calculate average heating price (the prices we actually paid)
    avg_heating_price = sum(prices) / len(prices) if prices else 0

    # Calculate baseline cost using average of ALL window prices
    # This shows savings vs heating at random times
    print("  Fetching all window prices for baseline calculation...")
    all_window_prices = []

    nordpool_history = fetch_history(
        "sensor.nordpool_kwh_fi_eur_3_10_0255",
        cycle_start,
        cycle_end
    )
    if nordpool_history:
        for r in nordpool_history:
            state = r.get("state", "0")
            if state not in ["unknown", "unavailable", None]:
                try:
                    all_window_prices.append(float(state))
                except (ValueError, TypeError):
                    pass

    if all_window_prices:
        avg_window_price = sum(all_window_prices) / len(all_window_prices)
        print(f"  Window average price: {avg_window_price:.4f} EUR/kWh ({len(all_window_prices)} price points)")
    else:
        avg_window_price = avg_heating_price  # Fallback
        print("  No window prices found, using heating prices for baseline")

    baseline_cost = total_energy * avg_window_price
    savings = baseline_cost - total_cost
    avg_price = avg_heating_price

    print(f"  Total energy: {total_energy:.3f} kWh")
    print(f"  Total cost: {total_cost:.4f} EUR")
    print(f"  Periods with energy: {periods_with_energy}")
    print(f"  Average price: {avg_price:.4f} EUR/kWh")
    print(f"  Baseline cost: {baseline_cost:.4f} EUR")
    print(f"  Savings: {savings:.4f} EUR")

    return {
        "date": heating_date,
        "energy": round(total_energy, 3),
        "cost": round(total_cost, 4),
        "baseline": round(baseline_cost, 4),
        "savings": round(savings, 4),
        "periods": periods_with_energy,
        "avg_price": round(avg_price, 4)
    }


def store_summary(summary: dict) -> bool:
    """Store cycle summary in HA input_text entity.

    Args:
        summary: Dictionary with cycle summary data

    Returns:
        True if successful, False otherwise
    """
    if not HA_TOKEN:
        print("Error: HA_TOKEN not set", file=sys.stderr)
        return False

    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }

    # Store as JSON in input_text
    url = f"{BASE_URL}/services/input_text/set_value"
    payload = {
        "entity_id": "input_text.pool_heating_night_summary_data",
        "value": json.dumps(summary)
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print(f"  Summary stored in input_text.pool_heating_night_summary_data")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Error storing summary: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point."""
    # Determine heating date
    if len(sys.argv) > 1:
        heating_date = sys.argv[1]
    else:
        # Default to the cycle that just ended
        now = datetime.now()
        # If it's after 21:00, the cycle that just ended is yesterday's
        # If it's before 21:00, the cycle that just ended is the day before yesterday's
        if now.hour >= 21:
            heating_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            heating_date = (now - timedelta(days=2)).strftime("%Y-%m-%d")

    # Calculate totals
    summary = calculate_cycle_totals(heating_date)

    # Store in HA
    if "error" not in summary:
        store_summary(summary)

    # Output summary as JSON
    print("\nCycle Summary JSON:")
    print(json.dumps(summary, indent=2))

    return 0 if "error" not in summary else 1


if __name__ == "__main__":
    sys.exit(main())
