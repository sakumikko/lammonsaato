# Pool Temperature Control Implementation Plan

## Overview

Implementation of the Chase + Compensation algorithm for controlling fixed supply temperature during pool heating (FR-43 through FR-46).

## Requirements

| ID | Requirement |
|----|-------------|
| FR-43 | Keep 30-minute PID integral close to zero by adjusting fixed supply line target |
| FR-44 | Switch back to radiator heating if supply drops below 32°C |
| FR-45 | Switch back to radiator heating if supply drops >15°C below original target |
| FR-46 | Set minimum compressor gear to 6 during pool heating |

## Algorithm: Chase + Compensation

```python
new_target = current_supply - TARGET_OFFSET - drop_rate
```

Where:
- `current_supply`: Current system supply line temperature
- `TARGET_OFFSET`: 2°C (keep target below supply)
- `drop_rate`: Rate of temperature drop (°C per 5 minutes)

### How It Works

1. Target always stays below actual supply → error term stays positive
2. Positive error means PID doesn't accumulate in "needs heat" direction
3. External heater won't trigger (requires negative integral below threshold)
4. Drop rate compensation anticipates continued drops

### Example Scenario

| Time | Supply | Drop Rate | Target | Supply-Target |
|------|--------|-----------|--------|---------------|
| 0min | 45°C | 0 | 43°C | +2°C |
| 5min | 42°C | 3°C | 37°C | +5°C |
| 10min| 39°C | 3°C | 34°C | +5°C |
| 15min| 37°C | 2°C | 33°C | +4°C |
| 20min| 36°C | 1°C | 33°C | +3°C |

## File Structure

```
scripts/
├── pyscript/
│   ├── pool_heating.py              # Existing - unchanged
│   └── pool_temp_control.py         # NEW - temperature control logic
│
homeassistant/
└── packages/
    ├── pool_heating.yaml             # Existing - unchanged
    └── pool_temp_control.yaml        # NEW - entities & automations

tests/
└── test_temp_control.py              # NEW - algorithm unit tests
```

## New Entities

### Input Numbers (State Storage)
- `input_number.pool_heating_original_curve_target` - Curve target at heating start
- `input_number.pool_heating_original_min_gear` - Original min gear setting
- `input_number.pool_heating_prev_supply_temp` - Previous supply for drop rate

### Input Booleans (Flags)
- `input_boolean.pool_temp_control_active` - Control loop running
- `input_boolean.pool_heating_safety_fallback` - Safety fallback triggered

### Sensors (Monitoring)
- `sensor.pool_fixed_supply_delta` - Current supply - fixed target
- `sensor.pool_supply_drop_rate` - Temperature drop rate (°C/5min)

## Automations

| ID | Trigger | Action |
|----|---------|--------|
| `pool_temp_control_start` | Pool heating ON | Initialize control, enable fixed mode |
| `pool_temp_control_stop` | Pool heating OFF | Disable fixed mode, restore gear |
| `pool_temp_control_adjust` | Every 5 min | Calculate and set new target |
| `pool_temp_control_safety_check` | Every 1 min | Check FR-44, FR-45 thresholds |
| `pool_heating_60min_timeout` | Heating ON for 60min | Force stop for radiator recovery |
| `pool_temp_control_reset_fallback` | 20:00 daily | Clear safety fallback flag |

## Safety Conditions

### FR-44: Absolute Minimum (32°C)
If supply drops below 32°C, pool heating stops immediately. Floor heating requires minimum supply temperature.

### FR-45: Relative Drop (15°C below curve)
If supply drops more than 15°C below the original curve target, pool heating stops. Prevents excessive deviation from normal operation.

### 60-Minute Timeout
Pool heating automatically stops after 60 continuous minutes to allow radiators to recover heat. Existing block structure (30-60 min with equal breaks) normally prevents this.

## Configuration Constants

```python
TARGET_OFFSET = 2.0      # °C below supply
MIN_SETPOINT = 28.0      # Minimum allowed target
MAX_SETPOINT = 45.0      # Maximum allowed target
MIN_GEAR_POOL = 6        # Compressor gear during pool heating
ABSOLUTE_MIN_SUPPLY = 32.0  # FR-44 threshold
RELATIVE_DROP_MAX = 15.0    # FR-45 threshold
```

## Implementation Order

1. ✅ Write unit tests (`tests/test_temp_control.py`)
2. ✅ Run tests - verify FAIL
3. ✅ Create pyscript module (`scripts/pyscript/pool_temp_control.py`)
4. ✅ Run tests - verify PASS
5. ✅ Create HA package (`homeassistant/packages/pool_temp_control.yaml`)
6. ✅ Update mock server with new entities
7. ✅ Run full regression
8. Deploy to HA and observe during pool heating

## Dependencies

- Thermia integration with fixed supply entities enabled:
  - `switch.enable_fixed_system_supply_set_point`
  - `number.fixed_system_supply_set_point`
  - `number.minimum_allowed_gear_in_heating_mode`
- pythermiagenesis fork with KeyError fix (already deployed)

## Testing

### Unit Tests
```bash
./env/bin/python -m pytest tests/test_temp_control.py -v
```

### Manual HA Testing
```yaml
# Developer Tools → Services
service: pyscript.pool_temp_control_start
# Then monitor entities in States
```

### Observation During Pool Heating
1. Watch `sensor.pool_fixed_supply_delta` - should stay positive
2. Watch `sensor.heating_season_integral_value` - should stay stable
3. Watch `sensor.external_heater_demand` - should stay low/zero

## Rollback

If issues occur:
1. Disable automations `pool_temp_control_*` in HA
2. Turn off `switch.enable_fixed_system_supply_set_point`
3. Restore original `number.minimum_allowed_gear_in_heating_mode` if changed

## Related Documents

- `docs/PRODUCT_REQUIREMENTS.md` - Section 4.6 Pool Heating Temperature Control
- `docs/plans/FIXED_SUPPLY_INVESTIGATION.md` - Investigation notes
- `docs/plans/PYTHERMIAGENESIS_FIX.md` - Library bug fix
