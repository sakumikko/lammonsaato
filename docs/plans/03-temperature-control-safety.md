# Implementation Plan 03: Temperature Control & Safety for Cold Weather

**Depends on:** Plan 01 (entities exist)
**Findings source:** Review 03

## Goal

In cold weather mode, replace per-block PID control toggling with window-level fixed supply management. Tighten safety thresholds. The changes are conditional -- normal mode is unaffected.

## Design: Window-Level Control

Instead of toggling fixed supply mode 10 times per night (once per block), enable it once at heating window start and disable once at window end.

### New Automations (pool_temp_control.yaml or pool_heating.yaml)

#### 1. Cold Weather Mode Enabled

When user turns on cold weather mode, start window-level control:

```yaml
automation:
  - alias: pool_cold_weather_mode_on
    trigger:
      - platform: state
        entity_id: input_boolean.pool_heating_cold_weather_mode
        to: "on"
    condition:
      - condition: state
        entity_id: input_boolean.pool_heating_enabled
        state: "on"
    action:
      - service: pyscript.pool_cold_weather_start
```

#### 2. Cold Weather Mode Disabled

When user turns off cold weather mode, stop window-level control:

```yaml
  - alias: pool_cold_weather_mode_off
    trigger:
      - platform: state
        entity_id: input_boolean.pool_heating_cold_weather_mode
        to: "off"
    action:
      - service: pyscript.pool_cold_weather_stop
```

**Note:** No window start/end times needed. User selects which hours to run via checkboxes in UI. Fixed supply mode stays enabled the entire time cold weather mode is ON.

### New Pyscript Services (pool_temp_control.py)

#### pool_cold_weather_start()

1. Store original curve target (`ORIGINAL_CURVE_TARGET`)
2. Store original min gear (`ORIGINAL_MIN_GEAR`)
3. Store original comfort wheel (`ORIGINAL_COMFORT_WHEEL`)
4. Enable fixed supply mode with conservative setpoint: `curve_target - 2.0`
5. Set min gear to `max(9, MIN_GEAR_ENTITY, live_compressor_gear)` -- **not fixed 7!**
6. Optionally raise comfort wheel by +1C (mild boost, not the +3C of normal mode)
7. Mark `CONTROL_ACTIVE = on`
8. Log action

```python
# Gear formula: max of 9, current MIN_GEAR setting, and live compressor gear
COMPRESSOR_GEAR_SENSOR = "sensor.compressor_gear"  # or actual entity ID
cold_weather_min_gear = max(9,
    _safe_get_float(MIN_GEAR_ENTITY, 1),
    _safe_get_float(COMPRESSOR_GEAR_SENSOR, 1))
```

Total Modbus writes: 4 (setpoint, enable, gear, comfort wheel)

#### pool_cold_weather_stop()

1. Disable fixed supply mode
2. Restore original min gear
3. Restore original comfort wheel
4. Mark `CONTROL_ACTIVE = off`
5. Log action

Total Modbus writes: 3 (disable, gear, comfort wheel)

**Total for entire night: 7 Modbus writes** (vs ~70 with per-block toggling).

### Safety Threshold Changes (pool_temp_control.py)

Add cold weather thresholds as constants:

```python
# Cold weather safety thresholds (tighter than normal)
COLD_WEATHER_MIN_SUPPLY = 38.0      # vs 32.0 normal (FR-44-CW)
COLD_WEATHER_RELATIVE_DROP = 12.0   # vs 15.0 normal (FR-45-CW) -- per user feedback
```

Modify `check_safety_conditions()` to accept a `cold_weather` parameter:

```python
def check_safety_conditions(current_supply, original_curve, cold_weather=False):
    min_supply = COLD_WEATHER_MIN_SUPPLY if cold_weather else ABSOLUTE_MIN_SUPPLY
    max_drop = COLD_WEATHER_RELATIVE_DROP if cold_weather else RELATIVE_DROP_MAX
    # ... rest unchanged
```

The safety check automation (`pool_temp_control_safety_check`) already runs every 1 min. Modify it to pass the cold weather flag:

```python
@service
def pool_temp_control_safety_check():
    cold_weather = state.get("input_boolean.pool_heating_cold_weather_mode") == "on"
    # ... existing logic ...
    safe, reason = check_safety_conditions(current_supply, original_curve, cold_weather)
```

If safety triggers in cold weather:
- Disable fixed supply mode (same as normal)
- Set `SAFETY_FALLBACK = on` (same as normal)
- This prevents remaining blocks from heating (block_start checks safety_fallback)
- Notify user (same as normal)

### What Does NOT Change

- `pool_temp_control_adjust()` -- still runs every 5 min but only when `CONTROL_ACTIVE = on`. In cold weather, control IS active (window-level), so this will adjust the fixed setpoint. This is actually fine -- PID feedback over the entire window makes more sense than per-block.
- `pool_temp_control_preheat()` -- never called in cold weather (block_start skips it).
- `pool_temp_control_timeout()` -- 60-min timeout still available as failsafe. Won't trigger for 5-min blocks but protects against bugs.

### Block Start/Stop Interaction

In cold weather, the block start script (Plan 01) does NOT call `pool_temp_control_start()`. Fixed supply is already enabled from 21:00. It only operates switches (pump ON, prevention OFF).

Similarly, block stop does NOT call `pool_temp_control_stop()`. Fixed supply stays on until 07:00. It only operates switches (prevention ON, pump OFF after post-mix).

## Unit Tests

Add to existing `tests/test_pool_temp_control.py` or new `tests/test_cold_weather.py`:

```python
def test_cold_weather_safety_tighter_absolute():
    """FR-44-CW: safety triggers at 38C (not 32C)."""
    safe, _ = check_safety_conditions(37.0, 50.0, cold_weather=True)
    assert not safe

def test_cold_weather_safety_tighter_relative():
    """FR-45-CW: safety triggers at 12C drop (not 15C)."""
    safe, _ = check_safety_conditions(37.0, 50.0, cold_weather=True)
    assert not safe  # 50 - 37 = 13 > 12 relative max

def test_cold_weather_safety_relative_passes():
    """FR-45-CW: 11C drop is OK."""
    safe, _ = check_safety_conditions(39.0, 50.0, cold_weather=True)
    assert safe  # 50 - 39 = 11 < 12 relative max

def test_normal_mode_safety_unchanged():
    """Normal mode uses original thresholds."""
    safe, _ = check_safety_conditions(37.0, 50.0, cold_weather=False)
    assert safe  # 37 > 32 absolute min
    safe, _ = check_safety_conditions(41.0, 50.0, cold_weather=False)
    assert safe  # 50 - 41 = 9 < 15 relative max
```

## Risks

1. **PID adjust during window**: With `CONTROL_ACTIVE = on` for the entire window, the PID adjust automation fires every 5 min (even between blocks). This is actually beneficial -- it keeps the setpoint tracking the actual supply temperature. Between blocks (no pool heating), PID should be near target. Monitor for unexpected setpoint drift.

2. **Thermia hourly reload**: Could collide with the window-level fixed supply. Add condition to `thermia_hourly_reload` automation: skip if `pool_temp_control_active` is on AND `cold_weather_mode` is on.
