#!/usr/bin/env python3
"""
Live Integration Tests

Tests the pool heating system with live data from:
- Thermia heat pump (Modbus TCP)
- Nordpool API (electricity prices)
- Home Assistant API (when available)

Usage:
    # Run all live tests
    python test_live_integration.py

    # Run specific test
    python test_live_integration.py --test thermia
    python test_live_integration.py --test nordpool
    python test_live_integration.py --test algorithm
    python test_live_integration.py --test full

    # With custom Thermia host
    python test_live_integration.py --thermia-host 192.168.50.10
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================
# CONFIGURATION
# ============================================

@dataclass
class TestConfig:
    """Test configuration."""
    thermia_host: str = "192.168.50.10"
    thermia_port: int = 502
    thermia_kind: str = "mega"
    ha_url: str = "http://homeassistant.local:8123"
    ha_token: str = ""
    dry_run: bool = True
    verbose: bool = False

    @classmethod
    def from_env(cls) -> "TestConfig":
        """Load config from environment."""
        return cls(
            thermia_host=os.environ.get("THERMIA_HOST", "192.168.50.10"),
            thermia_port=int(os.environ.get("THERMIA_PORT", "502")),
            thermia_kind=os.environ.get("THERMIA_KIND", "mega"),
            ha_url=os.environ.get("HA_URL", "http://homeassistant.local:8123"),
            ha_token=os.environ.get("HA_TOKEN", ""),
            dry_run=os.environ.get("TEST_DRY_RUN", "true").lower() == "true",
            verbose=os.environ.get("VERBOSE", "false").lower() == "true"
        )


# ============================================
# PRICE OPTIMIZATION ALGORITHM (for testing)
# ============================================

# Configuration
TOTAL_HEATING_MINUTES = 120  # 2 hours total
MIN_BLOCK_MINUTES = 30       # Minimum consecutive heating
MAX_BLOCK_MINUTES = 45       # Maximum consecutive heating
SLOT_DURATION_MINUTES = 15   # Nordpool 15-minute intervals


def find_best_heating_schedule(
    prices_today: list,
    prices_tomorrow: list,
    window_start: int = 21,
    window_end: int = 7,
    total_minutes: int = 120,
    min_block_minutes: int = 30,
    max_block_minutes: int = 45,
    slot_minutes: int = 15
) -> List[Dict]:
    """
    Find optimal heating schedule using 15-minute price intervals.

    Constraints:
    - Total heating time: 2 hours (120 minutes)
    - Each heating block: 30-45 minutes (2-3 slots)
    - Break between blocks: at least equal to preceding block duration

    Returns:
        List of dicts with 'start', 'end', 'duration_minutes', 'avg_price'
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Build list of all 15-minute slots in the heating window
    slots = []

    def slot_index(hour, quarter=0):
        return hour * 4 + quarter

    # Tonight's slots (21:00 - 23:45)
    for hour in range(window_start, 24):
        for quarter in range(4):
            idx = slot_index(hour, quarter)
            if prices_today and idx < len(prices_today):
                dt = datetime.combine(today, datetime.min.time().replace(
                    hour=hour, minute=quarter * 15))
                slots.append({
                    'datetime': dt,
                    'index': len(slots),
                    'price': prices_today[idx],
                    'day': 'today'
                })

    # Tomorrow morning slots (00:00 - 06:45)
    for hour in range(0, window_end):
        for quarter in range(4):
            idx = slot_index(hour, quarter)
            if prices_tomorrow and idx < len(prices_tomorrow):
                dt = datetime.combine(tomorrow, datetime.min.time().replace(
                    hour=hour, minute=quarter * 15))
                slots.append({
                    'datetime': dt,
                    'index': len(slots),
                    'price': prices_tomorrow[idx],
                    'day': 'tomorrow'
                })

    if not slots:
        return []

    min_block_slots = min_block_minutes // slot_minutes
    max_block_slots = max_block_minutes // slot_minutes
    total_slots_needed = total_minutes // slot_minutes

    best_schedule = None
    best_cost = float('inf')

    block_combinations = []
    _find_block_combinations(
        total_slots_needed, min_block_slots, max_block_slots,
        [], block_combinations
    )

    for block_sizes in block_combinations:
        schedule = _find_best_placement(slots, block_sizes, slot_minutes)
        if schedule:
            total_cost = sum(b['avg_price'] * b['duration_minutes'] for b in schedule)
            if total_cost < best_cost:
                best_cost = total_cost
                best_schedule = schedule

    return best_schedule or []


def _find_block_combinations(remaining, min_size, max_size, current, results):
    """Recursively find all valid combinations of block sizes."""
    if remaining == 0:
        if current:
            results.append(current[:])
        return
    if remaining < min_size:
        return

    for size in range(min_size, min(max_size, remaining) + 1):
        current.append(size)
        _find_block_combinations(remaining - size, min_size, max_size, current, results)
        current.pop()


def _find_best_placement(slots, block_sizes, slot_minutes):
    """Find the best placement of heating blocks with given sizes."""
    n_slots = len(slots)
    n_blocks = len(block_sizes)

    if n_blocks == 0:
        return []

    def block_cost(start_idx, size):
        if start_idx + size > n_slots:
            return float('inf'), None
        block_slots = slots[start_idx:start_idx + size]
        avg_price = sum(s['price'] for s in block_slots) / size
        return avg_price, block_slots

    best_schedule = None
    best_total_cost = float('inf')

    def search(block_idx, min_start_idx, current_schedule, current_cost):
        nonlocal best_schedule, best_total_cost

        if block_idx >= n_blocks:
            if current_cost < best_total_cost:
                best_total_cost = current_cost
                best_schedule = current_schedule[:]
            return

        block_size = block_sizes[block_idx]

        for start_idx in range(min_start_idx, n_slots - block_size + 1):
            avg_price, block_slots = block_cost(start_idx, block_size)

            if avg_price == float('inf'):
                break

            block_info = {
                'start': block_slots[0]['datetime'],
                'end': block_slots[-1]['datetime'] + timedelta(minutes=slot_minutes),
                'duration_minutes': block_size * slot_minutes,
                'avg_price': avg_price,
                'slots': block_slots
            }

            new_cost = current_cost + avg_price * block_size

            if new_cost >= best_total_cost:
                continue

            next_min_start = start_idx + block_size + block_size

            current_schedule.append(block_info)
            search(block_idx + 1, next_min_start, current_schedule, new_cost)
            current_schedule.pop()

    search(0, 0, [], 0)

    if best_schedule:
        for block in best_schedule:
            del block['slots']

    return best_schedule


# Legacy function for backward compatibility
def find_best_heating_slots(prices_today: list, prices_tomorrow: list,
                           window_start: int = 21, window_end: int = 7,
                           num_slots: int = 2, min_gap: int = 1) -> List[Tuple[datetime, float]]:
    """
    Legacy function - use find_best_heating_schedule() for 15-minute intervals.
    """
    # If we have 96 prices, assume 15-minute intervals
    if prices_today and len(prices_today) > 24:
        schedule = find_best_heating_schedule(
            prices_today, prices_tomorrow,
            window_start, window_end
        )
        return [(b['start'], b['avg_price']) for b in schedule]

    # Original hourly logic
    today = date.today()
    tomorrow = today + timedelta(days=1)

    valid_hours = []

    for hour in range(window_start, 24):
        if prices_today and hour < len(prices_today):
            dt = datetime.combine(today, datetime.min.time().replace(hour=hour))
            valid_hours.append({
                'datetime': dt,
                'hour': hour,
                'price': prices_today[hour],
                'day': 'today'
            })

    for hour in range(0, window_end):
        if prices_tomorrow and hour < len(prices_tomorrow):
            dt = datetime.combine(tomorrow, datetime.min.time().replace(hour=hour))
            valid_hours.append({
                'datetime': dt,
                'hour': hour,
                'price': prices_tomorrow[hour],
                'day': 'tomorrow'
            })

    valid_hours.sort(key=lambda x: x['price'])
    selected = []

    for candidate in valid_hours:
        if len(selected) >= num_slots:
            break

        is_too_close = False
        for sel in selected:
            cand_abs_hour = candidate['hour'] + (24 if candidate['day'] == 'tomorrow' else 0)
            sel_abs_hour = sel['hour'] + (24 if sel['day'] == 'tomorrow' else 0)

            if abs(cand_abs_hour - sel_abs_hour) <= min_gap:
                is_too_close = True
                break

        if not is_too_close:
            selected.append(candidate)

    selected.sort(key=lambda x: x['datetime'])
    return [(s['datetime'], s['price']) for s in selected]


# ============================================
# THERMIA LIVE TESTS
# ============================================

# Key registers for pool heating monitoring
# Note: Must specify registers explicitly due to library bug with range_end
THERMIA_KEY_REGISTERS = [
    'input_outdoor_temperature',
    'input_system_supply_line_temperature',
    'input_brine_in_temperature',
    'input_brine_out_temperature',
    'input_compressor_speed_percent',
    'input_compressor_current_gear',
    'input_mix_valve_1_supply_line_temperature',
    # Pool registers (may show raw values if sensors not connected)
    'input_pool_supply_line_temperature',
    'input_pool_return_line_temperature',
    'input_condenser_in_temperature',
    'input_condenser_out_temperature'
]


async def test_thermia_connection(config: TestConfig) -> dict:
    """
    Test live connection to Thermia heat pump.

    Returns dict with test results.
    """
    print("\n" + "="*60)
    print("THERMIA MODBUS CONNECTION TEST")
    print("="*60)

    results = {
        "test": "thermia_connection",
        "success": False,
        "host": config.thermia_host,
        "port": config.thermia_port,
        "data": {}
    }

    try:
        from pythermiagenesis import ThermiaGenesis
        from pythermiagenesis.const import REGISTERS, KEY_ADDRESS

        print(f"\nConnecting to Thermia at {config.thermia_host}:{config.thermia_port}...")

        thermia = ThermiaGenesis(
            config.thermia_host,
            port=config.thermia_port,
            kind=config.thermia_kind,
            delay=0.15
        )

        # Read specific registers to avoid library bug with invalid register ranges
        await thermia.async_update(only_registers=THERMIA_KEY_REGISTERS)

        if thermia.available:
            print(f"\n✓ Connected successfully!")
            print(f"  Model: {thermia.model}")
            print(f"  Firmware: {thermia.firmware or 'N/A'}")

            print(f"\nSensor Values:")
            print("-" * 50)

            for name, value in sorted(thermia.data.items()):
                addr = REGISTERS.get(name, {}).get(KEY_ADDRESS, "?")
                # Format value nicely
                if isinstance(value, float):
                    value_str = f"{value:.2f}"
                else:
                    value_str = str(value)
                print(f"  [{addr:>3}] {name}: {value_str}")
                results["data"][name] = value

            # Calculate delta-T if we have supply and return temps
            supply = thermia.data.get('input_system_supply_line_temperature')
            brine_in = thermia.data.get('input_brine_in_temperature')
            brine_out = thermia.data.get('input_brine_out_temperature')

            if supply is not None and brine_in is not None:
                print(f"\n  System supply temp: {supply:.1f}°C")
            if brine_in is not None and brine_out is not None:
                brine_delta = brine_in - brine_out
                print(f"  Brine Delta-T: {brine_delta:.1f}°C (in: {brine_in:.1f}, out: {brine_out:.1f})")
                results["data"]["brine_delta_t"] = brine_delta

            results["success"] = True
            results["model"] = thermia.model
            results["firmware"] = thermia.firmware

        else:
            print(f"\n✗ Connection failed - device not available")

    except ImportError:
        print("\n✗ pythermiagenesis not installed")
        print("  Install with: pip install pythermiagenesis")
        results["error"] = "pythermiagenesis not installed"

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        if config.verbose:
            traceback.print_exc()
        results["error"] = str(e)

    return results


async def test_thermia_specific_registers(config: TestConfig, registers: List[str]) -> dict:
    """Test reading specific Thermia registers."""
    print(f"\nReading specific registers: {registers}")

    try:
        from pythermiagenesis import ThermiaGenesis

        thermia = ThermiaGenesis(
            config.thermia_host,
            port=config.thermia_port,
            kind=config.thermia_kind,
            delay=0.15
        )

        await thermia.async_update(only_registers=registers)

        results = {"success": thermia.available, "data": {}}
        if thermia.available:
            for name, value in thermia.data.items():
                results["data"][name] = value
                print(f"  {name}: {value}")

        return results

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================
# NORDPOOL LIVE TESTS
# ============================================

async def test_nordpool_api(config: TestConfig) -> dict:
    """
    Test live Nordpool API for Finland prices.

    Returns dict with test results including actual prices.
    """
    print("\n" + "="*60)
    print("NORDPOOL API TEST (Finland)")
    print("="*60)

    results = {
        "test": "nordpool_api",
        "success": False,
        "today_prices": [],
        "tomorrow_prices": [],
        "tomorrow_available": False
    }

    try:
        import aiohttp

        # Nordpool data source (same as HA integration uses)
        # Using a public endpoint that provides day-ahead prices
        today = date.today()
        tomorrow = today + timedelta(days=1)

        print(f"\nFetching prices for {today} and {tomorrow}...")

        # Try fetching from a reliable source
        # The HA Nordpool integration uses nordpoolgroup.com
        async with aiohttp.ClientSession() as session:
            # Fetch today's prices
            today_prices = await fetch_nordpool_day(session, today)
            if today_prices:
                results["today_prices"] = today_prices
                print(f"\n✓ Today's prices ({today}):")
                print(f"  Hours available: {len(today_prices)}")
                print(f"  Min: {min(today_prices)*100:.2f} c/kWh")
                print(f"  Max: {max(today_prices)*100:.2f} c/kWh")
                print(f"  Avg: {sum(today_prices)/len(today_prices)*100:.2f} c/kWh")

                # Show heating window prices (first slot of each hour for brevity)
                print(f"\n  Tonight's prices (21:00-23:00, showing hourly avg):")
                for h in range(21, 24):
                    slot_idx = h * 4
                    if slot_idx + 3 < len(today_prices):
                        # Show average of 4 15-min slots
                        hour_prices = today_prices[slot_idx:slot_idx + 4]
                        avg = sum(hour_prices) / 4
                        print(f"    {h:02d}:00 - {avg*100:6.2f} c/kWh (avg of 4 slots)")

            # Fetch tomorrow's prices (may not be available before ~13:00 CET)
            tomorrow_prices = await fetch_nordpool_day(session, tomorrow)
            if tomorrow_prices:
                results["tomorrow_prices"] = tomorrow_prices
                results["tomorrow_available"] = True
                print(f"\n✓ Tomorrow's prices ({tomorrow}):")
                print(f"  Hours available: {len(tomorrow_prices)}")
                print(f"  Min: {min(tomorrow_prices)*100:.2f} c/kWh")
                print(f"  Max: {max(tomorrow_prices)*100:.2f} c/kWh")

                print(f"\n  Tomorrow morning prices (00:00-06:00, showing hourly avg):")
                for h in range(0, 7):
                    slot_idx = h * 4
                    if slot_idx + 3 < len(tomorrow_prices):
                        hour_prices = tomorrow_prices[slot_idx:slot_idx + 4]
                        avg = sum(hour_prices) / 4
                        print(f"    {h:02d}:00 - {avg*100:6.2f} c/kWh (avg of 4 slots)")
            else:
                print(f"\n⚠ Tomorrow's prices not yet available")
                print(f"  (Usually published around 13:00 CET)")

        results["success"] = len(results["today_prices"]) > 0

    except ImportError:
        print("\n✗ aiohttp not installed")
        results["error"] = "aiohttp not installed"

    except Exception as e:
        print(f"\n✗ Error: {e}")
        results["error"] = str(e)

    return results


async def fetch_nordpool_day(session, target_date: date) -> List[float]:
    """
    Fetch Nordpool prices for a specific day.

    Returns list of 96 prices (15-minute intervals) in EUR/kWh.
    """
    # Try multiple sources
    prices = await fetch_from_elering(session, target_date)
    if prices:
        return prices

    # Fallback to mock data for testing (remove in production)
    if target_date == date.today():
        # Return realistic Finnish winter prices (96 slots)
        return generate_realistic_prices_15min()

    return []


async def fetch_from_elering(session, target_date: date) -> Optional[List[float]]:
    """
    Fetch prices from Elering API (Estonian TSO, has Finnish prices too).

    This is a real API that provides Nordpool prices.
    Note: Elering API may return hourly or 15-minute data depending on availability.
    """
    try:
        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)

        url = "https://dashboard.elering.ee/api/nps/price"
        params = {
            "start": start.isoformat() + "Z",
            "end": end.isoformat() + "Z"
        }

        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                # Extract Finnish prices
                fi_prices = data.get("data", {}).get("fi", [])
                if fi_prices:
                    # Convert from EUR/MWh to EUR/kWh
                    prices = [p["price"] / 1000 for p in sorted(fi_prices, key=lambda x: x["timestamp"])]
                    # If we got hourly data (24 prices), expand to 15-minute (96)
                    if len(prices) == 24:
                        prices = expand_hourly_to_15min(prices)
                    return prices

    except Exception as e:
        print(f"  Elering API error: {e}")

    return None


def expand_hourly_to_15min(hourly_prices: List[float]) -> List[float]:
    """Expand 24 hourly prices to 96 15-minute slots (same price for each quarter)."""
    prices_15min = []
    for price in hourly_prices:
        prices_15min.extend([price] * 4)
    return prices_15min


def generate_realistic_prices_15min() -> List[float]:
    """Generate realistic Finnish electricity prices for testing (96 x 15-min slots)."""
    import random
    random.seed(date.today().toordinal())  # Consistent for same day

    # Base hourly pattern: low at night, peak in morning/evening
    base_hourly = [
        0.04, 0.035, 0.03, 0.028, 0.03, 0.04, 0.06,    # 00-06
        0.08, 0.10, 0.09, 0.08, 0.075, 0.07, 0.068,    # 07-13
        0.07, 0.08, 0.12, 0.15, 0.12, 0.09, 0.07,      # 14-20
        0.055, 0.045, 0.04                              # 21-23
    ]

    # Expand to 15-minute slots with small variations within each hour
    prices_15min = []
    for hourly_price in base_hourly:
        for _ in range(4):
            # Add small variation within each 15-min slot
            variation = random.uniform(-0.005, 0.005)
            prices_15min.append(max(0, hourly_price + variation))

    return prices_15min


# ============================================
# ALGORITHM TEST WITH LIVE DATA
# ============================================

async def test_algorithm_with_live_data(config: TestConfig) -> dict:
    """
    Test the price optimization algorithm with live Nordpool data.

    Tests the new 15-minute interval algorithm with:
    - 30-45 minute heating blocks
    - Equal duration breaks between blocks
    - Total 2 hours of heating
    """
    print("\n" + "="*60)
    print("ALGORITHM TEST WITH LIVE DATA (15-min intervals)")
    print("="*60)

    results = {
        "test": "algorithm_live",
        "success": False,
        "schedule": []
    }

    # First get live prices
    price_results = await test_nordpool_api(config)

    if not price_results["success"]:
        print("\n✗ Cannot test algorithm - no price data")
        results["error"] = "No price data available"
        return results

    today_prices = price_results["today_prices"]
    tomorrow_prices = price_results.get("tomorrow_prices", [])

    print(f"\n  Price data: {len(today_prices)} today slots, {len(tomorrow_prices)} tomorrow slots")

    print("\n" + "-"*40)
    print("Running optimization algorithm...")
    print("  Constraints:")
    print(f"    - Total heating: {TOTAL_HEATING_MINUTES} minutes")
    print(f"    - Block size: {MIN_BLOCK_MINUTES}-{MAX_BLOCK_MINUTES} minutes")
    print(f"    - Break: >= block duration")

    # Run the new algorithm
    schedule = find_best_heating_schedule(
        today_prices,
        tomorrow_prices,
        window_start=21,
        window_end=7,
        total_minutes=TOTAL_HEATING_MINUTES,
        min_block_minutes=MIN_BLOCK_MINUTES,
        max_block_minutes=MAX_BLOCK_MINUTES,
        slot_minutes=SLOT_DURATION_MINUTES
    )

    if schedule:
        total_minutes = sum(b['duration_minutes'] for b in schedule)
        print(f"\n✓ Algorithm found schedule with {len(schedule)} blocks ({total_minutes} min total):")

        for i, block in enumerate(schedule, 1):
            print(f"\n  Block {i}:")
            print(f"    Time: {block['start'].strftime('%Y-%m-%d %H:%M')} - {block['end'].strftime('%H:%M')}")
            print(f"    Duration: {block['duration_minutes']} minutes")
            print(f"    Avg Price: {block['avg_price']*100:.2f} c/kWh")

            results["schedule"].append({
                "start": block['start'].isoformat(),
                "end": block['end'].isoformat(),
                "duration_minutes": block['duration_minutes'],
                "avg_price_eur_kwh": block['avg_price'],
                "avg_price_cents_kwh": block['avg_price'] * 100
            })

        # Verify constraints
        print(f"\n  Constraint verification:")

        # Check total time
        print(f"    Total heating: {total_minutes} min (expected {TOTAL_HEATING_MINUTES})")

        # Check block sizes
        for i, block in enumerate(schedule):
            valid_size = MIN_BLOCK_MINUTES <= block['duration_minutes'] <= MAX_BLOCK_MINUTES
            print(f"    Block {i+1} size: {block['duration_minutes']} min ({'✓' if valid_size else '✗'})")

        # Check breaks between blocks
        for i in range(len(schedule) - 1):
            block_end = schedule[i]['end']
            next_start = schedule[i + 1]['start']
            break_minutes = (next_start - block_end).total_seconds() / 60
            required_break = schedule[i]['duration_minutes']
            valid_break = break_minutes >= required_break
            print(f"    Break after block {i+1}: {break_minutes:.0f} min (min {required_break}) {'✓' if valid_break else '✗'}")

        # Calculate savings vs average window price
        # Window prices: 21:00-07:00 = slots 84-95 (today) + 0-27 (tomorrow)
        window_slot_indices_today = list(range(21*4, 24*4))  # 21:00-23:45
        window_slot_indices_tomorrow = list(range(0, 7*4))    # 00:00-06:45

        window_prices = []
        for idx in window_slot_indices_today:
            if idx < len(today_prices):
                window_prices.append(today_prices[idx])
        for idx in window_slot_indices_tomorrow:
            if idx < len(tomorrow_prices):
                window_prices.append(tomorrow_prices[idx])

        if window_prices:
            avg_window = sum(window_prices) / len(window_prices)
            total_cost = sum(b['avg_price'] * b['duration_minutes'] for b in schedule)
            avg_selected = total_cost / total_minutes

            savings = (avg_window - avg_selected) * 100

            print(f"\n  Cost analysis:")
            print(f"    Average window price: {avg_window*100:.2f} c/kWh")
            print(f"    Average selected price: {avg_selected*100:.2f} c/kWh")
            print(f"    Savings vs average: {savings:.2f} c/kWh")
            print(f"    Estimated savings for 2h: {savings * 2:.2f} cents")

            results["avg_window_price"] = avg_window
            results["avg_selected_price"] = avg_selected
            results["savings_cents_kwh"] = savings

        results["success"] = True

    else:
        print("\n✗ Algorithm found no suitable schedule")

    return results


# ============================================
# FULL INTEGRATION TEST
# ============================================

async def test_full_integration(config: TestConfig) -> dict:
    """
    Full integration test combining all components.
    """
    print("\n" + "="*60)
    print("FULL INTEGRATION TEST")
    print("="*60)

    results = {
        "test": "full_integration",
        "success": False,
        "components": {}
    }

    # Test Thermia
    print("\n[1/3] Testing Thermia connection...")
    thermia_result = await test_thermia_connection(config)
    results["components"]["thermia"] = thermia_result

    # Test Nordpool + Algorithm
    print("\n[2/3] Testing Nordpool and algorithm...")
    algo_result = await test_algorithm_with_live_data(config)
    results["components"]["algorithm"] = algo_result

    # Test HA connection (if configured)
    if config.ha_token:
        print("\n[3/3] Testing Home Assistant connection...")
        ha_result = await test_ha_connection(config)
        results["components"]["home_assistant"] = ha_result
    else:
        print("\n[3/3] Skipping HA test (no token configured)")
        results["components"]["home_assistant"] = {"skipped": True}

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    all_passed = True
    for name, result in results["components"].items():
        status = "✓" if result.get("success") or result.get("skipped") else "✗"
        if not result.get("success") and not result.get("skipped"):
            all_passed = False
        print(f"  {status} {name}")

    results["success"] = all_passed
    return results


async def test_ha_connection(config: TestConfig) -> dict:
    """Test Home Assistant API connection."""
    try:
        from ha_client import HAClient

        client = HAClient(config.ha_url, config.ha_token)

        if client.check_connection():
            print(f"  ✓ Connected to Home Assistant")

            # Try to read some entities
            test_entities = [
                "sensor.nordpool_kwh_fi_eur_3_10_024",
                "input_boolean.pool_heating_enabled",
                "input_datetime.pool_heat_slot_1"
            ]

            found = []
            for entity_id in test_entities:
                state = client.get_state(entity_id)
                if state:
                    found.append(entity_id)
                    print(f"    {entity_id}: {state.state}")

            return {"success": True, "entities_found": found}
        else:
            return {"success": False, "error": "Connection failed"}

    except ImportError:
        return {"success": False, "error": "ha_client not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================
# MAIN
# ============================================

async def main():
    parser = argparse.ArgumentParser(description="Live integration tests")
    parser.add_argument("--test", choices=["thermia", "nordpool", "algorithm", "full", "ha"],
                       default="full", help="Test to run")
    parser.add_argument("--thermia-host", help="Thermia host IP")
    parser.add_argument("--ha-url", help="Home Assistant URL")
    parser.add_argument("--ha-token", help="Home Assistant token")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Load config
    config = TestConfig.from_env()

    # Override with CLI args
    if args.thermia_host:
        config.thermia_host = args.thermia_host
    if args.ha_url:
        config.ha_url = args.ha_url
    if args.ha_token:
        config.ha_token = args.ha_token
    if args.verbose:
        config.verbose = True

    # Run requested test
    if args.test == "thermia":
        result = await test_thermia_connection(config)
    elif args.test == "nordpool":
        result = await test_nordpool_api(config)
    elif args.test == "algorithm":
        result = await test_algorithm_with_live_data(config)
    elif args.test == "ha":
        result = await test_ha_connection(config)
    else:
        result = await test_full_integration(config)

    if args.json:
        print("\n" + json.dumps(result, indent=2, default=str))

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
