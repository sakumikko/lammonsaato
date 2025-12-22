# Pool Heating PID Temperature Control

## Overview

This document describes the PID-Feedback Target Control algorithm used to manage the Thermia Mega heat pump during pool heating operations. The algorithm ensures seamless transitions between pool heating and radiator heating while maintaining room comfort.

**Implementation:** `scripts/pyscript/pool_temp_control.py`

---

## The Problem

### Heat Pump PID Controller Background

The Thermia Mega uses a PID controller to regulate the system supply line temperature. The controller adjusts compressor power based on:

- **Proportional (P):** Immediate response to current error (target - actual)
- **Integral (I):** Accumulated error over time (corrects persistent offset)
- **Derivative (D):** Rate of change (dampens oscillation)

The **30-minute heating integral** (`sensor.heating_season_integral_value`) is the key metric we manage.

### What Happens During Pool Heating Without Control

When pool heating starts:

1. Heat is diverted from radiators to pool heat exchanger
2. Pool water (10-30°C) absorbs heat from condenser (40-50°C)
3. Condenser return temperature drops significantly
4. System supply temperature drops as heat goes to pool instead of radiators
5. If no intervention: PID controller sees supply below target → **integral accumulates**

```
                    ┌─────────────────────────────────────────────────┐
   Normal Mode      │  Curve Target: 40°C                             │
                    │  Actual Supply: 40°C                            │
                    │  Error: 0°C → Integral stable                   │
                    └─────────────────────────────────────────────────┘
                                           │
                                           ▼
                    ┌─────────────────────────────────────────────────┐
   Pool Heating     │  Curve Target: 40°C (unchanged)                 │
   Without Fix      │  Actual Supply: 35°C (heat going to pool)       │
                    │  Error: -5°C → Integral accumulates ++++        │
                    └─────────────────────────────────────────────────┘
```

### The Consequence

When pool heating ends:
- **Large positive integral** remains in the PID controller
- Controller thinks it needs MORE heat (due to accumulated "debt")
- This causes:
  - Delayed radiator response
  - Potential external heater activation
  - System takes 30+ minutes to recover to normal operation

### Observed Data (2025-12-21/22)

Without proper control, PID Integral 30m accumulated significantly:

| Block | Time | PID30 Start | PID30 End | Change |
|-------|------|-------------|-----------|--------|
| 1 | 21:00-21:45 | -0.2 | +29.8 | +30.0 |
| 2 | 23:00-23:45 | +24.5 | +33.7 | +9.2 |
| 3 | 01:00-01:45 | +20.5 | +36.6 | +16.1 |

---

## The Solution

We use a **three-phase strategy**:

1. **Preheat Phase:** Warm radiators before pool heating
2. **Fixed Supply Phase:** Keep PID integral in target range [-5, 0]
3. **Transition Phase:** Graceful return to curve-based control

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         POOL HEATING TIMELINE                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  20:45          21:00              21:30              21:30+           22:00 │
│    │              │                  │                  │               │    │
│    ▼              ▼                  ▼                  ▼               ▼    │
│ ┌──────┐      ┌───────────────────────────┐      ┌──────────┐      ┌──────┐ │
│ │PREHEAT│      │     POOL HEATING BLOCK     │      │TRANSITION│      │BREAK │ │
│ │  +3°C │      │   PID-Feedback Control     │      │  to Curve │      │      │ │
│ │comfort│      │   target = supply + corr   │      │  Pool circ│      │      │ │
│ │ wheel │      │   PID integral ≈ [-5,0]    │      │  continues│      │      │ │
│ └──────┘      └───────────────────────────┘      └──────────┘      └──────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Radiator Preheat

### Purpose

Pre-warm the radiators and condenser before pool heating starts. This:

1. **Stores thermal mass** in radiators (buffer for pool heating period)
2. **Pre-warms condenser** to higher temperature (pool gets more heat)
3. **Reduces initial temperature drop** when pool valve opens

### Mechanism

```
┌─────────────────────────────────────────────────────────────────┐
│  15 min before first pool block                                  │
│                                                                  │
│  1. Store original comfort wheel value                           │
│  2. Raise comfort wheel by +3°C (max 30°C)                       │
│  3. Heat pump increases supply target                            │
│  4. Radiators receive extra heat                                 │
│                                                                  │
│  When pool heating starts:                                       │
│  → Restore original comfort wheel                                │
│  → Radiators have stored thermal energy                          │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

| Entity | Purpose |
|--------|---------|
| `number.comfort_wheel_setting` | Thermia comfort wheel (room temp offset) |
| `input_number.pool_heating_original_comfort_wheel` | Stored original value |
| `input_boolean.pool_heating_preheat_active` | Tracks preheat state |

### Safety

- **Maximum comfort wheel:** 30°C (never exceed)
- **Timeout:** 20 minutes (restore if pool heating doesn't start)
- **Skip if already high:** Don't boost if already at or above 30°C

---

## Phase 2: PID-Feedback Target Control

### Purpose

During pool heating, we override the heat curve with a **fixed supply target** that actively responds to PID integral value, keeping it in the target range [-5, 0].

### The Algorithm

```python
def calculate_new_setpoint(current_supply, prev_supply, pid_30m):
    """
    PID-Feedback Target Control Algorithm

    Goal: Keep PID Integral 30m in range [-5, 0]
    """
    # Configuration
    PID_TARGET = -2.5      # Middle of desired range [-5, 0]
    PID_GAIN = 0.10        # °C correction per unit of PID error
    MIN_CORRECTION = -1.0  # Allow target down to 1°C below supply
    MAX_CORRECTION = 4.0   # Allow target up to 4°C above supply
    MIN_SETPOINT = 28.0    # Minimum allowed temperature
    MAX_SETPOINT = 45.0    # Maximum allowed temperature

    # Calculate PID correction
    pid_error = pid_30m - PID_TARGET
    pid_correction = clamp(pid_error * PID_GAIN, MIN_CORRECTION, MAX_CORRECTION)

    # Calculate target (CORRECTED FORMULA)
    target = current_supply + pid_correction

    return clamp(target, MIN_SETPOINT, MAX_SETPOINT)
```

### Key Insight: Error Direction

The crucial discovery from data analysis:

```
Error = Target - Supply

  Positive error (target > supply) → PID DECREASES
  Negative error (target < supply) → PID INCREASES
```

**This means:**
- When PID is too high (+25), we need positive error to drive it down
- Positive error requires target ABOVE supply
- Therefore: `target = supply + correction` (not minus!)

### Correction Table

| PID30 Value | pid_correction | Target vs Supply | Effect |
|-------------|----------------|------------------|--------|
| +30 | +3.25 | Target 3.25°C above supply | Large positive error → PID decreases |
| +20 | +2.25 | Target 2.25°C above supply | Positive error → PID decreases |
| +10 | +1.25 | Target 1.25°C above supply | Positive error → PID decreases |
| 0 | +0.25 | Target 0.25°C above supply | Small positive error → PID decreases |
| -2.5 | 0.00 | Target equals supply | No error → PID stable |
| -5 | -0.25 | Target 0.25°C below supply | Small negative error → PID increases |
| -10 | -0.75 | Target 0.75°C below supply | Negative error → PID increases |

### Example Calculation

At 21:35 when PID30 = +25 and supply = 39.3°C:

```
pid_error = 25 - (-2.5) = 27.5
pid_correction = min(27.5 × 0.10, 4.0) = 2.75
target = 39.3 + 2.75 = 42.05°C  (above supply!)

Error = 42.05 - 39.3 = +2.75°C (positive)
→ PID will decrease toward target range
```

### Simulation Results

Using real data from 2025-12-21/22 heating sessions:

```
SIMULATION SUMMARY
==================================================================
Metric                              Observed    New Algorithm
------------------------------------------------------------
Final PID 30m                         +36.6           -2.5
% in target range [-5,0]              10.6%          96.5%
Mean PID 30m                          +12.3           -2.3
```

### Implementation

| Entity | Purpose |
|--------|---------|
| `switch.enable_fixed_system_supply_set_point` | Enable fixed mode |
| `number.fixed_system_supply_set_point` | The target value |
| `sensor.heating_season_integral_value` | PID Integral 30m |
| `input_number.pool_heating_original_curve_target` | Stored curve target |
| `sensor.pool_temp_control_setpoint` | Current calculated target |

### Safety Conditions

Two safety checks run **every minute** (FR-44, FR-45):

| Check | Condition | Action |
|-------|-----------|--------|
| FR-44 | Supply < 32°C | Disable fixed mode, safety fallback |
| FR-45 | Supply < curve_target - 15°C | Disable fixed mode, safety fallback |

```
┌─────────────────────────────────────────────────────────────────┐
│  SAFETY CHECK (every 1 minute)                                   │
│                                                                  │
│  if supply_temp < ABSOLUTE_MIN_SUPPLY (32°C):                   │
│      → Disable fixed mode                                        │
│      → Set safety_fallback flag                                  │
│      → Log: "Supply below absolute minimum"                      │
│                                                                  │
│  if supply_temp < original_curve_target - 15°C:                 │
│      → Disable fixed mode                                        │
│      → Set safety_fallback flag                                  │
│      → Log: "Supply dropped too far from curve target"          │
│                                                                  │
│  Pool circulation CONTINUES (no data loss)                       │
│  Heat pump reverts to normal curve control                       │
└─────────────────────────────────────────────────────────────────┘
```

### Compressor Gear Control (FR-46)

During pool heating, we set minimum compressor gear to 7:

```
┌─────────────────────────────────────────────────────────────────┐
│  WHY MINIMUM GEAR = 7?                                           │
│                                                                  │
│  Pool absorbs heat rapidly, causing temperature swings.          │
│  Without gear floor:                                             │
│    → Compressor hunts between gears 2-8                          │
│    → Unstable operation                                          │
│    → Wear on compressor                                          │
│                                                                  │
│  With MIN_GEAR_POOL = 7:                                         │
│    → Compressor stays at gear 7+                                 │
│    → Stable power output                                         │
│    → Sufficient heat for both pool and minimum radiator demand   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 3: Transition to Curve

### Purpose

When pool heating block ends, gracefully return to normal curve-based control while pool circulation continues during break.

### Mechanism

```
┌─────────────────────────────────────────────────────────────────┐
│  POOL HEATING BLOCK ENDS                                         │
│                                                                  │
│  1. DISABLE fixed supply mode                                    │
│     → switch.enable_fixed_system_supply_set_point = OFF          │
│     → Heat pump reverts to heating curve                         │
│                                                                  │
│  2. RESTORE original minimum gear                                │
│     → number.minimum_allowed_gear_in_pool = original value       │
│                                                                  │
│  3. CONTINUE pool circulation                                    │
│     → Pool pump stays on during break                            │
│     → Condenser heat still reaches pool (residual)               │
│                                                                  │
│  4. PID integral in range [-5, 0]                                │
│     → Radiator heating responds immediately                      │
│     → No accumulated "debt" to work off                          │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Works

```
                         Pool Heating          Break (Transition)
                         Block Active          Pool Circ Continues
                              │                       │
                              ▼                       ▼
Supply Target:          Fixed (PID-feedback)  →  Curve (from outdoor temp)
Supply Actual:          35-40°C               →  Rising toward curve
PID Integral:           -5 to 0 (controlled)  →  Stays in normal range
External Heater:        OFF                   →  OFF (no accumulated demand)
Radiator Response:      (paused)              →  IMMEDIATE
```

---

## Complete State Machine

```
                                    ┌─────────────────┐
                                    │     IDLE        │
                                    │  Normal curve   │
                                    │  No pool heat   │
                                    └────────┬────────┘
                                             │
                        15 min before first block
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │    PREHEAT      │
                                    │  Comfort +3°C   │
                                    │  Warm radiators │
                                    └────────┬────────┘
                                             │
                              Pool heating block starts
                                             │
                                             ▼
                                    ┌─────────────────┐
                  ┌────────────────▶│  POOL HEATING   │◀───────────────┐
                  │                 │  Fixed supply   │                │
                  │                 │  PID-Feedback   │                │
                  │                 │  Gear ≥ 7       │                │
                  │                 └───────┬─────────┘                │
                  │                         │                          │
                  │           ┌─────────────┼─────────────┐            │
                  │           │             │             │            │
                  │      Block ends    Safety trip    Timeout 60m      │
                  │           │             │             │            │
                  │           ▼             ▼             ▼            │
                  │     ┌──────────┐  ┌──────────┐  ┌──────────┐       │
                  │     │TRANSITION│  │  SAFETY  │  │ TIMEOUT  │       │
                  │     │ to curve │  │ FALLBACK │  │  STOP    │       │
                  │     │ pool circ│  │ to curve │  │          │       │
                  │     └────┬─────┘  └────┬─────┘  └────┬─────┘       │
                  │          │             │             │             │
                  │          ▼             ▼             ▼             │
                  │     ┌──────────────────────────────────────┐       │
                  │     │               BREAK                   │       │
                  │     │  Normal curve, pool circ continues    │       │
                  │     └──────────────────────────────────────┘       │
                  │                        │                           │
                  │              Next block starts                     │
                  └────────────────────────┴───────────────────────────┘
```

---

## Algorithm Parameters

### PID-Feedback Control

| Parameter | Value | Description |
|-----------|-------|-------------|
| PID_TARGET | -2.5 | Target PID30 value (middle of [-5, 0]) |
| PID_GAIN | 0.10 | °C offset per unit of PID error |
| MIN_CORRECTION | -1.0 | Minimum correction (allow target 1°C below supply) |
| MAX_CORRECTION | 4.0 | Maximum correction (allow target 4°C above supply) |
| MIN_SETPOINT | 28.0 | Minimum allowed fixed setpoint |
| MAX_SETPOINT | 45.0 | Maximum allowed fixed setpoint |

### Safety Thresholds

| Parameter | Value | Description |
|-----------|-------|-------------|
| ABSOLUTE_MIN_SUPPLY | 32.0 | FR-44: Stop if supply below this |
| RELATIVE_DROP_MAX | 15.0 | FR-45: Stop if supply drops this much from curve |
| MIN_GEAR_POOL | 7 | FR-46: Minimum compressor gear during pool heating |

### Preheat Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| PREHEAT_OFFSET | 3.0 | Degrees to raise comfort wheel |
| MAX_COMFORT_WHEEL | 30.0 | Never exceed this value |
| PREHEAT_DURATION | 15 min | Time before pool heating starts |
| PREHEAT_TIMEOUT | 20 min | Restore if pool heating doesn't start |

---

## Tuning Guide

### If PID30 still goes too positive (>0)

- Increase PID_GAIN (e.g., 0.10 → 0.12)
- Increase MAX_CORRECTION (e.g., 4.0 → 5.0)

### If PID30 goes too negative (<-5)

- Decrease PID_GAIN (e.g., 0.10 → 0.08)
- Decrease MIN_CORRECTION (e.g., -1.0 → -0.5)

### If supply drops too low (triggering safety)

- Consider shorter heating blocks
- Check if outdoor temperature is very cold
- Verify heat pump capacity for simultaneous loads

---

## Key Metrics to Monitor

| Metric | Normal Range | Warning |
|--------|--------------|---------|
| `sensor.heating_season_integral_value` | -5 to 0 | > 0 or < -10 |
| `sensor.system_supply_line_temperature` | 28-45°C | < 32°C (FR-44) |
| Target - Supply (Error) | -1 to +4°C | < -2°C consistently |

---

## Files and Services

### Pyscript Services

| Service | Trigger | Purpose |
|---------|---------|---------|
| `pool_temp_control_preheat` | 15 min before first block | Raise comfort wheel |
| `pool_temp_control_start` | Pool heating starts | Enable fixed mode, store values |
| `pool_temp_control_adjust` | Every 5 min during heating | Calculate and apply new target |
| `pool_temp_control_safety_check` | Every 1 min during heating | FR-44, FR-45 checks |
| `pool_temp_control_stop` | Pool heating stops | Disable fixed mode, restore values |
| `pool_temp_control_timeout` | 60 min since start | Hard stop safety |

### Source Files

| File | Purpose |
|------|---------|
| `scripts/pyscript/pool_temp_control.py` | Algorithm implementation |
| `homeassistant/packages/pool_temp_control.yaml` | HA entities and automations |
| `tests/test_temp_control.py` | Unit tests |

---

## Troubleshooting

### PID Integral Goes Positive During Pool Heating

**Symptom:** `sensor.heating_season_integral_value` exceeds +5 during pool heating.

**Possible Causes:**
1. Adjustment service not running - check automation triggers
2. Fixed supply mode not activating - check `switch.enable_fixed_system_supply_set_point`
3. PID_GAIN too low - increase to 0.12

### Radiators Cold After Pool Heating

**Symptom:** Room temperature drops during break period.

**Possible Causes:**
1. Preheat not running - check `input_boolean.pool_heating_preheat_active`
2. Comfort wheel not restoring - check `input_number.pool_heating_original_comfort_wheel`
3. PID integral was not controlled - check algorithm is active

### Safety Fallback Keeps Triggering

**Symptom:** `input_boolean.pool_heating_safety_fallback` goes ON repeatedly.

**Possible Causes:**
1. Pool absorbing too much heat - consider shorter blocks
2. Outdoor temp very cold - curve target high, supply drops too far
3. Heat pump undersized for simultaneous pool + radiator load

---

## Historical Context

### Previous Algorithm (Deprecated)

The original "Chase + Compensation" algorithm used:
```
target = supply - 0.5 - drop_rate
```

This approach had a fundamental flaw: it always set the target BELOW supply, creating negative error, which caused PID to increase rather than decrease. The result was PID30 accumulating to +30 or higher during pool heating.

### Current Algorithm

The PID-Feedback algorithm fixes this by:
1. Reading the actual PID Integral 30m value
2. Calculating correction proportional to how far PID is from target
3. Setting target ABOVE supply when PID is too positive

This creates the positive error needed to drive PID back into the target range [-5, 0].
