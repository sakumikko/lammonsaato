#!/usr/bin/env python3
"""
Integration test for pythermiagenesis library against real Thermia Mega.

This script tests the actual library (from ../pythermiagenesis) against
the real heat pump to verify the fix works in practice.

Prerequisites:
    # Install the cloned library in editable mode
    cd ../pythermiagenesis
    pip install -e .

Usage:
    ./env/bin/python scripts/standalone/test_pythermiagenesis_integration.py

    # Or with verbose output
    ./env/bin/python scripts/standalone/test_pythermiagenesis_integration.py -v
"""

import argparse
import asyncio
import sys
import logging

# Thermia Mega connection settings
THERMIA_HOST = "192.168.50.10"
THERMIA_PORT = 502

# Register names to test
ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT = "coil_enable_fixed_system_supply_set_point"
ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT = "holding_fixed_system_supply_set_point"


async def test_with_library():
    """
    Test the pythermiagenesis library with the fixed supply registers.
    """
    try:
        from pythermiagenesis import ThermiaGenesis
        from pythermiagenesis.const import REGISTERS
    except ImportError as e:
        print(f"ERROR: Cannot import pythermiagenesis: {e}")
        print()
        print("Make sure the library is installed:")
        print("  cd ../pythermiagenesis && pip install -e .")
        return False

    print("=" * 60)
    print("Integration Test: pythermiagenesis with Thermia Mega")
    print("=" * 60)
    print()

    # Verify the registers exist in the library
    print("Checking register definitions...")
    if ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT not in REGISTERS:
        print(f"  ERROR: {ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT} not in REGISTERS")
        return False
    if ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT not in REGISTERS:
        print(f"  ERROR: {ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT} not in REGISTERS")
        return False
    print(f"  {ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT}: {REGISTERS[ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]}")
    print(f"  {ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT}: {REGISTERS[ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT]}")
    print()

    # Create client
    print(f"Connecting to Thermia Mega at {THERMIA_HOST}:{THERMIA_PORT}...")
    try:
        client = ThermiaGenesis(THERMIA_HOST, kind="mega")
    except Exception as e:
        print(f"  ERROR creating client: {e}")
        return False
    print("  Client created")
    print()

    # Test 1: Read just the coil first
    print("Test 1: Read coil only")
    print("-" * 40)
    try:
        registers_to_read = [ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]
        print(f"  Requesting: {registers_to_read}")
        data = await client.async_update(only_registers=registers_to_read)
        print(f"  Response: {data}")
        coil_value = data.get(ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT)
        print(f"  Coil value: {coil_value}")
        print("  SUCCESS")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()

    # Test 2: Read both registers (this is where the bug occurs)
    print("Test 2: Read both coil and holding register")
    print("-" * 40)
    try:
        registers_to_read = [
            ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT,
            ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT,
        ]
        print(f"  Requesting: {registers_to_read}")
        data = await client.async_update(only_registers=registers_to_read)
        print(f"  Response keys: {list(data.keys())}")

        coil_value = data.get(ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT)
        holding_value = data.get(ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT)

        print(f"  Coil value: {coil_value}")
        print(f"  Holding value: {holding_value}")

        if coil_value is False and holding_value is None:
            print("  Note: Holding register skipped because coil is False (expected behavior)")
        elif coil_value is True:
            print(f"  Fixed supply setpoint: {holding_value}°C")

        print("  SUCCESS - No KeyError!")
    except KeyError as e:
        print(f"  ERROR: KeyError raised: {e}")
        print()
        print("  This is the bug! The library tried to access raw_data[key]")
        print("  when the key didn't exist.")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()

    # Test 3: Request in reverse order (holding before coil)
    print("Test 3: Read registers in reverse order (holding first)")
    print("-" * 40)
    try:
        # Note: This might trigger the bug in unfixed versions
        registers_to_read = [
            ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT,
            ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT,
        ]
        print(f"  Requesting: {registers_to_read}")
        data = await client.async_update(only_registers=registers_to_read)
        print(f"  Response keys: {list(data.keys())}")
        print("  SUCCESS - No KeyError!")
    except KeyError as e:
        print(f"  ERROR: KeyError raised: {e}")
        print("  This order exposes the bug more directly!")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()

    print("=" * 60)
    print("All integration tests passed!")
    print("=" * 60)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Integration test for pythermiagenesis library"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    success = asyncio.run(test_with_library())

    if success:
        print()
        print("Integration test PASSED")
        print("The library fix works correctly against real Thermia Mega")
        sys.exit(0)
    else:
        print()
        print("Integration test FAILED")
        print("Check the errors above and verify the fix is applied")
        sys.exit(1)


if __name__ == "__main__":
    main()
