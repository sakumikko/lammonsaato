#!/usr/bin/env python3
"""
Check which Thermia Genesis entities are actually available and have real data.
Disables entities that return unavailable/unknown states.

Usage:
    export HA_TOKEN="your_long_lived_access_token"
    python scripts/standalone/check_thermia_availability.py

This script:
1. Gets all Thermia entities that are currently enabled
2. Checks their state - if unavailable/unknown, disable them
3. Outputs a report of available vs unavailable entities
"""

import os
import sys
import json
import asyncio
from collections import defaultdict

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

# Configuration
HA_HOST = os.environ.get("HA_HOST", "192.168.50.11")
HA_PORT = os.environ.get("HA_PORT", "8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
THERMIA_DEVICE_ID = "ac1e4962ee893b58e6d2c1f95e4caeef"

WS_URL = f"ws://{HA_HOST}:{HA_PORT}/api/websocket"

# States that indicate the entity is not available
UNAVAILABLE_STATES = {"unavailable", "unknown", None, ""}


async def ha_websocket():
    """Connect to HA WebSocket and check entity availability."""
    msg_id = 1

    async def send_command(ws, command_type, **kwargs):
        nonlocal msg_id
        message = {"id": msg_id, "type": command_type, **kwargs}
        msg_id += 1
        await ws.send(json.dumps(message))
        response = await ws.recv()
        return json.loads(response)

    print(f"Connecting to Home Assistant WebSocket at {WS_URL}")

    async with websockets.connect(WS_URL) as ws:
        # Wait for auth_required
        auth_req = await ws.recv()
        auth_req = json.loads(auth_req)
        if auth_req.get("type") != "auth_required":
            print(f"Unexpected message: {auth_req}")
            return

        # Authenticate
        await ws.send(json.dumps({
            "type": "auth",
            "access_token": HA_TOKEN
        }))
        auth_result = await ws.recv()
        auth_result = json.loads(auth_result)

        if auth_result.get("type") != "auth_ok":
            print(f"Authentication failed: {auth_result}")
            return

        print("Authenticated successfully!\n")

        # Get entity registry
        print("Fetching entity registry...")
        registry_result = await send_command(ws, "config/entity_registry/list")
        if not registry_result.get("success"):
            print(f"Failed to get entity registry: {registry_result}")
            return

        all_registry = registry_result.get("result", [])

        # Filter Thermia entities that are enabled
        thermia_registry = {
            e["entity_id"]: e
            for e in all_registry
            if e.get("device_id") == THERMIA_DEVICE_ID and not e.get("disabled_by")
        }

        print(f"Found {len(thermia_registry)} enabled Thermia entities")

        # Get all states
        print("Fetching entity states...")
        states_result = await send_command(ws, "get_states")
        if not states_result.get("success"):
            print(f"Failed to get states: {states_result}")
            return

        all_states = {s["entity_id"]: s for s in states_result.get("result", [])}

        # Check availability
        available = []
        unavailable = []

        for entity_id, registry_entry in thermia_registry.items():
            state_obj = all_states.get(entity_id, {})
            state = state_obj.get("state")

            if state in UNAVAILABLE_STATES:
                unavailable.append({
                    "entity_id": entity_id,
                    "name": registry_entry.get("name") or registry_entry.get("original_name"),
                    "state": state,
                })
            else:
                available.append({
                    "entity_id": entity_id,
                    "name": registry_entry.get("name") or registry_entry.get("original_name"),
                    "state": state,
                })

        # Group by domain
        available_by_domain = defaultdict(list)
        unavailable_by_domain = defaultdict(list)

        for e in available:
            domain = e["entity_id"].split(".")[0]
            available_by_domain[domain].append(e)

        for e in unavailable:
            domain = e["entity_id"].split(".")[0]
            unavailable_by_domain[domain].append(e)

        print(f"\n{'='*60}")
        print(f"AVAILABILITY REPORT")
        print(f"{'='*60}")
        print(f"\nAvailable: {len(available)} entities")
        for domain, ents in sorted(available_by_domain.items()):
            print(f"  {domain}: {len(ents)}")

        print(f"\nUnavailable: {len(unavailable)} entities")
        for domain, ents in sorted(unavailable_by_domain.items()):
            print(f"  {domain}: {len(ents)}")

        # Ask whether to disable unavailable entities
        if unavailable:
            print(f"\n{'='*60}")
            print(f"UNAVAILABLE ENTITIES (will be disabled)")
            print(f"{'='*60}")
            for e in sorted(unavailable, key=lambda x: x["entity_id"]):
                print(f"  - {e['entity_id']}: {e['name']} (state: {e['state']})")

            print(f"\nDisabling {len(unavailable)} unavailable entities...")
            disabled_count = 0
            failed_count = 0

            for e in unavailable:
                entity_id = e["entity_id"]
                result = await send_command(
                    ws,
                    "config/entity_registry/update",
                    entity_id=entity_id,
                    disabled_by="user"
                )
                if result.get("success"):
                    disabled_count += 1
                else:
                    failed_count += 1
                    print(f"  ✗ Failed to disable: {entity_id}")

            print(f"\nDisabled {disabled_count} entities, {failed_count} failed")

        # Save report
        report = {
            "device_id": THERMIA_DEVICE_ID,
            "available_count": len(available),
            "unavailable_count": len(unavailable),
            "available_by_domain": {d: len(e) for d, e in available_by_domain.items()},
            "unavailable_by_domain": {d: len(e) for d, e in unavailable_by_domain.items()},
            "available_entities": [
                {"entity_id": e["entity_id"], "name": e["name"], "state": e["state"]}
                for e in sorted(available, key=lambda x: x["entity_id"])
            ],
            "unavailable_entities": [
                {"entity_id": e["entity_id"], "name": e["name"]}
                for e in sorted(unavailable, key=lambda x: x["entity_id"])
            ],
        }

        output_file = "thermia_availability_report.json"
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {output_file}")

        print(f"\n{'='*60}")
        print(f"AVAILABLE ENTITIES (keeping enabled)")
        print(f"{'='*60}")
        for domain in sorted(available_by_domain.keys()):
            print(f"\n### {domain.upper()} ({len(available_by_domain[domain])}) ###")
            for e in sorted(available_by_domain[domain], key=lambda x: x["entity_id"]):
                print(f"  - {e['entity_id']}: {e['state']}")


def main():
    if not HA_TOKEN:
        print("ERROR: HA_TOKEN environment variable not set")
        print("Usage: export HA_TOKEN='your_token' && python scripts/standalone/check_thermia_availability.py")
        sys.exit(1)

    asyncio.run(ha_websocket())


if __name__ == "__main__":
    main()
