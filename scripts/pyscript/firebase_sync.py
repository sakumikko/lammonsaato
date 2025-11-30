"""
Data Logging Module for Pool Heating

Logs heating session data to local JSON files for analysis.
Firebase sync has been disabled - data is stored locally in /config/pool_heating_logs/

Place this file in /config/pyscript/data_logger.py
"""

import json
import os
from datetime import datetime

# ============================================
# CONFIGURATION
# ============================================

LOG_DIR = "/config/pool_heating_logs"


# ============================================
# LOCAL FILE LOGGING
# ============================================

def _ensure_log_dir():
    """Ensure log directory exists."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        return True
    except Exception as e:
        log.error(f"Cannot create log directory {LOG_DIR}: {e}")
        return False


def _write_json_log(data: dict, prefix: str = "session"):
    """Write data to a JSON log file."""
    if not _ensure_log_dir():
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{LOG_DIR}/{prefix}_{timestamp}.json"

    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        log.info(f"Data logged to {filename}")
        return True
    except Exception as e:
        log.error(f"Failed to write log file: {e}")
        return False


@service
def log_data(data: dict = None, log_type: str = "general"):
    """
    Log data to local JSON file.

    Args:
        data: Dictionary to log
        log_type: Type prefix for filename (e.g., "session", "schedule", "daily")
    """
    if not data:
        log.warning("No data provided to log_data")
        return False

    data['_logged_at'] = datetime.now().isoformat()
    data['_source'] = 'home_assistant'

    return _write_json_log(data, prefix=log_type)


# ============================================
# EVENT LISTENERS
# ============================================

@event_trigger("pool_heating_session_complete")
def on_heating_session_complete(**kwargs):
    """
    Handle heating session completion event.
    Log session data to local file.
    """
    session_data = kwargs.get('session_data', {})

    if not session_data:
        log.warning("Received empty session data")
        return

    log.info("Logging heating session...")

    # Prepare data for logging
    log_data_dict = {
        'start_time': session_data.get('start_time'),
        'end_time': session_data.get('end_time'),
        'duration_hours': session_data.get('duration_hours'),
        'electricity_price_eur': session_data.get('electricity_price'),
        'avg_delta_t': session_data.get('avg_delta_t'),
        'pool_temp_before': session_data.get('pool_temp_before'),
        'pool_temp_after': session_data.get('pool_temp_after'),
        'pool_temp_change': session_data.get('pool_temp_change'),
        'estimated_kwh': session_data.get('estimated_kwh'),
        'num_readings': len(session_data.get('temperature_readings', []))
    }

    _write_json_log(log_data_dict, prefix="session")


@time_trigger("cron(0 8 * * *)")
def daily_price_summary():
    """
    Daily summary of prices and heating decisions.
    Runs at 8 AM after the heating window closes.
    """
    log.info("Generating daily price summary...")

    # Get block information
    block_prices = []
    block_times = []
    for i in range(1, 5):
        price = float(state.get(f"input_number.pool_heat_block_{i}_price") or 0)
        start = state.get(f"input_datetime.pool_heat_block_{i}_start")
        end = state.get(f"input_datetime.pool_heat_block_{i}_end")
        if price > 0:
            block_prices.append(price)
            block_times.append({'start': start, 'end': end, 'price': price})

    # Get Nordpool prices for analysis
    nordpool_attrs = state.getattr("sensor.nordpool_kwh_fi_eur_3_10_0255") or {}
    today_prices = nordpool_attrs.get('today', [])

    if today_prices and block_prices:
        # For 15-min prices, night window is slots 84-95 (21:00-23:45) + 0-27 (00:00-06:45)
        if len(today_prices) > 24:
            night_prices = today_prices[84:96] + today_prices[0:28]
        else:
            night_prices = today_prices[21:24] + today_prices[0:7]

        avg_night_price = sum(night_prices) / len(night_prices) if night_prices else 0
        avg_selected_price = sum(block_prices) / len(block_prices)

        summary_data = {
            'date': datetime.now().strftime("%Y-%m-%d"),
            'blocks': block_times,
            'num_blocks': len(block_prices),
            'avg_selected_price_cents': avg_selected_price,
            'avg_night_price_cents': avg_night_price * 100,
            'savings_cents': avg_night_price * 100 - avg_selected_price,
            'total_heating_minutes': len(block_prices) * 30
        }

        _write_json_log(summary_data, prefix="daily")


# ============================================
# MANUAL UTILITIES
# ============================================

@service
def log_current_schedule():
    """
    Manually log the current heating schedule.
    """
    schedule_info = state.get("input_text.pool_heating_schedule_info")

    blocks = []
    for i in range(1, 5):
        start = state.get(f"input_datetime.pool_heat_block_{i}_start")
        end = state.get(f"input_datetime.pool_heat_block_{i}_end")
        price = float(state.get(f"input_number.pool_heat_block_{i}_price") or 0)
        if price > 0:
            blocks.append({
                'block': i,
                'start': start,
                'end': end,
                'price_cents': price
            })

    schedule_data = {
        'schedule_info': schedule_info,
        'blocks': blocks,
        'heating_enabled': state.get("input_boolean.pool_heating_enabled")
    }

    _write_json_log(schedule_data, prefix="schedule")


@service
def test_logging():
    """
    Test logging with sample data.
    Call from Developer Tools > Services > pyscript.test_logging
    """
    test_data = {
        'test': True,
        'timestamp': datetime.now().isoformat(),
        'message': 'Logging test from Home Assistant'
    }

    success = _write_json_log(test_data, prefix="test")
    if success:
        log.info("Logging test successful!")
    else:
        log.error("Logging test failed - check logs")
