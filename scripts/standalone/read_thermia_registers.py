#!/usr/bin/env python3
"""
Read Thermia heat pump register values via Modbus TCP.
This script is READ-ONLY and will not modify any values.

Usage:
    python read_thermia_registers.py [--host HOST] [--port PORT]

Default: 192.168.50.10:502
"""

import argparse
import sys
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# Thermia Modbus configuration
DEFAULT_HOST = "192.168.50.10"
DEFAULT_PORT = 502
UNIT_ID = 1  # Modbus slave ID

# Register definitions from pythermiagenesis library
# Format: (name, address, scale, description)
HOLDING_REGISTERS = [
    ("external_additional_heater_start", 75, 1, "External heater start threshold (°C)"),
    ("external_additional_heater_stop", 78, 100, "External heater stop threshold (°C)"),
    ("twc_start_delay_immersion_heater", 36, 100, "TWC immersion heater start delay"),
    ("heat_curve", 4, 100, "Heat curve setting"),
    ("heat_curve_fine_tune", 5, 100, "Heat curve fine tune"),
    ("indoor_temperature_setting", 6, 100, "Indoor temperature setting (°C)"),
    ("set_max_supply_line_temp", 9, 100, "Max supply line temp (°C)"),
    ("set_min_supply_line_temp", 11, 100, "Min supply line temp (°C)"),
    ("operational_mode", 0, 1, "Operational mode"),
    ("hot_water_setting", 7, 100, "Hot water setting (°C)"),
]

# Input registers (read-only sensor values)
# Addresses verified from pythermiagenesis const.py
INPUT_REGISTERS = [
    ("condenser_in_temperature", 8, 100, "Condenser in (from pool) (°C)"),
    ("condenser_out_temperature", 9, 100, "Condenser out (to pool) (°C)"),
    ("brine_in_temperature", 10, 100, "Brine in temperature (°C)"),
    ("brine_out_temperature", 11, 100, "Brine out temperature (°C)"),
    ("system_supply_line_temperature", 12, 100, "System supply line (°C)"),
    ("outdoor_temperature", 13, 100, "Outdoor temperature (°C)"),
    ("tap_water_top_temperature", 15, 100, "Tap water top (°C)"),
    ("tap_water_lower_temperature", 16, 100, "Tap water lower (°C)"),
    ("tap_water_weighted_temperature", 17, 100, "Tap water weighted (°C)"),
    ("system_supply_line_set_point", 18, 100, "Supply line set point (°C)"),
    ("compressor_speed", 35, 1, "Compressor speed (%)"),
    ("heating_effect", 304, 100, "Heating effect (kW)"),
]


def read_holding_registers(client, registers):
    """Read holding registers and return decoded values."""
    results = []
    for name, address, scale, description in registers:
        try:
            response = client.read_holding_registers(address, count=1, device_id=UNIT_ID)
            if response.isError():
                results.append((name, address, None, description, f"Error: {response}"))
            else:
                raw_value = response.registers[0]
                # Handle signed values (16-bit signed integer)
                if raw_value > 32767:
                    raw_value = raw_value - 65536
                scaled_value = raw_value / scale if scale != 1 else raw_value
                results.append((name, address, scaled_value, description, None))
        except ModbusException as e:
            results.append((name, address, None, description, f"ModbusException: {e}"))
        except Exception as e:
            results.append((name, address, None, description, f"Error: {e}"))
    return results


def read_input_registers(client, registers):
    """Read input registers and return decoded values."""
    results = []
    for name, address, scale, description in registers:
        try:
            response = client.read_input_registers(address, count=1, device_id=UNIT_ID)
            if response.isError():
                results.append((name, address, None, description, f"Error: {response}"))
            else:
                raw_value = response.registers[0]
                # Handle signed values (16-bit signed integer)
                if raw_value > 32767:
                    raw_value = raw_value - 65536
                scaled_value = raw_value / scale if scale != 1 else raw_value
                results.append((name, address, scaled_value, description, None))
        except ModbusException as e:
            results.append((name, address, None, description, f"ModbusException: {e}"))
        except Exception as e:
            results.append((name, address, None, description, f"Error: {e}"))
    return results


def print_results(title, results):
    """Print results in a formatted table."""
    print(f"\n{'=' * 70}")
    print(f" {title}")
    print(f"{'=' * 70}")
    print(f"{'Register Name':<40} {'Addr':>5} {'Value':>10}  Description")
    print(f"{'-' * 70}")

    for name, address, value, description, error in results:
        if error:
            print(f"{name:<40} {address:>5} {'ERROR':>10}  {error}")
        else:
            if isinstance(value, float) and value == int(value):
                value_str = str(int(value))
            else:
                value_str = f"{value:.2f}" if isinstance(value, float) else str(value)
            print(f"{name:<40} {address:>5} {value_str:>10}  {description}")


def main():
    parser = argparse.ArgumentParser(
        description="Read Thermia heat pump register values via Modbus TCP (READ-ONLY)"
    )
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help=f"Thermia host (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Modbus port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--holding-only", action="store_true", help="Only read holding registers"
    )
    parser.add_argument(
        "--input-only", action="store_true", help="Only read input registers"
    )
    args = parser.parse_args()

    print(f"Connecting to Thermia at {args.host}:{args.port}...")
    print("(This is a READ-ONLY operation - no values will be modified)")

    client = ModbusTcpClient(args.host, port=args.port, timeout=10)

    try:
        if not client.connect():
            print(f"ERROR: Failed to connect to {args.host}:{args.port}")
            sys.exit(1)

        print(f"Connected successfully!")

        if not args.input_only:
            holding_results = read_holding_registers(client, HOLDING_REGISTERS)
            print_results("HOLDING REGISTERS (Settings)", holding_results)

        if not args.holding_only:
            input_results = read_input_registers(client, INPUT_REGISTERS)
            print_results("INPUT REGISTERS (Sensors)", input_results)

        print(f"\n{'=' * 70}")
        print(" Read complete. No values were modified.")
        print(f"{'=' * 70}")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
