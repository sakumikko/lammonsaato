#!/usr/bin/env python3
"""
Test script for Firebase connection and data operations.

Usage:
    python scripts/standalone/test_firebase.py
    python scripts/standalone/test_firebase.py --test-connection
    python scripts/standalone/test_firebase.py --write-test
    python scripts/standalone/test_firebase.py --read-path heating_sessions

Requirements:
    pip install cryptography requests python-dotenv
    Place your service account key at: ./secrets/firebase-key.json
"""

import argparse
import json
import os
import sys
import time
import base64
from datetime import datetime
from pathlib import Path

# Add project root for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
except ImportError:
    pass

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("requests not installed - pip install requests")

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("cryptography not installed - pip install cryptography")


# ============================================
# CONFIGURATION
# ============================================

FIREBASE_PROJECT_ID = "lammonsaato-96768"

# Path to service account key
SERVICE_ACCOUNT_KEY = os.environ.get(
    'FIREBASE_KEY_PATH',
    str(PROJECT_ROOT / 'secrets' / 'firebase-key.json')
)

# Firebase Realtime Database URL
FIREBASE_URL = os.environ.get(
    'FIREBASE_URL',
    'https://lammonsaato-96768-default-rtdb.europe-west1.firebasedatabase.app'
)

# Token cache
_token_cache = {'token': None, 'expires_at': 0}


# ============================================
# JWT / OAuth2 Authentication
# ============================================

def _base64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')


def _load_service_account() -> dict:
    """Load service account credentials from file."""
    try:
        with open(SERVICE_ACCOUNT_KEY, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Service account key not found: {SERVICE_ACCOUNT_KEY}")
        return None
    except json.JSONDecodeError as e:
        print(f"Invalid service account JSON: {e}")
        return None


def _create_jwt(service_account: dict) -> str:
    """Create a JWT for Google OAuth2 service account authentication."""
    if not CRYPTO_AVAILABLE:
        print("cryptography module required for JWT signing")
        return None

    now = int(time.time())

    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": service_account["client_email"],
        "sub": service_account["client_email"],
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
        "scope": "https://www.googleapis.com/auth/firebase.database https://www.googleapis.com/auth/userinfo.email"
    }

    header_b64 = _base64url_encode(json.dumps(header).encode('utf-8'))
    claims_b64 = _base64url_encode(json.dumps(claims).encode('utf-8'))
    sign_input = f"{header_b64}.{claims_b64}"

    private_key = serialization.load_pem_private_key(
        service_account["private_key"].encode('utf-8'),
        password=None,
        backend=default_backend()
    )

    signature = private_key.sign(
        sign_input.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    signature_b64 = _base64url_encode(signature)
    return f"{sign_input}.{signature_b64}"


def get_access_token() -> str:
    """Get OAuth2 access token using service account credentials."""
    global _token_cache

    # Return cached token if still valid (with 5 min buffer)
    if _token_cache['token'] and time.time() < _token_cache['expires_at'] - 300:
        return _token_cache['token']

    service_account = _load_service_account()
    if not service_account:
        return None

    jwt_token = _create_jwt(service_account)
    if not jwt_token:
        return None

    # Exchange JWT for access token
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt_token
        }
    )

    if response.status_code == 200:
        data = response.json()
        _token_cache['token'] = data['access_token']
        _token_cache['expires_at'] = time.time() + data.get('expires_in', 3600)
        return _token_cache['token']
    else:
        print(f"Token exchange failed: {response.status_code} - {response.text}")
        return None


# ============================================
# FIREBASE REST API (with OAuth2 auth)
# ============================================

def test_connection():
    """Test Firebase connection using REST API with OAuth2."""
    if not REQUESTS_AVAILABLE:
        print("requests package not installed")
        return False

    print("Getting access token...")
    access_token = get_access_token()
    if not access_token:
        print("Failed to get access token")
        return False
    print(f"  ✓ Got token: {access_token[:30]}...")

    print("\nTesting Firebase connection...")
    url = f"{FIREBASE_URL}/.json"

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Connected successfully!")
            if data:
                print(f"  Root keys: {list(data.keys())}")
            else:
                print("  (empty database)")
            return True
        else:
            print(f"  ✗ Connection failed: HTTP {response.status_code}")
            print(f"  {response.text}")
            return False
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return False


def write_test_data():
    """Write test data using REST API with OAuth2."""
    if not REQUESTS_AVAILABLE:
        print("requests package not installed")
        return False

    access_token = get_access_token()
    if not access_token:
        return False

    print("Writing test data...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    test_data = {
        'test': True,
        'timestamp': datetime.now().isoformat(),
        'source': 'test_firebase.py',
        'message': 'Connection test from development machine'
    }

    url = f"{FIREBASE_URL}/connection_tests/{timestamp}.json"

    try:
        response = requests.put(
            url,
            json=test_data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        if response.status_code == 200:
            print(f"  ✓ Test data written to: connection_tests/{timestamp}")
            return True
        else:
            print(f"  ✗ Write failed: HTTP {response.status_code}")
            print(f"  {response.text}")
            return False
    except Exception as e:
        print(f"  ✗ Write failed: {e}")
        return False


def read_path(path: str):
    """Read data from a specific path using REST API with OAuth2."""
    if not REQUESTS_AVAILABLE:
        print("requests package not installed")
        return None

    access_token = get_access_token()
    if not access_token:
        return None

    print(f"Reading path: {path}")
    url = f"{FIREBASE_URL}/{path}.json"

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2, default=str))
            return data
        else:
            print(f"  ✗ Read failed: HTTP {response.status_code}")
            print(f"  {response.text}")
            return None
    except Exception as e:
        print(f"  ✗ Read failed: {e}")
        return None


# ============================================
# UTILITY FUNCTIONS
# ============================================

def generate_sample_session_data():
    """Generate sample heating session data for testing."""
    return {
        'start_time': datetime.now().isoformat(),
        'end_time': datetime.now().isoformat(),
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
    access_token = get_access_token()
    if not access_token:
        return False

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
        'schedules': {
            '_info': {
                'description': 'Heating schedules',
                'created': datetime.now().isoformat()
            }
        },
        'connection_tests': {
            '_info': {
                'description': 'Connection test records',
                'created': datetime.now().isoformat()
            }
        }
    }

    url = f"{FIREBASE_URL}/.json"
    response = requests.put(
        url,
        json=structure,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    )
    if response.status_code == 200:
        print("  ✓ Database structure created")
        return True
    else:
        print(f"  ✗ Failed: {response.status_code} - {response.text}")
        return False


# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(description='Test Firebase connection and operations')
    parser.add_argument('--test-connection', '-t', action='store_true', help='Test Firebase connection')
    parser.add_argument('--write-test', '-w', action='store_true', help='Write test data')
    parser.add_argument('--read-path', '-r', type=str, help='Read data from path')
    parser.add_argument('--setup', action='store_true', help='Set up database structure')
    parser.add_argument('--url', type=str, help='Firebase URL (overrides env var)')
    args = parser.parse_args()

    global FIREBASE_URL
    if args.url:
        FIREBASE_URL = args.url

    print("Firebase Connection Test")
    print("=" * 50)
    print(f"Project ID:  {FIREBASE_PROJECT_ID}")
    print(f"Database:    {FIREBASE_URL}")
    print(f"Service Key: {SERVICE_ACCOUNT_KEY}")
    print(f"Crypto:      {'Available' if CRYPTO_AVAILABLE else 'Not installed'}")
    print(f"Requests:    {'Available' if REQUESTS_AVAILABLE else 'Not installed'}")
    print("=" * 50)
    print()

    if not CRYPTO_AVAILABLE or not REQUESTS_AVAILABLE:
        print("Missing dependencies. Install with:")
        print("  pip install cryptography requests")
        return 1

    if args.test_connection:
        return 0 if test_connection() else 1

    elif args.write_test:
        return 0 if write_test_data() else 1

    elif args.read_path:
        return 0 if read_path(args.read_path) else 1

    elif args.setup:
        return 0 if setup_database_structure() else 1

    else:
        # Default: run full test
        print("[1/2] Testing connection...")
        if not test_connection():
            return 1

        print("\n[2/2] Writing test data...")
        if not write_test_data():
            return 1

        print("\n" + "=" * 50)
        print("All tests passed! Firebase connection is working.")
        print()
        print("To test from Home Assistant after deployment:")
        print("  Developer Tools > Services > pyscript.firebase_test_connection")
        return 0


if __name__ == "__main__":
    sys.exit(main())
