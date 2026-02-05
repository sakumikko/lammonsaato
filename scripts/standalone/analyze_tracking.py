#!/usr/bin/env python3
"""
Analyze heating cycles and simulate tracking formula.

Simulates: next_supply_target = current_supply_temp - current_supply_temp*(outdoor_temp - current_supply_temp)*k
Applied every 30 seconds, k ≈ 0.0001

Usage:
    ./env/bin/python scripts/standalone/analyze_tracking.py
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HA_URL = os.environ.get("HA_URL", "http://192.168.50.11:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")

SUPPLY_ENTITY = "sensor.system_supply_line_temperature"
OUTDOOR_ENTITY = "sensor.outdoor_temperature"

def fetch_history(entity_id: str, start_time: datetime, end_time: datetime) -> list:
    """Fetch history for an entity between start and end times."""
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}

    # Format times for HA API
    start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S")

    url = f"{HA_URL}/api/history/period/{start_str}"
    params = {
        "filter_entity_id": entity_id,
        "end_time": end_str,
        "minimal_response": "false"
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                return data[0]
        return []
    except Exception as e:
        print(f"Error fetching {entity_id}: {e}")
        return []


def parse_history(history: list) -> list:
    """Parse history into list of (timestamp, value) tuples."""
    result = []
    for entry in history:
        try:
            ts = datetime.fromisoformat(entry["last_changed"].replace("Z", "+00:00"))
            val = float(entry["state"])
            result.append((ts, val))
        except (ValueError, KeyError):
            continue
    return sorted(result, key=lambda x: x[0])


def interpolate_at_time(data: list, target_time: datetime) -> float | None:
    """Interpolate value at a specific time from historical data."""
    if not data:
        return None

    # Make target_time offset-aware if data has timezone info
    if data[0][0].tzinfo is not None and target_time.tzinfo is None:
        from datetime import timezone
        target_time = target_time.replace(tzinfo=timezone.utc)

    # Find surrounding points
    before = None
    after = None

    for ts, val in data:
        if ts <= target_time:
            before = (ts, val)
        elif after is None:
            after = (ts, val)
            break

    if before is None:
        return data[0][1] if data else None
    if after is None:
        return before[1]

    # Linear interpolation
    t0, v0 = before
    t1, v1 = after

    total_seconds = (t1 - t0).total_seconds()
    if total_seconds == 0:
        return v0

    elapsed = (target_time - t0).total_seconds()
    ratio = elapsed / total_seconds

    return v0 + (v1 - v0) * ratio


def simulate_tracking(supply_data: list, outdoor_data: list,
                      start_time: datetime, duration_minutes: int,
                      k: float = 0.0001, interval_seconds: int = 30) -> dict:
    """
    Simulate the tracking formula over a period.

    Formula: next_supply_target = current_supply - current_supply * (outdoor - current_supply) * k

    Returns simulation results including PID sum.
    """
    from datetime import timezone

    results = {
        "k": k,
        "interval_seconds": interval_seconds,
        "start_time": start_time.isoformat(),
        "duration_minutes": duration_minutes,
        "steps": [],
        "pid_sum": 0.0,
        "total_steps": 0
    }

    # Make start_time offset-aware
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)

    current_time = start_time
    end_time = start_time + timedelta(minutes=duration_minutes)

    # Get initial supply temp as our starting target
    supply_target = interpolate_at_time(supply_data, current_time)
    if supply_target is None:
        print(f"  No supply data at {current_time}")
        return results

    print(f"\n  Simulation: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
    print(f"  Initial supply target: {supply_target:.2f}°C")
    print(f"  k={k}, interval={interval_seconds}s")

    step = 0
    while current_time < end_time:
        # Get current actual values
        actual_supply = interpolate_at_time(supply_data, current_time)
        outdoor = interpolate_at_time(outdoor_data, current_time)

        if actual_supply is None or outdoor is None:
            current_time += timedelta(seconds=interval_seconds)
            continue

        # Calculate next target using formula (corrected: + not -)
        # next_supply_target = current_supply + current_supply * (outdoor - current_supply) * k
        # When outdoor < supply, (outdoor - supply) is negative, so target decreases (tracks down)
        delta = supply_target * (outdoor - supply_target) * k
        next_target = supply_target + delta

        # Error = actual - target (for PID tracking)
        error = actual_supply - supply_target

        results["steps"].append({
            "time": current_time.strftime("%H:%M:%S"),
            "actual_supply": round(actual_supply, 2),
            "outdoor": round(outdoor, 2),
            "target": round(supply_target, 2),
            "delta": round(delta, 4),
            "next_target": round(next_target, 2),
            "error": round(error, 2)
        })

        results["pid_sum"] += error
        results["total_steps"] += 1

        # Update target for next iteration
        supply_target = next_target
        current_time += timedelta(seconds=interval_seconds)
        step += 1

    if results["total_steps"] > 0:
        results["avg_error"] = results["pid_sum"] / results["total_steps"]
    else:
        results["avg_error"] = 0

    return results


def analyze_period(name: str, start: datetime, end: datetime, k: float = 0.0001):
    """Analyze a specific heating period."""
    print(f"\n{'='*60}")
    print(f"Period: {name}")
    print(f"Time: {start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%H:%M')}")
    print(f"{'='*60}")

    # Fetch historical data with some buffer before/after
    fetch_start = start - timedelta(minutes=15)
    fetch_end = end + timedelta(minutes=15)

    print(f"Fetching supply temperature...")
    supply_history = fetch_history(SUPPLY_ENTITY, fetch_start, fetch_end)
    supply_data = parse_history(supply_history)
    print(f"  Got {len(supply_data)} data points")

    print(f"Fetching outdoor temperature...")
    outdoor_history = fetch_history(OUTDOOR_ENTITY, fetch_start, fetch_end)
    outdoor_data = parse_history(outdoor_history)
    print(f"  Got {len(outdoor_data)} data points")

    if not supply_data or not outdoor_data:
        print("  Insufficient data for analysis")
        return None

    # Show data range
    if supply_data:
        temps = [v for _, v in supply_data]
        print(f"  Supply range: {min(temps):.1f} - {max(temps):.1f}°C")
    if outdoor_data:
        temps = [v for _, v in outdoor_data]
        print(f"  Outdoor range: {min(temps):.1f} - {max(temps):.1f}°C")

    # Run simulation
    duration = int((end - start).total_seconds() / 60)
    results = simulate_tracking(supply_data, outdoor_data, start, duration, k=k)

    return results


def main():
    if not HA_TOKEN:
        print("Error: HA_TOKEN required")
        sys.exit(1)

    print("Pool Heating Tracking Formula Analysis")
    print("=" * 60)
    print(f"Formula: next_target = supply + supply * (outdoor - supply) * k")
    print(f"When outdoor < supply, (outdoor-supply) is negative => target decreases")
    print(f"Applied every 30 seconds")

    # Define the periods from last night (2026-02-04 night to 2026-02-05 morning)
    # Based on user's info: 00:30-01:00, 02:30-03:00, 06:00-06:30
    # NOTE: Today is 2026-02-05

    periods = [
        ("Period 1: 00:30-01:00",
         datetime(2026, 2, 5, 0, 30),
         datetime(2026, 2, 5, 1, 0)),
        ("Period 2: 02:30-03:00",
         datetime(2026, 2, 5, 2, 30),
         datetime(2026, 2, 5, 3, 0)),
        ("Period 3: 06:00-06:30",
         datetime(2026, 2, 5, 6, 0),
         datetime(2026, 2, 5, 6, 30)),
    ]

    # Test different k values
    k_values = [0.0001, 0.0002, 0.00005, 0.0003]

    all_results = {}

    for k in k_values:
        print(f"\n\n{'#'*60}")
        print(f"# Testing k = {k}")
        print(f"{'#'*60}")

        all_results[k] = {}
        total_pid_sum = 0
        total_steps = 0

        for name, start, end in periods:
            result = analyze_period(name, start, end, k=k)
            if result:
                all_results[k][name] = result
                total_pid_sum += result["pid_sum"]
                total_steps += result["total_steps"]

                print(f"\n  Results for k={k}:")
                print(f"    Steps: {result['total_steps']}")
                print(f"    PID Sum: {result['pid_sum']:.2f}")
                print(f"    Avg Error: {result['avg_error']:.2f}°C")

                # Show first few steps
                if result["steps"]:
                    print(f"\n    First 5 steps:")
                    for step in result["steps"][:5]:
                        print(f"      {step['time']}: supply={step['actual_supply']}°C, "
                              f"outdoor={step['outdoor']}°C, target={step['target']}°C, "
                              f"delta={step['delta']}, error={step['error']}°C")

        if total_steps > 0:
            print(f"\n  === Summary for k={k} ===")
            print(f"  Total steps: {total_steps}")
            print(f"  Total PID Sum: {total_pid_sum:.2f}")
            print(f"  Overall Avg Error: {total_pid_sum/total_steps:.2f}°C")

    # Summary comparison
    print(f"\n\n{'='*60}")
    print("COMPARISON SUMMARY")
    print("="*60)
    print(f"{'k':<12} {'Total Steps':<15} {'PID Sum':<15} {'Avg Error':<15}")
    print("-"*60)

    for k in k_values:
        total_steps = sum(r.get("total_steps", 0) for r in all_results[k].values())
        total_pid = sum(r.get("pid_sum", 0) for r in all_results[k].values())
        avg_err = total_pid / total_steps if total_steps > 0 else 0
        print(f"{k:<12} {total_steps:<15} {total_pid:<15.2f} {avg_err:<15.2f}°C")


if __name__ == "__main__":
    main()
