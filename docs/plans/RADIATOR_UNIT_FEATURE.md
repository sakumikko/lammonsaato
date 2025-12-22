# RadiatorUnit Feature - System Supply Temperatures

**Status:** TDD Step 2 - Tests written, need to verify they fail
**Branch:** feature/fixed-supply-pool-heating
**Date:** 2025-12-20

## Requirement

The RadiatorUnit component should show:
1. **System supply line temperature** (actual current temp)
2. **Calculated target** (from heat curve)
3. **Fixed target** (fixed supply setpoint)
4. Clear indication of which target mode is active (fixed vs curve)
5. Stable layout - positions don't jump based on active mode

## Entities to Use

| Entity | Description | Status |
|--------|-------------|--------|
| `sensor.system_supply_line_temperature` | Current supply temp | Works (address 12) |
| `sensor.system_supply_line_calculated_set_point` | Heat curve target | Works (address 18) |
| `number.fixed_system_supply_set_point` | Fixed target value | Works (after pythermiagenesis fix) |
| `switch.enable_fixed_system_supply_set_point` | Fixed mode toggle | Works (after pythermiagenesis fix) |

## TDD Progress

### Step 1: E2E Test Written ✅
File: `web-ui/e2e/radiator-unit.spec.ts`

Tests:
1. `should display system supply line temperature` - expects `[data-testid="supply-temp"]`
2. `should display calculated target temperature from heat curve` - expects `[data-testid="curve-target"]`
3. `should display fixed supply target temperature` - expects `[data-testid="fixed-target"]`
4. `should indicate which target mode is active` - expects `[data-testid="active-target-indicator"]`
5. `should keep layout stable - positions do not change based on active mode`

### Step 2: Run Tests - Verify FAIL ⏳
Need to run: `cd web-ui && npx playwright test e2e/radiator-unit.spec.ts`
Expected: All 5 tests FAIL (data-testid attributes don't exist yet)

### Step 3: Implement Feature (PENDING)
Files to modify:
- `web-ui/src/components/heating/RadiatorUnit.tsx` - Update props and UI
- `web-ui/src/hooks/useHomeAssistant.ts` - Add new entity mappings
- `scripts/mock_server/` - Add mock data for new entities

### Step 4: Run Tests - Verify PASS (PENDING)

### Step 5: Full Regression (PENDING)

## UI Design Notes

- Keep curve and fixed targets in fixed positions (e.g., curve always first)
- Use visual indicator (highlight, badge, icon) for active mode
- Inactive mode shows "last known" value with muted styling
- Example layout:
  ```
  Supply: 32.5°C
  ┌─────────────────┬─────────────────┐
  │ Curve Target    │ Fixed Target    │
  │ 35.0°C ●ACTIVE  │ 30.0°C          │
  └─────────────────┴─────────────────┘
  ```

## Related Work This Session

1. **pythermiagenesis KeyError fix** - User deployed fix from fork
2. **Sensor warnings fixed** - state_class and timestamp handling in pool_heating.yaml
3. **test_system_temps.py** - Script to read registers 12 and 27 via Modbus
