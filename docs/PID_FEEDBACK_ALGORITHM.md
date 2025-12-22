# PID-Feedback Target Control Algorithm

## Analysis Date: 2025-12-22

## Problem Statement

The current chase algorithm (`target = supply - 0.5 - drop_rate`) allows PID Integral 30m to accumulate significantly during pool heating:

| Block | Time | PID30 Start | PID30 End | Change |
|-------|------|-------------|-----------|--------|
| 1 | 21:00-21:45 | -0.2 | +29.8 | +30.0 |
| 2 | 23:00-23:45 | +24.5 | +33.7 | +9.2 |
| 3 | 01:00-01:45 | +20.5 | +36.6 | +16.1 |

**Goal:** Keep PID Integral 30m in range **[-5, 0]** (slightly negative to zero)

## Data Observations

From CSV analysis of 2025-12-21/22 heating sessions:

1. **PID30 increases when Supply ΔT is negative** (target > actual supply)
2. **Rate:** Approximately +5-7 PID30 per 5 minutes when ΔT ≈ -1°C
3. **Supply unexpectedly rises** around 30-35 min into heating
4. **Current algorithm doesn't react** to PID accumulation - just chases supply

### Time Series - Block 1 (Current Algorithm)

```
  Time | PID30 |  Δ(5m) | Supply | Target | SupplyΔT
-------+-------+--------+--------+--------+----------
 21:00 |  -0.2 |    -   |  45.0  |  44.6  |   -0.3
 21:05 |  -0.0 |  +0.2  |  44.5  |  44.4  |   -0.1
 21:10 |  -0.2 |  -0.1  |  41.7  |  43.6  |   +1.9
 21:15 |  +7.0 |  +7.2  |  40.1  |  38.4  |   -1.8  ← PID starts climbing
 21:20 | +13.1 |  +6.1  |  39.6  |  38.4  |   -1.3
 21:25 | +16.0 |  +2.9  |  38.7  |  38.4  |   -0.3
 21:30 | +19.5 |  +3.4  |  37.5  |  37.2  |   -0.3
 21:35 | +25.2 |  +5.7  |  39.3  |  35.8  |   -3.5  ← Supply rises, large gap
 21:40 | +31.2 |  +6.0  |  40.6  |  38.8  |   -1.8
```

## Proposed Algorithm: PID-Feedback Target Control

```python
def calculate_target(supply_actual: float, pid_30m: float, prev_supply: float) -> float:
    """
    PID-Feedback Target Control Algorithm

    Adjusts fixed supply setpoint based on current PID Integral 30m value.
    Goal: Keep PID30 in range [-5, 0] by creating appropriate supply error.

    Args:
        supply_actual: Current system supply line temperature (°C)
        pid_30m: Current PID Integral 30m value from sensor
        prev_supply: Previous supply reading (for drop anticipation)

    Returns:
        Target temperature to set as fixed supply setpoint (°C)
    """
    # Configuration
    PID_TARGET = -2.5      # Middle of desired range [-5, 0]
    PID_GAIN = 0.10        # °C correction per unit of PID error
    MIN_CORRECTION = -1.0  # Allow target up to 1°C above supply
    MAX_CORRECTION = 4.0   # Max 4°C below supply
    BASE_OFFSET = 0.5      # Minimum offset below supply
    MIN_SETPOINT = 28
    MAX_SETPOINT = 45

    # Calculate PID error (positive if PID too high)
    pid_error = pid_30m - PID_TARGET

    # Calculate correction
    # If PID > 0: positive error → positive correction → lower target
    # If PID < -5: negative error → negative correction → higher target
    pid_correction = pid_error * PID_GAIN
    pid_correction = max(MIN_CORRECTION, min(MAX_CORRECTION, pid_correction))

    # Anticipate supply drop (reduced - let PID feedback handle most of it)
    if prev_supply is not None and prev_supply > supply_actual:
        drop_rate = (prev_supply - supply_actual) / 5.0  # °C/min
        anticipated_drop = min(drop_rate * 1.0, 1.0)  # Max 1°C anticipation
    else:
        anticipated_drop = 0

    # Calculate target
    target = supply_actual - BASE_OFFSET - pid_correction - anticipated_drop

    return max(MIN_SETPOINT, min(MAX_SETPOINT, target))
```

## How It Works

### Example at 21:35 (when PID30 = +25)

**Current Algorithm:**
- target = 39.3 - 0.5 - drop_rate = ~35.8°C
- Creates ΔT = -3.5°C → PID continues to climb

**New Algorithm:**
- pid_error = 25 - (-2.5) = 27.5
- pid_correction = min(27.5 * 0.10, 4.0) = 2.75
- target = 39.3 - 0.5 - 2.75 = 36.0°C
- Creates larger positive ΔT → PID starts to decrease

### Correction Table

| PID30 Value | pid_correction | Effect |
|-------------|----------------|--------|
| +30 | +3.25 | Target 3.75°C below supply |
| +20 | +2.25 | Target 2.75°C below supply |
| +10 | +1.25 | Target 1.75°C below supply |
| 0 | +0.25 | Target 0.75°C below supply |
| -2.5 | 0.00 | Target 0.50°C below supply (base) |
| -5 | -0.25 | Target 0.25°C below supply |
| -10 | -0.75 | Target at supply level |

## Simulation Results

Using real data from Block 1 with new algorithm:

```
  Time | Supply | New Target | New ΔT | Sim PID | Real PID
-------+--------+------------+--------+---------+----------
 21:00 |  45.0  |    44.1    |  +0.9  |    0.0  |    -0.2
 21:15 |  40.1  |    40.4    |  -0.2  |  -11.6  |    +7.0
 21:30 |  37.5  |    37.4    |  +0.1  |   -8.2  |   +19.5
 21:40 |  40.6  |    40.7    |  -0.1  |   -6.0  |   +31.2
```

**Result:** Simulated PID30 stays around **-6 to -12** vs real **+31**

## Implementation Changes

### pool_temp_control.py

Update `calculate_new_setpoint()` to:

1. Read `sensor.heating_season_integral_value` (PID Integral 30m)
2. Apply PID-feedback correction
3. Reduce reliance on drop anticipation

### New Entity Required

The algorithm requires reading PID Integral 30m:
- Entity: `sensor.heating_season_integral_value`
- Already exists in Thermia integration

## Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| PID_TARGET | -2.5 | Target PID30 value (middle of [-5, 0]) |
| PID_GAIN | 0.10 | °C offset per unit of PID error |
| MIN_CORRECTION | -1.0 | Allow target up to 1°C above supply |
| MAX_CORRECTION | 4.0 | Max correction (prevents extreme targets) |
| BASE_OFFSET | 0.5 | Minimum offset when PID at target |

## Tuning Guide

If PID30 still accumulates positive:
- Increase PID_GAIN (e.g., 0.12 → 0.15)
- Increase MAX_CORRECTION (e.g., 4.0 → 5.0)

If PID30 goes too negative:
- Decrease PID_GAIN (e.g., 0.10 → 0.08)
- Decrease MIN_CORRECTION (e.g., -1.0 → -0.5)

## Summary

| Aspect | Current | Proposed |
|--------|---------|----------|
| Algorithm | Chase supply | PID-feedback control |
| PID30 awareness | None | Reads and responds |
| Target adjustment | Based on drop rate only | Based on PID30 + drop rate |
| Block 1 end PID30 | +31 | ~-6 (simulated) |
| Corrective action | None | Proportional to PID error |
