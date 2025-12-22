# Fixed System Supply Setpoint Investigation

**Branch:** `feature/fixed-supply-pool-heating`
**Date:** 2024-12-14

## Problem Statement

During pool heating, the heat pump controller uses the house heating curve to calculate supply temperature setpoint. This causes issues:

1. System supply target comes from house heat curve (designed for radiators)
2. Supply temp sensor is in poor position relative to pool loop
3. Large error between calculated target and actual supply
4. PID freaks out → integral goes massively negative
5. Compressor + external heater demand increases unnecessarily

## Proposed Solution

Enable **fixed system supply setpoint** during pool-only operation:

- Set a low, fixed target (e.g., 28-32°C) instead of heat curve
- Reduces error between target and actual
- Keeps PID and integral stable
- Reduces/avoids external heater demand

## Phase 1: Entity Validation

### 1.1 Enable Required Entities

Add to `scripts/config/thermia_required_entities.yaml`:

```yaml
  # ============================================
  # FIXED_SUPPLY_CONTROLS - For pool heating mode
  # ============================================
  fixed_supply_controls:
    description: "Fixed system supply setpoint for pool-only operation"
    entities:
      - switch.enable_fixed_system_supply_set_point
      - number.fixed_system_supply_set_point
```

### 1.2 Run Entity Sync Script

```bash
./env/bin/python scripts/standalone/sync_thermia_entities.py
```

### 1.3 Verify Entities Available

```bash
# Check entities are enabled and have valid states
curl -s -H "Authorization: Bearer $HA_TOKEN" \
  "http://192.168.50.11:8123/api/states/switch.enable_fixed_system_supply_set_point"

curl -s -H "Authorization: Bearer $HA_TOKEN" \
  "http://192.168.50.11:8123/api/states/number.fixed_system_supply_set_point"
```

Expected:
- Switch: `off` (normal curve mode)
- Number: Some value (e.g., 30-40°C)

### 1.4 Document Entity Attributes

Record min/max/step for the number entity to understand valid range.

## Phase 2: Baseline Behavior (No Changes)

### 2.1 Capture Current Pool Heating Session

Monitor a complete pool heating block (30-45 min) with existing behavior:

**Entities to record:**
| Entity | Purpose |
|--------|---------|
| `sensor.system_supply_line_calculated_set_point` | Heat curve target |
| `sensor.system_supply_line_temperature` | Actual supply temp |
| `sensor.supply_line_temperature_difference` | Error (target - actual) |
| `sensor.external_heater_pid_sum` | PID output |
| `sensor.i_value_for_gear_shifting_and_demand_calculation` | Integral component |
| `sensor.external_additional_heater_current_demand` | Heater demand % |
| `sensor.compressor_speed_rpm` | Compressor load |
| `sensor.condenser_out_temperature` | Pool heat delivery |
| `sensor.pool_heat_exchanger_delta_t` | Pool delta-T |

**Use web UI:** `/graphs` with Comprehensive Analysis preset, 1h range

**Export CSV:** For later comparison

### 2.2 Record Key Metrics

| Metric | Baseline Value |
|--------|---------------|
| Supply setpoint (from curve) | ___ °C |
| Actual supply temp | ___ °C |
| Supply delta (error) | ___ °C |
| PID sum (typical range) | ___ to ___ |
| Integral value (trend) | ___ |
| External heater demand | ___ % |
| Pool delta-T | ___ °C |

## Phase 3: Manual Test (Via HA Developer Tools)

### 3.1 Pre-Test Checklist

- [ ] Pool heating block scheduled in next 30-60 min
- [ ] Web UI graphs page open with Comprehensive Analysis
- [ ] CSV export ready for comparison

### 3.2 Test Procedure

**Before pool heating starts:**

1. Set fixed supply setpoint value:
   ```yaml
   service: number.set_value
   target:
     entity_id: number.fixed_system_supply_set_point
   data:
     value: 30  # Start conservative
   ```

2. DO NOT enable the switch yet - wait for pool heating to start

**When pool heating activates (prevention OFF, pump ON):**

3. Enable fixed supply mode:
   ```yaml
   service: switch.turn_on
   target:
     entity_id: switch.enable_fixed_system_supply_set_point
   ```

4. Monitor for 10-15 minutes:
   - Does `sensor.system_supply_line_calculated_set_point` change to 30°C?
   - Does supply delta (error) reduce?
   - Does PID sum stabilize?
   - Does integral stop accumulating negatively?
   - Does external heater demand decrease?

**When pool heating block ends:**

5. Disable fixed supply mode:
   ```yaml
   service: switch.turn_off
   target:
     entity_id: switch.enable_fixed_system_supply_set_point
   ```

6. Verify system returns to curve-based control

### 3.3 Record Test Results

| Metric | Fixed Mode Value | Change from Baseline |
|--------|-----------------|---------------------|
| Supply setpoint | 30 °C (fixed) | ___ °C lower |
| Actual supply temp | ___ °C | |
| Supply delta (error) | ___ °C | ___ °C smaller |
| PID sum range | ___ to ___ | |
| Integral trend | ___ | stable? |
| External heater demand | ___ % | ___ % lower |
| Pool delta-T | ___ °C | similar? |

### 3.4 Safety Checks

- [ ] House heating not affected (should be off in summer anyway)
- [ ] DHW heating not affected
- [ ] Compressor operates normally
- [ ] No alarms triggered
- [ ] Pool still gets heat (delta-T positive)

## Phase 4: Iterate Setpoint Value

If Phase 3 shows promise, test different setpoint values:

| Test | Setpoint | Result |
|------|----------|--------|
| A | 28°C | |
| B | 30°C | |
| C | 32°C | |
| D | 35°C | |

Find the **minimum effective value** that:
- Delivers adequate pool heat (delta-T > 3°C)
- Keeps PID stable (no wild oscillations)
- Minimizes external heater demand

## Phase 5: Automation Implementation

### 5.1 Detection Logic

Pool-only operation = both conditions true:
- `binary_sensor.pool_heating_active` = ON
- `sensor.first_prioritised_demand` = "Pool" (verify exact state value)

### 5.2 Automation Triggers

**Enter fixed mode:**
```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.pool_heating_active
    to: "on"
condition:
  - condition: state
    entity_id: sensor.first_prioritised_demand
    state: "Pool"  # Verify exact value
action:
  - service: number.set_value
    target:
      entity_id: number.fixed_system_supply_set_point
    data:
      value: 30
  - service: switch.turn_on
    target:
      entity_id: switch.enable_fixed_system_supply_set_point
```

**Exit fixed mode:**
```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.pool_heating_active
    to: "off"
action:
  - service: switch.turn_off
    target:
      entity_id: switch.enable_fixed_system_supply_set_point
```

### 5.3 Safety Considerations

- What if HA restarts while in fixed mode?
  - On startup: check pool_heating_active, turn off fixed mode if not heating
- What if user manually starts house heating?
  - Monitor first_prioritised_demand, exit fixed mode if not pool
- Maximum time limit?
  - Maybe auto-disable after 2 hours as failsafe

## Test Cycle Summary

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Enable entities in HA (sync script)                      │
│ 2. Verify entities available and readable                   │
│ 3. Record baseline pool heating session (no changes)        │
│ 4. Manual test: enable fixed mode during pool heating       │
│ 5. Compare metrics: baseline vs fixed mode                  │
│ 6. Iterate setpoint value (28-35°C range)                   │
│ 7. Write automation if results positive                     │
│ 8. Test automation over multiple heating cycles             │
│ 9. Monitor for regressions (house heating, DHW)             │
└─────────────────────────────────────────────────────────────┘
```

## Files to Modify

| File | Changes |
|------|---------|
| `scripts/config/thermia_required_entities.yaml` | Add fixed_supply_controls group |
| `homeassistant/packages/pool_heating.yaml` | Add automations (after validation) |
| `web-ui/src/constants/entityPresets.ts` | Add fixed supply entities to graphs |

## Success Criteria

Phase 3 is successful if:
- [ ] Supply delta (error) reduced by > 50%
- [ ] PID sum stays within ±10 (not wild swings)
- [ ] Integral doesn't go massively negative
- [ ] External heater demand ≤ 20% (ideally 0%)
- [ ] Pool still receives heat (delta-T > 2°C)
- [ ] No alarms or unexpected behavior
