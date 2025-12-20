#!/usr/bin/env python3
"""
Test script for Fixed System Supply Setpoint registers on Thermia Mega.

This script directly reads/writes Modbus registers to test if the fixed supply
setpoint feature is available on this heat pump model.

Registers (from pythermiagenesis.const):
- coil_enable_fixed_system_supply_set_point: address=41, type=coil (bit 0/1)
- holding_fixed_system_supply_set_point: address=116, type=holding, scale=100

Usage:
    # Read current values (safe)
    python scripts/standalone/test_fixed_supply.py --read

    # Write enable switch (CAUTION: modifies heat pump settings!)
    python scripts/standalone/test_fixed_supply.py --enable
    python scripts/standalone/test_fixed_supply.py --disable

    # Write setpoint value (CAUTION: modifies heat pump settings!)
    python scripts/standalone/test_fixed_supply.py --setpoint 30

    # Full test: set 30°C and enable (CAUTION!)
    python scripts/standalone/test_fixed_supply.py --setpoint 30 --enable
"""

import argparse
import sys
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# Thermia Mega Modbus settings
THERMIA_HOST = "192.168.50.10"
THERMIA_PORT = 502
DEVICE_ID = 1

# Register definitions (from pythermiagenesis.const)
COIL_ENABLE_FIXED_SUPPLY = 41  # bit: 0=disabled, 1=enabled
HOLDING_FIXED_SUPPLY_SETPOINT = 116  # int, scale=100 (30°C = 3000)
SCALE_FACTOR = 100


def read_registers(client: ModbusTcpClient) -> dict:
    """Read current values of fixed supply registers."""
    results = {}

    # Read coil (enable switch)
    print(f"Reading coil {COIL_ENABLE_FIXED_SUPPLY} (enable switch)...")
    try:
        response = client.read_coils(COIL_ENABLE_FIXED_SUPPLY, count=1, device_id=DEVICE_ID)
        if response.isError():
            print(f"  ERROR: {response}")
            results["enable"] = None
        else:
            value = response.bits[0]
            results["enable"] = value
            print(f"  Value: {value} ({'ENABLED' if value else 'DISABLED'})")
    except ModbusException as e:
        print(f"  EXCEPTION: {e}")
        results["enable"] = None

    # Read holding register (setpoint)
    print(f"\nReading holding register {HOLDING_FIXED_SUPPLY_SETPOINT} (setpoint)...")
    try:
        response = client.read_holding_registers(HOLDING_FIXED_SUPPLY_SETPOINT, count=1, device_id=DEVICE_ID)
        if response.isError():
            print(f"  ERROR: {response}")
            results["setpoint_raw"] = None
            results["setpoint_celsius"] = None
        else:
            raw_value = response.registers[0]
            # Handle signed int16
            if raw_value > 32767:
                raw_value = raw_value - 65536
            celsius = raw_value / SCALE_FACTOR
            results["setpoint_raw"] = raw_value
            results["setpoint_celsius"] = celsius
            print(f"  Raw value: {raw_value}")
            print(f"  Temperature: {celsius}°C")
    except ModbusException as e:
        print(f"  EXCEPTION: {e}")
        results["setpoint_raw"] = None
        results["setpoint_celsius"] = None

    return results


def write_enable(client: ModbusTcpClient, enable: bool) -> bool:
    """Write to the enable coil."""
    print(f"\nWriting coil {COIL_ENABLE_FIXED_SUPPLY} = {enable}...")
    try:
        response = client.write_coil(COIL_ENABLE_FIXED_SUPPLY, enable, device_id=DEVICE_ID)
        if response.isError():
            print(f"  ERROR: {response}")
            return False
        else:
            print(f"  SUCCESS: Fixed supply {'ENABLED' if enable else 'DISABLED'}")
            return True
    except ModbusException as e:
        print(f"  EXCEPTION: {e}")
        return False


def write_setpoint(client: ModbusTcpClient, celsius: float) -> bool:
    """Write to the setpoint holding register."""
    raw_value = int(celsius * SCALE_FACTOR)
    print(f"\nWriting holding register {HOLDING_FIXED_SUPPLY_SETPOINT} = {raw_value} ({celsius}°C)...")
    try:
        response = client.write_register(HOLDING_FIXED_SUPPLY_SETPOINT, raw_value, device_id=DEVICE_ID)
        if response.isError():
            print(f"  ERROR: {response}")
            return False
        else:
            print(f"  SUCCESS: Setpoint set to {celsius}°C")
            return True
    except ModbusException as e:
        print(f"  EXCEPTION: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test Fixed System Supply Setpoint registers on Thermia Mega"
    )
    parser.add_argument(
        "--read", action="store_true", help="Read current register values (safe)"
    )
    parser.add_argument(
        "--enable", action="store_true", help="Enable fixed supply mode (WRITES TO HEAT PUMP!)"
    )
    parser.add_argument(
        "--disable", action="store_true", help="Disable fixed supply mode (WRITES TO HEAT PUMP!)"
    )
    parser.add_argument(
        "--setpoint",
        type=float,
        metavar="CELSIUS",
        help="Set fixed supply setpoint in °C (WRITES TO HEAT PUMP!)",
    )
    parser.add_argument(
        "--host",
        default=THERMIA_HOST,
        help=f"Thermia Modbus host (default: {THERMIA_HOST})",
    )

    args = parser.parse_args()

    # Default to read if no action specified
    if not any([args.read, args.enable, args.disable, args.setpoint is not None]):
        args.read = True

    # Validate setpoint range
    if args.setpoint is not None:
        if args.setpoint < -40 or args.setpoint > 100:
            print(f"ERROR: Setpoint {args.setpoint}°C out of range (-40 to 100)")
            sys.exit(1)

    # Warn about write operations
    if args.enable or args.disable or args.setpoint is not None:
        print("=" * 60)
        print("WARNING: This will MODIFY heat pump settings!")
        print("=" * 60)
        print()

    # Connect to Modbus
    print(f"Connecting to {args.host}:{THERMIA_PORT}...")
    client = ModbusTcpClient(args.host, port=THERMIA_PORT)

    if not client.connect():
        print("ERROR: Failed to connect to Modbus server")
        sys.exit(1)

    print("Connected!")
    print()

    try:
        # Always read first to show current state
        print("=" * 40)
        print("CURRENT VALUES")
        print("=" * 40)
        results = read_registers(client)

        # Perform write operations if requested
        if args.setpoint is not None:
            print()
            print("=" * 40)
            print("WRITING SETPOINT")
            print("=" * 40)
            if not write_setpoint(client, args.setpoint):
                sys.exit(1)

        if args.enable:
            print()
            print("=" * 40)
            print("ENABLING FIXED SUPPLY")
            print("=" * 40)
            if not write_enable(client, True):
                sys.exit(1)

        if args.disable:
            print()
            print("=" * 40)
            print("DISABLING FIXED SUPPLY")
            print("=" * 40)
            if not write_enable(client, False):
                sys.exit(1)

        # Read again after writes to verify
        if args.enable or args.disable or args.setpoint is not None:
            print()
            print("=" * 40)
            print("VALUES AFTER WRITE")
            print("=" * 40)
            read_registers(client)

    finally:
        client.close()
        print()
        print("Connection closed.")


if __name__ == "__main__":
    main()
