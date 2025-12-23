# Post-Pool-Heating Transition Management Plan

**Related:** [PID_TEMPERATURE_CONTROL.md](../PID_TEMPERATURE_CONTROL.md) - Phase 3 enhancement

## Problem Statement

The current Phase 3 transition (lines 290-332 in PID_TEMPERATURE_CONTROL.md) is too abrupt:
- Fixed mode disabled immediately → target jumps from ~30°C to ~51°C
- Gear allowed to drop → compressor can't keep up with sudden demand
- PID accumulates debt → overshoot when catching up

After pool heating ends, the system experiences overshoots due to poor gear/supply transition:

```
Timeline Example:
┌─────────────────┬──────────────┬────────────────┬──────────────────┐
│ Phase           │ Supply Temp  │ Target (Curve) │ Gear Behavior    │
├─────────────────┼──────────────┼────────────────┼──────────────────┤
│ Pre-heating     │ 51°C         │ 51°C           │ Stable (e.g., 6) │
│ During heating  │ 43°C         │ Fixed 30°C     │ Min gear (7)     │
│ Post-heating    │ 43°C         │ 51°C (sudden)  │ Drops to 4-5     │
│ Recovery        │ 43→55°C      │ 51°C           │ Jumps to 10      │
│ Overshoot       │ 55°C+        │ 51°C           │ Back to 4        │
└─────────────────┴──────────────┴────────────────┴──────────────────┘
```

### Root Cause Analysis

1. **Sudden target jump**: When fixed mode disabled, target jumps from ~30°C to ~51°C
2. **Large error gap**: Error = 51 - 43 = 8°C (huge negative error)
3. **PID debt accumulates**: Thermia sees "we're 8°C below target" → PID goes positive
4. **Gear drops then spikes**: System first under-reacts, then over-compensates
5. **No transition buffer**: Curve target immediately takes over

## Proposed Solution: Gradual Transition Mode

### Concept

Instead of immediately returning to heat curve:
1. Start from current actual supply temperature
2. Gradually ramp target toward curve target over N minutes
3. Maintain minimum gear during transition to prevent drops
4. Only exit transition when supply approaches curve target

### State Machine Update

```
                    ┌─────────────┐
                    │   IDLE      │
                    └──────┬──────┘
                           │ pool_heating_active = ON
                           ▼
                    ┌─────────────┐
                    │  PREHEAT    │ (comfort wheel +3°C, store pre-heat gear)
                    └──────┬──────┘
                           │ 15 minutes elapsed
                           ▼
         ┌────────────────────────────────────────────┐
         │                                            │
         ▼                                            │
  ┌─────────────┐                                     │
  │ FIXED MODE  │ (PID-feedback algorithm)            │
  │ Block N     │                                     │
  └──────┬──────┘                                     │
         │ block ends                                 │
         ▼                                            │
  ┌────────────────────────┐                          │
  │  TRANSITION            │                          │
  │  - Ramp toward curve   │     next block starts    │
  │  - Gear ≥ pre-heat     │ ─────────────────────────┘
  └───────────┬────────────┘
              │ supply >= curve - TOLERANCE
              │ OR all blocks complete
              ▼
       ┌─────────────┐
       │    IDLE     │
       └─────────────┘
```

**Key change:** Transition happens after EACH block. If another block starts during transition, it's interrupted and we re-enter fixed mode.

## Parameters (All Adjustable via input_number)

| Entity | Default | Description |
|--------|---------|-------------|
| `pool_temp_transition_ramp_rate` | 0.5 °C/min | Target ramp rate toward curve |
| `pool_temp_transition_tolerance` | 2.0 °C | Exit when `abs(supply - curve)` <= this |
| `pool_temp_transition_max_duration` | 30 min | Safety timeout to force exit |
| `pool_temp_pre_heat_gear` | (stored) | Gear before pool heating, used as floor |

## Implementation Approach

### Option A: Fixed Duration Ramp
```python
# Calculate target during transition
elapsed_min = (now - transition_start).total_seconds() / 60
progress = min(1.0, elapsed_min / TRANSITION_DURATION_MIN)

transition_target = start_supply + (curve_target - start_supply) * progress
```

### Option B: Fixed Rate Ramp
```python
# Ramp at constant rate toward curve target
elapsed_min = (now - transition_start).total_seconds() / 60
ramp_amount = TRANSITION_RAMP_RATE * elapsed_min

if curve_target > start_supply:
    transition_target = min(curve_target, start_supply + ramp_amount)
else:
    transition_target = max(curve_target, start_supply - ramp_amount)
```

### Recommendation: Option B (Fixed Rate)

Fixed rate is more predictable regardless of the gap size:
- 8°C gap with 0.5°C/min = 16 minutes
- 4°C gap with 0.5°C/min = 8 minutes
- Larger gaps take proportionally longer (appropriate)

## Implementation Details

### 1. New Entities (pool_temp_control.yaml)

```yaml
input_number:
  # Adjustable parameters
  pool_temp_transition_ramp_rate:
    name: "Pool Temp Transition Ramp Rate"
    min: 0.2
    max: 2.0
    step: 0.1
    unit_of_measurement: "°C/min"
    initial: 0.5

  pool_temp_transition_tolerance:
    name: "Pool Temp Transition Tolerance"
    min: 0.5
    max: 5.0
    step: 0.5
    unit_of_measurement: "°C"
    initial: 2.0

  pool_temp_transition_max_duration:
    name: "Pool Temp Transition Max Duration"
    min: 10
    max: 60
    step: 5
    unit_of_measurement: "min"
    initial: 30

  # State storage
  pool_temp_pre_heat_gear:
    name: "Pool Temp Pre-Heat Gear"
    min: 1
    max: 10
    step: 1
    initial: 6

  pool_temp_transition_start_supply:
    name: "Pool Temp Transition Start Supply"
    min: 20
    max: 60
    step: 0.1
    unit_of_measurement: "°C"
    initial: 40

input_datetime:
  pool_temp_transition_start:
    name: "Pool Temp Transition Start Time"
    has_date: true
    has_time: true

input_boolean:
  pool_temp_transition_active:
    name: "Pool Temp Transition Active"
    initial: false
```

### 2. Pyscript: Store pre-heat gear (in preheat service)

```python
@service
def pool_temp_control_preheat():
    """Start preheat phase - store gear BEFORE modifying anything."""
    # Store current gear as pre-heat baseline
    current_gear = int(float(state.get("sensor.compressor_speed_gear") or 5))
    service.call("input_number", "set_value",
                 entity_id="input_number.pool_temp_pre_heat_gear",
                 value=current_gear)

    log.info(f"Preheat: stored pre-heat gear = {current_gear}")

    # ... rest of existing preheat logic (comfort wheel +3°C, etc.)
```

### 3. Pyscript Service: pool_temp_control_start_transition

```python
@service
def pool_temp_control_start_transition():
    """Start gradual transition from fixed mode back to curve."""
    current_supply = float(state.get("sensor.system_supply_line_temperature"))

    # Store starting point
    service.call("input_number", "set_value",
                 entity_id="input_number.pool_temp_transition_start_supply",
                 value=current_supply)

    # Store start time
    service.call("input_datetime", "set_datetime",
                 entity_id="input_datetime.pool_temp_transition_start",
                 datetime=datetime.now().isoformat())

    # Activate transition mode
    service.call("input_boolean", "turn_on",
                 entity_id="input_boolean.pool_temp_transition_active")

    # Use pre-heat gear as floor (stored before pool heating started)
    pre_heat_gear = int(float(state.get("input_number.pool_temp_pre_heat_gear") or 5))
    service.call("number", "set_value",
                 entity_id="number.minimum_allowed_gear_in_heating",
                 value=pre_heat_gear)

    log.info(f"Transition started: supply={current_supply}°C, min_gear={pre_heat_gear} (pre-heat)")
```

### 4. Pyscript Service: pool_temp_control_adjust_transition

```python
@service
def pool_temp_control_adjust_transition():
    """Called every minute during transition to update target."""
    if not state.get("input_boolean.pool_temp_transition_active") == "on":
        return

    # Get parameters
    start_supply = float(state.get("input_number.pool_temp_transition_start_supply"))
    curve_target = float(state.get("sensor.system_supply_line_calculated_set_point"))
    current_supply = float(state.get("sensor.system_supply_line_temperature"))
    ramp_rate = float(state.get("input_number.pool_temp_transition_ramp_rate"))
    tolerance = float(state.get("input_number.pool_temp_transition_tolerance"))

    # Calculate elapsed time
    start_str = state.get("input_datetime.pool_temp_transition_start")
    start_time = datetime.fromisoformat(start_str)
    elapsed_min = (datetime.now() - start_time).total_seconds() / 60

    # Check exit conditions
    # Use abs() - supply could be above or below curve target
    if abs(current_supply - curve_target) <= tolerance:
        log.info(f"Transition complete: supply {current_supply:.1f}°C within {tolerance}°C of curve {curve_target:.1f}°C")
        pool_temp_control_stop_transition()
        return

    # Safety timeout (adjustable)
    max_duration = float(state.get("input_number.pool_temp_transition_max_duration") or 30)
    if elapsed_min > max_duration:
        log.warning("Transition timeout - forcing exit")
        pool_temp_control_stop_transition()
        return

    # Calculate ramped target
    ramp_amount = ramp_rate * elapsed_min
    if curve_target > start_supply:
        new_target = min(curve_target, start_supply + ramp_amount)
    else:
        new_target = max(curve_target, start_supply - ramp_amount)

    # Set the target
    service.call("number", "set_value",
                 entity_id="number.fixed_system_supply_set_point",
                 value=new_target)

    log.debug(f"Transition: target={new_target:.1f}°C, actual={current_supply:.1f}°C, "
              f"curve={curve_target:.1f}°C, elapsed={elapsed_min:.1f}min")
```

### 5. Pyscript Service: pool_temp_control_stop_transition

```python
@service
def pool_temp_control_stop_transition():
    """Exit transition mode and return to normal curve control."""
    # Disable transition
    service.call("input_boolean", "turn_off",
                 entity_id="input_boolean.pool_temp_transition_active")

    # Disable fixed supply mode - return to curve
    service.call("switch", "turn_off",
                 entity_id="switch.enable_fixed_system_supply_set_point")

    # Restore original minimum gear (stored at pool_temp_control_start)
    original_gear = int(float(state.get("input_number.pool_temp_control_original_min_gear")))
    service.call("number", "set_value",
                 entity_id="number.minimum_allowed_gear_in_heating",
                 value=original_gear)

    log.info("Transition complete - returned to curve control")
```

### 6. Updated Block Stop Sequence

```yaml
# In pool_heating.yaml - pool_heating_block_stop script
sequence:
  # ... existing steps ...

  # Instead of immediately calling stop_temp_control:
  - service: pyscript.pool_temp_control_start_transition

  # Continue with pump mixing etc.
```

### 7. Automation: Transition Adjustment Timer

```yaml
automation:
  - id: pool_temp_transition_adjust
    alias: "Pool Temp: Adjust Transition Target"
    trigger:
      - platform: time_pattern
        minutes: "/1"
    condition:
      - condition: state
        entity_id: input_boolean.pool_temp_transition_active
        state: "on"
    action:
      - service: pyscript.pool_temp_control_adjust_transition
```

### 8. Automation: Interrupt Transition on New Block

```yaml
automation:
  - id: pool_temp_transition_interrupt
    alias: "Pool Temp: Interrupt Transition on Block Start"
    trigger:
      - platform: state
        entity_id: binary_sensor.pool_heating_active
        to: "on"
    condition:
      - condition: state
        entity_id: input_boolean.pool_temp_transition_active
        state: "on"
    action:
      # Stop transition immediately
      - service: input_boolean.turn_off
        target:
          entity_id: input_boolean.pool_temp_transition_active
      # pool_temp_control_start will handle re-entering fixed mode
      - service: system_log.write
        data:
          message: "Transition interrupted - new pool heating block started"
          level: info
```

## Expected Behavior

### Multi-Block Session Example

```
Full Session Timeline (3 blocks with transitions):

PRE-HEAT (20:45-21:00)
├── Store pre-heat gear = 6, comfort +3°C

BLOCK 1 (21:00-21:30) - Fixed mode
├── Supply drops 51→43°C
├── PID controlled via feedback algorithm
└── Gear held ≥ 7

TRANSITION 1 (21:30-21:45)
├── Target ramps 43→47°C (0.5°C/min × 8min before block 2 starts)
├── Gear held ≥ 6 (pre-heat value)
├── Interrupted when block 2 starts
└── Supply recovering: 43→46°C

BLOCK 2 (21:45-22:15) - Fixed mode
├── Re-enter fixed mode, continue PID feedback
├── Supply may drop again during heating
└── Gear held ≥ 7

TRANSITION 2 (22:15-22:30) ...

BLOCK 3 (22:30-23:00) - Fixed mode ...

FINAL TRANSITION (23:00-23:16)
├── No more blocks → full transition to curve
├── Target ramps from current supply to curve (e.g., 43→51°C)
├── Gear held ≥ 6 until supply within 2°C of curve
└── Exit when supply ≥ 49°C (curve - tolerance)

IDLE (23:16+)
├── Fixed mode disabled
├── Gear floor restored to original
└── Normal curve control
```

### Single Transition Detail

```
Post-Block Transition Timeline:
┌───────┬─────────────┬─────────────┬──────────────┬──────────────┐
│ Time  │ Supply Temp │ Target      │ Curve Target │ Gear         │
├───────┼─────────────┼─────────────┼──────────────┼──────────────┤
│ 0 min │ 43°C        │ 43°C        │ 51°C         │ 6 (pre-heat) │
│ 2 min │ 44°C        │ 44°C        │ 51°C         │ 6            │
│ 4 min │ 45°C        │ 45°C        │ 51°C         │ 6            │
│ 6 min │ 46°C        │ 46°C        │ 51°C         │ 6            │
│ 8 min │ 47°C        │ 47°C        │ 51°C         │ 6            │
│ 10min │ 48°C        │ 48°C        │ 51°C         │ 6            │
│ 12min │ 49°C        │ 49°C        │ 51°C         │ → curve exit │
│ 14min │ 50°C        │ (curve)     │ 51°C         │ natural      │
│ 16min │ 51°C        │ (curve)     │ 51°C         │ natural      │
└───────┴─────────────┴─────────────┴──────────────┴──────────────┘
```

Key benefits:
- **No sudden target jump**: Target tracks actual supply, then ramps up
- **Gear held at pre-heat level**: Appropriate for current weather conditions
- **Smooth PID**: Error stays small (~0-1°C) throughout transition
- **No overshoot**: Supply rises smoothly to curve target
- **Inter-block recovery**: Partial recovery between blocks aids radiators

## Testing Plan

1. **Unit tests**: Add tests for transition target calculation
2. **Simulation**: Extend pid_simulation.py to model transition phase
3. **Live test**: Monitor next pool heating session with transition enabled

## Questions for User

1. **Ramp rate**: 0.5°C/min means 16 min for 8°C gap - is this acceptable?
2. **Min gear during transition**: 7 same as during pool heating, or different?
3. **Keep fixed mode during transition**: Or use a different mechanism?

## Files to Modify

| File | Changes |
|------|---------|
| `homeassistant/packages/pool_temp_control.yaml` | Add transition entities, automation |
| `scripts/pyscript/pool_temp_control.py` | Add transition services |
| `homeassistant/packages/pool_heating.yaml` | Update block_stop to use transition |
| `docs/PID_TEMPERATURE_CONTROL.md` | Document transition phase |
| `tests/test_temp_control.py` | Add transition unit tests |

---

## Key Insight: Pre-Heating Gear Preservation

The user's observation about gear dropping is critical:

```
Pre-heating:  Compressor at gear 6, supply = 51°C
Pool heating: Compressor at gear 7 (min floor), supply = 43°C
Post-heating (current): Gear drops to 4-5 (WHY?)
```

### Why Gear Drops

When pool heating ends:
1. Fixed supply mode disables → curve target becomes active
2. Curve target is 51°C, actual supply is 43°C → 8°C error
3. BUT: No accumulated PID debt (our algorithm worked!)
4. Thermia sees "target near supply" and REDUCES power
5. Gear drops because there's no integral driving it up

### The Fix

**Store the pre-heating gear** and use it as minimum during transition:

```python
# In pool_temp_control_start():
pre_heat_gear = state.get("sensor.compressor_speed_gear")  # e.g., 6
state.set("input_number.pool_temp_control_pre_heat_gear", pre_heat_gear)

# In transition:
# Don't allow gear below pre-heating value until supply recovers
min_gear = max(pre_heat_gear, MIN_GEAR_POOL)  # e.g., 6 or 7
```

This ensures:
- Gear never drops below what it was before pool heating started
- Compressor maintains power to catch up supply to curve
- No overshoot because we're ramping target, not slamming it

---

## Design Decisions (Confirmed)

1. **Ramp rate**: 0.5°C/min as starting point, **adjustable via `input_number`**

2. **Gear floor**: Use **pre-heating gear value** (not fixed 7)
   - Reason: In warmer weather, smaller gear (e.g., 4-5) may be appropriate
   - Store gear before pool heating starts, use as floor during transition

3. **Multi-block handling**: Transition **after each block**
   - Block ends → start transition → ramp toward curve
   - Next block starts → transition interrupted, re-enter fixed mode
   - Final block ends → full transition until curve reached

---

## Implementation Priority

1. **Phase 1**: Add transition with fixed duration (20 min), ramp rate 0.5°C/min
2. **Phase 2**: Tune parameters based on real data
3. **Phase 3**: Add adaptive logic (faster ramp if gap is small, etc.)
