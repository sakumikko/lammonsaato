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

# Optional plotting libraries (installed via: pip install matplotlib plotly)
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import the actual deployed algorithm (must be after path setup)
from scripts.pyscript.pool_temp_control import calculate_new_setpoint as deployed_algorithm


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
    NEW algorithm - wrapper around the actual deployed algorithm.

    Uses the real calculate_new_setpoint() from pool_temp_control.py
    to ensure simulation matches deployed behavior exactly.

    Formula: target = supply + pid_correction
    See pool_temp_control.py for full documentation.
    """
    # Call the actual deployed algorithm
    target, _drop_rate, _correction = deployed_algorithm(supply, prev_supply, pid_30m)
    return target


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


def cmd_plot(args):
    """Generate comprehensive algorithm comparison graphs.

    Shows:
    - Observed/real values from HA
    - New algorithm targets and simulated P/PID values
    - Proper PID simulation using P ≈ (Supply - Target) relationship
    """
    if not MATPLOTLIB_AVAILABLE:
        print("Error: matplotlib not installed. Run: pip install matplotlib")
        return 1

    print("=" * 70)
    print("GENERATING ALGORITHM COMPARISON PLOTS")
    print("=" * 70)

    csv_path = args.csv or os.path.join(PROJECT_ROOT, DEFAULT_COMPREHENSIVE_CSV)
    readings = load_comprehensive_csv(csv_path)

    if not readings:
        print(f"No data loaded from {csv_path}")
        return 1

    # Load real P values if available
    pid_csv_path = os.path.join(PROJECT_ROOT, DEFAULT_PID_CSV)
    pid_data = {}
    if os.path.exists(pid_csv_path):
        pid_data = load_pid_values_csv(pid_csv_path)
        print(f"Loaded P values from {pid_csv_path}")

    # Build lookup for real P values
    p_entity = 'sensor.p_value_for_gear_shifting_and_demand_calculation'

    # Calculate and simulate
    timestamps = []
    supply_values = []
    real_targets = []
    real_pid_30m = []
    real_p_values = []

    new_algo_targets = []
    new_algo_p_expected = []  # P = Supply - Target
    new_algo_pid_simulated = []

    # Initialize simulation
    prev_supply = readings[0].supply_actual if readings else 40.0
    simulated_pid = readings[0].pid_30m if readings else 0.0

    # PID dynamics from empirical analysis:
    # - Error = Target - Supply
    # - PID_rate ≈ -3.5 * Error per 5 minutes = -0.7 * (Target - Supply) per minute
    # - Which equals: +0.7 * (Supply - Target) per minute = +0.7 * P
    # - When Target > Supply: negative P → PID decreases (good for reducing high PID)
    # - When Target < Supply: positive P → PID increases
    PID_RATE_PER_MIN = 0.7  # Positive: PID_change = rate * (Supply - Target)

    for i, r in enumerate(readings):
        timestamps.append(r.timestamp)
        supply_values.append(r.supply_actual)
        real_targets.append(r.supply_target)
        real_pid_30m.append(r.pid_30m)

        # Get real P value if available
        ts_key = r.timestamp.strftime('%Y-%m-%dT%H:%M')
        real_p = None
        if ts_key in pid_data and p_entity in pid_data[ts_key]:
            real_p = pid_data[ts_key][p_entity]
        real_p_values.append(real_p)

        # Calculate new algorithm target using SIMULATED PID (not real)
        new_target = algorithm_new(r.supply_actual, prev_supply, simulated_pid)
        new_algo_targets.append(new_target)

        # Expected P if we used this target: P ≈ Supply - Target
        expected_p = r.supply_actual - new_target
        new_algo_p_expected.append(expected_p)

        # Record current simulated PID
        new_algo_pid_simulated.append(simulated_pid)

        # Update simulated PID for next iteration
        # Time delta (assume ~1 min between readings on average)
        if i > 0:
            dt_seconds = (r.timestamp - readings[i-1].timestamp).total_seconds()
            dt_minutes = dt_seconds / 60.0
            # PID change based on expected P
            pid_change = PID_RATE_PER_MIN * expected_p * dt_minutes
            simulated_pid += pid_change
            # Clamp to reasonable range
            simulated_pid = max(-30, min(50, simulated_pid))

        prev_supply = r.supply_actual

    # Create figure with 4 subplots
    fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)
    fig.suptitle('PID Algorithm Comparison - Full Simulation', fontsize=14, fontweight='bold')

    # --- Plot 1: PID 30m (Real vs Simulated) ---
    ax1 = axes[0]
    ax1.plot(timestamps, real_pid_30m, 'b-', label='Observed PID 30m', linewidth=1.5)
    ax1.plot(timestamps, new_algo_pid_simulated, 'g-', label='New Algo PID (simulated)', linewidth=1.5, alpha=0.8)

    ax1.axhspan(-5, 0, alpha=0.15, color='green', label='Target Range [-5, 0]')
    ax1.axhline(y=PID_TARGET, color='gray', linestyle=':', alpha=0.5, label=f'Target ({PID_TARGET})')

    ax1.set_ylabel('PID 30m Sum')
    ax1.set_title('PID Integral: Observed vs New Algorithm Simulation')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-20, 50)

    # --- Plot 2: P Value (Real vs Expected) ---
    ax2 = axes[1]
    # Filter out None values for real P
    real_p_ts = [t for t, p in zip(timestamps, real_p_values) if p is not None]
    real_p_vals = [p for p in real_p_values if p is not None]
    if real_p_vals:
        ax2.plot(real_p_ts, real_p_vals, 'b-', label='Observed P', linewidth=1.5)
    ax2.plot(timestamps, new_algo_p_expected, 'g-', label='New Algo Expected P', linewidth=1.5, alpha=0.8)

    ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    ax2.set_ylabel('P Value')
    ax2.set_title('P Value: Observed vs New Algorithm Expected (P ≈ Supply - Target)')
    ax2.legend(loc='upper left', fontsize=8)
    ax2.grid(True, alpha=0.3)

    # --- Plot 3: Temperature Targets ---
    ax3 = axes[2]
    ax3.plot(timestamps, supply_values, 'b-', label='Supply Actual', linewidth=2)
    ax3.plot(timestamps, real_targets, 'k--', label='Observed Target (HA)', alpha=0.7, linewidth=1)
    ax3.plot(timestamps, new_algo_targets, 'g-', label='New Algo Target', alpha=0.8, linewidth=1.5)

    ax3.set_ylabel('Temperature (°C)')
    ax3.set_title('Supply Temperature & Targets: Observed vs New Algorithm')
    ax3.legend(loc='upper right', fontsize=8)
    ax3.grid(True, alpha=0.3)

    # --- Plot 4: Error (Target - Supply) ---
    ax4 = axes[3]
    real_error = [t - s for t, s in zip(real_targets, supply_values)]
    new_error = [t - s for t, s in zip(new_algo_targets, supply_values)]

    ax4.plot(timestamps, real_error, 'k--', label='Observed Error', alpha=0.7, linewidth=1)
    ax4.plot(timestamps, new_error, 'g-', label='New Algo Error', alpha=0.8, linewidth=1.5)
    ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)

    ax4.set_ylabel('Error (Target - Supply)')
    ax4.set_xlabel('Time')
    ax4.set_title('Control Error: Negative → PID Increases, Positive → PID Decreases')
    ax4.legend(loc='upper right', fontsize=8)
    ax4.grid(True, alpha=0.3)

    # Format x-axis
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax4.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    plt.xticks(rotation=45)

    plt.tight_layout()

    # Save plot
    output_dir = os.path.join(PROJECT_ROOT, "findings")
    os.makedirs(output_dir, exist_ok=True)

    # PNG output
    png_path = os.path.join(output_dir, "algorithm_comparison.png")
    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved PNG: {png_path}")

    # Interactive HTML if plotly available
    if PLOTLY_AVAILABLE and args.interactive:
        fig_plotly = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            subplot_titles=('PID 30m: Observed vs Simulated', 'P Value: Observed vs Expected',
                           'Temperature Targets', 'Control Error'),
            vertical_spacing=0.06
        )

        # Plot 1: PID comparison
        fig_plotly.add_trace(go.Scatter(x=timestamps, y=real_pid_30m,
            name='Observed PID 30m', line=dict(color='blue')), row=1, col=1)
        fig_plotly.add_trace(go.Scatter(x=timestamps, y=new_algo_pid_simulated,
            name='New Algo PID (sim)', line=dict(color='green')), row=1, col=1)

        # Plot 2: P values
        if real_p_vals:
            fig_plotly.add_trace(go.Scatter(x=real_p_ts, y=real_p_vals,
                name='Observed P', line=dict(color='blue')), row=2, col=1)
        fig_plotly.add_trace(go.Scatter(x=timestamps, y=new_algo_p_expected,
            name='New Algo Expected P', line=dict(color='green')), row=2, col=1)

        # Plot 3: Temps and targets
        fig_plotly.add_trace(go.Scatter(x=timestamps, y=supply_values,
            name='Supply Actual', line=dict(color='blue', width=2)), row=3, col=1)
        fig_plotly.add_trace(go.Scatter(x=timestamps, y=real_targets,
            name='Observed Target', line=dict(color='black', dash='dash')), row=3, col=1)
        fig_plotly.add_trace(go.Scatter(x=timestamps, y=new_algo_targets,
            name='New Algo Target', line=dict(color='green')), row=3, col=1)

        # Plot 4: Error
        fig_plotly.add_trace(go.Scatter(x=timestamps, y=real_error,
            name='Observed Error', line=dict(color='black', dash='dash')), row=4, col=1)
        fig_plotly.add_trace(go.Scatter(x=timestamps, y=new_error,
            name='New Algo Error', line=dict(color='green')), row=4, col=1)

        fig_plotly.update_layout(
            title='PID Algorithm Comparison - Full Simulation',
            height=900,
            showlegend=True
        )

        html_path = os.path.join(output_dir, "algorithm_comparison.html")
        fig_plotly.write_html(html_path)
        print(f"Saved interactive HTML: {html_path}")

    # Print summary stats
    print("\n" + "=" * 70)
    print("SIMULATION SUMMARY")
    print("=" * 70)
    print(f"{'Metric':<30} {'Observed':>15} {'New Algo (sim)':>15}")
    print("-" * 60)

    # PID statistics
    real_in_range = sum(1 for p in real_pid_30m if -5 <= p <= 0)
    sim_in_range = sum(1 for p in new_algo_pid_simulated if -5 <= p <= 0)
    total = len(real_pid_30m)

    print(f"{'Final PID 30m':<30} {real_pid_30m[-1]:>15.1f} {new_algo_pid_simulated[-1]:>15.1f}")
    print(f"{'% in target range [-5,0]':<30} {100*real_in_range/total:>14.1f}% {100*sim_in_range/total:>14.1f}%")
    print(f"{'Mean PID 30m':<30} {sum(real_pid_30m)/total:>15.1f} {sum(new_algo_pid_simulated)/total:>15.1f}")

    # Error statistics
    new_positive = sum(1 for e in new_error if e > 0)
    real_positive = sum(1 for e in real_error if e > 0)

    print(f"\n{'Mean target error':<30} {sum(real_error)/total:>15.2f} {sum(new_error)/total:>15.2f}")
    print(f"{'% positive error':<30} {100*real_positive/total:>14.1f}% {100*new_positive/total:>14.1f}%")
    print("(positive error → PID decreases)")

    # P value comparison if available
    if real_p_vals:
        print(f"\n{'Mean P (observed)':<30} {sum(real_p_vals)/len(real_p_vals):>15.2f}")
    print(f"{'Mean P (expected by algo)':<30} {'':>15} {sum(new_algo_p_expected)/total:>15.2f}")

    if not args.no_show:
        plt.show()

    return 0


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

    # plot command
    p_plot = subparsers.add_parser('plot',
        help='Generate visual comparison graphs')
    p_plot.add_argument('--csv', help='Path to comprehensive CSV file')
    p_plot.add_argument('--interactive', '-i', action='store_true',
        help='Also generate interactive HTML (requires plotly)')
    p_plot.add_argument('--no-show', action='store_true',
        help='Save files without displaying')

    args = parser.parse_args()

    if args.command == 'analyze-p':
        cmd_analyze_p(args)
    elif args.command == 'benchmark':
        cmd_benchmark(args)
    elif args.command == 'compare':
        cmd_compare(args)
    elif args.command == 'validate':
        return cmd_validate(args)
    elif args.command == 'plot':
        return cmd_plot(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    sys.exit(main() or 0)
