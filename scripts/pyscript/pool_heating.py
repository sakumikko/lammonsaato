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
NUM_HEATING_SLOTS = 2
MIN_GAP_HOURS = 1          # Minimum gap between heating slots

# Entity IDs
NORDPOOL_SENSOR = "sensor.nordpool_kwh_fi_eur_3_10_024"
SLOT_1_DATETIME = "input_datetime.pool_heat_slot_1"
SLOT_2_DATETIME = "input_datetime.pool_heat_slot_2"
SLOT_1_PRICE = "input_number.pool_heat_slot_1_price"
SLOT_2_PRICE = "input_number.pool_heat_slot_2_price"
SCHEDULE_INFO = "input_text.pool_heating_schedule_info"
SUPPLY_TEMP = "sensor.thermia_supply_temperature"
RETURN_TEMP = "sensor.thermia_return_temperature"
POOL_TEMP = "sensor.pool_water_temperature"  # Add your pool temp sensor


# ============================================
# PRICE OPTIMIZATION ALGORITHM
# ============================================

def find_best_heating_slots(prices_today: list, prices_tomorrow: list,
                           window_start: int = 21, window_end: int = 7,
                           num_slots: int = 2, min_gap: int = 1) -> list:
    """
    Find N cheapest non-consecutive hours in the heating window.

    Args:
        prices_today: List of 24 hourly prices for today
        prices_tomorrow: List of 24 hourly prices for tomorrow
        window_start: Start hour (21 = 9 PM)
        window_end: End hour (7 = 7 AM)
        num_slots: Number of heating slots needed
        min_gap: Minimum hours gap between slots

    Returns:
        List of (datetime, price) tuples for best slots
    """
    # Build list of valid hours with their prices and datetime
    # Tonight: hours 21-23 from today
    # Tomorrow morning: hours 0-6 from tomorrow
    today = date.today()
    tomorrow = today + timedelta(days=1)

    valid_hours = []

    # Tonight's hours (21:00 - 23:00)
    for hour in range(window_start, 24):
        if prices_today and hour < len(prices_today):
            dt = datetime.combine(today, datetime.min.time().replace(hour=hour))
            valid_hours.append({
                'datetime': dt,
                'hour': hour,
                'price': prices_today[hour],
                'day': 'today'
            })

    # Tomorrow morning hours (00:00 - 06:00)
    for hour in range(0, window_end):
        if prices_tomorrow and hour < len(prices_tomorrow):
            dt = datetime.combine(tomorrow, datetime.min.time().replace(hour=hour))
            valid_hours.append({
                'datetime': dt,
                'hour': hour,
                'price': prices_tomorrow[hour],
                'day': 'tomorrow'
            })

    # Sort by price (cheapest first)
    valid_hours.sort(key=lambda x: x['price'])

    # Select non-consecutive hours
    selected = []

    for candidate in valid_hours:
        if len(selected) >= num_slots:
            break

        # Check if this hour is adjacent to any already selected hour
        is_too_close = False
        for sel in selected:
            # Calculate hour difference considering day boundary
            cand_abs_hour = candidate['hour'] + (24 if candidate['day'] == 'tomorrow' else 0)
            sel_abs_hour = sel['hour'] + (24 if sel['day'] == 'tomorrow' else 0)

            if abs(cand_abs_hour - sel_abs_hour) <= min_gap:
                is_too_close = True
                break

        if not is_too_close:
            selected.append(candidate)

    # Sort selected by datetime
    selected.sort(key=lambda x: x['datetime'])

    return [(s['datetime'], s['price']) for s in selected]


# ============================================
# PYSCRIPT SERVICES
# ============================================

@service
def calculate_pool_heating_slots():
    """
    Calculate and set optimal pool heating slots based on Nordpool prices.

    Called by automation when tomorrow's prices become available.
    """
    log.info("Calculating pool heating slots...")

    # Get prices from Nordpool sensor
    nordpool_state = state.get(NORDPOOL_SENSOR)
    if nordpool_state in ['unknown', 'unavailable']:
        log.error("Nordpool sensor not available")
        return

    # Get price arrays from attributes
    prices_today = state.getattr(NORDPOOL_SENSOR).get('today', [])
    prices_tomorrow = state.getattr(NORDPOOL_SENSOR).get('tomorrow', [])
    tomorrow_valid = state.getattr(NORDPOOL_SENSOR).get('tomorrow_valid', False)

    if not tomorrow_valid:
        log.warning("Tomorrow's prices not yet available")
        return

    if not prices_today or not prices_tomorrow:
        log.error("Price data missing")
        return

    # Calculate best slots
    best_slots = find_best_heating_slots(
        prices_today=prices_today,
        prices_tomorrow=prices_tomorrow,
        window_start=HEATING_WINDOW_START,
        window_end=HEATING_WINDOW_END,
        num_slots=NUM_HEATING_SLOTS,
        min_gap=MIN_GAP_HOURS
    )

    if len(best_slots) < NUM_HEATING_SLOTS:
        log.error(f"Could only find {len(best_slots)} suitable slots")
        return

    # Update input_datetime helpers
    slot1_dt, slot1_price = best_slots[0]
    slot2_dt, slot2_price = best_slots[1]

    # Set slot 1
    service.call(
        "input_datetime",
        "set_datetime",
        entity_id=SLOT_1_DATETIME,
        datetime=slot1_dt.isoformat()
    )
    service.call(
        "input_number",
        "set_value",
        entity_id=SLOT_1_PRICE,
        value=round(slot1_price * 100, 2)  # Convert to cents
    )

    # Set slot 2
    service.call(
        "input_datetime",
        "set_datetime",
        entity_id=SLOT_2_DATETIME,
        datetime=slot2_dt.isoformat()
    )
    service.call(
        "input_number",
        "set_value",
        entity_id=SLOT_2_PRICE,
        value=round(slot2_price * 100, 2)
    )

    # Update info text
    avg_price = (slot1_price + slot2_price) / 2 * 100
    info_text = f"Slots: {slot1_dt.strftime('%H:%M')} ({slot1_price*100:.1f}c), {slot2_dt.strftime('%H:%M')} ({slot2_price*100:.1f}c) | Avg: {avg_price:.1f}c/kWh"
    service.call(
        "input_text",
        "set_value",
        entity_id=SCHEDULE_INFO,
        value=info_text
    )

    log.info(f"Pool heating scheduled: {info_text}")


# ============================================
# HEATING SESSION LOGGING
# ============================================

# Session tracking (in-memory for current session)
_current_session = {}


@service
def log_heating_start():
    """
    Log the start of a heating session.
    Records initial temperatures and electricity price.
    """
    global _current_session

    now = datetime.now()

    _current_session = {
        'start_time': now.isoformat(),
        'start_supply_temp': float(state.get(SUPPLY_TEMP) or 0),
        'start_return_temp': float(state.get(RETURN_TEMP) or 0),
        'start_pool_temp': float(state.get(POOL_TEMP) or 0),
        'electricity_price': float(state.get(NORDPOOL_SENSOR) or 0),
        'temperature_readings': []
    }

    log.info(f"Heating session started at {now.strftime('%H:%M')}")
    log.info(f"Initial temps - Supply: {_current_session['start_supply_temp']}°C, "
             f"Return: {_current_session['start_return_temp']}°C")


@service
def log_pool_temperatures():
    """
    Log current temperatures during heating session.
    Called periodically by automation.
    """
    global _current_session

    if not _current_session:
        return

    reading = {
        'timestamp': datetime.now().isoformat(),
        'supply_temp': float(state.get(SUPPLY_TEMP) or 0),
        'return_temp': float(state.get(RETURN_TEMP) or 0),
        'pool_temp': float(state.get(POOL_TEMP) or 0),
        'delta_t': float(state.get("sensor.pool_heat_exchanger_delta_t") or 0)
    }

    _current_session['temperature_readings'].append(reading)
    log.debug(f"Temperature logged: Delta-T = {reading['delta_t']}°C")


@service
def log_heating_end():
    """
    Log the end of a heating session.
    Calculate energy consumption and prepare data for Firebase.
    """
    global _current_session

    if not _current_session:
        log.warning("No active heating session to end")
        return

    now = datetime.now()

    # Calculate session metrics
    end_supply_temp = float(state.get(SUPPLY_TEMP) or 0)
    end_return_temp = float(state.get(RETURN_TEMP) or 0)
    end_pool_temp = float(state.get(POOL_TEMP) or 0)

    # Average delta-T during session
    if _current_session['temperature_readings']:
        avg_delta_t = sum(r['delta_t'] for r in _current_session['temperature_readings']) / len(_current_session['temperature_readings'])
    else:
        avg_delta_t = end_supply_temp - end_return_temp

    # Pool temperature change
    pool_temp_change = end_pool_temp - _current_session['start_pool_temp']

    # Session duration in hours
    start_time = datetime.fromisoformat(_current_session['start_time'])
    duration_hours = (now - start_time).total_seconds() / 3600

    # Estimated energy (simplified: Q = flow_rate * delta_T * time * specific_heat)
    # This is a rough estimate - actual calculation needs flow rate
    # For now, store raw delta-T data for later analysis
    estimated_kwh = avg_delta_t * duration_hours * 0.5  # Rough estimate factor

    session_data = {
        'start_time': _current_session['start_time'],
        'end_time': now.isoformat(),
        'duration_hours': round(duration_hours, 2),
        'electricity_price': _current_session['electricity_price'],
        'start_supply_temp': _current_session['start_supply_temp'],
        'start_return_temp': _current_session['start_return_temp'],
        'end_supply_temp': end_supply_temp,
        'end_return_temp': end_return_temp,
        'avg_delta_t': round(avg_delta_t, 2),
        'pool_temp_before': _current_session['start_pool_temp'],
        'pool_temp_after': end_pool_temp,
        'pool_temp_change': round(pool_temp_change, 2),
        'estimated_kwh': round(estimated_kwh, 2),
        'temperature_readings': _current_session['temperature_readings']
    }

    log.info(f"Heating session ended. Duration: {duration_hours:.1f}h, "
             f"Avg Delta-T: {avg_delta_t:.1f}°C, Pool change: {pool_temp_change:.1f}°C")

    # Store session data for Firebase sync
    # This fires an event that firebase_sync.py listens to
    event.fire("pool_heating_session_complete", session_data=session_data)

    # Clear current session
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
    log.info(f"Tonight (21-23): {[f'{p*100:.1f}c' for p in prices_today[21:24]] if len(prices_today) > 21 else 'N/A'}")
    log.info(f"Tomorrow (0-6): {[f'{p*100:.1f}c' for p in prices_tomorrow[0:7]] if prices_tomorrow else 'N/A'}")
