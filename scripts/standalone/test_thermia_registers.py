#!/usr/bin/env python3
"""
Test which Thermia Genesis registers are available by testing each one individually.

Usage:
    python scripts/standalone/test_thermia_registers.py

This script:
1. Uses register definitions from pythermiagenesis const.py
2. Tests each register individually via Modbus TCP
3. Reports which registers are readable on this specific heat pump
"""

import asyncio
import json
import sys

try:
    from pymodbus.client import AsyncModbusTcpClient
except ImportError:
    print("Installing pymodbus...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymodbus"])
    from pymodbus.client import AsyncModbusTcpClient

try:
    from pythermiagenesis.const import REGISTERS, MODEL_MEGA, KEY_ADDRESS, KEY_REG_TYPE
except ImportError:
    print("Installing pythermiagenesis...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pythermiagenesis"])
    from pythermiagenesis.const import REGISTERS, MODEL_MEGA, KEY_ADDRESS, KEY_REG_TYPE

# Thermia configuration
THERMIA_HOST = "192.168.50.10"
THERMIA_PORT = 502
UNIT_ID = 1


async def test_register(client, name: str, reg_info: dict) -> dict:
    """Test a single register and return result."""
    address = reg_info.get(KEY_ADDRESS)
    reg_type = reg_info.get(KEY_REG_TYPE)
    is_mega = reg_info.get(MODEL_MEGA, False)

    result = {
        "name": name,
        "address": address,
        "type": reg_type,
        "mega_supported": is_mega,
        "available": False,
        "value": None,
        "error": None
    }

    if address is None:
        result["error"] = "No address defined"
        return result

    try:
        if reg_type == "input":
            response = await client.read_input_registers(address=address, count=1, device_id=UNIT_ID)
        elif reg_type == "holding":
            response = await client.read_holding_registers(address=address, count=1, device_id=UNIT_ID)
        elif reg_type == "coil":
            response = await client.read_coils(address=address, count=1, device_id=UNIT_ID)
        elif reg_type == "dinput":
            response = await client.read_discrete_inputs(address=address, count=1, device_id=UNIT_ID)
        else:
            result["error"] = f"Unknown register type: {reg_type}"
            return result

        if response.isError():
            result["error"] = str(response)
        else:
            result["available"] = True
            if reg_type in ("coil", "dinput"):
                result["value"] = int(response.bits[0])
            else:
                result["value"] = response.registers[0]

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


async def test_all_registers():
    """Test all registers from pythermiagenesis."""
    print(f"Connecting to Thermia Genesis at {THERMIA_HOST}:{THERMIA_PORT}")
    print(f"Testing {len(REGISTERS)} registers individually...")
    print("=" * 60)

    client = AsyncModbusTcpClient(host=THERMIA_HOST, port=THERMIA_PORT, timeout=5)
    await client.connect()

    if not client.connected:
        print(f"ERROR: Failed to connect to {THERMIA_HOST}:{THERMIA_PORT}")
        return

    print("Connected successfully!\n")

    results = []
    available = []
    unavailable = []

    # Filter for MEGA model registers only
    mega_registers = {
        name: info for name, info in REGISTERS.items()
        if info.get(MODEL_MEGA, False)
    }
    print(f"Testing {len(mega_registers)} registers marked as MEGA-compatible...\n")

    for i, (name, reg_info) in enumerate(mega_registers.items()):
        result = await test_register(client, name, reg_info)
        results.append(result)

        if result["available"]:
            available.append(result)
            status = f"✓ {result['value']}"
        else:
            unavailable.append(result)
            status = f"✗ {result['error'][:40] if result['error'] else 'N/A'}"

        # Progress indicator every 50 registers
        if (i + 1) % 50 == 0:
            print(f"  Tested {i + 1}/{len(mega_registers)} registers...")

    client.close()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total MEGA registers: {len(mega_registers)}")
    print(f"Available (readable): {len(available)}")
    print(f"Unavailable: {len(unavailable)}")

    # Group by type
    by_type = {}
    for r in available:
        t = r["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(r)

    print("\nAvailable by type:")
    for t, regs in sorted(by_type.items()):
        print(f"  {t}: {len(regs)}")

    # Print available registers
    print("\n" + "=" * 60)
    print("AVAILABLE REGISTERS")
    print("=" * 60)
    for r in sorted(available, key=lambda x: (x["type"], x["name"])):
        print(f"  [{r['type']:7}] {r['name']}: {r['value']}")

    # Save results
    output = {
        "host": THERMIA_HOST,
        "port": THERMIA_PORT,
        "total_mega_registers": len(mega_registers),
        "available_count": len(available),
        "unavailable_count": len(unavailable),
        "available_registers": [
            {"name": r["name"], "type": r["type"], "address": r["address"], "value": r["value"]}
            for r in sorted(available, key=lambda x: x["name"])
        ],
        "unavailable_registers": [
            {"name": r["name"], "type": r["type"], "address": r["address"], "error": r["error"]}
            for r in sorted(unavailable, key=lambda x: x["name"])
        ]
    }

    output_file = "thermia_registers_available.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {output_file}")


def main():
    asyncio.run(test_all_registers())


if __name__ == "__main__":
    main()
