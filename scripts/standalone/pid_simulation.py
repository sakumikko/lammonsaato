#!/usr/bin/env python3
"""
PID Algorithm Simulation Workbench

This script provides tools for:
1. Loading historical sensor data from CSV exports
2. Simulating different target control algorithms
3. Comparing algorithm performance against real PID behavior
4. Validating algorithm changes before deployment

Usage:
    # Run benchmark on last night's data
    python scripts/standalone/pid_simulation.py benchmark

    # Analyze P value relationship
    python scripts/standalone/pid_simulation.py analyze-p

    # Compare old vs new algorithm
    python scripts/standalone/pid_simulation.py compare

    # Run with specific CSV file
    python scripts/standalone/pid_simulation.py benchmark --csv findings/my-data.csv

Key Findings (2025-12-22):
    - P ≈ Kp × (Supply_Actual - Supply_Target) with correlation 0.986
    - Kp ≈ 1.0 (P term directly tracks the error)
    - Negative error (target > supply) → PID INCREASES
    - Positive error (target < supply) → PID DECREASES

Algorithm Evolution:
    OLD (wrong):  target = supply - 0.5 - pid_correction
                  → Always creates negative error → PID always increases

    NEW (correct): target = supply + pid_correction
                  → When PID high: positive correction → target above supply
                  → Creates positive error → PID decreases back to target
"""

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# CONFIGURATION
# ============================================================================

# Default CSV files (relative to project root)
DEFAULT_COMPREHENSIVE_CSV = "findings/comprehensive-analysis-2025-12-22T07-10-28.csv"
DEFAULT_PID_CSV = "findings/p_i_d_values.csv"

# Algorithm parameters (from pool_temp_control.py)
PID_TARGET = -2.5        # Target PID30 value (middle of [-5, 0])
PID_GAIN = 0.10          # °C offset per unit of PID error
MIN_CORRECTION = -1.0    # Max 1°C below supply
MAX_CORRECTION = 4.0     # Max 4°C above supply
MIN_SETPOINT = 28.0
MAX_SETPOINT = 45.0

# PID dynamics (estimated from data analysis)
# PID_rate ≈ -3.5 × Error per 5 minutes
PID_RATE_FACTOR = -3.5 / 5.0  # per minute


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class SensorReading:
    """A single timestamped sensor reading."""
    timestamp: datetime
    supply_actual: float
    supply_target: float
    pid_30m: float
    p_value: Optional[float] = None
    i_value: Optional[float] = None
    d_value: Optional[float] = None


@dataclass
class SimulationResult:
    """Result of simulating an algorithm over a time series."""
    algorithm_name: str
    timestamps: List[datetime]
    supply_values: List[float]
    target_values: List[float]
    pid_values: List[float]
    real_pid_values: List[float]

    @property
    def final_pid(self) -> float:
        return self.pid_values[-1] if self.pid_values else 0.0

    @property
    def final_real_pid(self) -> float:
        return self.real_pid_values[-1] if self.real_pid_values else 0.0

    @property
    def in_target_range_pct(self) -> float:
        """Percentage of samples where PID is in target range [-5, 0]."""
        if not self.pid_values:
            return 0.0
        in_range = sum(1 for p in self.pid_values if -5 <= p <= 0)
        return 100.0 * in_range / len(self.pid_values)


@dataclass
class BlockAnalysis:
    """Analysis of a single heating block."""
    block_num: int
    start_time: datetime
    end_time: datetime
    start_pid: float
    end_pid: float
    real_start_pid: float
    real_end_pid: float
    samples: int


# ============================================================================
# ALGORITHMS
# ============================================================================

def algorithm_old(supply: float, prev_supply: float, pid_30m: float) -> float:
    """
    OLD algorithm (incorrect sign).

    Formula: target = supply - 0.5 - pid_correction
    Problem: Always sets target below supply, creating negative error.
    """
    pid_error = pid_30m - PID_TARGET
    pid_correction = max(MIN_CORRECTION, min(pid_error * PID_GAIN, MAX_CORRECTION))

    # OLD: subtract correction (wrong!)
    target = supply - 0.5 - pid_correction
    return max(MIN_SETPOINT, min(target, MAX_SETPOINT))


def algorithm_new(supply: float, prev_supply: float, pid_30m: float) -> float:
    """
    NEW algorithm (correct sign).

    Formula: target = supply + pid_correction

    When PID is too high (+25):
        correction = (25 - (-2.5)) * 0.10 = +2.75
        target = supply + 2.75 (ABOVE supply)
        → Positive error → PID decreases

    When PID is too low (-10):
        correction = (-10 - (-2.5)) * 0.10 = -0.75
        target = supply - 0.75 (BELOW supply)
        → Negative error → PID increases
    """
    pid_error = pid_30m - PID_TARGET
    pid_correction = max(MIN_CORRECTION, min(pid_error * PID_GAIN, MAX_CORRECTION))

    # NEW: add correction (correct!)
    target = supply + pid_correction
    return max(MIN_SETPOINT, min(target, MAX_SETPOINT))


# Registry of available algorithms
ALGORITHMS: Dict[str, Callable[[float, float, float], float]] = {
    "old": algorithm_old,
    "new": algorithm_new,
}


# ============================================================================
# DATA LOADING
# ============================================================================

def load_comprehensive_csv(filepath: str) -> List[SensorReading]:
    """
    Load data from comprehensive analysis CSV.

    Expected columns:
        timestamp, PID Sum, Supply ΔT, Supply Actual, Supply Target,
        Mix Valve 1 Supply, Mix Valve 1 Target, Compressor RPM,
        Heater Demand, PID Integral 30m
    """
    readings = []

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                readings.append(SensorReading(
                    timestamp=ts,
                    supply_actual=float(row['Supply Actual']),
                    supply_target=float(row['Supply Target']),
                    pid_30m=float(row['PID Integral 30m']),
                ))
            except (ValueError, KeyError) as e:
                continue  # Skip malformed rows

    return readings


def load_pid_values_csv(filepath: str) -> Dict[str, Dict[str, float]]:
    """
    Load P, I, D values from entity CSV export.

    Returns dict: {timestamp_minute: {entity_id: value}}
    """
    data = {}

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = row['last_changed'][:16]  # Truncate to minute
                entity = row['entity_id']
                value = float(row['state'])

                if ts not in data:
                    data[ts] = {}
                data[ts][entity] = value
            except (ValueError, KeyError):
                continue

    return data


def find_heating_blocks(readings: List[SensorReading],
                        min_gap_minutes: int = 30) -> List[Tuple[int, int]]:
    """
    Find heating blocks in data based on gaps between readings.

    Returns list of (start_idx, end_idx) tuples.
    """
    if not readings:
        return []

    blocks = []
    block_start = 0

    for i in range(1, len(readings)):
        gap = (readings[i].timestamp - readings[i-1].timestamp).total_seconds() / 60
        if gap > min_gap_minutes:
            blocks.append((block_start, i - 1))
            block_start = i

    blocks.append((block_start, len(readings) - 1))
    return blocks


# ============================================================================
# SIMULATION
# ============================================================================

def simulate_algorithm(
    readings: List[SensorReading],
    algorithm: Callable[[float, float, float], float],
    algorithm_name: str,
) -> SimulationResult:
    """
    Simulate an algorithm on historical data.

    Uses real supply values from data, but calculates new targets
    and estimates what PID would be with those targets.
    """
    if not readings:
        return SimulationResult(algorithm_name, [], [], [], [], [])

    timestamps = []
    supply_values = []
    target_values = []
    simulated_pid = []
    real_pid = []

    # Start with real initial PID
    current_pid = readings[0].pid_30m
    prev_supply = readings[0].supply_actual

    for i, reading in enumerate(readings):
        supply = reading.supply_actual

        # Calculate target using algorithm
        target = algorithm(supply, prev_supply, current_pid)

        # Estimate error (P term ≈ supply - target based on 0.986 correlation)
        error = supply - target

        # Estimate PID change
        # From data: PID changes by ~-3.5 × error per 5 minutes
        if i > 0:
            dt_minutes = (reading.timestamp - readings[i-1].timestamp).total_seconds() / 60
            pid_delta = error * PID_RATE_FACTOR * dt_minutes
            current_pid += pid_delta

        timestamps.append(reading.timestamp)
        supply_values.append(supply)
        target_values.append(target)
        simulated_pid.append(current_pid)
        real_pid.append(reading.pid_30m)

        prev_supply = supply

    return SimulationResult(
        algorithm_name=algorithm_name,
        timestamps=timestamps,
        supply_values=supply_values,
        target_values=target_values,
        pid_values=simulated_pid,
        real_pid_values=real_pid,
    )


def analyze_blocks(
    readings: List[SensorReading],
    result: SimulationResult,
) -> List[BlockAnalysis]:
    """Analyze each heating block separately."""
    blocks = find_heating_blocks(readings)
    analyses = []

    for i, (start, end) in enumerate(blocks):
        if end <= start:
            continue

        analyses.append(BlockAnalysis(
            block_num=i + 1,
            start_time=result.timestamps[start],
            end_time=result.timestamps[end],
            start_pid=result.pid_values[start],
            end_pid=result.pid_values[end],
            real_start_pid=result.real_pid_values[start],
            real_end_pid=result.real_pid_values[end],
            samples=end - start + 1,
        ))

    return analyses


# ============================================================================
# ANALYSIS COMMANDS
# ============================================================================

def cmd_analyze_p(args):
    """Analyze P value relationship with (Supply - Target)."""
    print("=" * 70)
    print("P VALUE ANALYSIS: Does P = Kp × (Supply - Target)?")
    print("=" * 70)

    # Load data
    pid_data = load_pid_values_csv(os.path.join(PROJECT_ROOT, DEFAULT_PID_CSV))
    readings = load_comprehensive_csv(os.path.join(PROJECT_ROOT, DEFAULT_COMPREHENSIVE_CSV))

    # Build lookup by timestamp minute
    reading_map = {}
    for r in readings:
        key = r.timestamp.strftime('%Y-%m-%dT%H:%M')
        reading_map[key] = r

    # Find common timestamps with P values
    matches = []
    for ts, entities in pid_data.items():
        p_entity = 'sensor.p_value_for_gear_shifting_and_demand_calculation'
        if p_entity not in entities:
            continue
        if ts not in reading_map:
            continue

        p_value = entities[p_entity]
        reading = reading_map[ts]
        error = reading.supply_actual - reading.supply_target

        matches.append({
            'timestamp': ts,
            'p_value': p_value,
            'supply': reading.supply_actual,
            'target': reading.supply_target,
            'error': error,
        })

    if not matches:
        print("No matching data found!")
        return

    print(f"\nFound {len(matches)} matching timestamps\n")

    # Print sample
    print(f"{'Time':>8} {'P':>8} {'Supply':>8} {'Target':>8} {'S-T':>8} {'Match?':>8}")
    print("-" * 56)

    for m in matches[:20]:
        time_str = m['timestamp'][11:16]
        match = abs(m['p_value'] - m['error']) < 0.1
        marker = '✓' if match else '✗'
        print(f"{time_str:>8} {m['p_value']:>8.2f} {m['supply']:>8.2f} "
              f"{m['target']:>8.2f} {m['error']:>8.2f} {marker:>8}")

    # Calculate correlation
    p_values = [m['p_value'] for m in matches]
    errors = [m['error'] for m in matches]

    mean_p = sum(p_values) / len(p_values)
    mean_e = sum(errors) / len(errors)

    numerator = sum((p - mean_p) * (e - mean_e) for p, e in zip(p_values, errors))
    denom_p = sum((p - mean_p) ** 2 for p in p_values) ** 0.5
    denom_e = sum((e - mean_e) ** 2 for e in errors) ** 0.5

    if denom_p > 0 and denom_e > 0:
        correlation = numerator / (denom_p * denom_e)
        print(f"\n{'='*56}")
        print(f"Correlation: {correlation:.4f}")
        print(f"Conclusion: P ≈ {correlation:.2f} × (Supply - Target)")
        print(f"{'='*56}")

    # Estimate Kp
    if errors:
        # Linear regression: P = Kp * error + b
        n = len(matches)
        sum_e = sum(errors)
        sum_p = sum(p_values)
        sum_ep = sum(e * p for e, p in zip(errors, p_values))
        sum_e2 = sum(e * e for e in errors)

        kp = (n * sum_ep - sum_e * sum_p) / (n * sum_e2 - sum_e * sum_e)
        b = (sum_p - kp * sum_e) / n

        print(f"\nLinear fit: P = {kp:.3f} × Error + {b:.3f}")
        print(f"Kp ≈ {kp:.2f} (proportional gain)")


def cmd_benchmark(args):
    """Run benchmark comparing algorithms."""
    print("=" * 70)
    print("ALGORITHM BENCHMARK")
    print("=" * 70)

    csv_path = args.csv or os.path.join(PROJECT_ROOT, DEFAULT_COMPREHENSIVE_CSV)
    readings = load_comprehensive_csv(csv_path)

    if not readings:
        print(f"No data loaded from {csv_path}")
        return

    print(f"\nLoaded {len(readings)} readings")
    print(f"Time range: {readings[0].timestamp} to {readings[-1].timestamp}")

    # Find heating blocks
    blocks = find_heating_blocks(readings)
    print(f"Found {len(blocks)} heating blocks\n")

    # Run simulations
    results = {}
    for name, algo in ALGORITHMS.items():
        results[name] = simulate_algorithm(readings, algo, name)

    # Summary table
    print(f"{'Algorithm':>12} {'In Range %':>12} {'Final PID':>12}")
    print("-" * 40)
    for name, result in results.items():
        print(f"{name:>12} {result.in_target_range_pct:>11.1f}% {result.final_pid:>12.1f}")

    print(f"{'real data':>12} {'':>12} {readings[-1].pid_30m:>12.1f}")

    # Per-block analysis
    print(f"\n{'Block Analysis':^70}")
    print("-" * 70)
    print(f"{'Block':>6} {'Old Final':>12} {'New Final':>12} {'Real Final':>12}")
    print("-" * 70)

    old_blocks = analyze_blocks(readings, results['old'])
    new_blocks = analyze_blocks(readings, results['new'])

    for i, (old, new) in enumerate(zip(old_blocks, new_blocks)):
        print(f"{old.block_num:>6} {old.end_pid:>12.1f} {new.end_pid:>12.1f} "
              f"{old.real_end_pid:>12.1f}")

    # Save results
    output = {
        "algorithm": {
            "old": "target = supply - 0.5 - pid_correction",
            "new": "target = supply + pid_correction",
        },
        "summary": {
            "old_in_range_pct": results['old'].in_target_range_pct,
            "new_in_range_pct": results['new'].in_target_range_pct,
        },
        "blocks": {},
    }

    for i, (old, new) in enumerate(zip(old_blocks, new_blocks)):
        output["blocks"][f"Block {i+1}"] = {
            "old_final_pid": old.end_pid,
            "new_final_pid": new.end_pid,
            "real_final_pid": old.real_end_pid,
        }

    output_path = os.path.join(PROJECT_ROOT, "findings/algorithm_benchmark_latest.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {output_path}")


def cmd_compare(args):
    """Compare two algorithms side by side."""
    print("=" * 70)
    print("ALGORITHM COMPARISON")
    print("=" * 70)

    csv_path = args.csv or os.path.join(PROJECT_ROOT, DEFAULT_COMPREHENSIVE_CSV)
    readings = load_comprehensive_csv(csv_path)

    if not readings:
        print(f"No data loaded from {csv_path}")
        return

    # Run both algorithms
    old_result = simulate_algorithm(readings, algorithm_old, "old")
    new_result = simulate_algorithm(readings, algorithm_new, "new")

    # Show time series comparison
    print(f"\n{'Time':>8} {'Supply':>8} {'Old Tgt':>8} {'New Tgt':>8} "
          f"{'Old PID':>8} {'New PID':>8} {'Real':>8}")
    print("-" * 64)

    step = max(1, len(readings) // 30)  # Show ~30 samples
    for i in range(0, len(readings), step):
        ts = readings[i].timestamp.strftime('%H:%M')
        print(f"{ts:>8} {old_result.supply_values[i]:>8.1f} "
              f"{old_result.target_values[i]:>8.1f} {new_result.target_values[i]:>8.1f} "
              f"{old_result.pid_values[i]:>8.1f} {new_result.pid_values[i]:>8.1f} "
              f"{readings[i].pid_30m:>8.1f}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Old algorithm: {old_result.in_target_range_pct:.1f}% in target range, "
          f"final PID = {old_result.final_pid:.1f}")
    print(f"New algorithm: {new_result.in_target_range_pct:.1f}% in target range, "
          f"final PID = {new_result.final_pid:.1f}")
    print(f"Real data: final PID = {readings[-1].pid_30m:.1f}")


def cmd_validate(args):
    """Validate the current algorithm implementation."""
    print("=" * 70)
    print("ALGORITHM VALIDATION")
    print("=" * 70)

    # Test cases
    test_cases = [
        # (supply, prev_supply, pid_30m, expected_direction)
        (40.0, 40.0, 25.0, "above"),   # High PID → target above supply
        (40.0, 40.0, -10.0, "below"),  # Low PID → target below supply
        (40.0, 40.0, -2.5, "equal"),   # At target → target equals supply
        (40.0, 40.0, 0.0, "above"),    # Zero PID → slight correction up
    ]

    print(f"\n{'Supply':>8} {'PID30':>8} {'Expected':>10} {'Target':>8} {'Result':>8}")
    print("-" * 50)

    all_passed = True
    for supply, prev, pid, expected in test_cases:
        target = algorithm_new(supply, prev, pid)

        if expected == "above":
            passed = target > supply
        elif expected == "below":
            passed = target < supply
        else:  # equal
            passed = abs(target - supply) < 0.01

        status = "✓ PASS" if passed else "✗ FAIL"
        if not passed:
            all_passed = False

        print(f"{supply:>8.1f} {pid:>8.1f} {expected:>10} {target:>8.1f} {status:>8}")

    print("\n" + "=" * 50)
    if all_passed:
        print("All validation tests PASSED")
    else:
        print("Some validation tests FAILED")

    return 0 if all_passed else 1


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="PID Algorithm Simulation Workbench",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # analyze-p command
    p_analyze = subparsers.add_parser('analyze-p',
        help='Analyze P value relationship with error')

    # benchmark command
    p_benchmark = subparsers.add_parser('benchmark',
        help='Run benchmark comparing algorithms')
    p_benchmark.add_argument('--csv', help='Path to comprehensive CSV file')

    # compare command
    p_compare = subparsers.add_parser('compare',
        help='Compare algorithms side by side')
    p_compare.add_argument('--csv', help='Path to comprehensive CSV file')

    # validate command
    p_validate = subparsers.add_parser('validate',
        help='Validate current algorithm implementation')

    args = parser.parse_args()

    if args.command == 'analyze-p':
        cmd_analyze_p(args)
    elif args.command == 'benchmark':
        cmd_benchmark(args)
    elif args.command == 'compare':
        cmd_compare(args)
    elif args.command == 'validate':
        return cmd_validate(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    sys.exit(main() or 0)
