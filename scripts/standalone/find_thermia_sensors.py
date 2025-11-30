#!/usr/bin/env python3
"""Find all Thermia-related sensors in Home Assistant."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ha_client import HAClient

client = HAClient()

if not client.check_connection():
    print("Cannot connect to HA")
    sys.exit(1)

print("Searching for Thermia sensors...\n")

states = client.get_states()

# Search for thermia, pannuhuone, condenser, temperature sensors
keywords = ['thermia', 'pannuhuone', 'condenser', 'heat_pump', 'heatpump', 'input_']

found = []
for entity_id, state in states.items():
    entity_lower = entity_id.lower()
    if any(kw in entity_lower for kw in keywords):
        found.append((entity_id, state))

if found:
    print(f"Found {len(found)} matching sensors:\n")
    for entity_id, state in sorted(found):
        print(f"{entity_id}")
        print(f"  State: {state.state}")
        if state.attributes.get('unit_of_measurement'):
            print(f"  Unit: {state.attributes['unit_of_measurement']}")
        print()
else:
    print("No Thermia sensors found!")
    print("\nSearching for any temperature sensors...")
    for entity_id, state in sorted(states.items()):
        if 'temperature' in entity_id.lower() and entity_id.startswith('sensor.'):
            print(f"  {entity_id}: {state.state}")
