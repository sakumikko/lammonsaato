#!/usr/bin/env python3
"""
Test script for Firebase connection and data operations.

Usage:
    python test_firebase.py --test-connection
    python test_firebase.py --write-test
    python test_firebase.py --read-path heating_sessions

Requirements:
    pip install firebase-admin
    Place your service account key at: ./firebase-key.json

Alternative (REST API, no firebase-admin required):
    pip install requests
    Use --rest flag
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

# Try to import firebase-admin, fall back to REST API
try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_ADMIN_AVAILABLE = True
except ImportError:
    FIREBASE_ADMIN_AVAILABLE = False
    print("firebase-admin not installed, using REST API fallback")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ============================================
# CONFIGURATION
# ============================================

# Path to service account key (for firebase-admin)
SERVICE_ACCOUNT_KEY = os.environ.get(
    'FIREBASE_KEY_PATH',
    str(Path(__file__).parent / 'firebase-key.json')
)

# Firebase Realtime Database URL
FIREBASE_URL = os.environ.get(
    'FIREBASE_URL',
    'https://your-project-id.firebaseio.com'
)

# Optional: Database secret for REST API auth
FIREBASE_SECRET = os.environ.get('FIREBASE_SECRET', '')


# ============================================
# FIREBASE ADMIN SDK METHODS
# ============================================

def init_firebase_admin():
    """Initialize Firebase Admin SDK."""
    if not FIREBASE_ADMIN_AVAILABLE:
        raise ImportError("firebase-admin package not installed")

    if not os.path.exists(SERVICE_ACCOUNT_KEY):
        raise FileNotFoundError(f"Service account key not found: {SERVICE_ACCOUNT_KEY}")

    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_URL
        })

    return db.reference()


def test_connection_admin():
    """Test Firebase connection using Admin SDK."""
    print("Testing Firebase connection (Admin SDK)...")
    try:
        ref = init_firebase_admin()
        # Try to read the root
        data = ref.get()
        print(f"Connected successfully!")
        print(f"Root keys: {list(data.keys()) if data else '(empty database)'}")
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


def write_test_data_admin():
    """Write test data using Admin SDK."""
    print("Writing test data (Admin SDK)...")
    try:
        ref = init_firebase_admin()

        test_data = {
            'test': True,
            'timestamp': datetime.now().isoformat(),
            'source': 'test_firebase.py',
            'sample_heating_session': {
                'start_time': '2024-01-15T22:00:00',
                'end_time': '2024-01-15T23:00:00',
                'electricity_price': 0.0523,
                'avg_delta_t': 7.1,
                'pool_temp_change': 0.6
            }
        }

        # Write to test path
        test_ref = ref.child('connection_tests').push(test_data)
        print(f"Test data written to: connection_tests/{test_ref.key}")
        return True
    except Exception as e:
        print(f"Write failed: {e}")
        return False


def read_path_admin(path: str):
    """Read data from a specific path using Admin SDK."""
    print(f"Reading path: {path}")
    try:
        ref = init_firebase_admin()
        data = ref.child(path).get()
        print(json.dumps(data, indent=2, default=str))
        return data
    except Exception as e:
        print(f"Read failed: {e}")
        return None


# ============================================
# REST API METHODS (No firebase-admin required)
# ============================================

def test_connection_rest():
    """Test Firebase connection using REST API."""
    if not REQUESTS_AVAILABLE:
        raise ImportError("requests package not installed")

    print("Testing Firebase connection (REST API)...")
    url = f"{FIREBASE_URL}/.json"
    if FIREBASE_SECRET:
        url += f"?auth={FIREBASE_SECRET}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f"Connected successfully!")
            print(f"Root keys: {list(data.keys()) if data else '(empty database)'}")
            return True
        else:
            print(f"Connection failed: HTTP {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


def write_test_data_rest():
    """Write test data using REST API."""
    if not REQUESTS_AVAILABLE:
        raise ImportError("requests package not installed")

    print("Writing test data (REST API)...")

    test_data = {
        'test': True,
        'timestamp': datetime.now().isoformat(),
        'source': 'test_firebase.py (REST)',
        'sample_heating_session': {
            'start_time': '2024-01-15T22:00:00',
            'end_time': '2024-01-15T23:00:00',
            'electricity_price': 0.0523,
            'avg_delta_t': 7.1,
            'pool_temp_change': 0.6
        }
    }

    url = f"{FIREBASE_URL}/connection_tests.json"
    if FIREBASE_SECRET:
        url += f"?auth={FIREBASE_SECRET}"

    try:
        response = requests.post(url, json=test_data)
        if response.status_code == 200:
            result = response.json()
            print(f"Test data written to: connection_tests/{result.get('name')}")
            return True
        else:
            print(f"Write failed: HTTP {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Write failed: {e}")
        return False


def read_path_rest(path: str):
    """Read data from a specific path using REST API."""
    if not REQUESTS_AVAILABLE:
        raise ImportError("requests package not installed")

    print(f"Reading path: {path}")
    url = f"{FIREBASE_URL}/{path}.json"
    if FIREBASE_SECRET:
        url += f"?auth={FIREBASE_SECRET}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2, default=str))
            return data
        else:
            print(f"Read failed: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"Read failed: {e}")
        return None


# ============================================
# UTILITY FUNCTIONS
# ============================================

def generate_sample_session_data():
    """Generate sample heating session data for testing."""
    return {
        'start_time': '2024-01-15T22:00:00',
        'end_time': '2024-01-15T23:00:00',
        'duration_hours': 1.0,
        'electricity_price_eur': 0.0523,
        'avg_delta_t': 7.1,
        'pool_temp_before': 28.5,
        'pool_temp_after': 29.1,
        'pool_temp_change': 0.6,
        'estimated_kwh': 3.55,
        'num_readings': 12
    }


def setup_database_structure():
    """Set up initial database structure."""
    print("Setting up database structure...")

    structure = {
        'heating_sessions': {
            '_info': {
                'description': 'Individual pool heating sessions',
                'created': datetime.now().isoformat()
            }
        },
        'daily_summaries': {
            '_info': {
                'description': 'Daily price and heating summaries',
                'created': datetime.now().isoformat()
            }
        },
        'config': {
            'heating_window_start': 21,
            'heating_window_end': 7,
            'num_slots': 2,
            'min_gap_hours': 1
        }
    }

    if FIREBASE_ADMIN_AVAILABLE:
        ref = init_firebase_admin()
        ref.set(structure)
        print("Database structure created (Admin SDK)")
    elif REQUESTS_AVAILABLE:
        url = f"{FIREBASE_URL}/.json"
        if FIREBASE_SECRET:
            url += f"?auth={FIREBASE_SECRET}"
        response = requests.put(url, json=structure)
        if response.status_code == 200:
            print("Database structure created (REST API)")
        else:
            print(f"Failed: {response.status_code}")


# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(description='Test Firebase connection and operations')
    parser.add_argument('--test-connection', action='store_true', help='Test Firebase connection')
    parser.add_argument('--write-test', action='store_true', help='Write test data')
    parser.add_argument('--read-path', type=str, help='Read data from path')
    parser.add_argument('--setup', action='store_true', help='Set up database structure')
    parser.add_argument('--rest', action='store_true', help='Use REST API instead of Admin SDK')
    parser.add_argument('--url', type=str, help='Firebase URL (overrides env var)')
    args = parser.parse_args()

    global FIREBASE_URL
    if args.url:
        FIREBASE_URL = args.url

    use_rest = args.rest or not FIREBASE_ADMIN_AVAILABLE

    if args.test_connection:
        if use_rest:
            test_connection_rest()
        else:
            test_connection_admin()

    elif args.write_test:
        if use_rest:
            write_test_data_rest()
        else:
            write_test_data_admin()

    elif args.read_path:
        if use_rest:
            read_path_rest(args.read_path)
        else:
            read_path_admin(args.read_path)

    elif args.setup:
        setup_database_structure()

    else:
        print("No action specified. Use --help for options.")
        print(f"\nConfiguration:")
        print(f"  Firebase URL: {FIREBASE_URL}")
        print(f"  Service Key:  {SERVICE_ACCOUNT_KEY}")
        print(f"  Admin SDK:    {'Available' if FIREBASE_ADMIN_AVAILABLE else 'Not installed'}")
        print(f"  Requests:     {'Available' if REQUESTS_AVAILABLE else 'Not installed'}")


if __name__ == "__main__":
    main()
