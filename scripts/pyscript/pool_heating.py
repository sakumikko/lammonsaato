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
TOTAL_HEATING_MINUTES = 120  # 2 hours total heating
MIN_BLOCK_MINUTES = 30       # Minimum consecutive heating duration
MAX_BLOCK_MINUTES = 45       # Maximum consecutive heating duration
SLOT_DURATION_MINUTES = 15   # Nordpool now uses 15-minute intervals

# Entity IDs
# IMPORTANT: Update this if your Nordpool sensor has a different entity ID
# Find your sensor ID in Developer Tools > States > search "nordpool"
NORDPOOL_SENSOR = "sensor.nordpool_kwh_fi_eur_3_10_0255"

# Pool heating control switches
# Heating prevention: turn OFF to allow heating, ON to prevent
HEATING_PREVENTION_SWITCH = "switch.altaan_lammityksen_esto"
# Circulation pump: turn ON when heating, OFF when not
CIRCULATION_PUMP_SWITCH = "switch.altaan_kiertovesipumppu"

# Heating block entities (supports up to 4 blocks for flexibility)
BLOCK_ENTITIES = [
    {"start": "input_datetime.pool_heat_block_1_start",
     "end": "input_datetime.pool_heat_block_1_end",
     "price": "input_number.pool_heat_block_1_price",
     "enabled": "input_boolean.pool_heat_block_1_enabled"},
    {"start": "input_datetime.pool_heat_block_2_start",
     "end": "input_datetime.pool_heat_block_2_end",
     "price": "input_number.pool_heat_block_2_price",
     "enabled": "input_boolean.pool_heat_block_2_enabled"},
    {"start": "input_datetime.pool_heat_block_3_start",
     "end": "input_datetime.pool_heat_block_3_end",
     "price": "input_number.pool_heat_block_3_price",
     "enabled": "input_boolean.pool_heat_block_3_enabled"},
    {"start": "input_datetime.pool_heat_block_4_start",
     "end": "input_datetime.pool_heat_block_4_end",
     "price": "input_number.pool_heat_block_4_price",
     "enabled": "input_boolean.pool_heat_block_4_enabled"},
]
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
    slot_minutes: int = 15
) -> list:
    """
    Find optimal heating schedule using 15-minute price intervals.

    Constraints:
    - Total heating time: 2 hours (120 minutes)
    - Each heating block: 30-45 minutes (2-3 slots)
    - Break between blocks: at least equal to preceding block duration

    Args:
        prices_today: List of 15-minute prices for today (96 slots)
        prices_tomorrow: List of 15-minute prices for tomorrow (96 slots)
        window_start: Start hour (21 = 9 PM)
        window_end: End hour (7 = 7 AM)
        total_minutes: Total heating time needed (default 120)
        min_block_minutes: Minimum consecutive heating (default 30)
        max_block_minutes: Maximum consecutive heating (default 45)
        slot_minutes: Duration per price slot (default 15)

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
    for block_sizes in block_combinations:
        schedule = _find_best_placement(slots, block_sizes, slot_minutes)
        if schedule:
            total_cost = 0
            for b in schedule:
                total_cost = total_cost + b['avg_price'] * b['duration_minutes']
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


def _find_best_placement(slots, block_sizes, slot_minutes):
    """
    Find the best placement of heating blocks with given sizes.

    Each block must be followed by a break of at least equal duration.
    """
    n_slots = len(slots)
    n_blocks = len(block_sizes)

    if n_blocks == 0:
        return []

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

            # Prune if already worse than best
            if new_cost >= best_total_cost:
                continue

            # Calculate minimum start for next block
            # Break must be at least equal to this block's duration
            next_min_start = start_idx + block_size + block_size  # block + equal break

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
# PYSCRIPT SERVICES
# ============================================

@service
def calculate_pool_heating_schedule():
    """
    Calculate and set optimal pool heating schedule based on Nordpool prices.

    Uses 15-minute price intervals and schedules heating blocks of 30-45 minutes
    with equal break periods between them, totaling 2 hours of heating.

    Called by automation when tomorrow's prices become available.
    """
    log.info("Calculating pool heating schedule...")

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

    # Calculate optimal schedule
    schedule = find_best_heating_schedule(
        prices_today=prices_today,
        prices_tomorrow=prices_tomorrow,
        window_start=HEATING_WINDOW_START,
        window_end=HEATING_WINDOW_END,
        total_minutes=TOTAL_HEATING_MINUTES,
        min_block_minutes=MIN_BLOCK_MINUTES,
        max_block_minutes=MAX_BLOCK_MINUTES,
        slot_minutes=SLOT_DURATION_MINUTES
    )

    if not schedule:
        log.error("Could not find suitable heating schedule")
        return

    total_minutes = 0
    for b in schedule:
        total_minutes = total_minutes + b['duration_minutes']
    log.info(f"Found schedule with {len(schedule)} blocks, {total_minutes} total minutes")

    # Reset night complete flag for new schedule (new night session)
    service.call(
        "input_boolean",
        "turn_off",
        entity_id=NIGHT_COMPLETE_FLAG
    )
    log.info("Reset night complete flag for new schedule")

    # Enable all blocks by default for new schedule
    for block_entity in BLOCK_ENTITIES:
        service.call(
            "input_boolean",
            "turn_on",
            entity_id=block_entity["enabled"]
        )
    log.info("Enabled all heating blocks for new schedule")

    # Update block entities
    for i, block_entity in enumerate(BLOCK_ENTITIES):
        if i < len(schedule):
            block = schedule[i]
            # Set start time
            service.call(
                "input_datetime",
                "set_datetime",
                entity_id=block_entity["start"],
                datetime=block['start'].isoformat()
            )
            # Set end time
            service.call(
                "input_datetime",
                "set_datetime",
                entity_id=block_entity["end"],
                datetime=block['end'].isoformat()
            )
            # Set price
            service.call(
                "input_number",
                "set_value",
                entity_id=block_entity["price"],
                value=round(block['avg_price'] * 100, 2)  # Convert to cents
            )
            # Enable the block
            service.call(
                "input_boolean",
                "turn_on",
                entity_id=block_entity["enabled"]
            )
        else:
            # Clear unused block slots
            # Set to a date in the past so automations won't trigger
            # Using start=end signals an invalid/unused block
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
                entity_id=block_entity["end"],
                datetime=past_date.isoformat()  # Same as start = invalid block
            )
            service.call(
                "input_number",
                "set_value",
                entity_id=block_entity["price"],
                value=0
            )
            # Disable unused blocks
            service.call(
                "input_boolean",
                "turn_off",
                entity_id=block_entity["enabled"]
            )

    # Calculate average price
    total_cost = 0
    for b in schedule:
        total_cost = total_cost + b['avg_price'] * b['duration_minutes']
    avg_price = total_cost / total_minutes * 100 if total_minutes > 0 else 0

    # Build info text
    block_info = []
    for b in schedule:
        block_info.append(
            f"{b['start'].strftime('%H:%M')}-{b['end'].strftime('%H:%M')} "
            f"({b['duration_minutes']}min, {b['avg_price']*100:.1f}c)"
        )
    info_text = " | ".join(block_info) + f" | Avg: {avg_price:.1f}c/kWh"

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
            'avg_price': b['avg_price']
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
# NIGHTLY SUMMARY
# ============================================

@service
def calculate_night_summary(heating_date=None):
    """
    Calculate summary for a heating night (21:00 to 07:00).

    This is called at 07:00 each day to aggregate all heating blocks
    from the previous night into a single summary.

    Args:
        heating_date: The date string (YYYY-MM-DD) of the heating night start.
                     Defaults to the previous night.
    """
    now = datetime.now()

    if heating_date is None:
        # Default to the night that just ended
        heating_date = get_heating_date(now - timedelta(hours=1))

    log.info(f"Calculating night summary for {heating_date}")

    # Get current utility meter values (these reset at 07:00)
    total_energy = _safe_get_temp("sensor.pool_heating_electricity_daily")
    total_cost = _safe_get_temp("sensor.pool_heating_cost_daily")

    # Get pool temperatures from first and last blocks
    # We'll use current values as approximation since blocks just ended
    pool_temp_final = _safe_get_temp(POOL_WATER_TEMP)
    outdoor_temp = _safe_get_temp(OUTDOOR_TEMP_SENSOR)

    # Get block prices for average calculation
    block_prices = []
    blocks_count = 0
    total_duration = 0

    for i in range(1, 5):
        enabled = state.get(f"input_boolean.pool_heat_block_{i}_enabled")
        if enabled == "on":
            price = _safe_get_temp(f"input_number.pool_heat_block_{i}_price")
            if price > 0:
                block_prices.append(price)
                blocks_count += 1
                # Estimate duration from block times
                start = state.get(f"input_datetime.pool_heat_block_{i}_start")
                end = state.get(f"input_datetime.pool_heat_block_{i}_end")
                if start and end and start not in ['unknown', 'unavailable']:
                    try:
                        start_dt = datetime.fromisoformat(start.replace(' ', 'T'))
                        end_dt = datetime.fromisoformat(end.replace(' ', 'T'))
                        duration = (end_dt - start_dt).total_seconds() / 60
                        total_duration += int(duration)
                    except (ValueError, TypeError):
                        pass

    # Calculate average price
    avg_price = sum(block_prices) / len(block_prices) if block_prices else 0

    # Calculate baseline cost (what it would cost at average 21-07 price)
    # Get average of all Nordpool prices in the 21-07 window
    prices_yesterday = state.getattr(NORDPOOL_SENSOR).get('today', [])  # yesterday's prices now
    prices_today_morning = state.getattr(NORDPOOL_SENSOR).get('today', [])

    window_prices = []
    # 21:00-23:45 yesterday (slots 84-95)
    if prices_yesterday and len(prices_yesterday) >= 96:
        for i in range(84, 96):  # 21:00 to 23:45
            window_prices.append(prices_yesterday[i])
    # 00:00-06:45 today (slots 0-27)
    if prices_today_morning and len(prices_today_morning) >= 28:
        for i in range(0, 28):  # 00:00 to 06:45
            window_prices.append(prices_today_morning[i])

    avg_window_price = sum(window_prices) / len(window_prices) if window_prices else 0.10
    baseline_cost = total_energy * avg_window_price

    # Calculate savings
    savings = baseline_cost - total_cost

    # Update night summary entity
    state.set(
        NIGHT_SUMMARY_ENTITY,
        value=round(total_energy, 3),
        new_attributes={
            "heating_date": heating_date,
            "total_energy": round(total_energy, 3),
            "total_cost": round(total_cost, 4),
            "total_duration": total_duration,
            "blocks_count": blocks_count,
            "pool_temp_final": round(pool_temp_final, 1),
            "outdoor_temp_avg": round(outdoor_temp, 1),
            "avg_price": round(avg_price, 2),
            "avg_window_price": round(avg_window_price * 100, 2),  # Convert to cents
            "baseline_cost": round(baseline_cost, 4),
            "savings": round(savings, 4),
            "savings_percent": round((savings / baseline_cost * 100) if baseline_cost > 0 else 0, 1),
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "measurement",
            "friendly_name": "Pool Heating Night Summary",
        }
    )

    log.info(f"Night summary for {heating_date}: {total_energy:.2f} kWh, "
             f"{total_cost:.3f}€, {blocks_count} blocks, "
             f"savings: {savings:.3f}€ ({savings/baseline_cost*100:.1f}%)" if baseline_cost > 0 else "")


@service
def backfill_night_summaries(days=7):
    """
    Backfill night summaries from historical sensor data.

    This queries HA history for past days and creates night summary
    entries based on available data.

    Args:
        days: Number of days to backfill (default 7)
    """
    import homeassistant.core as ha_core

    log.info(f"Backfilling night summaries for {days} days")

    # We need to query history via HA's recorder
    # For each day, we'll get the daily electricity/cost meter values
    end_date = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)

    summaries_created = 0

    for day_offset in range(1, days + 1):
        # Calculate the heating date (night starts at 21:00 on this date)
        target_date = (end_date - timedelta(days=day_offset)).date()
        heating_date = target_date.strftime('%Y-%m-%d')

        # Time range for this night: 21:00 on target_date to 07:00 next day
        night_start = datetime.combine(target_date, datetime.min.time().replace(hour=21))
        night_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time().replace(hour=7))

        log.info(f"Processing {heating_date}: {night_start} to {night_end}")

        # Query historical state for electricity and cost at night boundaries
        # We'll use the state_get service if available, or estimate from statistics
        try:
            # Get energy consumption for this period using history_stats
            # This is an approximation - we take the meter value change

            # Try to get values from recorder history
            # Note: This requires the recorder integration
            energy_start = None
            energy_end = None
            cost_start = None
            cost_end = None
            pool_temp = None
            outdoor_temp = None

            # For now, we'll create estimates based on typical values
            # In production, you'd query HA history via:
            # hass.states.async_get_history(start, end, entity_ids)

            # Since we can't directly query history from pyscript easily,
            # we'll use a workaround: check if recorder has data via service call

            # Estimate values based on current patterns (fallback)
            # Typical night: 2 hours heating at 2-3 kW = 4-6 kWh thermal, 1.3-2 kWh electric
            estimated_energy = 1.5  # kWh electric (2h * ~0.75kW average)
            estimated_cost = 0.08   # EUR (at ~5c/kWh average)

            # Use history service to get actual data if available
            history_result = task.executor(
                _query_history_for_date,
                heating_date,
                night_start,
                night_end
            )

            if history_result:
                estimated_energy = history_result.get('energy', estimated_energy)
                estimated_cost = history_result.get('cost', estimated_cost)
                pool_temp = history_result.get('pool_temp', 25.0)
                outdoor_temp = history_result.get('outdoor_temp', 5.0)
            else:
                pool_temp = 25.0
                outdoor_temp = 5.0

            # Calculate baseline and savings (estimate)
            avg_window_price = 0.08  # 8c/kWh fallback
            baseline_cost = estimated_energy * avg_window_price
            savings = baseline_cost - estimated_cost

            # Update the night summary entity with historical data
            # Each update creates a new history entry
            state.set(
                NIGHT_SUMMARY_ENTITY,
                value=round(estimated_energy, 3),
                new_attributes={
                    "heating_date": heating_date,
                    "total_energy": round(estimated_energy, 3),
                    "total_cost": round(estimated_cost, 4),
                    "total_duration": 120,  # Estimated 2h
                    "blocks_count": 3,  # Typical
                    "pool_temp_final": round(pool_temp, 1),
                    "outdoor_temp_avg": round(outdoor_temp, 1),
                    "avg_price": round(estimated_cost / estimated_energy * 100, 2) if estimated_energy > 0 else 0,
                    "avg_window_price": round(avg_window_price * 100, 2),
                    "baseline_cost": round(baseline_cost, 4),
                    "savings": round(savings, 4),
                    "savings_percent": round((savings / baseline_cost * 100) if baseline_cost > 0 else 0, 1),
                    "backfilled": True,  # Mark as backfilled data
                    "unit_of_measurement": "kWh",
                    "device_class": "energy",
                    "state_class": "measurement",
                    "friendly_name": "Pool Heating Night Summary",
                }
            )

            summaries_created += 1
            log.info(f"Created summary for {heating_date}: {estimated_energy:.2f} kWh, {estimated_cost:.3f}€")

            # Small delay to ensure distinct history entries
            task.sleep(0.5)

        except Exception as e:
            log.error(f"Failed to process {heating_date}: {e}")
            continue

    log.info(f"Backfill complete: {summaries_created} summaries created")


def _query_history_for_date(heating_date, night_start, night_end):
    """
    Query HA history for a specific night period.
    This runs in executor to avoid blocking.

    Returns dict with energy, cost, pool_temp, outdoor_temp or None.
    """
    try:
        # Import HA components
        from homeassistant.components.recorder import history
        from homeassistant.core import HomeAssistant

        # Get the hass object
        hass = pyscript.hass

        # Query history for the electricity daily sensor
        # Note: We're looking for state changes during this period
        entity_ids = [
            "sensor.pool_heating_electricity_daily",
            "sensor.pool_heating_cost_daily",
            "sensor.pool_return_line_temperature_corrected",
            "sensor.outdoor_temperature"
        ]

        # This is a synchronous history query
        states_by_entity = history.state_changes_during_period(
            hass,
            night_start,
            night_end,
            entity_ids,
        )

        result = {}

        # Get energy - look for max value during the period (utility meter accumulates)
        if "sensor.pool_heating_electricity_daily" in states_by_entity:
            energy_states = states_by_entity["sensor.pool_heating_electricity_daily"]
            if energy_states:
                values = [float(s.state) for s in energy_states if s.state not in ['unknown', 'unavailable']]
                if values:
                    result['energy'] = max(values)

        # Get cost
        if "sensor.pool_heating_cost_daily" in states_by_entity:
            cost_states = states_by_entity["sensor.pool_heating_cost_daily"]
            if cost_states:
                values = [float(s.state) for s in cost_states if s.state not in ['unknown', 'unavailable']]
                if values:
                    result['cost'] = max(values)

        # Get pool temp (average)
        if "sensor.pool_return_line_temperature_corrected" in states_by_entity:
            temp_states = states_by_entity["sensor.pool_return_line_temperature_corrected"]
            if temp_states:
                values = [float(s.state) for s in temp_states if s.state not in ['unknown', 'unavailable']]
                if values:
                    result['pool_temp'] = sum(values) / len(values)

        # Get outdoor temp (average)
        if "sensor.outdoor_temperature" in states_by_entity:
            temp_states = states_by_entity["sensor.outdoor_temperature"]
            if temp_states:
                values = [float(s.state) for s in temp_states if s.state not in ['unknown', 'unavailable']]
                if values:
                    result['outdoor_temp'] = sum(values) / len(values)

        return result if result else None

    except Exception as e:
        log.warning(f"History query failed: {e}")
        return None
