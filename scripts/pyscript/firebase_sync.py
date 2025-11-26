"""
Firebase Data Sync Module for Pool Heating

Syncs heating session data to Firebase Realtime Database for external analysis.

Place this file in /config/pyscript/firebase_sync.py

Requirements:
- Firebase project with Realtime Database
- Service account key in /config/secrets/firebase-key.json
- firebase-admin package (may need custom component or AppDaemon for full support)

Note: Due to pyscript limitations with external packages, consider using:
1. REST API approach (shown here)
2. AppDaemon for full firebase-admin support
3. Node-RED with Firebase nodes
"""

import json
from datetime import datetime

# ============================================
# CONFIGURATION
# ============================================

# Firebase configuration (use secrets in production)
FIREBASE_URL = "https://your-project.firebaseio.com"
FIREBASE_AUTH_KEY = ""  # Optional: Database secret or leave empty for rules-based auth

# Alternative: Store config in pyscript config
# pyscript.config.get('firebase_url')

# ============================================
# REST API APPROACH (Works in pyscript)
# ============================================

@service
async def sync_to_firebase(data: dict = None, path: str = "heating_sessions"):
    """
    Sync data to Firebase using REST API.

    This approach works within pyscript without external packages.
    Firebase must be configured with appropriate security rules.

    Args:
        data: Dictionary to store
        path: Firebase path (e.g., "heating_sessions", "daily_prices")
    """
    if not data:
        log.warning("No data provided to sync_to_firebase")
        return

    # Generate unique key based on timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_path = f"{path}/{timestamp}"

    # Add metadata
    data['_synced_at'] = datetime.now().isoformat()

    url = f"{FIREBASE_URL}/{full_path}.json"
    if FIREBASE_AUTH_KEY:
        url += f"?auth={FIREBASE_AUTH_KEY}"

    try:
        # Use HA's built-in REST command or pyscript's task.executor
        # This is a simplified version - actual implementation depends on
        # available HTTP client in pyscript

        log.info(f"Would sync to Firebase: {url}")
        log.info(f"Data: {json.dumps(data, default=str)[:200]}...")

        # In actual implementation with REST support:
        # response = await task.executor(requests.put, url, json=data)
        # if response.status_code == 200:
        #     log.info(f"Successfully synced to Firebase: {full_path}")
        # else:
        #     log.error(f"Firebase sync failed: {response.status_code}")

    except Exception as e:
        log.error(f"Firebase sync error: {e}")


# ============================================
# EVENT LISTENERS
# ============================================

@event_trigger("pool_heating_session_complete")
def on_heating_session_complete(**kwargs):
    """
    Handle heating session completion event.
    Automatically sync session data to Firebase.
    """
    session_data = kwargs.get('session_data', {})

    if not session_data:
        log.warning("Received empty session data")
        return

    log.info("Syncing heating session to Firebase...")

    # Prepare data for Firebase (flatten for easier querying)
    firebase_data = {
        'start_time': session_data.get('start_time'),
        'end_time': session_data.get('end_time'),
        'duration_hours': session_data.get('duration_hours'),
        'electricity_price_eur': session_data.get('electricity_price'),
        'avg_delta_t': session_data.get('avg_delta_t'),
        'pool_temp_before': session_data.get('pool_temp_before'),
        'pool_temp_after': session_data.get('pool_temp_after'),
        'pool_temp_change': session_data.get('pool_temp_change'),
        'estimated_kwh': session_data.get('estimated_kwh'),
        # Store raw readings separately or summarize
        'num_readings': len(session_data.get('temperature_readings', []))
    }

    task.create(sync_to_firebase(data=firebase_data, path="heating_sessions"))


@time_trigger("cron(0 8 * * *)")
def daily_price_summary():
    """
    Daily summary of prices and heating decisions.
    Runs at 8 AM after the heating window closes.
    """
    log.info("Generating daily price summary...")

    # Get yesterday's slot information
    slot1_price = float(state.get("input_number.pool_heat_slot_1_price") or 0)
    slot2_price = float(state.get("input_number.pool_heat_slot_2_price") or 0)
    slot1_time = state.get("input_datetime.pool_heat_slot_1")
    slot2_time = state.get("input_datetime.pool_heat_slot_2")

    # Get Nordpool prices for analysis
    nordpool_attrs = state.getattr("sensor.nordpool_kwh_fi_eur_3_10_024") or {}
    today_prices = nordpool_attrs.get('today', [])

    if today_prices:
        # Calculate what the average nighttime price was
        night_prices = today_prices[21:24] + today_prices[0:7]
        avg_night_price = sum(night_prices) / len(night_prices) if night_prices else 0

        summary_data = {
            'date': datetime.now().strftime("%Y-%m-%d"),
            'slot1_time': slot1_time,
            'slot1_price_cents': slot1_price,
            'slot2_time': slot2_time,
            'slot2_price_cents': slot2_price,
            'avg_selected_price': (slot1_price + slot2_price) / 2,
            'avg_night_price_cents': avg_night_price * 100,
            'savings_vs_avg': avg_night_price * 100 - (slot1_price + slot2_price) / 2,
            'all_night_prices_cents': [p * 100 for p in night_prices]
        }

        task.create(sync_to_firebase(data=summary_data, path="daily_summaries"))


# ============================================
# MANUAL SYNC UTILITIES
# ============================================

@service
def firebase_test_connection():
    """
    Test Firebase connection with a simple write.
    """
    test_data = {
        'test': True,
        'timestamp': datetime.now().isoformat(),
        'source': 'home_assistant'
    }

    task.create(sync_to_firebase(data=test_data, path="connection_tests"))
    log.info("Firebase connection test initiated")


@service
def firebase_export_history(days: int = 7):
    """
    Export recent history data to Firebase.
    Useful for initial data migration.
    """
    log.info(f"Would export {days} days of history to Firebase")
    # Implementation would query HA history and batch upload


# ============================================
# ALTERNATIVE: FILE-BASED BACKUP
# ============================================

@service
def backup_session_to_file(session_data: dict = None):
    """
    Backup heating session data to local JSON file.
    Alternative/supplement to Firebase for local redundancy.
    """
    if not session_data:
        return

    backup_dir = "/config/pool_heating_logs"
    filename = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Note: File operations in pyscript may have limitations
    # Consider using HA's file notification or shell commands

    log.info(f"Would backup to {backup_dir}/{filename}")
