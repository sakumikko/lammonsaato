"""
Pool Heating Optimizer - Pyscript Module for Home Assistant

This module calculates optimal pool heating times based on Nordpool electricity prices
and logs heating session data.

Place this file in /config/pyscript/pool_heating.py
"""

from datetime import datetime, timedelta, date
import json

# ============================================
# CONFIGURATION
# ============================================

HEATING_WINDOW_START = 21  # 9 PM
HEATING_WINDOW_END = 7     # 7 AM
SLOT_DURATION_MINUTES = 15   # Nordpool now uses 15-minute intervals

# Default values for schedule parameters (used as fallbacks)
DEFAULT_TOTAL_HEATING_MINUTES = 120  # 2 hours total heating
DEFAULT_MIN_BLOCK_MINUTES = 30       # Minimum consecutive heating duration
DEFAULT_MAX_BLOCK_MINUTES = 45       # Maximum consecutive heating duration

# Power consumption for cost calculation
POWER_KW = 5.0  # Heat pump electrical draw during pool heating

# Preheat duration - preheat is FREE (uses minimal power, not charged)
# Block start time = preheat start, heating_start = preheat + 15 min
PREHEAT_MINUTES = 15  # Fixed preheat duration before each heating block
PREHEAT_SLOTS = PREHEAT_MINUTES // SLOT_DURATION_MINUTES  # 1 slot

# Minimum break duration between heating blocks (independent of block duration)
# Radiators need time to stabilize between heating cycles
DEFAULT_MIN_BREAK_DURATION = 60  # Default 60 minutes
VALID_BREAK_DURATIONS = [60, 75, 90, 105, 120]  # Valid options in minutes

# Valid ranges for schedule parameters
VALID_BLOCK_DURATIONS = [30, 45, 60]  # minutes
VALID_TOTAL_HOURS = [x * 0.5 for x in range(0, 11)]  # 0, 0.5, 1.0, ..., 5.0

# Schedule parameter entity IDs
PARAM_MIN_BLOCK_DURATION = "input_number.pool_heating_min_block_duration"
PARAM_MAX_BLOCK_DURATION = "input_number.pool_heating_max_block_duration"
PARAM_TOTAL_HOURS = "input_number.pool_heating_total_hours"
PARAM_MIN_BREAK_DURATION = "input_number.pool_heating_min_break_duration"

# Entity IDs
# IMPORTANT: Update this if your Nordpool sensor has a different entity ID
# Find your sensor ID in Developer Tools > States > search "nordpool"
NORDPOOL_SENSOR = "sensor.nordpool_kwh_fi_eur_3_10_0255"

# Pool heating control switches
# Heating prevention: turn OFF to allow heating, ON to prevent
HEATING_PREVENTION_SWITCH = "switch.altaan_lammityksen_esto"
# Circulation pump: turn ON when heating, OFF when not
CIRCULATION_PUMP_SWITCH = "switch.altaan_kiertovesipumppu"

# Heating block entities (supports up to 10 blocks)
BLOCK_ENTITIES = [
    {"start": "input_datetime.pool_heat_block_1_start",
     "heating_start": "input_datetime.pool_heat_block_1_heating_start",
     "end": "input_datetime.pool_heat_block_1_end",
     "price": "input_number.pool_heat_block_1_price",
     "cost": "input_number.pool_heat_block_1_cost",
     "enabled": "input_boolean.pool_heat_block_1_enabled",
     "cost_exceeded": "input_boolean.pool_heat_block_1_cost_exceeded"},
    {"start": "input_datetime.pool_heat_block_2_start",
     "heating_start": "input_datetime.pool_heat_block_2_heating_start",
     "end": "input_datetime.pool_heat_block_2_end",
     "price": "input_number.pool_heat_block_2_price",
     "cost": "input_number.pool_heat_block_2_cost",
     "enabled": "input_boolean.pool_heat_block_2_enabled",
     "cost_exceeded": "input_boolean.pool_heat_block_2_cost_exceeded"},
    {"start": "input_datetime.pool_heat_block_3_start",
     "heating_start": "input_datetime.pool_heat_block_3_heating_start",
     "end": "input_datetime.pool_heat_block_3_end",
     "price": "input_number.pool_heat_block_3_price",
     "cost": "input_number.pool_heat_block_3_cost",
     "enabled": "input_boolean.pool_heat_block_3_enabled",
     "cost_exceeded": "input_boolean.pool_heat_block_3_cost_exceeded"},
    {"start": "input_datetime.pool_heat_block_4_start",
     "heating_start": "input_datetime.pool_heat_block_4_heating_start",
     "end": "input_datetime.pool_heat_block_4_end",
     "price": "input_number.pool_heat_block_4_price",
     "cost": "input_number.pool_heat_block_4_cost",
     "enabled": "input_boolean.pool_heat_block_4_enabled",
     "cost_exceeded": "input_boolean.pool_heat_block_4_cost_exceeded"},
    {"start": "input_datetime.pool_heat_block_5_start",
     "heating_start": "input_datetime.pool_heat_block_5_heating_start",
     "end": "input_datetime.pool_heat_block_5_end",
     "price": "input_number.pool_heat_block_5_price",
     "cost": "input_number.pool_heat_block_5_cost",
     "enabled": "input_boolean.pool_heat_block_5_enabled",
     "cost_exceeded": "input_boolean.pool_heat_block_5_cost_exceeded"},
    {"start": "input_datetime.pool_heat_block_6_start",
     "heating_start": "input_datetime.pool_heat_block_6_heating_start",
     "end": "input_datetime.pool_heat_block_6_end",
     "price": "input_number.pool_heat_block_6_price",
     "cost": "input_number.pool_heat_block_6_cost",
     "enabled": "input_boolean.pool_heat_block_6_enabled",
     "cost_exceeded": "input_boolean.pool_heat_block_6_cost_exceeded"},
    {"start": "input_datetime.pool_heat_block_7_start",
     "heating_start": "input_datetime.pool_heat_block_7_heating_start",
     "end": "input_datetime.pool_heat_block_7_end",
     "price": "input_number.pool_heat_block_7_price",
     "cost": "input_number.pool_heat_block_7_cost",
     "enabled": "input_boolean.pool_heat_block_7_enabled",
     "cost_exceeded": "input_boolean.pool_heat_block_7_cost_exceeded"},
    {"start": "input_datetime.pool_heat_block_8_start",
     "heating_start": "input_datetime.pool_heat_block_8_heating_start",
     "end": "input_datetime.pool_heat_block_8_end",
     "price": "input_number.pool_heat_block_8_price",
     "cost": "input_number.pool_heat_block_8_cost",
     "enabled": "input_boolean.pool_heat_block_8_enabled",
     "cost_exceeded": "input_boolean.pool_heat_block_8_cost_exceeded"},
    {"start": "input_datetime.pool_heat_block_9_start",
     "heating_start": "input_datetime.pool_heat_block_9_heating_start",
     "end": "input_datetime.pool_heat_block_9_end",
     "price": "input_number.pool_heat_block_9_price",
     "cost": "input_number.pool_heat_block_9_cost",
     "enabled": "input_boolean.pool_heat_block_9_enabled",
     "cost_exceeded": "input_boolean.pool_heat_block_9_cost_exceeded"},
    {"start": "input_datetime.pool_heat_block_10_start",
     "heating_start": "input_datetime.pool_heat_block_10_heating_start",
     "end": "input_datetime.pool_heat_block_10_end",
     "price": "input_number.pool_heat_block_10_price",
     "cost": "input_number.pool_heat_block_10_cost",
     "enabled": "input_boolean.pool_heat_block_10_enabled",
     "cost_exceeded": "input_boolean.pool_heat_block_10_cost_exceeded"},
]

# Cost constraint parameters
PARAM_MAX_COST_EUR = "input_number.pool_heating_max_cost_eur"
PARAM_TOTAL_COST = "input_number.pool_heating_total_cost"
PARAM_COST_LIMIT_APPLIED = "input_boolean.pool_heating_cost_limit_applied"
NIGHT_COMPLETE_FLAG = "input_boolean.pool_heating_night_complete"
SCHEDULE_INFO = "input_text.pool_heating_schedule_info"
SCHEDULE_JSON = "input_text.pool_heating_schedule_json"  # Full schedule as JSON
# Thermia sensors from thermiagenesis integration
# These are the actual sensor entity IDs from your HA installation
#
# Condenser temperatures (for delta-T and energy calculation):
#   condenser_out = hot water leaving condenser (going TO pool)
#   condenser_in = cooler water returning to condenser (coming FROM pool)
CONDENSER_OUT_TEMP = "sensor.condenser_out_temperature"
CONDENSER_IN_TEMP = "sensor.condenser_in_temperature"

# System temperatures (for reference/logging) - set to None if not available
SYSTEM_SUPPLY_TEMP = None  # sensor.thermia_supply_temperature shows wrong values
OUTDOOR_TEMP = None  # sensor.thermia_outdoor_temperature shows wrong values

# Pool water temperature sensor
# Using corrected return line temperature as proxy for pool temp
POOL_WATER_TEMP = "sensor.pool_return_line_temperature_corrected"

# Session entity for analytics (updated per block)
SESSION_ENTITY = "sensor.pool_heating_session"
NIGHT_SUMMARY_ENTITY = "sensor.pool_heating_night_summary"
NIGHT_SUMMARY_DATA_ENTITY = "input_text.pool_heating_night_summary_data"

# Running totals for current cycle (accumulated as blocks complete)
# This is separate from NIGHT_SUMMARY_DATA_ENTITY which holds finalized data
CYCLE_RUNNING_TOTALS_ENTITY = "input_text.pool_heating_cycle_running_totals"

# Outdoor temperature sensor
OUTDOOR_TEMP_SENSOR = "sensor.outdoor_temperature"


# ============================================
# PRICE OPTIMIZATION ALGORITHM
# ============================================

def find_best_heating_schedule(
    prices_today: list,
    prices_tomorrow: list,
    window_start: int = 21,
    window_end: int = 7,
    total_minutes: int = 120,
    min_block_minutes: int = 30,
    max_block_minutes: int = 45,
    slot_minutes: int = 15,
    min_break_minutes: int = None
) -> list:
    """
    Find optimal heating schedule using 15-minute price intervals.

    Constraints:
    - Total heating time: configurable (default 2 hours / 120 minutes)
    - Each heating block: 30-60 minutes (configurable)
    - Break between blocks: at least min_break_minutes (default: 60 minutes)

    Args:
        prices_today: List of 15-minute prices for today (96 slots)
        prices_tomorrow: List of 15-minute prices for tomorrow (96 slots)
        window_start: Start hour (21 = 9 PM)
        window_end: End hour (7 = 7 AM)
        total_minutes: Total heating time needed (default 120)
        min_block_minutes: Minimum consecutive heating (default 30)
        max_block_minutes: Maximum consecutive heating (default 45)
        slot_minutes: Duration per price slot (default 15)
        min_break_minutes: Minimum break between blocks in minutes (default 60)

    Returns:
        List of dicts with 'start' (datetime), 'end' (datetime),
        'duration_minutes', 'avg_price' for each heating block
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Build list of all 15-minute slots in the heating window
    slots = []

    # Helper to get slot index from hour and quarter
    def slot_index(hour, quarter=0):
        return hour * 4 + quarter

    # Capture preheat slot prices (slots before window for cost calculation)
    # Preheat happens 15 min before first block to warm up radiators
    preheat_prices = []
    for i in range(PREHEAT_SLOTS):
        # Work backwards from window start (20:45 for window_start=21, PREHEAT_SLOTS=1)
        preheat_quarter = 3 - i  # 3, 2, 1, 0 for slots before window
        preheat_hour = window_start - 1
        if preheat_quarter < 0:
            preheat_quarter += 4
            preheat_hour -= 1
        idx = slot_index(preheat_hour, preheat_quarter)
        if prices_today and idx < len(prices_today) and idx >= 0:
            preheat_prices.append(prices_today[idx])
        else:
            # Fallback: use first slot in window if preheat price unavailable
            fallback_idx = slot_index(window_start, 0)
            if prices_today and fallback_idx < len(prices_today):
                preheat_prices.append(prices_today[fallback_idx])
            else:
                preheat_prices.append(0)

    # Tonight's slots (21:00 - 23:45)
    for hour in range(window_start, 24):
        for quarter in range(4):
            idx = slot_index(hour, quarter)
            if prices_today and idx < len(prices_today):
                dt = datetime.combine(today, datetime.min.time().replace(
                    hour=hour, minute=quarter * 15))
                slots.append({
                    'datetime': dt,
                    'index': len(slots),  # Sequential index in window
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

    # Calculate slot counts
    min_block_slots = min_block_minutes // slot_minutes  # 2 slots = 30 min
    max_block_slots = max_block_minutes // slot_minutes  # 3 slots = 45 min
    total_slots_needed = total_minutes // slot_minutes   # 8 slots = 120 min

    # Calculate minimum break in slots (default 60 minutes = 4 slots)
    if min_break_minutes is None:
        min_break_minutes = DEFAULT_MIN_BREAK_DURATION
    min_break_slots_val = min_break_minutes // slot_minutes  # 4 slots = 60 min

    # Find optimal combination of heating blocks
    # Strategy: Try different block configurations and pick cheapest total
    best_schedule = None
    best_cost = float('inf')

    # Generate valid block size combinations that sum to total_slots_needed
    # Each block must be min_block_slots to max_block_slots
    block_combinations = []
    _find_block_combinations(
        total_slots_needed, min_block_slots, max_block_slots,
        [], block_combinations
    )

    # For each combination of block sizes, find optimal placement
    # Pass preheat_prices so the optimization includes preheat cost
    # Pass min_break_slots for configurable break duration between blocks
    for block_sizes in block_combinations:
        schedule = _find_best_placement(slots, block_sizes, slot_minutes, preheat_prices, min_break_slots_val)
        if schedule:
            total_cost = 0
            for b in schedule:
                total_cost = total_cost + b['avg_price'] * b['duration_minutes']
            # Add preheat cost to total (for comparison after selection)
            if preheat_prices and schedule:
                first_block_start = schedule[0]['start']
                # Find if first block starts at window start
                if slots and first_block_start == slots[0]['datetime']:
                    # Add captured preheat price (20:45)
                    for p in preheat_prices:
                        total_cost = total_cost + p
                elif slots:
                    # Find the preceding slot's price
                    for i, s in enumerate(slots):
                        if s['datetime'] == first_block_start and i > 0:
                            total_cost = total_cost + slots[i-1]['price']
                            break
            if total_cost < best_cost:
                best_cost = total_cost
                best_schedule = schedule

    return best_schedule or []


def _find_block_combinations(remaining, min_size, max_size, current, results):
    """Recursively find all valid combinations of block sizes."""
    if remaining == 0:
        if current:  # Don't allow empty
            results.append(current[:])
        return
    if remaining < min_size:
        return

    for size in range(min_size, min(max_size, remaining) + 1):
        current.append(size)
        _find_block_combinations(remaining - size, min_size, max_size, current, results)
        current.pop()


def _find_best_placement(slots, block_sizes, slot_minutes, preheat_prices=None, min_break_slots=None):
    """
    Find the best placement of heating blocks with given sizes.

    Each block must be followed by a break of at least min_break_slots duration.

    Args:
        slots: List of slot dicts with 'price', 'datetime', etc.
        block_sizes: List of block sizes (in slots)
        slot_minutes: Duration of each slot in minutes
        preheat_prices: List of prices for preheat slots (before first block)
                       If provided, preheat cost is added to first block's cost
        min_break_slots: Minimum break duration in slots (default: use block size for backwards compat)
    """
    n_slots = len(slots)
    n_blocks = len(block_sizes)

    if n_blocks == 0:
        return []

    # Calculate total preheat cost (sum of all preheat slot prices)
    preheat_cost = 0
    if preheat_prices:
        for p in preheat_prices:
            preheat_cost = preheat_cost + p

    # Calculate average price for a block starting at position i with given size
    def block_cost(start_idx, size):
        if start_idx + size > n_slots:
            return float('inf'), None
        block_slots = slots[start_idx:start_idx + size]
        price_sum = 0
        for s in block_slots:
            price_sum = price_sum + s['price']
        avg_price = price_sum / size
        return avg_price, block_slots

    # Dynamic programming / recursive search with memoization
    # For simplicity with small search space, use brute force
    best_schedule = None
    best_total_cost = float('inf')

    def search(block_idx, min_start_idx, current_schedule, current_cost):
        nonlocal best_schedule, best_total_cost

        if block_idx >= n_blocks:
            # All blocks placed
            if current_cost < best_total_cost:
                best_total_cost = current_cost
                best_schedule = current_schedule[:]
            return

        block_size = block_sizes[block_idx]

        # Try all valid starting positions for this block
        for start_idx in range(min_start_idx, n_slots - block_size + 1):
            avg_price, block_slots = block_cost(start_idx, block_size)

            if avg_price == float('inf'):
                break

            # Build block info
            block_info = {
                'start': block_slots[0]['datetime'],
                'end': block_slots[-1]['datetime'] + timedelta(minutes=slot_minutes),
                'duration_minutes': block_size * slot_minutes,
                'avg_price': avg_price,
                'slots': block_slots
            }

            new_cost = current_cost + avg_price * block_size

            # For first block, add preheat cost
            # Preheat happens 15 min before first block to warm radiators
            if block_idx == 0 and preheat_prices:
                # Get price of slot before this block's start
                if start_idx > 0:
                    # Use preceding slot's price (it's within the heating window)
                    preheat_slot_price = slots[start_idx - 1]['price']
                else:
                    # First block starts at beginning of window (21:00)
                    # Use the pre-captured preheat price (20:45)
                    preheat_slot_price = preheat_cost
                new_cost = new_cost + preheat_slot_price

            # Prune if already worse than best
            if new_cost >= best_total_cost:
                continue

            # Calculate minimum start for next block
            # Break must be at least min_break_slots (or block_size for backwards compat)
            actual_break_slots = min_break_slots if min_break_slots is not None else block_size
            next_min_start = start_idx + block_size + actual_break_slots  # block + required break

            current_schedule.append(block_info)
            search(block_idx + 1, next_min_start, current_schedule, new_cost)
            current_schedule.pop()

    search(0, 0, [], 0)

    # Clean up schedule (remove internal 'slots' data)
    if best_schedule:
        for block in best_schedule:
            del block['slots']

    return best_schedule


# Legacy function for backward compatibility
def find_best_heating_slots(prices_today: list, prices_tomorrow: list,
                           window_start: int = 21, window_end: int = 7,
                           num_slots: int = 2, min_gap: int = 1) -> list:
    """
    Legacy function - converts to new schedule format.

    Note: This expects hourly prices (24 per day). For 15-minute prices,
    use find_best_heating_schedule() directly.
    """
    # If we have 96 prices, assume 15-minute intervals
    if prices_today and len(prices_today) > 24:
        schedule = find_best_heating_schedule(
            prices_today, prices_tomorrow,
            window_start, window_end
        )
        # Convert schedule blocks to (datetime, price) tuples for compatibility
        result = []
        for block in schedule:
            result.append((block['start'], block['avg_price']))
        return result

    # Original hourly logic for backward compatibility
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

    result = []
    for s in selected:
        result.append((s['datetime'], s['price']))
    return result


# ============================================
# SCHEDULE PARAMETER HELPERS
# ============================================

def get_schedule_parameters():
    """
    Get and validate schedule parameters from input_number entities.

    Returns validated parameters with fallback to defaults if:
    - Entity is unavailable or unknown
    - Value is out of valid range
    - min_block > max_block (conflict)

    Returns:
        dict with keys: min_block_minutes, max_block_minutes, total_minutes, min_break_minutes
    """
    params = {
        'min_block_minutes': DEFAULT_MIN_BLOCK_MINUTES,
        'max_block_minutes': DEFAULT_MAX_BLOCK_MINUTES,
        'total_minutes': DEFAULT_TOTAL_HEATING_MINUTES,
        'min_break_minutes': DEFAULT_MIN_BREAK_DURATION,
    }

    fallback_used = []

    # Get min block duration
    try:
        min_block_val = state.get(PARAM_MIN_BLOCK_DURATION)
        if min_block_val not in ['unknown', 'unavailable', None]:
            min_block = int(float(min_block_val))
            if min_block in VALID_BLOCK_DURATIONS:
                params['min_block_minutes'] = min_block
            else:
                fallback_used.append(f"min_block={min_block} not in {VALID_BLOCK_DURATIONS}")
        else:
            fallback_used.append("min_block entity unavailable")
    except (ValueError, TypeError) as e:
        fallback_used.append(f"min_block parse error: {e}")

    # Get max block duration
    try:
        max_block_val = state.get(PARAM_MAX_BLOCK_DURATION)
        if max_block_val not in ['unknown', 'unavailable', None]:
            max_block = int(float(max_block_val))
            if max_block in VALID_BLOCK_DURATIONS:
                params['max_block_minutes'] = max_block
            else:
                fallback_used.append(f"max_block={max_block} not in {VALID_BLOCK_DURATIONS}")
        else:
            fallback_used.append("max_block entity unavailable")
    except (ValueError, TypeError) as e:
        fallback_used.append(f"max_block parse error: {e}")

    # Get total heating hours
    try:
        total_hours_val = state.get(PARAM_TOTAL_HOURS)
        if total_hours_val not in ['unknown', 'unavailable', None]:
            total_hours = float(total_hours_val)
            # Allow 0 to 6 hours
            if 0 <= total_hours <= 6:
                # Round to nearest 15min (0.25h) - the slot size
                # This supports all block sizes: 30min (0.5h), 45min (0.75h), 60min (1h)
                total_hours = round(total_hours * 4) / 4
                params['total_minutes'] = int(total_hours * 60)
            else:
                fallback_used.append(f"total_hours={total_hours} not in 0-6 range")
        else:
            fallback_used.append("total_hours entity unavailable")
    except (ValueError, TypeError) as e:
        fallback_used.append(f"total_hours parse error: {e}")

    # Get min break duration between blocks
    try:
        min_break_val = state.get(PARAM_MIN_BREAK_DURATION)
        if min_break_val not in ['unknown', 'unavailable', None]:
            min_break = int(float(min_break_val))
            if min_break in VALID_BREAK_DURATIONS:
                params['min_break_minutes'] = min_break
            else:
                fallback_used.append(f"min_break={min_break} not in {VALID_BREAK_DURATIONS}")
        else:
            fallback_used.append("min_break entity unavailable")
    except (ValueError, TypeError) as e:
        fallback_used.append(f"min_break parse error: {e}")

    # Validate min <= max constraint
    if params['min_block_minutes'] > params['max_block_minutes']:
        log.warning(f"min_block ({params['min_block_minutes']}) > max_block ({params['max_block_minutes']}), using defaults")
        params['min_block_minutes'] = DEFAULT_MIN_BLOCK_MINUTES
        params['max_block_minutes'] = DEFAULT_MAX_BLOCK_MINUTES
        fallback_used.append("min > max conflict")

    if fallback_used:
        log.info(f"Parameter fallbacks used: {', '.join(fallback_used)}")

    log.info(f"Schedule parameters: min={params['min_block_minutes']}min, "
             f"max={params['max_block_minutes']}min, total={params['total_minutes']}min, "
             f"break={params['min_break_minutes']}min")

    return params


# ============================================
# PYSCRIPT SERVICES
# ============================================

@service
def calculate_pool_heating_schedule():
    """
    Calculate and set optimal pool heating schedule based on Nordpool prices.

    Uses 15-minute price intervals and schedules heating blocks based on
    configurable parameters (min/max block duration, total heating time).

    Called by automation when tomorrow's prices become available.
    """
    log.info("Calculating pool heating schedule...")

    # Reset night complete flag FIRST - allows heating for new night
    # This must happen before any early returns to prevent stale blocks
    service.call(
        "input_boolean",
        "turn_off",
        entity_id=NIGHT_COMPLETE_FLAG
    )
    log.info("Reset night complete flag for new schedule")

    # Get prices from Nordpool sensor
    nordpool_state = state.get(NORDPOOL_SENSOR)
    if nordpool_state in ['unknown', 'unavailable']:
        log.error("Nordpool sensor not available")
        return

    # Get price arrays from attributes
    # New Nordpool format: 96 prices per day (15-minute intervals)
    prices_today = state.getattr(NORDPOOL_SENSOR).get('today', [])
    prices_tomorrow = state.getattr(NORDPOOL_SENSOR).get('tomorrow', [])
    tomorrow_valid = state.getattr(NORDPOOL_SENSOR).get('tomorrow_valid', False)

    if not tomorrow_valid:
        log.warning("Tomorrow's prices not yet available")
        return

    if not prices_today or not prices_tomorrow:
        log.error("Price data missing")
        return

    log.info(f"Price data: {len(prices_today)} today slots, {len(prices_tomorrow)} tomorrow slots")

    # Get schedule parameters (with validation and fallbacks)
    params = get_schedule_parameters()

    # Handle zero heating time (disabled)
    if params['total_minutes'] == 0:
        log.info("Total heating time set to 0, no heating scheduled")
        # Clear all blocks
        for block_entity in BLOCK_ENTITIES:
            past_date = datetime.combine(date.today() - timedelta(days=7), datetime.min.time())
            service.call("input_datetime", "set_datetime",
                        entity_id=block_entity["start"], datetime=past_date.isoformat())
            service.call("input_datetime", "set_datetime",
                        entity_id=block_entity["heating_start"], datetime=past_date.isoformat())
            service.call("input_datetime", "set_datetime",
                        entity_id=block_entity["end"], datetime=past_date.isoformat())
            service.call("input_number", "set_value",
                        entity_id=block_entity["price"], value=0)
            service.call("input_number", "set_value",
                        entity_id=block_entity["cost"], value=0)
            service.call("input_boolean", "turn_off",
                        entity_id=block_entity["enabled"])
            service.call("input_boolean", "turn_off",
                        entity_id=block_entity["cost_exceeded"])
        # Clear cost totals
        service.call("input_number", "set_value",
                    entity_id=PARAM_TOTAL_COST, value=0)
        service.call("input_boolean", "turn_off",
                    entity_id=PARAM_COST_LIMIT_APPLIED)
        service.call("input_text", "set_value",
                    entity_id=SCHEDULE_INFO, value="Heating disabled (0 hours)")
        service.call("input_text", "set_value",
                    entity_id=SCHEDULE_JSON, value="[]")
        return

    # Calculate optimal schedule
    schedule = find_best_heating_schedule(
        prices_today=prices_today,
        prices_tomorrow=prices_tomorrow,
        window_start=HEATING_WINDOW_START,
        window_end=HEATING_WINDOW_END,
        total_minutes=params['total_minutes'],
        min_block_minutes=params['min_block_minutes'],
        max_block_minutes=params['max_block_minutes'],
        slot_minutes=SLOT_DURATION_MINUTES,
        min_break_minutes=params['min_break_minutes']
    )

    if not schedule:
        log.error("Could not find suitable heating schedule")
        return

    total_minutes = 0
    for b in schedule:
        total_minutes = total_minutes + b['duration_minutes']
    log.info(f"Found schedule with {len(schedule)} blocks, {total_minutes} total minutes")

    # Calculate cost for each block
    for b in schedule:
        duration_hours = b['duration_minutes'] / 60.0
        energy_kwh = POWER_KW * duration_hours
        # avg_price is in EUR/kWh, cost_eur is in EUR
        b['cost_eur'] = energy_kwh * b['avg_price']

    # Get cost constraint parameter
    max_cost_eur = 0.0
    try:
        max_cost_val = state.get(PARAM_MAX_COST_EUR)
        if max_cost_val not in ['unknown', 'unavailable', None]:
            max_cost_eur = float(max_cost_val)
    except (ValueError, TypeError):
        max_cost_eur = 0.0

    # Apply cost constraint if set (0 = no limit)
    cost_limit_applied = False
    if max_cost_eur > 0:
        # Sort blocks by price to enable cheapest first
        # Note: Use list comprehension instead of lambda to avoid pyscript closure issues
        index_prices = [(i, schedule[i]['avg_price']) for i in range(len(schedule))]
        index_prices.sort(key=lambda x: x[1])
        sorted_indices = [x[0] for x in index_prices]
        running_cost = 0.0
        for idx in sorted_indices:
            block = schedule[idx]
            if running_cost + block['cost_eur'] <= max_cost_eur:
                block['cost_exceeded'] = False
                running_cost += block['cost_eur']
            else:
                block['cost_exceeded'] = True
                cost_limit_applied = True
        log.info(f"Cost constraint: max €{max_cost_eur:.2f}, scheduled €{running_cost:.2f}, limit_applied={cost_limit_applied}")
    else:
        # No cost limit - all blocks enabled
        for b in schedule:
            b['cost_exceeded'] = False

    # Calculate window average price for baseline savings calculation
    # This needs to be captured NOW before Nordpool prices roll over
    all_window_prices = []
    if len(prices_today) >= 96:
        # 15-minute intervals: 84-95 (21:00-23:45 today) + 0-27 (00:00-06:45 tomorrow)
        for p in prices_today[84:96]:
            all_window_prices.append(p)
        for p in prices_tomorrow[0:28]:
            all_window_prices.append(p)
    elif len(prices_today) >= 24:
        # Hourly prices: 21-23 today + 0-6 tomorrow
        for p in prices_today[21:24]:
            all_window_prices.append(p)
        for p in prices_tomorrow[0:7]:
            all_window_prices.append(p)

    if all_window_prices:
        window_avg_price = sum(all_window_prices) / len(all_window_prices)
    else:
        # Fallback: use average of schedule block prices
        schedule_prices = [b['avg_price'] for b in schedule]
        window_avg_price = sum(schedule_prices) / len(schedule_prices) if schedule_prices else 0.05

    # Initialize new cycle tracking with captured window price
    # This also finalizes any previous cycle data
    heating_date = get_heating_date(datetime.now())
    _init_cycle_with_window_price(heating_date, window_avg_price)

    # Update block entities
    total_cost_eur = 0.0
    for i, block_entity in enumerate(BLOCK_ENTITIES):
        if i < len(schedule):
            block = schedule[i]
            # Calculate preheat start (15 minutes before heating starts)
            preheat_start = block['start'] - timedelta(minutes=PREHEAT_MINUTES)
            heating_start = block['start']  # Actual heating start time

            # Set start time (preheat start - when automation should trigger)
            service.call(
                "input_datetime",
                "set_datetime",
                entity_id=block_entity["start"],
                datetime=preheat_start.isoformat()
            )
            # Set heating_start time (actual heating start, after preheat)
            service.call(
                "input_datetime",
                "set_datetime",
                entity_id=block_entity["heating_start"],
                datetime=heating_start.isoformat()
            )
            # Set end time (heating end)
            service.call(
                "input_datetime",
                "set_datetime",
                entity_id=block_entity["end"],
                datetime=block['end'].isoformat()
            )
            # Set price (in cents)
            service.call(
                "input_number",
                "set_value",
                entity_id=block_entity["price"],
                value=round(block['avg_price'] * 100, 2)
            )
            # Set cost (in EUR)
            service.call(
                "input_number",
                "set_value",
                entity_id=block_entity["cost"],
                value=round(block['cost_eur'], 3)
            )
            # Set enabled (not cost_exceeded)
            if block.get('cost_exceeded', False):
                service.call("input_boolean", "turn_off",
                            entity_id=block_entity["enabled"])
                service.call("input_boolean", "turn_on",
                            entity_id=block_entity["cost_exceeded"])
            else:
                service.call("input_boolean", "turn_on",
                            entity_id=block_entity["enabled"])
                service.call("input_boolean", "turn_off",
                            entity_id=block_entity["cost_exceeded"])
                total_cost_eur += block['cost_eur']
        else:
            # Clear unused block slots
            past_date = datetime.combine(date.today() - timedelta(days=7), datetime.min.time())
            service.call(
                "input_datetime",
                "set_datetime",
                entity_id=block_entity["start"],
                datetime=past_date.isoformat()
            )
            service.call(
                "input_datetime",
                "set_datetime",
                entity_id=block_entity["heating_start"],
                datetime=past_date.isoformat()
            )
            service.call(
                "input_datetime",
                "set_datetime",
                entity_id=block_entity["end"],
                datetime=past_date.isoformat()
            )
            service.call("input_number", "set_value",
                        entity_id=block_entity["price"], value=0)
            service.call("input_number", "set_value",
                        entity_id=block_entity["cost"], value=0)
            service.call("input_boolean", "turn_off",
                        entity_id=block_entity["enabled"])
            service.call("input_boolean", "turn_off",
                        entity_id=block_entity["cost_exceeded"])

    # Set total cost and cost limit applied flag
    service.call("input_number", "set_value",
                entity_id=PARAM_TOTAL_COST, value=round(total_cost_eur, 3))
    if cost_limit_applied:
        service.call("input_boolean", "turn_on",
                    entity_id=PARAM_COST_LIMIT_APPLIED)
    else:
        service.call("input_boolean", "turn_off",
                    entity_id=PARAM_COST_LIMIT_APPLIED)

    # Calculate average price
    total_cost = 0
    for b in schedule:
        total_cost = total_cost + b['avg_price'] * b['duration_minutes']
    avg_price = total_cost / total_minutes * 100 if total_minutes > 0 else 0

    # Build info text
    block_info = []
    for b in schedule:
        exceeded_marker = "!" if b.get('cost_exceeded', False) else ""
        block_info.append(
            f"{exceeded_marker}{b['start'].strftime('%H:%M')}-{b['end'].strftime('%H:%M')} "
            f"({b['duration_minutes']}min, {b['avg_price']*100:.1f}c, €{b['cost_eur']:.2f})"
        )
    info_text = " | ".join(block_info) + f" | Avg: {avg_price:.1f}c/kWh | Total: €{total_cost_eur:.2f}"

    service.call(
        "input_text",
        "set_value",
        entity_id=SCHEDULE_INFO,
        value=info_text[:255]  # Truncate if too long
    )

    # Store full schedule as JSON for automations
    schedule_list = []
    for b in schedule:
        schedule_list.append({
            'start': b['start'].isoformat(),
            'end': b['end'].isoformat(),
            'duration_minutes': b['duration_minutes'],
            'avg_price': b['avg_price'],
            'cost_eur': round(b['cost_eur'], 3),
            'cost_exceeded': b.get('cost_exceeded', False)
        })
    schedule_json = json.dumps(schedule_list)

    service.call(
        "input_text",
        "set_value",
        entity_id=SCHEDULE_JSON,
        value=schedule_json[:255]  # May need a longer entity for complex schedules
    )

    log.info(f"Pool heating scheduled: {info_text}")


# Keep old function name as alias for backward compatibility
@service
def calculate_pool_heating_slots():
    """Legacy alias for calculate_pool_heating_schedule."""
    calculate_pool_heating_schedule()


@service
def debug_constraint_params():
    """Debug service to log constraint parameters to a file."""
    import os
    debug_file = "/config/pyscript_debug.txt"

    lines = ["=== DEBUG: Constraint Parameters ==="]

    # Check max_cost_eur
    max_cost_val = state.get(PARAM_MAX_COST_EUR)
    lines.append(f"max_cost_val raw: {max_cost_val}, type: {type(max_cost_val)}")
    lines.append(f"max_cost_val == 'unknown': {max_cost_val == 'unknown'}")
    lines.append(f"max_cost_val in list: {max_cost_val in ['unknown', 'unavailable', None]}")
    lines.append(f"str(max_cost_val): {str(max_cost_val)}")

    try:
        max_cost_eur = float(max_cost_val)
        lines.append(f"float(max_cost_val): {max_cost_eur}")
    except Exception as e:
        lines.append(f"float() failed: {e}")

    # Check total_hours
    total_hours_val = state.get(PARAM_TOTAL_HOURS)
    lines.append(f"total_hours_val raw: {total_hours_val}, type: {type(total_hours_val)}")

    # Check block 1 cost
    block1_cost = state.get("input_number.pool_heat_block_1_cost")
    lines.append(f"block1_cost raw: {block1_cost}, type: {type(block1_cost)}")

    # Check str() comparisons
    lines.append(f"str(max_cost_val) in list: {str(max_cost_val) in ['unknown', 'unavailable', 'None']}")

    lines.append("=== END DEBUG ===")

    # Write to file
    with open(debug_file, 'w') as f:
        f.write('\n'.join(lines))

    log.warning(f"Debug output written to {debug_file}")


# ============================================
# HEATING SESSION LOGGING
# ============================================

# Session tracking (in-memory for current session)
_current_session = {}
_block_number = 0  # Track which block we're in


def get_heating_date(timestamp=None):
    """
    Get the heating date for a given timestamp.
    The heating day is defined by the 21:00-07:00 window.

    Examples:
        21:00 Dec 5 to 06:59 Dec 6 → "2024-12-05"
        07:00 Dec 6 onwards → "2024-12-06"
    """
    if timestamp is None:
        timestamp = datetime.now()

    if timestamp.hour < 7:
        # Before 7am = previous day's heating night
        return (timestamp - timedelta(days=1)).strftime('%Y-%m-%d')
    elif timestamp.hour >= 21:
        # After 9pm = this day's heating night
        return timestamp.strftime('%Y-%m-%d')
    else:
        # 7am-9pm = no heating window, use previous night
        return (timestamp - timedelta(days=1)).strftime('%Y-%m-%d')


def _safe_get_temp(sensor_id):
    """Safely get temperature value, returning 0 if sensor unavailable."""
    if sensor_id is None:
        return 0
    try:
        val = state.get(sensor_id)
        if val in ['unknown', 'unavailable', None]:
            return 0
        return float(val)
    except (ValueError, TypeError):
        return 0


@service
def log_heating_start(block_number=None):
    """
    Log the start of a heating session.
    Records initial temperatures and electricity price.

    Args:
        block_number: Optional block number (1-4) for tracking
    """
    global _current_session, _block_number

    now = datetime.now()
    _block_number = block_number if block_number else 0

    _current_session = {
        'start_time': now.isoformat(),
        'block_number': _block_number,
        'heating_date': get_heating_date(now),
        'start_condenser_out_temp': _safe_get_temp(CONDENSER_OUT_TEMP),
        'start_condenser_in_temp': _safe_get_temp(CONDENSER_IN_TEMP),
        'start_system_supply_temp': _safe_get_temp(SYSTEM_SUPPLY_TEMP),
        'start_outdoor_temp': _safe_get_temp(OUTDOOR_TEMP_SENSOR),
        'start_pool_water_temp': _safe_get_temp(POOL_WATER_TEMP),
        'electricity_price': _safe_get_temp(NORDPOOL_SENSOR),
        'temperature_readings': []
    }

    log.info(f"Heating session started at {now.strftime('%H:%M')} (Block {_block_number}, Date: {_current_session['heating_date']})")
    log.info(f"Initial temps - Condenser Out: {_current_session['start_condenser_out_temp']}°C, "
             f"Condenser In: {_current_session['start_condenser_in_temp']}°C, "
             f"Pool: {_current_session['start_pool_water_temp']}°C")


@service
def log_pool_temperatures():
    """
    Log current temperatures during heating session.
    Called periodically by automation.
    """
    global _current_session

    if not _current_session:
        return

    condenser_out = _safe_get_temp(CONDENSER_OUT_TEMP)
    condenser_in = _safe_get_temp(CONDENSER_IN_TEMP)
    # condenser_out = hot water leaving condenser (going TO pool)
    # condenser_in = cooler water returning to condenser (coming FROM pool)
    delta_t = condenser_out - condenser_in

    reading = {
        'timestamp': datetime.now().isoformat(),
        'condenser_out_temp': condenser_out,
        'condenser_in_temp': condenser_in,
        'system_supply_temp': _safe_get_temp(SYSTEM_SUPPLY_TEMP),
        'outdoor_temp': _safe_get_temp(OUTDOOR_TEMP),
        'pool_water_temp': _safe_get_temp(POOL_WATER_TEMP),
        'delta_t': delta_t
    }

    _current_session['temperature_readings'].append(reading)
    log.debug(f"Temperature logged: Delta-T = {delta_t}°C")


@service
def log_heating_end():
    """
    Log the end of a heating session.
    Calculate energy consumption and prepare data for local logging.
    """
    global _current_session

    if not _current_session:
        log.warning("No active heating session to end")
        return

    now = datetime.now()

    # Calculate session metrics
    end_condenser_out_temp = _safe_get_temp(CONDENSER_OUT_TEMP)
    end_condenser_in_temp = _safe_get_temp(CONDENSER_IN_TEMP)
    end_pool_water_temp = _safe_get_temp(POOL_WATER_TEMP)

    # Average delta-T during session
    if _current_session['temperature_readings']:
        delta_sum = 0
        for r in _current_session['temperature_readings']:
            delta_sum = delta_sum + r['delta_t']
        avg_delta_t = delta_sum / len(_current_session['temperature_readings'])
    else:
        # condenser_out = hot (to pool), condenser_in = cool (from pool)
        avg_delta_t = end_condenser_out_temp - end_condenser_in_temp

    # Pool water temperature change (only if pool water sensor available)
    pool_water_temp_change = 0
    if POOL_WATER_TEMP is not None:
        pool_water_temp_change = end_pool_water_temp - _current_session.get('start_pool_water_temp', 0)

    # Session duration in hours
    start_time = datetime.fromisoformat(_current_session['start_time'])
    duration_hours = (now - start_time).total_seconds() / 3600

    # Energy calculation using 45 L/min flow and COP of 3
    # Thermal energy (kWh) = delta_T × flow_rate × specific_heat × time
    # flow_rate = 45 L/min = 0.75 L/s = 0.00075 m³/s
    # Q (kW) = ΔT × 0.75 × 4.186 = ΔT × 3.14 kW
    # Q (kWh) = Q (kW) × hours
    thermal_kwh = avg_delta_t * 3.14 * duration_hours
    electrical_kwh = thermal_kwh / 3.0  # COP of 3

    # Cost calculation (Nordpool sensor provides EUR/kWh directly)
    electricity_price_eur = _current_session.get('electricity_price', 0)
    estimated_cost_eur = electrical_kwh * electricity_price_eur

    session_data = {
        'start_time': _current_session['start_time'],
        'end_time': now.isoformat(),
        'duration_hours': round(duration_hours, 2),
        'electricity_price_eur': _current_session.get('electricity_price', 0),
        'start_condenser_out_temp': _current_session.get('start_condenser_out_temp', 0),
        'start_condenser_in_temp': _current_session.get('start_condenser_in_temp', 0),
        'end_condenser_out_temp': end_condenser_out_temp,
        'end_condenser_in_temp': end_condenser_in_temp,
        'avg_delta_t': round(avg_delta_t, 2),
        'thermal_kwh': round(thermal_kwh, 2),
        'electrical_kwh': round(electrical_kwh, 2),
        'estimated_cost_eur': round(estimated_cost_eur, 3),
        'pool_water_temp_before': _current_session.get('start_pool_water_temp', 0),
        'pool_water_temp_after': end_pool_water_temp,
        'pool_water_temp_change': round(pool_water_temp_change, 2),
        'temperature_readings': _current_session['temperature_readings']
    }

    log.info(f"Heating session ended. Duration: {duration_hours:.1f}h, "
             f"Avg Delta-T: {avg_delta_t:.1f}°C, Electrical: {electrical_kwh:.2f}kWh, "
             f"Cost: {estimated_cost_eur:.3f}€")

    # Store session data for local logging
    # This fires an event that firebase_sync.py (local logger) listens to
    event.fire("pool_heating_session_complete", session_data=session_data)

    # Update session entity for analytics
    # This creates a state change that gets stored in HA history
    duration_minutes = int(duration_hours * 60)
    heating_date = _current_session.get('heating_date', get_heating_date(now))
    outdoor_temp = _safe_get_temp(OUTDOOR_TEMP_SENSOR)

    state.set(
        SESSION_ENTITY,
        value=round(electrical_kwh, 3),
        new_attributes={
            "block_number": _current_session.get('block_number', 0),
            "heating_date": heating_date,
            "start_time": _current_session['start_time'],
            "end_time": now.isoformat(),
            "duration_minutes": duration_minutes,
            "energy_kwh": round(electrical_kwh, 3),
            "thermal_kwh": round(thermal_kwh, 3),
            "cost_eur": round(estimated_cost_eur, 4),
            "price_eur_kwh": round(electricity_price_eur, 4),
            "pool_temp_start": round(_current_session.get('start_pool_water_temp', 0), 1),
            "pool_temp_end": round(end_pool_water_temp, 1),
            "outdoor_temp": round(outdoor_temp, 1),
            "avg_delta_t": round(avg_delta_t, 2),
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "measurement",
            "friendly_name": "Pool Heating Session",
        }
    )
    log.info(f"Updated session entity: {SESSION_ENTITY}")

    # Update cycle running totals (incremental aggregation for daily summary)
    _update_cycle_running_totals(
        energy_kwh=electrical_kwh,
        cost_eur=estimated_cost_eur,
        duration_minutes=duration_minutes,
        price_eur_kwh=electricity_price_eur,
        heating_date=heating_date
    )

    # Keep session data for final temp update after mixing
    _current_session['logged'] = True
    _current_session['session_entity_heating_date'] = heating_date


@service
def log_session_final_temp():
    """
    Update the session with final pool temperature after mixing period.

    Call this 15 minutes after heating stops, when circulation has mixed
    the water and the pool temperature sensor reflects the true pool temp.
    """
    global _current_session

    if not _current_session or not _current_session.get('logged'):
        log.warning("No logged session to update final temp for")
        return

    # Get current pool temperature (after mixing)
    final_pool_temp = _safe_get_temp(POOL_WATER_TEMP)

    # Get current session entity attributes and update pool_temp_end
    current_attrs = state.getattr(SESSION_ENTITY) or {}

    state.set(
        SESSION_ENTITY,
        value=current_attrs.get('energy_kwh', 0),
        new_attributes={
            **current_attrs,
            "pool_temp_end": round(final_pool_temp, 1),
            "pool_temp_mixed": True,  # Flag indicating this is post-mixing temp
        }
    )

    log.info(f"Updated session final pool temp (after mixing): {final_pool_temp}°C")

    # Clear the session now
    _current_session = {}


# ============================================
# CYCLE RUNNING TOTALS (Incremental Aggregation)
# ============================================

def _update_cycle_running_totals(energy_kwh, cost_eur, duration_minutes, price_eur_kwh, heating_date):
    """
    Update running totals for the current heating cycle.

    Called after each heating block completes to accumulate totals.
    Data is stored in input_text for persistence across HA restarts.

    Args:
        energy_kwh: Electrical energy consumed by this block
        cost_eur: Cost of this block (energy × price)
        duration_minutes: Duration of this block in minutes
        price_eur_kwh: Electricity price during this block
        heating_date: Heating cycle date (YYYY-MM-DD)
    """
    # Read current running totals
    current_json = state.get(CYCLE_RUNNING_TOTALS_ENTITY)

    if current_json in ['unknown', 'unavailable', '', None]:
        # Initialize new running totals
        running = {
            "heating_date": heating_date,
            "energy": 0.0,
            "cost": 0.0,
            "blocks": 0,
            "duration": 0,
            "prices": [],
            "window_avg_price": None,  # Captured at cycle start
            "last_updated": None,
        }
    else:
        try:
            running = json.loads(current_json)
        except (json.JSONDecodeError, TypeError):
            log.warning(f"Invalid running totals JSON, reinitializing: {current_json}")
            running = {
                "heating_date": heating_date,
                "energy": 0.0,
                "cost": 0.0,
                "blocks": 0,
                "duration": 0,
                "prices": [],
                "window_avg_price": None,
                "last_updated": None,
            }

    # Check if this is a new cycle (different heating_date)
    if running.get("heating_date") != heating_date:
        log.info(f"New heating cycle detected: {heating_date} (was {running.get('heating_date')})")
        running = {
            "heating_date": heating_date,
            "energy": 0.0,
            "cost": 0.0,
            "blocks": 0,
            "duration": 0,
            "prices": [],
            "window_avg_price": None,
            "last_updated": None,
        }

    # Add this block's data
    running["energy"] = running.get("energy", 0) + energy_kwh
    running["cost"] = running.get("cost", 0) + cost_eur
    running["blocks"] = running.get("blocks", 0) + 1
    running["duration"] = running.get("duration", 0) + duration_minutes
    if "prices" not in running:
        running["prices"] = []
    running["prices"].append(price_eur_kwh)
    running["last_updated"] = datetime.now().isoformat()

    # Store updated running totals
    service.call(
        "input_text",
        "set_value",
        entity_id=CYCLE_RUNNING_TOTALS_ENTITY,
        value=json.dumps(running)
    )

    log.info(f"Cycle running totals updated: {running['blocks']} blocks, "
             f"{running['energy']:.3f} kWh, €{running['cost']:.4f}")


def _init_cycle_with_window_price(heating_date, window_avg_price):
    """
    Initialize a new cycle's running totals with the window average price.

    Called when a new schedule is calculated (at ~21:00). This captures the
    window average price BEFORE the Nordpool prices roll over to the new day,
    so we can calculate accurate baseline/savings at cycle end.

    Args:
        heating_date: The heating cycle date (YYYY-MM-DD)
        window_avg_price: Average Nordpool price for the heating window (EUR/kWh)
    """
    # Read current running totals to check if we need to finalize previous cycle
    current_json = state.get(CYCLE_RUNNING_TOTALS_ENTITY)

    if current_json and current_json not in ['unknown', 'unavailable', '']:
        try:
            running = json.loads(current_json)
            # If there's data from a previous cycle, finalize it first
            if running.get("heating_date") and running.get("heating_date") != heating_date:
                if running.get("blocks", 0) > 0:
                    log.info(f"Finalizing previous cycle ({running.get('heating_date')}) before starting new one")
                    _finalize_and_reset_cycle(window_avg_price_eur=running.get("window_avg_price"))
        except (json.JSONDecodeError, TypeError):
            pass

    # Initialize new cycle with window price captured NOW (before Nordpool rolls over)
    new_running = {
        "heating_date": heating_date,
        "energy": 0.0,
        "cost": 0.0,
        "blocks": 0,
        "duration": 0,
        "prices": [],
        "window_avg_price": window_avg_price,  # Captured at schedule time!
        "last_updated": datetime.now().isoformat(),
    }

    service.call(
        "input_text",
        "set_value",
        entity_id=CYCLE_RUNNING_TOTALS_ENTITY,
        value=json.dumps(new_running)
    )

    log.info(f"Initialized new cycle {heating_date} with window avg price: {window_avg_price*100:.2f} c/kWh")


def _finalize_and_reset_cycle(window_avg_price_eur=None):
    """
    Finalize the current cycle's running totals and reset for new cycle.

    Called when a new cycle starts (via _init_cycle_with_window_price) or
    manually via calculate_night_summary. Takes the running totals,
    calculates baseline/savings, and stores as finalized summary.

    Args:
        window_avg_price_eur: Average Nordpool price in the heating window.
                             If None, uses the stored window_avg_price from
                             running totals (captured at schedule time).
    """
    # Read current running totals
    current_json = state.get(CYCLE_RUNNING_TOTALS_ENTITY)

    if current_json in ['unknown', 'unavailable', '', None]:
        log.info("No running totals to finalize")
        return None

    try:
        running = json.loads(current_json)
    except (json.JSONDecodeError, TypeError):
        log.warning(f"Invalid running totals JSON, cannot finalize: {current_json}")
        return None

    # Skip if no blocks were recorded
    if running.get("blocks", 0) == 0:
        log.info("No heating blocks in this cycle, skipping finalization")
        return None

    # Calculate average of prices we actually paid
    prices = running.get("prices", [])
    avg_heating_price = sum(prices) / len(prices) if prices else 0

    # Use stored window average price (captured at schedule time)
    # Fall back to provided value or heating average if not available
    if window_avg_price_eur is None or window_avg_price_eur <= 0:
        window_avg_price_eur = running.get("window_avg_price")

    if window_avg_price_eur is None or window_avg_price_eur <= 0:
        # Last resort: use average of prices we paid
        window_avg_price_eur = avg_heating_price
        log.warning("No window average price available, using heating average for baseline")

    # Calculate baseline and savings
    energy = running.get("energy", 0)
    cost = running.get("cost", 0)
    baseline = energy * window_avg_price_eur
    savings = baseline - cost

    # Get current conditions
    pool_temp = _safe_get_temp(POOL_WATER_TEMP)
    outdoor_temp = _safe_get_temp(OUTDOOR_TEMP_SENSOR)

    # Build finalized summary
    finalized = {
        "date": running.get("heating_date", ""),
        "energy": round(energy, 3),
        "cost": round(cost, 4),
        "baseline": round(baseline, 4),
        "savings": round(savings, 4),
        "duration": running.get("duration", 0),
        "blocks": running.get("blocks", 0),
        "avg_price": round(avg_heating_price, 4),
        "outdoor_avg": round(outdoor_temp, 1),
        "pool_final": round(pool_temp, 1),
    }

    # Store finalized summary
    service.call(
        "input_text",
        "set_value",
        entity_id=NIGHT_SUMMARY_DATA_ENTITY,
        value=json.dumps(finalized)
    )

    log.info(f"Cycle finalized for {finalized['date']}: "
             f"{finalized['energy']:.2f} kWh, €{finalized['cost']:.3f}, "
             f"savings €{finalized['savings']:.3f}")

    # Reset running totals for new cycle
    # Don't clear completely - new cycle will reinitialize when schedule is calculated
    service.call(
        "input_text",
        "set_value",
        entity_id=CYCLE_RUNNING_TOTALS_ENTITY,
        value=""
    )

    log.info("Running totals reset for new cycle")

    return finalized


# ============================================
# UTILITY FUNCTIONS
# ============================================

@service
def test_price_calculation():
    """
    Test service to verify price calculation with mock data.
    """
    # Mock prices (EUR/kWh)
    mock_today = [0.05] * 21 + [0.03, 0.02, 0.04]  # Hours 21-23 are cheap
    mock_tomorrow = [0.01, 0.06, 0.02, 0.07, 0.03, 0.08, 0.04] + [0.05] * 17

    best_slots = find_best_heating_slots(
        prices_today=mock_today,
        prices_tomorrow=mock_tomorrow,
        window_start=21,
        window_end=7,
        num_slots=2,
        min_gap=1
    )

    log.info("Test results:")
    for dt, price in best_slots:
        log.info(f"  {dt.strftime('%Y-%m-%d %H:%M')} - {price*100:.1f} c/kWh")


@service
def get_heating_window_prices():
    """
    Get all prices in the heating window for debugging.
    """
    prices_today = state.getattr(NORDPOOL_SENSOR).get('today', [])
    prices_tomorrow = state.getattr(NORDPOOL_SENSOR).get('tomorrow', [])

    log.info("Heating window prices:")

    if len(prices_today) > 21:
        tonight_prices = []
        for p in prices_today[21:24]:
            tonight_prices.append(str(round(p*100, 1)) + "c")
        log.info(f"Tonight (21-23): {tonight_prices}")
    else:
        log.info("Tonight (21-23): N/A")

    if prices_tomorrow:
        tomorrow_prices = []
        for p in prices_tomorrow[0:7]:
            tomorrow_prices.append(str(round(p*100, 1)) + "c")
        log.info(f"Tomorrow (0-6): {tomorrow_prices}")
    else:
        log.info("Tomorrow (0-6): N/A")


# ============================================
# CYCLE SUMMARY (21:00 → 21:00 aggregation)
# ============================================

@service
def calculate_night_summary(heating_date=None):
    """
    Finalize and store the cycle summary.

    This service finalizes the running totals accumulated during the heating
    cycle and stores them as the night summary.

    Normally called automatically when a new schedule is calculated
    (via _init_cycle_with_window_price which finalizes the previous cycle).
    Can also be called manually to force finalization.

    Note: The actual energy/cost data is accumulated incrementally by
    log_heating_end() after each heating block completes.

    Args:
        heating_date: Optional - for API compatibility only, not used.
                     Finalization always uses the running totals' heating_date.
    """
    log.info("Finalizing cycle summary (manual call)...")

    # Finalize current running totals
    # The stored window_avg_price from cycle initialization will be used
    result = _finalize_and_reset_cycle()

    if result:
        log.info(f"Cycle summary stored: {result['date']}, {result['energy']:.2f} kWh, "
                 f"€{result['cost']:.3f}, savings €{result['savings']:.3f}")
    else:
        log.info("No cycle data to finalize (no heating occurred or already finalized)")


@service
def backfill_cycle_summaries(days=7):
    """
    Backfill cycle summaries for past days using the standalone script.

    Args:
        days: Number of days to backfill (default 7)
    """
    import subprocess
    import os

    log.info(f"Backfilling cycle summaries for {days} days")

    script_path = "/config/scripts/standalone/calculate_cycle_summary.py"
    env = os.environ.copy()
    env["HA_HOST"] = "localhost"
    env["HA_PORT"] = "8123"

    today = datetime.now().date()
    summaries_created = 0

    for day_offset in range(1, days + 1):
        target_date = today - timedelta(days=day_offset)
        heating_date = target_date.strftime('%Y-%m-%d')

        log.info(f"Processing cycle for {heating_date}")

        try:
            result = subprocess.run(
                ["python3", script_path, heating_date],
                capture_output=True,
                text=True,
                timeout=60,
                env=env
            )

            if result.returncode == 0:
                summaries_created += 1
                log.info(f"Created summary for {heating_date}")
            else:
                log.warning(f"Failed for {heating_date}: {result.stderr}")

        except Exception as e:
            log.error(f"Error processing {heating_date}: {e}")

    log.info(f"Backfill complete: {summaries_created} summaries created")


# ============================================
# THERMAL CALIBRATION
# ============================================

# Pool thermal parameters (calibrated from Dec 5 circulation test)
POOL_VOLUME_LITERS = 32000
PIPE_TAU_MINUTES = 7  # Time constant for sensor to reach true temp
ROOM_TEMP = 20  # Pool room temperature


@service
def record_true_pool_temp(measurement_type="pre_heating"):
    """
    Record stabilized pool temperature after circulation.

    Called after 25 min of circulation when sensor = true pool temp.
    The sensor needs ~21 min (3τ) to reach 95% of true temperature.

    Args:
        measurement_type: "pre_heating", "post_heating", or "daytime"
    """
    now = datetime.now()

    # Get current sensor reading (should be stable after 25 min circulation)
    sensor_temp = _safe_get_temp(POOL_WATER_TEMP)
    outdoor_temp = _safe_get_temp(OUTDOOR_TEMP_SENSOR)

    if sensor_temp == 0:
        log.warning(f"Cannot record true temp - sensor unavailable")
        return

    # Map measurement type to input_number entity
    entity_map = {
        "pre_heating": "input_number.pool_true_temp_pre_heating",
        "post_heating": "input_number.pool_true_temp_post_heating",
        "daytime": "input_number.pool_true_temp_daytime"
    }

    # Set the appropriate input_number entity
    entity_id = entity_map.get(measurement_type)
    if entity_id:
        service.call(
            "input_number", "set_value",
            entity_id=entity_id,
            value=round(sensor_temp, 1)
        )
        log.info(f"Set {entity_id} to {round(sensor_temp, 1)}°C")

    # Fire event to update the trigger-based template sensor
    # This sensor has state_class=measurement for long-term statistics
    event.fire("pool_true_temp_updated",
               temperature=round(sensor_temp, 2),
               outdoor_temp=round(outdoor_temp, 1) if outdoor_temp else None,
               measurement_type=measurement_type)

    # Update last calibration timestamp
    service.call(
        "input_datetime", "set_datetime",
        entity_id="input_datetime.pool_last_calibration_time",
        datetime=now.strftime("%Y-%m-%d %H:%M:%S")
    )

    # Log thermal data for historical analysis
    _log_thermal_calibration(measurement_type, sensor_temp, outdoor_temp)

    log.info(f"Recorded true pool temp: {sensor_temp}°C ({measurement_type})")


def _log_thermal_calibration(measurement_type, true_temp, outdoor_temp):
    """
    Log thermal calibration data for later analysis.
    """
    now = datetime.now()
    heating_date = get_heating_date(now)

    # Get the raw sensor temp for comparison
    raw_sensor = _safe_get_temp("sensor.pool_return_line_temperature_corrected")

    log_data = {
        "timestamp": now.isoformat(),
        "heating_date": heating_date,
        "measurement_type": measurement_type,
        "true_temp": true_temp,
        "raw_sensor_temp": raw_sensor,
        "outdoor_temp": outdoor_temp,
        "room_temp": ROOM_TEMP
    }

    # Fire event for firebase_sync to pick up
    event.fire("pool_thermal_calibration", data=log_data)

    log.info(f"Thermal calibration logged: {measurement_type} = {true_temp}°C "
             f"(outdoor: {outdoor_temp}°C)")


@service
def estimate_true_pool_temp():
    """
    Estimate current true pool temperature based on last calibration
    and cooling model.

    Updates sensor.pool_estimated_true_temp with the estimate.
    """
    now = datetime.now()

    # Get last calibration data
    pre_heat = _safe_get_temp("input_number.pool_true_temp_pre_heating")
    post_heat = _safe_get_temp("input_number.pool_true_temp_post_heating")
    daytime = _safe_get_temp("input_number.pool_true_temp_daytime")

    # Get last calibration time
    last_cal_str = state.get("input_datetime.pool_last_calibration_time")
    if not last_cal_str or last_cal_str in ['unknown', 'unavailable']:
        log.warning("No calibration data available")
        return

    try:
        last_cal_time = datetime.fromisoformat(last_cal_str.replace(' ', 'T'))
    except (ValueError, TypeError):
        log.warning(f"Invalid calibration time: {last_cal_str}")
        return

    hours_since_cal = (now - last_cal_time).total_seconds() / 3600

    # Determine which temp to use as baseline
    hour = now.hour
    if 7 <= hour < 14:
        # Morning after heating - use post_heating
        baseline_temp = post_heat if post_heat > 0 else pre_heat
        baseline_type = "post_heating"
    elif 14 <= hour < 20:
        # Afternoon - use daytime if available, else post_heating
        baseline_temp = daytime if daytime > 0 else (post_heat if post_heat > 0 else pre_heat)
        baseline_type = "daytime" if daytime > 0 else "post_heating"
    else:
        # Evening/night - use pre_heating
        baseline_temp = pre_heat if pre_heat > 0 else post_heat
        baseline_type = "pre_heating"

    if baseline_temp == 0:
        # Expected on fresh system or after reset - will self-heal after first calibration
        log.info("No baseline temperature yet - waiting for first calibration cycle")
        return

    # Apply cooling model: T(t) = T_room + (T_0 - T_room) * e^(-t/τ)
    # τ_cool ≈ 20 hours for covered indoor pool
    tau_cool_hours = 20

    outdoor_temp = _safe_get_temp(OUTDOOR_TEMP_SENSOR)

    # Estimate current temp using exponential decay toward room temp
    estimated_temp = ROOM_TEMP + (baseline_temp - ROOM_TEMP) * \
                     (2.718 ** (-hours_since_cal / tau_cool_hours))

    # Confidence decreases over time
    confidence = max(0, 1 - hours_since_cal / 12)

    # Update the estimate entity
    state.set(
        "sensor.pool_estimated_true_temp",
        value=round(estimated_temp, 1),
        new_attributes={
            "baseline_temp": baseline_temp,
            "baseline_type": baseline_type,
            "hours_since_calibration": round(hours_since_cal, 1),
            "confidence": round(confidence, 2),
            "outdoor_temp": outdoor_temp,
            "unit_of_measurement": "°C",
            "friendly_name": "Pool True Temperature (Estimated)",
            "icon": "mdi:thermometer-water"
        }
    )

    log.info(f"Estimated true pool temp: {estimated_temp:.1f}°C "
             f"(confidence: {confidence:.0%}, baseline: {baseline_type})")


@service
def predict_temp_after_heating():
    """
    Predict pool temperature after tonight's scheduled heating.

    Uses current true temp estimate, scheduled heating hours,
    and calibrated heating efficiency.
    """
    # Get current estimated true temp
    current_temp = _safe_get_temp("sensor.pool_estimated_true_temp")
    if current_temp == 0:
        current_temp = _safe_get_temp("input_number.pool_true_temp_pre_heating")

    if current_temp == 0:
        log.warning("No temperature estimate available")
        return

    # Get scheduled heating minutes
    total_hours = _safe_get_temp("input_number.pool_heating_total_hours")

    # Heating efficiency: °C per hour of heating
    # This should be calibrated from historical data
    # Initial estimate based on thermal calculations:
    # ~18 kW thermal input, 70% mixing efficiency, 32000L pool
    # → ~0.4°C per hour of heating
    heating_rate = 0.4  # °C per hour (will calibrate from data)

    # Heat loss during overnight window (10 hours)
    # Pool loses ~0.3°C per hour at ΔT=5°C from room
    loss_rate = 0.15  # °C per hour average overnight

    # Calculate predicted temp
    heating_hours = total_hours
    idle_hours = 10 - heating_hours  # Heating window is 10 hours

    temp_gain = heating_hours * heating_rate
    temp_loss = idle_hours * loss_rate

    predicted_temp = current_temp + temp_gain - temp_loss

    # Get target for comparison
    target_temp = _safe_get_temp("input_number.pool_target_temperature")

    state.set(
        "sensor.pool_predicted_temp_after_heating",
        value=round(predicted_temp, 1),
        new_attributes={
            "current_estimate": current_temp,
            "heating_hours": heating_hours,
            "predicted_gain": round(temp_gain, 2),
            "predicted_loss": round(temp_loss, 2),
            "target_temp": target_temp,
            "will_reach_target": predicted_temp >= target_temp,
            "unit_of_measurement": "°C",
            "friendly_name": "Predicted Pool Temp After Heating",
            "icon": "mdi:thermometer-chevron-up"
        }
    )

    log.info(f"Predicted temp after heating: {predicted_temp:.1f}°C "
             f"(current: {current_temp}°C, +{temp_gain:.1f}°C heating, -{temp_loss:.1f}°C loss)")
