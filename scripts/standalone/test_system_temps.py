#!/usr/bin/env python3
"""
Test script to read system supply and return line temperatures via direct Modbus.
Uses pythermiagenesis constants for register definitions.

From protocol_doc-00079973.pdf:
- Input register 12: System supply line temperature (scale 100)
- Input register 27: System return line temperature (scale 100) - NOT in pythermiagenesis!

Usage:
    ./env/bin/python scripts/standalone/test_system_temps.py
    ./env/bin/python scripts/standalone/test_system_temps.py --host 192.168.50.10
    ./env/bin/python scripts/standalone/test_system_temps.py --scan  # Scan registers 0-50
    ./env/bin/python scripts/standalone/test_system_temps.py --list-inputs  # List all input registers
"""

import argparse
import sys
from pymodbus.client import ModbusTcpClient

# Import pythermiagenesis constants
sys.path.insert(0, "/Users/sakumikko/code/pythermiagenesis")
from pythermiagenesis.const import (
    REGISTERS,
    REG_INPUT,
    KEY_ADDRESS,
    KEY_REG_TYPE,
    KEY_SCALE,
    MODEL_MEGA,
)

# Default connection settings for Thermia Mega
DEFAULT_HOST = "192.168.50.10"
DEFAULT_PORT = 502
DEVICE_ID = 1

# Build lookup from address to register name for input registers
INPUT_REGISTER_NAMES = {}
for name, reg in REGISTERS.items():
    if reg.get(KEY_REG_TYPE) == REG_INPUT:
        addr = reg.get(KEY_ADDRESS)
        INPUT_REGISTER_NAMES[addr] = {
            "name": name,
            "scale": reg.get(KEY_SCALE, 1),
            "mega": reg.get(MODEL_MEGA, False),
        }

# Additional registers from PDF that are NOT in pythermiagenesis
MISSING_REGISTERS = {
    27: {
        "name": "input_system_return_line_temperature (MISSING FROM LIBRARY)",
        "scale": 100,
        "mega": True,
    },
}


def read_input_register(client, address: int) -> tuple[int | None, bool]:
    """Read a single input register and return (raw_value, success)."""
    result = client.read_input_registers(address, count=1, device_id=DEVICE_ID)

    if result.isError():
        return None, False

    raw = result.registers[0]
    return raw, True


def get_register_info(address: int) -> dict | None:
    """Get register info from pythermiagenesis or missing registers list."""
    if address in INPUT_REGISTER_NAMES:
        return INPUT_REGISTER_NAMES[address]
    if address in MISSING_REGISTERS:
        return MISSING_REGISTERS[address]
    return None


def scale_value(raw: int, scale: int) -> float:
    """Scale raw value, handling signed int16."""
    # Handle signed int16 (values can be negative for temperatures)
    if raw > 32767:
        raw = raw - 65536
    return raw / scale


def list_input_registers():
    """List all input registers defined in pythermiagenesis."""
    print("\nInput registers defined in pythermiagenesis:")
    print("=" * 80)
    print(f"{'Addr':<6} {'Scale':<8} {'Mega':<6} {'Name'}")
    print("-" * 80)

    # Sort by address
    sorted_regs = sorted(INPUT_REGISTER_NAMES.items(), key=lambda x: x[0])
    for addr, info in sorted_regs:
        mega = "Yes" if info["mega"] else "No"
        print(f"{addr:<6} {info['scale']:<8} {mega:<6} {info['name']}")

    print("-" * 80)
    print(f"Total: {len(INPUT_REGISTER_NAMES)} input registers")

    # Show gaps (potential missing registers)
    addresses = set(INPUT_REGISTER_NAMES.keys())
    if addresses:
        max_addr = max(addresses)
        gaps = []
        for i in range(max_addr + 1):
            if i not in addresses:
                gaps.append(i)
        if gaps:
            print(f"\nGaps in address space (potential missing registers): {gaps[:20]}...")


def scan_input_registers(client, start: int = 0, end: int = 50):
    """Scan a range of input registers to see what's available."""
    print(f"\nScanning input registers {start}-{end}...")
    print("=" * 90)
    print(f"{'Addr':<6} {'Raw':<10} {'Scaled':<12} {'In Lib':<8} {'Name'}")
    print("-" * 90)

    for addr in range(start, end + 1):
        raw, success = read_input_register(client, addr)
        info = get_register_info(addr)

        if success:
            scale = info["scale"] if info else 100
            scaled = scale_value(raw, scale)
            in_lib = "Yes" if addr in INPUT_REGISTER_NAMES else "NO"
            name = info["name"] if info else f"(unknown - addr {addr})"

            # Flag suspicious values
            notes = ""
            if scaled > 100 or scaled < -50:
                notes = " [SUSPICIOUS]"

            print(f"{addr:<6} {raw:<10} {scaled:<12.2f} {in_lib:<8} {name}{notes}")
        else:
            in_lib = "Yes" if addr in INPUT_REGISTER_NAMES else "NO"
            name = info["name"] if info else ""
            print(f"{addr:<6} {'ERROR':<10} {'---':<12} {in_lib:<8} {name}")


def read_specific_registers(client, addresses: list[int]):
    """Read specific registers by address."""
    print("\nReading specified registers...")
    print("=" * 90)

    for addr in addresses:
        info = get_register_info(addr)
        raw, success = read_input_register(client, addr)

        print(f"\nAddress {addr} (De Facto: 3{addr:04d})")
        if info:
            print(f"  Name: {info['name']}")
            print(f"  Scale: {info['scale']}")
            print(f"  Mega support: {info['mega']}")
        else:
            print(f"  Name: (not in pythermiagenesis)")

        if success:
            scale = info["scale"] if info else 100
            scaled = scale_value(raw, scale)
            print(f"  Raw value: {raw}")
            print(f"  Scaled value: {scaled:.2f}")

            if scaled > 100:
                print(f"  WARNING: Value seems too high!")
            elif scaled < -50:
                print(f"  WARNING: Value seems too low!")
        else:
            print(f"  ERROR: Failed to read register")


def main():
    parser = argparse.ArgumentParser(description="Test system temperatures via Modbus using pythermiagenesis constants")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Thermia host (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Modbus port (default: {DEFAULT_PORT})")
    parser.add_argument("--scan", action="store_true", help="Scan input registers 0-50")
    parser.add_argument("--scan-range", type=str, help="Custom scan range, e.g. '0-100'")
    parser.add_argument("--list-inputs", action="store_true", help="List all input registers from pythermiagenesis")
    parser.add_argument("--addresses", type=str, help="Comma-separated addresses to read, e.g. '12,27'")
    args = parser.parse_args()

    # List mode doesn't need connection
    if args.list_inputs:
        list_input_registers()
        return

    print(f"Connecting to Thermia at {args.host}:{args.port}...")
    client = ModbusTcpClient(args.host, port=args.port)

    if not client.connect():
        print("ERROR: Failed to connect to Modbus server")
        sys.exit(1)

    print("Connected!\n")

    try:
        if args.scan or args.scan_range:
            if args.scan_range:
                start, end = map(int, args.scan_range.split("-"))
            else:
                start, end = 0, 50
            scan_input_registers(client, start, end)

        elif args.addresses:
            addresses = [int(a.strip()) for a in args.addresses.split(",")]
            read_specific_registers(client, addresses)

        else:
            # Default: read supply (12) and return (27) temperatures
            print("Reading system supply and return line temperatures...")
            read_specific_registers(client, [12, 27])

            print("\n" + "=" * 60)
            print("\nTo add system_return_line_temperature to pythermiagenesis:")
            print("""
In pythermiagenesis/const.py:

1. Add attribute constant (around line 217):
   ATTR_INPUT_SYSTEM_RETURN_LINE_TEMPERATURE = "input_system_return_line_temperature"

2. Add to REGISTERS dict (after ATTR_INPUT_SYSTEM_SUPPLY_LINE_TEMPERATURE entry):
   ATTR_INPUT_SYSTEM_RETURN_LINE_TEMPERATURE:
       { KEY_ADDRESS: 27, KEY_REG_TYPE: REG_INPUT, KEY_SCALE: 100, KEY_DATATYPE: TYPE_INT, MODEL_MEGA: True, MODEL_INVERTER: False },
""")

    finally:
        client.close()
        print("\nConnection closed.")


if __name__ == "__main__":
    main()
