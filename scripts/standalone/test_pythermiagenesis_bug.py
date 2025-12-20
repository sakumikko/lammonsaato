#!/usr/bin/env python3
"""
Test script to reproduce and validate the pythermiagenesis KeyError bug.

This script simulates the buggy code path in pythermiagenesis/_get_data()
to confirm the bug exists and that the fix works.

Usage:
    # Reproduce the bug (should raise KeyError)
    ./env/bin/python scripts/standalone/test_pythermiagenesis_bug.py --reproduce

    # Validate the fix (should NOT raise KeyError)
    ./env/bin/python scripts/standalone/test_pythermiagenesis_bug.py --validate-fix

    # Run both tests
    ./env/bin/python scripts/standalone/test_pythermiagenesis_bug.py --all
"""

import argparse
import sys

# Constants from pythermiagenesis (matching their naming)
ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT = "coil_enable_fixed_system_supply_set_point"
ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT = "holding_fixed_system_supply_set_point"


def simulate_buggy_code(raw_data: dict, self_data: dict) -> str:
    """
    Simulate the buggy code path from pythermiagenesis/__init__.py line ~185-198.

    This is what the library does when processing holding_fixed_system_supply_set_point:

    ```python
    if name == ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT:
        enableAttr = ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT
        if enableAttr not in raw_data and enableAttr not in self.data:
            continue  # Skip - we don't know coil state
        if (
            not raw_data[ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]      # BUG!
            and not self.data[ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]  # BUG!
        ):
            continue  # Skip - coil is False
    ```

    The bug is that raw_data[key] is accessed even when key might not exist in raw_data
    (it could only exist in self_data).
    """
    name = ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT
    enableAttr = ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT

    # First check passes if either has the key
    if enableAttr not in raw_data and enableAttr not in self_data:
        return "skipped: coil state unknown"

    # Second check - THIS IS THE BUG
    # It accesses raw_data[key] without checking if key exists
    if (
        not raw_data[enableAttr]  # KeyError if enableAttr not in raw_data!
        and not self_data[enableAttr]
    ):
        return "skipped: coil is False"

    return "would read holding register"


def simulate_fixed_code(raw_data: dict, self_data: dict) -> str:
    """
    Simulate the FIXED code path using .get() with default values.
    """
    name = ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT
    enableAttr = ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT

    # First check passes if either has the key
    if enableAttr not in raw_data and enableAttr not in self_data:
        return "skipped: coil state unknown"

    # Second check - FIXED with .get()
    if (
        not raw_data.get(enableAttr, False)  # Returns False if key missing
        and not self_data.get(enableAttr, False)
    ):
        return "skipped: coil is False"

    return "would read holding register"


def test_reproduce_bug():
    """
    Test case that reproduces the bug.

    Scenario: Coil exists in self_data (from previous read) but NOT in raw_data
    (because coil was read after holding in iteration order, or coil read failed).
    """
    print("=" * 60)
    print("TEST: Reproduce Bug")
    print("=" * 60)
    print()
    print("Scenario: coil exists in self_data but NOT in raw_data")
    print("  raw_data = {}")
    print(f"  self_data = {{'{ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT}': False}}")
    print()

    raw_data = {}  # Coil not in raw_data (not read yet, or read failed)
    self_data = {ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT: False}  # From previous read

    print("Running buggy code path...")
    try:
        result = simulate_buggy_code(raw_data, self_data)
        print(f"  Result: {result}")
        print()
        print("ERROR: Expected KeyError but none was raised!")
        return False
    except KeyError as e:
        print(f"  KeyError raised as expected: {e}")
        print()
        print("SUCCESS: Bug reproduced!")
        return True


def test_validate_fix():
    """
    Test case that validates the fix works.

    Same scenario as reproduce_bug, but using the fixed code.
    """
    print("=" * 60)
    print("TEST: Validate Fix")
    print("=" * 60)
    print()
    print("Scenario: coil exists in self_data but NOT in raw_data")
    print("  raw_data = {}")
    print(f"  self_data = {{'{ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT}': False}}")
    print()

    raw_data = {}
    self_data = {ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT: False}

    print("Running fixed code path...")
    try:
        result = simulate_fixed_code(raw_data, self_data)
        print(f"  Result: {result}")
        print()
        if result == "skipped: coil is False":
            print("SUCCESS: Fix works correctly!")
            print("  - No KeyError raised")
            print("  - Holding register correctly skipped (coil is False)")
            return True
        else:
            print(f"ERROR: Unexpected result: {result}")
            return False
    except KeyError as e:
        print(f"  KeyError raised: {e}")
        print()
        print("ERROR: Fix did not prevent KeyError!")
        return False


def test_fix_with_coil_true():
    """
    Additional test: when coil is True, should proceed to read holding register.
    """
    print("=" * 60)
    print("TEST: Fix with Coil=True")
    print("=" * 60)
    print()
    print("Scenario: coil is True in self_data")
    print("  raw_data = {}")
    print(f"  self_data = {{'{ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT}': True}}")
    print()

    raw_data = {}
    self_data = {ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT: True}

    print("Running fixed code path...")
    try:
        result = simulate_fixed_code(raw_data, self_data)
        print(f"  Result: {result}")
        print()
        if result == "would read holding register":
            print("SUCCESS: Correctly proceeds to read holding when coil is True")
            return True
        else:
            print(f"ERROR: Should have proceeded to read holding register")
            return False
    except KeyError as e:
        print(f"  KeyError raised: {e}")
        print()
        print("ERROR: Fix did not prevent KeyError!")
        return False


def test_fix_with_coil_unknown():
    """
    Additional test: when coil is completely unknown, should skip.
    """
    print("=" * 60)
    print("TEST: Fix with Coil Unknown")
    print("=" * 60)
    print()
    print("Scenario: coil not in raw_data or self_data")
    print("  raw_data = {}")
    print("  self_data = {}")
    print()

    raw_data = {}
    self_data = {}

    print("Running fixed code path...")
    try:
        result = simulate_fixed_code(raw_data, self_data)
        print(f"  Result: {result}")
        print()
        if result == "skipped: coil state unknown":
            print("SUCCESS: Correctly skips when coil state is unknown")
            return True
        else:
            print(f"ERROR: Should have skipped due to unknown coil state")
            return False
    except KeyError as e:
        print(f"  KeyError raised: {e}")
        print()
        print("ERROR: Unexpected exception!")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test pythermiagenesis KeyError bug reproduction and fix"
    )
    parser.add_argument(
        "--reproduce", action="store_true", help="Reproduce the bug (should raise KeyError)"
    )
    parser.add_argument(
        "--validate-fix", action="store_true", help="Validate the fix works"
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all tests"
    )

    args = parser.parse_args()

    # Default to --all if no args
    if not any([args.reproduce, args.validate_fix, args.all]):
        args.all = True

    results = []

    if args.reproduce or args.all:
        results.append(("Reproduce Bug", test_reproduce_bug()))
        print()

    if args.validate_fix or args.all:
        results.append(("Validate Fix (coil=False)", test_validate_fix()))
        print()
        results.append(("Validate Fix (coil=True)", test_fix_with_coil_true()))
        print()
        results.append(("Validate Fix (coil=unknown)", test_fix_with_coil_unknown()))
        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
