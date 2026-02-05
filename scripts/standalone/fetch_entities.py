#!/usr/bin/env python3
"""
Fetch Home Assistant entities matching a pattern.

Usage:
    ./env/bin/python scripts/standalone/fetch_entities.py pool_heating_cold
    ./env/bin/python scripts/standalone/fetch_entities.py nordpool
    ./env/bin/python scripts/standalone/fetch_entities.py --all

Environment variables:
    HA_URL   - Home Assistant URL (default: http://192.168.50.11:8123)
    HA_TOKEN - Long-lived access token (required)

Examples:
    # Fetch cold weather entities
    ./env/bin/python scripts/standalone/fetch_entities.py pool_heating_cold

    # Fetch with verbose output (includes attributes)
    ./env/bin/python scripts/standalone/fetch_entities.py pool_heating_cold -v

    # List all pool heating entities
    ./env/bin/python scripts/standalone/fetch_entities.py pool_heat
"""

import os
import sys
import argparse
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from standalone.ha_client import HAClient


def main():
    parser = argparse.ArgumentParser(
        description="Fetch HA entities matching a pattern",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "pattern",
        nargs="?",
        default="pool_heating_cold",
        help="Pattern to match in entity_id (default: pool_heating_cold)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Include attributes in output"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="List all entities (use with caution)"
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("HA_URL", "http://192.168.50.11:8123"),
        help="Home Assistant URL"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    args = parser.parse_args()

    # Check for token
    token = os.environ.get("HA_TOKEN", "")
    if not token:
        print("Error: HA_TOKEN environment variable required", file=sys.stderr)
        print("Get a token from: Home Assistant > Profile > Long-Lived Access Tokens", file=sys.stderr)
        sys.exit(1)

    # Create client
    client = HAClient(url=args.url, token=token)

    # Check connection
    print(f"Connecting to {client.url}...", file=sys.stderr)
    if not client.check_connection():
        print("Error: Could not connect to Home Assistant", file=sys.stderr)
        print("Check URL and token are correct", file=sys.stderr)
        sys.exit(1)

    # Fetch all states
    all_states = client.get_states()

    if not all_states:
        print("No entities found or connection error", file=sys.stderr)
        sys.exit(1)

    # Filter by pattern
    if args.all:
        matching = all_states
    else:
        pattern = args.pattern.lower()
        matching = {
            eid: state for eid, state in all_states.items()
            if pattern in eid.lower()
        }

    if not matching:
        print(f"No entities matching '{args.pattern}'", file=sys.stderr)
        sys.exit(0)

    # Output
    if args.json:
        output = {
            eid: {
                "state": state.state,
                "attributes": state.attributes if args.verbose else {}
            }
            for eid, state in sorted(matching.items())
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\nFound {len(matching)} entities matching '{args.pattern}':\n")
        for entity_id in sorted(matching.keys()):
            state = matching[entity_id]
            print(f"{entity_id}: {state.state}")
            if args.verbose and state.attributes:
                for key, value in state.attributes.items():
                    if key not in ("friendly_name", "icon"):
                        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
