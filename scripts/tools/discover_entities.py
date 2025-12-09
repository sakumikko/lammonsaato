#!/usr/bin/env python3
"""
Discovers all pool heating entities from live Home Assistant.
Exports entity signatures for mock server validation.

Usage:
    python -m scripts.tools.discover_entities --output entities.json
    python -m scripts.tools.discover_entities --verify
    python -m scripts.tools.discover_entities --diff

Environment:
    HA_URL - Home Assistant URL (e.g., http://192.168.50.11:8123)
    HA_TOKEN - Long-lived access token
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import aiohttp
except ImportError:
    print("Error: aiohttp required. Install with: pip install aiohttp")
    sys.exit(1)


@dataclass
class EntitySignature:
    """Signature of an HA entity for validation."""
    entity_id: str
    domain: str  # input_number, sensor, switch, etc.
    state_type: str  # "numeric", "boolean", "string", "datetime"
    deployed: bool = True
    attributes: list[str] = field(default_factory=list)
    unit_of_measurement: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    options: list[str] | None = None
    notes: str | None = None


# Entity prefixes to discover
POOL_HEATING_PREFIXES = [
    "input_boolean.pool_heat",
    "input_boolean.pool_heating",
    "input_number.pool_heat",
    "input_number.pool_heating",
    "input_number.pool_target",
    "input_number.pool_true",
    "input_datetime.pool_heat",
    "input_text.pool_heating",
    "sensor.pool_heat",
    "sensor.pool_heating",
    "sensor.pool_thermal",
    "sensor.pool_return",
    "sensor.pool_next",
    "sensor.current_nordpool",
    "binary_sensor.pool_",
    "binary_sensor.nordpool",
    "switch.altaan_",
    "sensor.condenser_",
    "sensor.outdoor_temperature",
    "sensor.compressor_speed",
    "sensor.nordpool_kwh",
    "number.minimum_allowed_gear",
    "number.maximum_allowed_gear",
    "number.tap_water_",
    "number.hot_gas_",
    "number.heat_curve_",
    "sensor.discharge_pipe",
    "sensor.tap_water_weighted",
    "number.minimum_allowed_gear_in_tap_water",
    "number.maximum_allowed_gear_in_tap_water",
]

DEFAULT_SIGNATURE_FILE = Path(__file__).parent.parent / "mock_server" / "entity_signatures.json"


def infer_state_type(state: str, domain: str) -> str:
    """Infer the state type from domain and value."""
    if domain in ("binary_sensor", "input_boolean", "switch"):
        return "boolean"
    if domain == "input_datetime":
        return "datetime"
    if domain == "input_text":
        return "string"
    if state in ("unavailable", "unknown", ""):
        return "string"
    try:
        float(state)
        return "numeric"
    except (ValueError, TypeError):
        return "string"


async def discover_entities(ha_url: str, token: str) -> list[EntitySignature]:
    """Connect to HA and discover all pool heating entities."""
    signatures = []

    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}

        # Get all states
        async with session.get(f"{ha_url}/api/states", headers=headers) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Failed to get states: {resp.status} {await resp.text()}")
            states = await resp.json()

        for state in states:
            entity_id = state["entity_id"]

            # Filter to pool heating entities
            if not any(entity_id.startswith(prefix) for prefix in POOL_HEATING_PREFIXES):
                continue

            domain = entity_id.split(".")[0]
            attrs = state.get("attributes", {})

            sig = EntitySignature(
                entity_id=entity_id,
                domain=domain,
                state_type=infer_state_type(state["state"], domain),
                deployed=True,
                attributes=sorted([k for k in attrs.keys() if not k.startswith("_")]),
                unit_of_measurement=attrs.get("unit_of_measurement"),
                min_value=attrs.get("min"),
                max_value=attrs.get("max"),
                step=attrs.get("step"),
                options=attrs.get("options"),
            )
            signatures.append(sig)

    # Sort by entity_id for consistent output
    signatures.sort(key=lambda s: s.entity_id)
    return signatures


def load_signatures(path: Path) -> dict:
    """Load existing signatures from file."""
    if not path.exists():
        return {"version": 0, "entities": []}
    with open(path) as f:
        return json.load(f)


def save_signatures(signatures: list[EntitySignature], path: Path, ha_version: str = "unknown"):
    """Save signatures to file."""
    # Load existing to preserve deployed=false entries
    existing = load_signatures(path)
    existing_map = {e["entity_id"]: e for e in existing.get("entities", [])}

    # Merge: keep deployed=false from existing if entity not found in live
    output_entities = []
    live_ids = {s.entity_id for s in signatures}

    for sig in signatures:
        d = asdict(sig)
        # Remove None values for cleaner output
        d = {k: v for k, v in d.items() if v is not None}
        output_entities.append(d)

    # Keep development entities (deployed=false) that weren't in live discovery
    for entity_id, existing_entity in existing_map.items():
        if entity_id not in live_ids and not existing_entity.get("deployed", True):
            output_entities.append(existing_entity)

    # Sort by entity_id
    output_entities.sort(key=lambda e: e["entity_id"])

    output = {
        "version": existing.get("version", 0) + 1,
        "last_verified": datetime.now(timezone.utc).isoformat(),
        "ha_version": ha_version,
        "entity_count": len(output_entities),
        "entities": output_entities,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    return output


def verify_signatures(live_signatures: list[EntitySignature], path: Path) -> tuple[list[str], list[str]]:
    """Compare live signatures against committed file. Returns (errors, warnings)."""
    errors = []
    warnings = []

    existing = load_signatures(path)
    existing_map = {e["entity_id"]: e for e in existing.get("entities", [])}
    live_map = {s.entity_id: s for s in live_signatures}

    # Check for missing entities in live HA
    for entity_id, existing_entity in existing_map.items():
        is_deployed = existing_entity.get("deployed", True)
        if entity_id not in live_map:
            if is_deployed:
                errors.append(f"MISSING: {entity_id} (deployed entity not found in live HA)")
            else:
                warnings.append(f"DEV: {entity_id} (not deployed yet)")

    # Check for new entities in live HA
    for entity_id in live_map:
        if entity_id not in existing_map:
            warnings.append(f"NEW: {entity_id} (exists in live HA but not in signatures)")

    # Check for type mismatches
    for entity_id, live_sig in live_map.items():
        if entity_id in existing_map:
            existing_entity = existing_map[entity_id]
            if existing_entity.get("state_type") != live_sig.state_type:
                errors.append(
                    f"TYPE MISMATCH: {entity_id} "
                    f"(expected {existing_entity.get('state_type')}, got {live_sig.state_type})"
                )

    return errors, warnings


def diff_signatures(live_signatures: list[EntitySignature], path: Path) -> dict:
    """Show what changed since last commit."""
    existing = load_signatures(path)
    existing_map = {e["entity_id"]: e for e in existing.get("entities", [])}
    live_map = {s.entity_id: s for s in live_signatures}

    diff = {
        "added": [],
        "removed": [],
        "changed": [],
    }

    for entity_id in live_map:
        if entity_id not in existing_map:
            diff["added"].append(entity_id)

    for entity_id, existing_entity in existing_map.items():
        if entity_id not in live_map:
            if existing_entity.get("deployed", True):
                diff["removed"].append(entity_id)

    # Check for changes in existing entities
    for entity_id, live_sig in live_map.items():
        if entity_id in existing_map:
            existing_entity = existing_map[entity_id]
            changes = []
            if existing_entity.get("state_type") != live_sig.state_type:
                changes.append(f"state_type: {existing_entity.get('state_type')} -> {live_sig.state_type}")
            if existing_entity.get("min_value") != live_sig.min_value:
                changes.append(f"min: {existing_entity.get('min_value')} -> {live_sig.min_value}")
            if existing_entity.get("max_value") != live_sig.max_value:
                changes.append(f"max: {existing_entity.get('max_value')} -> {live_sig.max_value}")
            if changes:
                diff["changed"].append({"entity_id": entity_id, "changes": changes})

    return diff


async def main():
    parser = argparse.ArgumentParser(description="Discover Home Assistant entities")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_SIGNATURE_FILE,
                        help="Output file path")
    parser.add_argument("--verify", action="store_true",
                        help="Verify live HA matches committed signatures")
    parser.add_argument("--diff", action="store_true",
                        help="Show what changed since last commit")
    parser.add_argument("--ha-url", default=os.environ.get("HA_URL", "http://192.168.50.11:8123"),
                        help="Home Assistant URL")
    parser.add_argument("--ha-token", default=os.environ.get("HA_TOKEN"),
                        help="Home Assistant long-lived access token")
    args = parser.parse_args()

    if not args.ha_token:
        print("Error: HA_TOKEN environment variable or --ha-token required")
        sys.exit(1)

    print(f"Connecting to {args.ha_url}...")

    try:
        signatures = await discover_entities(args.ha_url, args.ha_token)
        print(f"Discovered {len(signatures)} pool heating entities")

        # Print summary by domain
        by_domain: dict[str, list[str]] = {}
        for sig in signatures:
            by_domain.setdefault(sig.domain, []).append(sig.entity_id)

        for domain, ids in sorted(by_domain.items()):
            print(f"  {domain}: {len(ids)}")

        if args.verify:
            print(f"\nVerifying against {args.output}...")
            errors, warnings = verify_signatures(signatures, args.output)

            for w in warnings:
                print(f"  WARNING: {w}")
            for e in errors:
                print(f"  ERROR: {e}")

            if errors:
                print(f"\nVerification FAILED with {len(errors)} errors")
                sys.exit(1)
            else:
                print(f"\nVerification PASSED ({len(warnings)} warnings)")
                sys.exit(0)

        elif args.diff:
            print(f"\nComparing against {args.output}...")
            diff = diff_signatures(signatures, args.output)

            if diff["added"]:
                print(f"\nAdded ({len(diff['added'])}):")
                for e in diff["added"]:
                    print(f"  + {e}")

            if diff["removed"]:
                print(f"\nRemoved ({len(diff['removed'])}):")
                for e in diff["removed"]:
                    print(f"  - {e}")

            if diff["changed"]:
                print(f"\nChanged ({len(diff['changed'])}):")
                for c in diff["changed"]:
                    print(f"  ~ {c['entity_id']}: {', '.join(c['changes'])}")

            if not any(diff.values()):
                print("\nNo changes detected")

        else:
            # Save signatures
            output = save_signatures(signatures, args.output)
            print(f"\nSaved {output['entity_count']} entities to {args.output}")
            print(f"Version: {output['version']}")

    except aiohttp.ClientError as e:
        print(f"Error connecting to Home Assistant: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
