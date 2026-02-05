#!/usr/bin/env python3
"""
Validate all YAML files in homeassistant/packages/

Handles Home Assistant specific YAML tags: !secret, !include
"""

import glob
import sys
import yaml


def main():
    # Add custom constructors for HA-specific tags
    yaml.add_constructor('!secret', lambda l, n: '<secret>', Loader=yaml.SafeLoader)
    yaml.add_constructor('!include', lambda l, n: '<include>', Loader=yaml.SafeLoader)

    failed = []
    files = sorted(glob.glob('homeassistant/packages/*.yaml'))

    if not files:
        print("No YAML files found in homeassistant/packages/")
        sys.exit(1)

    for filepath in files:
        name = filepath.split('/')[-1]
        try:
            with open(filepath) as f:
                yaml.safe_load(f)
            print(f"  {name}: OK")
        except Exception as e:
            print(f"  {name}: FAILED - {e}")
            failed.append(name)

    if failed:
        print(f"\n{len(failed)} file(s) failed validation")
        sys.exit(1)
    else:
        print(f"\nAll {len(files)} files validated successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
