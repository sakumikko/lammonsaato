#!/usr/bin/env python3
"""
Sync Thermia Genesis entity enabled/disabled state with config file.

Reads homeassistant/packages/thermia_required_entities.yaml and:
- Enables all entities listed in entity_groups
- Disables all other Thermia entities (except known unavailable)

Requires HA_TOKEN environment variable.

Usage:
    # Dry run (show what would change)
    HA_TOKEN="your_token" python scripts/standalone/sync_thermia_entities.py --dry-run

    # Apply changes
    HA_TOKEN="your_token" python scripts/standalone/sync_thermia_entities.py

    # Enable only specific groups
    HA_TOKEN="your_token" python scripts/standalone/sync_thermia_entities.py --groups core,tap_water

    # List available groups
    HA_TOKEN="your_token" python scripts/standalone/sync_thermia_entities.py --list-groups
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import yaml

try:
    import websockets
except ImportError:
    print("ERROR: websockets library required. Install with: pip install websockets")
    sys.exit(1)


# Configuration
HA_HOST = "192.168.50.11"
HA_PORT = 8123
HA_WS_URL = f"ws://{HA_HOST}:{HA_PORT}/api/websocket"
CONFIG_PATH = Path(__file__).parent.parent.parent / "homeassistant/packages/thermia_required_entities.yaml"


def load_config() -> dict:
    """Load the entity configuration YAML file."""
    if not CONFIG_PATH.exists():
        print(f"ERROR: Config file not found: {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_required_entities(config: dict, groups: list[str] | None = None) -> set[str]:
    """Get all entity IDs that should be enabled based on config."""
    entities = set()

    for group_name, group_data in config.get("entity_groups", {}).items():
        # If specific groups requested, filter
        if groups and group_name not in groups:
            continue

        for entity_id in group_data.get("entities", []):
            entities.add(entity_id)

    return entities


def get_unavailable_entities(config: dict) -> set[str]:
    """Get entities known to be unavailable (don't try to enable)."""
    return set(config.get("unavailable_registers", []))


async def get_thermia_entities(ws, device_id: str) -> dict[str, dict]:
    """Get all entities from Thermia device via entity registry."""
    # Request entity registry
    await ws.send(json.dumps({
        "id": 10,
        "type": "config/entity_registry/list"
    }))

    response = await ws.recv()
    data = json.loads(response)

    if not data.get("success"):
        print(f"ERROR: Failed to get entity registry: {data}")
        return {}

    # Filter for Thermia device
    thermia_entities = {}
    for entity in data.get("result", []):
        if entity.get("device_id") == device_id:
            entity_id = entity.get("entity_id")
            thermia_entities[entity_id] = {
                "disabled_by": entity.get("disabled_by"),
                "platform": entity.get("platform"),
            }

    return thermia_entities


async def set_entity_disabled(ws, entity_id: str, disabled: bool, msg_id: int) -> bool:
    """Enable or disable an entity via WebSocket."""
    await ws.send(json.dumps({
        "id": msg_id,
        "type": "config/entity_registry/update",
        "entity_id": entity_id,
        "disabled_by": "user" if disabled else None
    }))

    response = await ws.recv()
    data = json.loads(response)
    return data.get("success", False)


async def sync_entities(
    dry_run: bool = False,
    groups: list[str] | None = None,
    list_groups_only: bool = False
):
    """Main sync function."""
    token = os.environ.get("HA_TOKEN", "")
    if not token:
        print("ERROR: HA_TOKEN environment variable required")
        sys.exit(1)

    # Load config
    config = load_config()

    # List groups only
    if list_groups_only:
        print("Available entity groups:")
        print("-" * 50)
        for group_name, group_data in config.get("entity_groups", {}).items():
            desc = group_data.get("description", "")
            count = len(group_data.get("entities", []))
            print(f"  {group_name}: {count} entities")
            print(f"    {desc}")
        return

    device_id = config.get("thermia_device_id")
    required = get_required_entities(config, groups)
    unavailable = get_unavailable_entities(config)

    print(f"Config: {len(required)} entities should be enabled")
    if groups:
        print(f"Groups: {', '.join(groups)}")

    # Connect to HA
    print(f"\nConnecting to {HA_WS_URL}...")

    async with websockets.connect(HA_WS_URL, open_timeout=30) as ws:
        # Authenticate
        auth_req = await ws.recv()
        auth_data = json.loads(auth_req)

        if auth_data.get("type") != "auth_required":
            print(f"ERROR: Unexpected auth response: {auth_data}")
            return

        await ws.send(json.dumps({
            "type": "auth",
            "access_token": token
        }))

        auth_result = await ws.recv()
        auth_result_data = json.loads(auth_result)

        if auth_result_data.get("type") != "auth_ok":
            print(f"ERROR: Authentication failed: {auth_result_data}")
            return

        print("Authenticated successfully")

        # Get Thermia entities
        thermia_entities = await get_thermia_entities(ws, device_id)
        print(f"Found {len(thermia_entities)} Thermia entities in registry")

        # Categorize entities
        currently_enabled = set()
        currently_disabled = set()

        for entity_id, info in thermia_entities.items():
            if info["disabled_by"] is None:
                currently_enabled.add(entity_id)
            else:
                currently_disabled.add(entity_id)

        print(f"  Currently enabled: {len(currently_enabled)}")
        print(f"  Currently disabled: {len(currently_disabled)}")

        # Calculate changes needed (only for entities that exist in registry)
        registry_entities = set(thermia_entities.keys())
        to_enable = (required & registry_entities) - currently_enabled - unavailable
        to_disable = currently_enabled - required - unavailable

        # Also find entities in config but missing from registry (for reporting)
        missing_from_registry = required - set(thermia_entities.keys())
        if missing_from_registry:
            print(f"\nWARNING: {len(missing_from_registry)} entities in config but not found in registry:")
            for entity_id in sorted(missing_from_registry):
                print(f"  - {entity_id}")

        print(f"\nChanges needed:")
        print(f"  To enable: {len(to_enable)}")
        print(f"  To disable: {len(to_disable)}")

        if dry_run:
            print("\n[DRY RUN] Would enable:")
            for entity_id in sorted(to_enable):
                print(f"  + {entity_id}")
            print("\n[DRY RUN] Would disable:")
            for entity_id in sorted(to_disable):
                print(f"  - {entity_id}")
            print("\n[DRY RUN] No changes applied.")
            return

        # Apply changes
        msg_id = 20
        enabled_count = 0
        disabled_count = 0

        if to_enable:
            print("\nEnabling entities...")
            for entity_id in sorted(to_enable):
                success = await set_entity_disabled(ws, entity_id, disabled=False, msg_id=msg_id)
                msg_id += 1
                if success:
                    enabled_count += 1
                    print(f"  + {entity_id}")
                else:
                    print(f"  ! FAILED: {entity_id}")

        if to_disable:
            print("\nDisabling entities...")
            for entity_id in sorted(to_disable):
                success = await set_entity_disabled(ws, entity_id, disabled=True, msg_id=msg_id)
                msg_id += 1
                if success:
                    disabled_count += 1
                    print(f"  - {entity_id}")
                else:
                    print(f"  ! FAILED: {entity_id}")

        print(f"\nSummary:")
        print(f"  Enabled: {enabled_count}")
        print(f"  Disabled: {disabled_count}")
        print("\nNote: Entities may take a few seconds to become available after enabling.")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync Thermia entity enabled state with config file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without applying"
    )
    parser.add_argument(
        "--groups",
        type=str,
        help="Comma-separated list of groups to enable (default: all)"
    )
    parser.add_argument(
        "--list-groups",
        action="store_true",
        help="List available entity groups and exit"
    )

    args = parser.parse_args()

    groups = None
    if args.groups:
        groups = [g.strip() for g in args.groups.split(",")]

    asyncio.run(sync_entities(
        dry_run=args.dry_run,
        groups=groups,
        list_groups_only=args.list_groups
    ))


if __name__ == "__main__":
    main()
