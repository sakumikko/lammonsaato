#!/usr/bin/env python3
"""
Home Assistant Automation & Script Testing

Tests HA automations, scripts, and services externally via REST API.
Allows validating the pool heating workflow without being inside HAOS.

Usage:
    # Test HA connection
    python test_ha_automation.py --check

    # List pool heating entities
    python test_ha_automation.py --list-entities

    # Test schedule calculation (calls pyscript)
    python test_ha_automation.py --test-schedule

    # Test heating control (DRY RUN by default)
    python test_ha_automation.py --test-heating

    # Actually control hardware (CAREFUL!)
    python test_ha_automation.py --test-heating --no-dry-run

    # Monitor heating session
    python test_ha_automation.py --monitor
"""

import asyncio
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ha_client import HAClient, AsyncHAClient, EntityState


# ============================================
# ENTITY DEFINITIONS
# ============================================

POOL_HEATING_ENTITIES = {
    # Input helpers
    "input_boolean.pool_heating_enabled": "Pool Heating Master Switch",
    "input_datetime.pool_heat_block_1_start": "Block 1 Start",
    "input_datetime.pool_heat_block_1_end": "Block 1 End",
    "input_datetime.pool_heat_block_2_start": "Block 2 Start",
    "input_datetime.pool_heat_block_2_end": "Block 2 End",
    "input_datetime.pool_heat_block_3_start": "Block 3 Start",
    "input_datetime.pool_heat_block_3_end": "Block 3 End",
    "input_datetime.pool_heat_block_4_start": "Block 4 Start",
    "input_datetime.pool_heat_block_4_end": "Block 4 End",
    "input_number.pool_heat_block_1_price": "Block 1 Price",
    "input_number.pool_heat_block_2_price": "Block 2 Price",
    "input_number.pool_heat_block_3_price": "Block 3 Price",
    "input_number.pool_heat_block_4_price": "Block 4 Price",
    "input_text.pool_heating_schedule_info": "Schedule Info",
    "input_text.pool_heating_schedule_json": "Schedule JSON",

    # Sensors
    "sensor.nordpool_kwh_fi_eur_3_10_024": "Nordpool Price",
    "sensor.thermia_supply_temperature": "Thermia Supply Temp",
    "sensor.thermia_return_temperature": "Thermia Return Temp",
    "sensor.pool_heat_exchanger_delta_t": "Heat Exchanger Delta-T",

    # Switches - Pool heating control
    "switch.altaan_lammityksen_esto": "Heating Prevention (OFF=allow)",
    "switch.altaan_kiertovesipumppu": "Circulation Pump (ON=heating)",

    # Binary sensors
    "binary_sensor.pool_heating_active": "Heating Active",
    "binary_sensor.nordpool_tomorrow_available": "Tomorrow Prices Available",
}

POOL_HEATING_AUTOMATIONS = [
    "automation.pool_calculate_heating_schedule",
    "automation.pool_start_heating_block_1",
    "automation.pool_start_heating_block_2",
    "automation.pool_start_heating_block_3",
    "automation.pool_start_heating_block_4",
    "automation.pool_stop_heating_block_1",
    "automation.pool_stop_heating_block_2",
    "automation.pool_stop_heating_block_3",
    "automation.pool_stop_heating_block_4",
    "automation.pool_log_temperatures",
]

POOL_HEATING_SCRIPTS = [
    "script.pool_heating_block_start",
    "script.pool_heating_block_stop",
    "script.pool_heating_stop",
    "script.pool_heating_manual_start",
]

PYSCRIPT_SERVICES = [
    "pyscript.calculate_pool_heating_schedule",
    "pyscript.log_heating_start",
    "pyscript.log_heating_end",
    "pyscript.log_pool_temperatures",
]


# ============================================
# TEST FUNCTIONS
# ============================================

def check_connection(client: HAClient, verbose: bool = True) -> bool:
    """Check if HA is reachable."""
    print("Checking Home Assistant connection...")
    print(f"  URL: {client.url}")
    print(f"  Token length: {len(client.token)} chars")

    if client.check_connection(verbose=verbose):
        print(f"✓ Connected to {client.url}")
        return True
    else:
        print(f"✗ Cannot connect to {client.url}")
        print("  Check URL and token are correct")
        return False


def list_pool_entities(client: HAClient) -> Dict[str, EntityState]:
    """List all pool heating related entities and their states."""
    print("\n" + "="*60)
    print("POOL HEATING ENTITIES")
    print("="*60)

    results = {}

    # Get all states at once (more efficient)
    all_states = client.get_states(list(POOL_HEATING_ENTITIES.keys()))

    print("\nInput Helpers:")
    print("-" * 40)
    for entity_id in POOL_HEATING_ENTITIES:
        if entity_id.startswith("input_"):
            state = all_states.get(entity_id)
            if state:
                print(f"  {entity_id}")
                print(f"    State: {state.state}")
                results[entity_id] = state
            else:
                print(f"  {entity_id}: NOT FOUND")

    print("\nSensors:")
    print("-" * 40)
    for entity_id in POOL_HEATING_ENTITIES:
        if entity_id.startswith("sensor.") or entity_id.startswith("binary_sensor."):
            state = all_states.get(entity_id)
            if state:
                unit = state.attributes.get("unit_of_measurement", "")
                print(f"  {entity_id}")
                print(f"    State: {state.state} {unit}")
                results[entity_id] = state
            else:
                print(f"  {entity_id}: NOT FOUND")

    print("\nSwitches:")
    print("-" * 40)
    for entity_id in POOL_HEATING_ENTITIES:
        if entity_id.startswith("switch."):
            state = all_states.get(entity_id)
            if state:
                print(f"  {entity_id}")
                print(f"    State: {state.state}")
                results[entity_id] = state
            else:
                print(f"  {entity_id}: NOT FOUND")

    # Check automations
    print("\nAutomations:")
    print("-" * 40)
    for entity_id in POOL_HEATING_AUTOMATIONS:
        state = client.get_state(entity_id)
        if state:
            print(f"  {entity_id}")
            print(f"    State: {state.state}")
            results[entity_id] = state
        else:
            print(f"  {entity_id}: NOT FOUND")

    # Check scripts
    print("\nScripts:")
    print("-" * 40)
    for entity_id in POOL_HEATING_SCRIPTS:
        state = client.get_state(entity_id)
        if state:
            print(f"  {entity_id}")
            print(f"    State: {state.state}")
            results[entity_id] = state
        else:
            print(f"  {entity_id}: NOT FOUND")

    return results


def test_schedule_calculation(client: HAClient) -> bool:
    """
    Test the schedule calculation by calling pyscript service.
    """
    print("\n" + "="*60)
    print("TESTING SCHEDULE CALCULATION")
    print("="*60)

    # First check if pyscript service exists
    services = client.get_services("pyscript")
    if not services:
        print("✗ Pyscript not available")
        return False

    print("\n1. Getting current schedule state...")
    slot1_before = client.get_state("input_datetime.pool_heat_slot_1")
    slot2_before = client.get_state("input_datetime.pool_heat_slot_2")

    if slot1_before:
        print(f"   Slot 1: {slot1_before.state}")
    if slot2_before:
        print(f"   Slot 2: {slot2_before.state}")

    print("\n2. Calling pyscript.calculate_pool_heating_slots...")
    result = client.call_service("pyscript", "calculate_pool_heating_slots")

    if result.success:
        print("   ✓ Service called successfully")

        # Wait a moment for state to update
        time.sleep(2)

        print("\n3. Checking updated schedule...")
        slot1_after = client.get_state("input_datetime.pool_heat_slot_1")
        slot2_after = client.get_state("input_datetime.pool_heat_slot_2")
        price1 = client.get_state("input_number.pool_heat_slot_1_price")
        price2 = client.get_state("input_number.pool_heat_slot_2_price")
        info = client.get_state("input_text.pool_heating_schedule_info")

        if slot1_after:
            print(f"   Slot 1: {slot1_after.state}")
            if price1:
                print(f"           Price: {price1.state} c/kWh")

        if slot2_after:
            print(f"   Slot 2: {slot2_after.state}")
            if price2:
                print(f"           Price: {price2.state} c/kWh")

        if info:
            print(f"\n   Info: {info.state}")

        # Check if values changed
        if slot1_before and slot1_after and slot1_before.state != slot1_after.state:
            print("\n✓ Schedule was updated!")
            return True
        else:
            print("\n⚠ Schedule unchanged (may already be optimal)")
            return True

    else:
        print(f"   ✗ Service call failed: {result.error}")
        return False


def test_heating_control(client: HAClient, dry_run: bool = True) -> bool:
    """
    Test the heating control flow.

    Pool heating requires:
    - switch.altaan_lammityksen_esto: OFF (disable prevention)
    - switch.altaan_kiertovesipumppu: ON (enable circulation)

    In dry_run mode, only simulates the actions.
    """
    print("\n" + "="*60)
    print(f"TESTING HEATING CONTROL {'(DRY RUN)' if dry_run else '(LIVE!)'}")
    print("="*60)

    PREVENTION_SWITCH = "switch.altaan_lammityksen_esto"
    CIRCULATION_SWITCH = "switch.altaan_kiertovesipumppu"

    if not dry_run:
        print("\n⚠ WARNING: This will control actual hardware!")
        response = input("  Type 'yes' to continue: ")
        if response.lower() != 'yes':
            print("  Aborted.")
            return False

    # Check current state
    print("\n1. Checking current state...")
    prevention_state = client.get_state(PREVENTION_SWITCH)
    circulation_state = client.get_state(CIRCULATION_SWITCH)

    if prevention_state:
        print(f"   Heating prevention: {prevention_state.state} (should be OFF to heat)")
        original_prevention = prevention_state.state
    else:
        print(f"   ✗ {PREVENTION_SWITCH} not found")
        return False

    if circulation_state:
        print(f"   Circulation pump: {circulation_state.state} (should be ON to heat)")
        original_circulation = circulation_state.state
    else:
        print(f"   ✗ {CIRCULATION_SWITCH} not found")
        return False

    # Test START heating (prevention OFF, circulation ON)
    print("\n2. Testing START heating sequence...")
    if dry_run:
        print(f"   [DRY RUN] Would turn OFF {PREVENTION_SWITCH}")
        print(f"   [DRY RUN] Would turn ON {CIRCULATION_SWITCH}")
    else:
        # Turn OFF prevention
        result = client.turn_off(PREVENTION_SWITCH)
        if result.success:
            print(f"   ✓ Prevention OFF command sent")
        else:
            print(f"   ✗ Failed: {result.error}")

        # Turn ON circulation
        result = client.turn_on(CIRCULATION_SWITCH)
        if result.success:
            print(f"   ✓ Circulation ON command sent")
        else:
            print(f"   ✗ Failed: {result.error}")

        time.sleep(2)
        new_prevention = client.get_state(PREVENTION_SWITCH)
        new_circulation = client.get_state(CIRCULATION_SWITCH)
        print(f"   Prevention: {new_prevention.state if new_prevention else 'unknown'}")
        print(f"   Circulation: {new_circulation.state if new_circulation else 'unknown'}")

    # Test STOP heating (prevention ON, circulation OFF)
    print("\n3. Testing STOP heating sequence...")
    if dry_run:
        print(f"   [DRY RUN] Would turn ON {PREVENTION_SWITCH}")
        print(f"   [DRY RUN] Would turn OFF {CIRCULATION_SWITCH}")
    else:
        # Turn ON prevention
        result = client.turn_on(PREVENTION_SWITCH)
        if result.success:
            print(f"   ✓ Prevention ON command sent")
        else:
            print(f"   ✗ Failed: {result.error}")

        # Turn OFF circulation
        result = client.turn_off(CIRCULATION_SWITCH)
        if result.success:
            print(f"   ✓ Circulation OFF command sent")
        else:
            print(f"   ✗ Failed: {result.error}")

        time.sleep(2)
        new_prevention = client.get_state(PREVENTION_SWITCH)
        new_circulation = client.get_state(CIRCULATION_SWITCH)
        print(f"   Prevention: {new_prevention.state if new_prevention else 'unknown'}")
        print(f"   Circulation: {new_circulation.state if new_circulation else 'unknown'}")

    # Restore original state if not dry run
    if not dry_run:
        print("\n4. Restoring original states...")
        if original_prevention == "off":
            client.turn_off(PREVENTION_SWITCH)
        else:
            client.turn_on(PREVENTION_SWITCH)

        if original_circulation == "on":
            client.turn_on(CIRCULATION_SWITCH)
        else:
            client.turn_off(CIRCULATION_SWITCH)

        print("   ✓ States restored")

    print("\n✓ Heating control test complete")
    return True


def test_automation_trigger(client: HAClient, automation_id: str, dry_run: bool = True) -> bool:
    """
    Test triggering an automation.
    """
    print(f"\nTriggering automation: {automation_id}")

    if dry_run:
        print(f"  [DRY RUN] Would trigger {automation_id}")
        return True

    result = client.trigger_automation(automation_id)
    if result.success:
        print(f"  ✓ Automation triggered")
        return True
    else:
        print(f"  ✗ Failed: {result.error}")
        return False


def test_script_run(client: HAClient, script_id: str, dry_run: bool = True) -> bool:
    """
    Test running a script.
    """
    print(f"\nRunning script: {script_id}")

    if dry_run:
        print(f"  [DRY RUN] Would run {script_id}")
        return True

    result = client.run_script(script_id)
    if result.success:
        print(f"  ✓ Script started")
        return True
    else:
        print(f"  ✗ Failed: {result.error}")
        return False


async def monitor_heating_session(client: AsyncHAClient, duration_minutes: int = 60):
    """
    Monitor a heating session in real-time via WebSocket.
    """
    print("\n" + "="*60)
    print(f"MONITORING HEATING SESSION ({duration_minutes} minutes)")
    print("="*60)
    print("Press Ctrl+C to stop\n")

    entities_to_watch = [
        "switch.shelly_pool_heating",
        "sensor.thermia_supply_temperature",
        "sensor.thermia_return_temperature",
        "sensor.pool_heat_exchanger_delta_t",
        "binary_sensor.pool_heating_active",
    ]

    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration_minutes)

    try:
        async with client:
            async for event in client.subscribe_events("state_changed"):
                if event.entity_id in entities_to_watch:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    old_val = event.old_state.state if event.old_state else "?"
                    new_val = event.new_state.state if event.new_state else "?"

                    print(f"[{timestamp}] {event.entity_id}: {old_val} → {new_val}")

                    # Log delta-T specifically
                    if event.entity_id == "sensor.pool_heat_exchanger_delta_t":
                        print(f"           Delta-T: {new_val}°C")

                if datetime.now() > end_time:
                    print(f"\nMonitoring duration reached ({duration_minutes} min)")
                    break

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        print(f"\nError: {e}")


def test_full_workflow(client: HAClient, dry_run: bool = True) -> bool:
    """
    Test the complete pool heating workflow.
    """
    print("\n" + "="*60)
    print(f"FULL WORKFLOW TEST {'(DRY RUN)' if dry_run else '(LIVE!)'}")
    print("="*60)

    results = {
        "entities_found": False,
        "schedule_calculation": False,
        "heating_control": False,
    }

    # Step 1: Check entities
    print("\n[Step 1/3] Checking entities...")
    entities = list_pool_entities(client)
    results["entities_found"] = len(entities) > 5

    # Step 2: Test schedule calculation
    print("\n[Step 2/3] Testing schedule calculation...")
    results["schedule_calculation"] = test_schedule_calculation(client)

    # Step 3: Test heating control
    print("\n[Step 3/3] Testing heating control...")
    results["heating_control"] = test_heating_control(client, dry_run)

    # Summary
    print("\n" + "="*60)
    print("WORKFLOW TEST SUMMARY")
    print("="*60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✓" if passed else "✗"
        if not passed:
            all_passed = False
        print(f"  {status} {test_name}")

    return all_passed


# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(description="Test HA automations and scripts")
    parser.add_argument("--url", help="Home Assistant URL")
    parser.add_argument("--token", help="Long-lived access token")

    # Test selection
    parser.add_argument("--check", action="store_true", help="Check HA connection")
    parser.add_argument("--list-entities", action="store_true", help="List pool heating entities")
    parser.add_argument("--test-schedule", action="store_true", help="Test schedule calculation")
    parser.add_argument("--test-heating", action="store_true", help="Test heating control")
    parser.add_argument("--test-workflow", action="store_true", help="Test full workflow")
    parser.add_argument("--monitor", action="store_true", help="Monitor heating session")

    # Options
    parser.add_argument("--no-dry-run", action="store_true", help="Actually control hardware")
    parser.add_argument("--monitor-duration", type=int, default=60, help="Monitor duration (minutes)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Create client
    url = args.url or os.environ.get("HA_URL")
    token = args.token or os.environ.get("HA_TOKEN")

    if not url or not token:
        print("Error: HA_URL and HA_TOKEN required")
        print("Set via environment variables or --url/--token flags")
        sys.exit(1)

    dry_run = not args.no_dry_run

    # Run requested test
    if args.monitor:
        # Async monitoring
        async_client = AsyncHAClient(url, token)
        asyncio.run(monitor_heating_session(async_client, args.monitor_duration))
    else:
        # Sync operations
        client = HAClient(url, token)

        if not check_connection(client):
            sys.exit(1)

        if args.list_entities:
            list_pool_entities(client)

        elif args.test_schedule:
            success = test_schedule_calculation(client)
            sys.exit(0 if success else 1)

        elif args.test_heating:
            success = test_heating_control(client, dry_run)
            sys.exit(0 if success else 1)

        elif args.test_workflow:
            success = test_full_workflow(client, dry_run)
            sys.exit(0 if success else 1)

        elif args.check:
            print("✓ Connection OK")

        else:
            # Default: list entities
            list_pool_entities(client)


if __name__ == "__main__":
    main()
