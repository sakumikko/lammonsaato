# Implementation Plan: New Pool Heating Features

## Overview

Implement three new features for the pool heating system:
1. **Target Temperature Control** - Stop heating when target temp reached, skip remaining night blocks
2. **Block Enable/Disable** - Allow users to skip individual heating blocks
3. **Web UI Controls** - Add block enable toggles to existing UI (target temp slider already exists)

## Existing Web UI Status

The Lämmönsäätö web UI add-on already includes:
- ✅ `ControlPanel.tsx` - Has target temperature slider (20-32°C) and Scheduled Heating toggle
- ✅ `SchedulePanel.tsx` - Shows schedule blocks with times and prices
- ✅ `useHomeAssistant.ts` - WebSocket integration with HA entities

**What's missing:**
- Block enable/disable toggles in SchedulePanel
- Night complete status display
- Backend entities and automations for these features

---

## Feature 1: Target Temperature Check

### Problem
Currently, heating runs for the full scheduled duration regardless of pool temperature. This wastes energy if the pool is already warm.

### Solution
Add a temperature check that:
- Monitors pool return line temperature during heating
- Stops current heating block when target is reached
- Sets a flag to skip remaining blocks for the night

### Implementation

#### 1.1 New Entity: Night Session Skip Flag
```yaml
input_boolean:
  pool_heating_night_complete:
    name: "Pool Heating Night Complete"
    icon: mdi:check-circle
```
- Reset to OFF when schedule is calculated (new night)
- Set to ON when target temp reached during heating

#### 1.2 Modify Block Start Automations
Add condition to each block start automation:
```yaml
condition:
  - condition: state
    entity_id: input_boolean.pool_heating_night_complete
    state: "off"
```

#### 1.3 New Automation: Target Temperature Monitor
```yaml
automation:
  - id: pool_target_temp_reached
    alias: "Pool: Stop When Target Reached"
    trigger:
      - platform: numeric_state
        entity_id: sensor.pool_return_line_temperature_corrected
        above: input_number.pool_target_temperature
    condition:
      - condition: state
        entity_id: binary_sensor.pool_heating_active
        state: "on"
    action:
      - service: script.pool_heating_block_stop
      - service: input_boolean.turn_on
        target:
          entity_id: input_boolean.pool_heating_night_complete
      - service: notify.persistent_notification
        data:
          title: "Pool Heating Complete"
          message: "Target temperature {{ states('input_number.pool_target_temperature') }}°C reached. Remaining blocks skipped."
```

#### 1.4 Update Pyscript
In `calculate_pool_heating_schedule()`, reset the night complete flag:
```python
input_boolean.pool_heating_night_complete = "off"
```

---

## Feature 2: Individual Block Enable/Disable

### Problem
Users cannot skip specific heating blocks (e.g., if one block has an unusually high price for the day).

### Solution
Add enable/disable toggles for each heating block (1-4).

### Implementation

#### 2.1 New Entities: Block Enable Toggles
```yaml
input_boolean:
  pool_heat_block_1_enabled:
    name: "Block 1 Enabled"
    icon: mdi:checkbox-marked
  pool_heat_block_2_enabled:
    name: "Block 2 Enabled"
    icon: mdi:checkbox-marked
  pool_heat_block_3_enabled:
    name: "Block 3 Enabled"
    icon: mdi:checkbox-marked
  pool_heat_block_4_enabled:
    name: "Block 4 Enabled"
    icon: mdi:checkbox-marked
```

#### 2.2 Default Behavior
- All blocks default to enabled when schedule is calculated
- Pyscript `calculate_pool_heating_schedule` sets all `pool_heat_block_N_enabled` to ON

#### 2.3 Modify Block Start Automations
Add condition to each block start automation (in addition to night_complete check):
```yaml
condition:
  - condition: state
    entity_id: input_boolean.pool_heat_block_N_enabled
    state: "on"
  - condition: state
    entity_id: input_boolean.pool_heating_night_complete
    state: "off"
```

#### 2.4 Update Recorder
Add new entities to recorder include list.

---

## Feature 3: Web UI Updates

### Problem
Users cannot enable/disable individual blocks from the web UI.

### Solution
Add block enable toggles to existing `SchedulePanel.tsx`.

### Implementation

#### 3.1 Update useHomeAssistant.ts
Add new entities to ENTITIES mapping:
```typescript
// In ENTITIES const
blockEnabled1: 'input_boolean.pool_heat_block_1_enabled',
blockEnabled2: 'input_boolean.pool_heat_block_2_enabled',
blockEnabled3: 'input_boolean.pool_heat_block_3_enabled',
blockEnabled4: 'input_boolean.pool_heat_block_4_enabled',
nightComplete: 'input_boolean.pool_heating_night_complete',
```

Add control function:
```typescript
const setBlockEnabled = useCallback(async (block: number, enabled: boolean) => {
  const entityId = `input_boolean.pool_heat_block_${block}_enabled`;
  await ws.current.callService('input_boolean', enabled ? 'turn_on' : 'turn_off', {
    entity_id: entityId,
  });
}, []);
```

#### 3.2 Update types/heating.ts
```typescript
interface PriceBlock {
  start: string;
  end: string;
  price: number;
  duration: number;
  enabled: boolean;  // NEW
}

interface PoolHeatingState {
  // ...existing fields
  nightComplete: boolean;  // NEW
}
```

#### 3.3 Update SchedulePanel.tsx
Add toggle switch to each block row:
```tsx
import { Switch } from '@/components/ui/switch';

// In the block map, add toggle:
<Switch
  checked={block.enabled}
  onCheckedChange={(checked) => onBlockEnabledChange(index + 1, checked)}
  className="ml-2"
/>
```

Add night complete status indicator:
```tsx
{poolHeating.nightComplete && (
  <div className="flex items-center gap-2 text-success">
    <CheckCircle className="w-4 h-4" />
    <span className="text-sm">Target reached - remaining blocks skipped</span>
  </div>
)}
```

#### 3.4 Update Index.tsx
Pass new props through to SchedulePanel:
```tsx
<SchedulePanel
  schedule={state.schedule}
  nightComplete={state.poolHeating.nightComplete}
  onBlockEnabledChange={setBlockEnabled}
/>
```

---

## Implementation Order

1. **Phase 1: Backend (pool_heating.yaml + pyscript)**
   - Add 5 new input_boolean entities
   - Add target temp reached automation
   - Modify 4 block start automations with new conditions
   - Update pyscript to reset flags and enable all blocks on schedule calculation
   - Add new entities to recorder

2. **Phase 2: Web UI Updates**
   - Update `useHomeAssistant.ts` - add entities and control function
   - Update `types/heating.ts` - add enabled and nightComplete fields
   - Update `SchedulePanel.tsx` - add toggle switches and night complete indicator
   - Update `Index.tsx` - pass new props
   - Rebuild addon with `./build-addon.sh`

3. **Phase 3: Testing**
   - Deploy to HA and verify entities created
   - Test block enable/disable from UI
   - Test target temp stop behavior
   - Verify night complete flag resets on new schedule

---

## Files to Modify

| File | Changes |
|------|---------|
| `homeassistant/packages/pool_heating.yaml` | Add 5 input_booleans, 1 automation, modify 4 automations, update recorder |
| `scripts/pyscript/pool_heating.py` | Reset night_complete flag, enable all blocks on schedule calc |
| `web-ui/src/hooks/useHomeAssistant.ts` | Add entity mappings, add setBlockEnabled function |
| `web-ui/src/types/heating.ts` | Add enabled to PriceBlock, nightComplete to PoolHeatingState |
| `web-ui/src/components/heating/SchedulePanel.tsx` | Add Switch toggles, night complete indicator |
| `web-ui/src/pages/Index.tsx` | Pass onBlockEnabledChange prop |

## New Entities Summary

| Entity ID | Type | Purpose |
|-----------|------|---------|
| `input_boolean.pool_heating_night_complete` | input_boolean | Flag when target temp reached |
| `input_boolean.pool_heat_block_1_enabled` | input_boolean | Block 1 enable toggle |
| `input_boolean.pool_heat_block_2_enabled` | input_boolean | Block 2 enable toggle |
| `input_boolean.pool_heat_block_3_enabled` | input_boolean | Block 3 enable toggle |
| `input_boolean.pool_heat_block_4_enabled` | input_boolean | Block 4 enable toggle |

**Existing entities used (no changes):**
- `input_number.pool_target_temperature` - Target temp (already in UI)
- `input_boolean.pool_heating_enabled` - Master toggle (already in UI)
- `sensor.pool_return_line_temperature_corrected` - For target temp comparison
