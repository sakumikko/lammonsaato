#!/usr/bin/env python3
"""
Bulk enable all Thermia Genesis entities in Home Assistant.

Usage:
    export HA_TOKEN="your_long_lived_access_token"
    python scripts/standalone/enable_thermia_entities.py

This script:
1. Queries all entities linked to the Thermia device via WebSocket
2. Enables any that are disabled
3. Outputs a list of all entities for analysis
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


async def ha_websocket():
    """Connect to HA WebSocket and perform operations."""
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
        result = await send_command(ws, "config/entity_registry/list")

        if not result.get("success"):
            print(f"Failed to get entity registry: {result}")
            return

        all_entities = result.get("result", [])
        print(f"Total entities in registry: {len(all_entities)}")

        # Filter by device_id
        thermia_entities = [
            e for e in all_entities
            if e.get("device_id") == THERMIA_DEVICE_ID
        ]

        if not thermia_entities:
            print(f"\nNo entities found for device {THERMIA_DEVICE_ID}")
            # Try to find device
            device_result = await send_command(ws, "config/device_registry/list")
            if device_result.get("success"):
                devices = device_result.get("result", [])
                thermia_device = next(
                    (d for d in devices if d.get("id") == THERMIA_DEVICE_ID),
                    None
                )
                if thermia_device:
                    print(f"Device found: {thermia_device.get('name', 'Unknown')}")
                    print("Check if the device ID is correct.")
                else:
                    print("Device not found in registry.")
                    print("\nAvailable devices:")
                    for d in devices[:10]:
                        print(f"  - {d.get('id')}: {d.get('name', 'Unknown')}")
            return

        # Group by domain
        by_domain = defaultdict(list)
        for entity in thermia_entities:
            domain = entity["entity_id"].split(".")[0]
            by_domain[domain].append(entity)

        print(f"\nFound {len(thermia_entities)} Thermia entities:")
        for domain, ents in sorted(by_domain.items()):
            print(f"  {domain}: {len(ents)}")

        # Count disabled entities
        disabled = [e for e in thermia_entities if e.get("disabled_by")]
        enabled = [e for e in thermia_entities if not e.get("disabled_by")]

        print(f"\nCurrently enabled: {len(enabled)}")
        print(f"Currently disabled: {len(disabled)}")

        if not disabled:
            print("\nAll entities are already enabled!")
        else:
            print(f"\nEnabling {len(disabled)} disabled entities...")
            success_count = 0
            fail_count = 0

            for entity in disabled:
                entity_id = entity["entity_id"]
                result = await send_command(
                    ws,
                    "config/entity_registry/update",
                    entity_id=entity_id,
                    disabled_by=None
                )
                if result.get("success"):
                    success_count += 1
                    print(f"  ✓ Enabled: {entity_id}")
                else:
                    fail_count += 1
                    print(f"  ✗ Failed: {entity_id} - {result.get('error', {}).get('message', 'Unknown error')}")

            print(f"\nEnabled {success_count} entities, {fail_count} failed")

        # Output full list for analysis
        print("\n" + "=" * 60)
        print("FULL ENTITY LIST (for later analysis)")
        print("=" * 60)

        for domain in sorted(by_domain.keys()):
            print(f"\n### {domain.upper()} ###")
            for entity in sorted(by_domain[domain], key=lambda e: e["entity_id"]):
                entity_id = entity["entity_id"]
                name = entity.get("name") or entity.get("original_name") or "unnamed"
                disabled_by = entity.get("disabled_by")
                status = " (was disabled)" if disabled_by else ""
                print(f"  - {entity_id}: {name}{status}")

        # Save to file for reference
        output_file = "thermia_entities.json"
        with open(output_file, "w") as f:
            json.dump({
                "device_id": THERMIA_DEVICE_ID,
                "total_count": len(thermia_entities),
                "by_domain": {d: len(e) for d, e in by_domain.items()},
                "entities": [
                    {
                        "entity_id": e["entity_id"],
                        "name": e.get("name") or e.get("original_name"),
                        "was_disabled": bool(e.get("disabled_by")),
                        "domain": e["entity_id"].split(".")[0],
                    }
                    for e in thermia_entities
                ]
            }, f, indent=2)
        print(f"\nEntity list saved to: {output_file}")
        print("\nREMEMBER: Restart Home Assistant for recorder changes to take effect!")


def main():
    if not HA_TOKEN:
        print("ERROR: HA_TOKEN environment variable not set")
        print("Usage: export HA_TOKEN='your_token' && python scripts/standalone/enable_thermia_entities.py")
        sys.exit(1)

    asyncio.run(ha_websocket())


if __name__ == "__main__":
    main()
