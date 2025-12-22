# Pool Heating PID Management Strategy

## Overview

This document describes the strategy for managing the Thermia Mega heat pump's PID controller during pool heating operations. The goal is to ensure seamless transitions between pool heating and radiator heating while maintaining room comfort.

## The Problem

### Heat Pump PID Controller Background

The Thermia Mega uses a PID controller to regulate the system supply line temperature. The controller adjusts compressor power based on:

- **Proportional (P):** Immediate response to current error (target - actual)
- **Integral (I):** Accumulated error over time (corrects persistent offset)
- **Derivative (D):** Rate of change (dampens oscillation)

The **30-minute heating integral** (`sensor.heating_season_integral_value`) is the key metric we manage.

### What Happens During Pool Heating

When pool heating starts:

1. Heat is diverted from radiators to pool heat exchanger
2. Pool water (10-30°C) absorbs heat from condenser (40-50°C)
3. Condenser return temperature drops significantly
4. System supply temperature drops as heat goes to pool instead of radiators
5. PID controller sees supply below target → **integral accumulates**

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

## The Solution

We use a **three-phase strategy**:

1. **Preheat Phase:** Warm radiators before pool heating
2. **Fixed Supply Phase:** Keep PID integral near zero during pool heating
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
│ │  +3°C │      │    Fixed Supply Mode       │      │  to Curve │      │      │ │
│ │comfort│      │    Chase + Compensate      │      │  Pool circ│      │      │ │
│ │ wheel │      │    PID integral ≈ 0        │      │  continues│      │      │ │
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

## Phase 2: Fixed Supply Target (Chase + Compensation)

### Purpose

During pool heating, we override the heat curve with a **fixed supply target** that:

1. **Tracks the actual supply** (target ≈ supply - 0.5°C)
2. **Keeps PID error near zero** (prevents integral accumulation)
3. **Allows pool to receive heat** (condenser still warm)

### The Algorithm

```
┌─────────────────────────────────────────────────────────────────┐
│                CHASE + COMPENSATION ALGORITHM                    │
│                                                                  │
│  Every 5 minutes:                                                │
│                                                                  │
│    drop_rate = max(0, prev_supply - current_supply)              │
│    new_target = current_supply - TARGET_OFFSET - drop_rate       │
│    new_target = clamp(new_target, MIN_SETPOINT, MAX_SETPOINT)    │
│                                                                  │
│  Where:                                                          │
│    TARGET_OFFSET = 0.5°C  (keeps target slightly below supply)   │
│    MIN_SETPOINT  = 28°C   (never go below)                       │
│    MAX_SETPOINT  = 45°C   (never go above)                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Why 0.5°C Offset?

```
                    ┌───────────────────────────────────────────────┐
   If offset = 0    │  Target exactly equals supply                 │
                    │  Any noise → target > supply → negative error │
                    │  Negative integral → delayed recovery         │
                    └───────────────────────────────────────────────┘

                    ┌───────────────────────────────────────────────┐
   If offset = 2.0  │  Target 2°C below supply                      │
                    │  Error = -2°C → large positive integral       │
                    │  +24 units in 5 min → delayed recovery        │
                    └───────────────────────────────────────────────┘

                    ┌───────────────────────────────────────────────┐
   If offset = 0.5  │  Target 0.5°C below supply                    │ ← CHOSEN
                    │  Error ≈ -0.5°C → small stable integral       │
                    │  +2 units in 5 min → fast recovery            │
                    └───────────────────────────────────────────────┘
```

### Drop Rate Compensation

When supply temperature is falling (pool absorbing heat):

```
Example:
  Previous supply: 40°C
  Current supply:  38°C
  Drop rate:       2°C (40 - 38)

  New target = 38 - 0.5 - 2 = 35.5°C

  This ANTICIPATES further drop, keeping target ahead of actual
```

### Implementation

| Entity | Purpose |
|--------|---------|
| `switch.enable_fixed_system_supply_set_point` | Enable fixed mode |
| `number.fixed_system_supply_set_point` | The target value |
| `input_number.pool_heating_original_curve_target` | Stored curve target |
| `input_number.pool_heating_prev_supply_temp` | Previous reading |
| `sensor.pool_temp_control_setpoint` | Current calculated target |
| `sensor.pool_supply_drop_rate` | Rate of temperature drop |

### Safety Conditions

Two safety checks run **every minute**:

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
│  if supply_temp < original_curve_target - RELATIVE_DROP_MAX:     │
│      → Disable fixed mode                                        │
│      → Set safety_fallback flag                                  │
│      → Log: "Supply dropped too far from curve target"          │
│                                                                  │
│  Pool circulation CONTINUES (no data loss)                       │
│  Heat pump reverts to normal curve control                       │
└─────────────────────────────────────────────────────────────────┘
```

### Compressor Gear Control

During pool heating, we set minimum compressor gear to 6:

```
┌─────────────────────────────────────────────────────────────────┐
│  WHY MINIMUM GEAR = 6?                                           │
│                                                                  │
│  Pool absorbs heat rapidly, causing temperature swings.          │
│  Without gear floor:                                             │
│    → Compressor hunts between gears 2-8                          │
│    → Unstable operation                                          │
│    → Wear on compressor                                          │
│                                                                  │
│  With MIN_GEAR_POOL = 6:                                         │
│    → Compressor stays at gear 6+                                 │
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
│  4. PID integral ≈ 0                                             │
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
Supply Target:          Fixed (tracks)  →  Curve (from outdoor temp)
Supply Actual:          35-40°C         →  Rising toward curve
PID Error:              ≈ -0.5°C        →  ≈ 0 (small positive)
PID Integral:           +2 (stable)     →  Decays quickly to 0
External Heater:        OFF             →  OFF (no accumulated demand)
Radiator Response:      (paused)        →  IMMEDIATE
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
                  │                 │  Chase + Comp   │                │
                  │                 │  Gear ≥ 6       │                │
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

## Key Metrics to Monitor

| Metric | Normal Range | Warning |
|--------|--------------|---------|
| `sensor.heating_season_integral_value` | -10 to +10 | > +20 or < -20 |
| `sensor.pool_supply_drop_rate` | 0-2°C | > 5°C |
| `sensor.pool_fixed_supply_delta` | -1 to +1°C | > 3°C |
| `sensor.system_supply_line_temperature` | 28-45°C | < 32°C (FR-44) |

---

## Files and Services

### Pyscript Services

| Service | Trigger | Purpose |
|---------|---------|---------|
| `pool_temp_control_preheat` | 15 min before first block | Raise comfort wheel |
| `pool_temp_control_start` | Pool heating starts | Enable fixed mode, store values |
| `pool_temp_control_adjust` | Every 5 min during heating | Chase + Compensation |
| `pool_temp_control_safety_check` | Every 1 min during heating | FR-44, FR-45 checks |
| `pool_temp_control_stop` | Pool heating stops | Disable fixed mode, restore values |
| `pool_temp_control_timeout` | 60 min since start | Hard stop safety |

### Source Files

| File | Purpose |
|------|---------|
| `scripts/pyscript/pool_temp_control.py` | Algorithm implementation |
| `homeassistant/packages/pool_temp_control.yaml` | HA entities and automations |
| `tests/test_temp_control.py` | Unit tests (31 tests) |

---

## Troubleshooting

### PID Integral Still Accumulating

**Symptom:** `sensor.heating_season_integral_value` reaches +20 or higher during pool heating.

**Possible Causes:**
1. `TARGET_OFFSET` too large - reduce to 0.5 or lower
2. Fixed supply mode not activating - check `switch.enable_fixed_system_supply_set_point`
3. Adjustment interval too long - check automation triggers

### Radiators Cold After Pool Heating

**Symptom:** Room temperature drops during break period.

**Possible Causes:**
1. Preheat not running - check `input_boolean.pool_heating_preheat_active`
2. Comfort wheel not restoring - check `input_number.pool_heating_original_comfort_wheel`
3. Safety fallback triggered - check `input_boolean.pool_heating_safety_fallback`

### Safety Fallback Keeps Triggering

**Symptom:** `input_boolean.pool_heating_safety_fallback` goes ON repeatedly.

**Possible Causes:**
1. Pool absorbing too much heat - consider shorter blocks
2. Outdoor temp very cold - curve target high, supply drops too far
3. Heat pump undersized for simultaneous pool + radiator load

---

## Configuration Tuning

### Conservative (Prioritize Radiators)

```yaml
TARGET_OFFSET: 1.0      # Larger gap, more integral accumulation
MIN_SETPOINT: 32.0      # Higher floor
PREHEAT_OFFSET: 5.0     # More preheat warmth
```

### Aggressive (Maximize Pool Heating)

```yaml
TARGET_OFFSET: 0.0      # Minimal gap (watch for noise issues)
MIN_SETPOINT: 25.0      # Lower floor
PREHEAT_OFFSET: 2.0     # Less preheat (faster transition)
```

### Balanced (Recommended)

```yaml
TARGET_OFFSET: 0.5      # Small stable gap
MIN_SETPOINT: 28.0      # Safe floor
PREHEAT_OFFSET: 3.0     # Moderate preheat
```
