# Review Plan 04: Web UI & HA Entities for Cold Weather Mode

## Objective

Review the web UI components and Home Assistant entity configuration to determine what changes are needed to support cold weather mode selection, display, and configuration.

## Context

The user needs to be able to:
- Enable/disable cold weather mode
- See the cold weather schedule in the UI (10 short blocks instead of 2-4 long blocks)
- Configure cold weather parameters (block duration, pre/post circulation time)

## Files to Review

| File | What to look for |
|------|-----------------|
| `homeassistant/packages/pool_heating.yaml` | Input entities, sensors, block entity definitions (10 blocks) |
| `web-ui/src/components/heating/SchedulePanel.tsx` | Schedule display, block rendering |
| `web-ui/src/components/heating/ScheduleEditor.tsx` | Schedule parameter editor (dropdowns) |
| `web-ui/src/hooks/useHomeAssistant.ts` | Entity data fetching and type definitions |
| `web-ui/src/types/` | TypeScript type definitions |
| `web-ui/e2e/` | Existing E2E tests |
| `scripts/mock_server/` | Mock server entity definitions |

## Review Checklist

### 1. HA Entity Configuration (pool_heating.yaml)

#### New Entities Needed
- [ ] `input_boolean.pool_heating_cold_weather_mode` - Toggle for cold weather mode
- [ ] `input_number.pool_heating_cold_block_duration` - Block duration in cold weather (min: 5, max: 15, step: 5?)
- [ ] `input_number.pool_heating_cold_pre_circulation` - Pre-circulation pump time (minutes)
- [ ] `input_number.pool_heating_cold_post_circulation` - Post-circulation pump time (minutes)
- [ ] Or: should cold weather mode have fixed parameters (no user configuration)?

#### Existing Entities to Review
- [ ] `input_number.pool_heating_min_block_duration` (min: 30) - Should this accept 5 in cold weather mode?
- [ ] `input_number.pool_heating_max_block_duration` (min: 30) - Same question
- [ ] `input_number.pool_heating_total_hours` (step: 0.5) - 50 min doesn't align with 0.5h steps
- [ ] Block entities (10 blocks): `pool_heat_block_X_start/end/price/cost/enabled/cost_exceeded` - sufficient for cold weather (10 hours * 1/hr = 10)
- [ ] What if someone wants 2 blocks per hour? That's 20 blocks. Current 10-block limit would be insufficient.

### 2. Schedule Panel Display (SchedulePanel.tsx)
- [ ] Block list rendering - 10 blocks (cold weather) vs 2-4 blocks (normal). UI may get cluttered.
- [ ] Block duration display - currently shows "30 min", "45 min". Need to handle "5 min".
- [ ] Total minutes display - `data-testid="total-minutes"`. Will show "50 min" for cold weather.
- [ ] Price color coding - same logic applies (green <2c, yellow <5c, red >=5c).
- [ ] Cost display - very small costs per block (5 min * 5 kW = 0.42 kWh per block).
- [ ] Toggle switches - should cold weather blocks be individually toggleable? Probably yes.
- [ ] Visual distinction - should cold weather blocks look different? (icon, color, badge?)

### 3. Schedule Editor (ScheduleEditor.tsx)
- [ ] Mode selector - need a toggle or radio: Normal / Cold Weather
- [ ] When cold weather mode selected:
  - [ ] Min/Max block duration dropdowns should offer [5, 10, 15] instead of [30, 45, 60]
  - [ ] Or: hide min/max and show single "block duration" dropdown
  - [ ] Total hours selector may need different options
  - [ ] Pre/post circulation time inputs (if configurable)
- [ ] Cost constraint - still relevant? Probably less so.
- [ ] Save action - must pass mode flag to pyscript service call
- [ ] Warning during heating window - same logic applies

### 4. Data Flow (useHomeAssistant.ts)
- [ ] Entity reading - must include new cold weather entities
- [ ] Type definitions - add cold weather mode fields
- [ ] Schedule info parsing - `input_text.pool_heating_schedule_info` format may change
- [ ] Schedule JSON parsing - `input_text.pool_heating_schedule_json` structure may change

### 5. Mock Server (scripts/mock_server/)
- [ ] Must add new cold weather entities to mock responses
- [ ] Mock calculate service must handle cold weather mode
- [ ] Test data should include cold weather schedule examples

### 6. Block Entity Capacity
- [ ] Current: 10 block entities (`pool_heat_block_1` through `pool_heat_block_10`)
- [ ] Normal mode: typically 2-6 blocks. Fine.
- [ ] Cold weather at 1 block/hour for 10 hours: exactly 10 blocks. Tight but OK.
- [ ] Cold weather at 2 blocks/hour: needs 20 block entities. NOT enough.
- [ ] Decision: limit cold weather to 1 block/hour, or expand block entities?

### 7. E2E Tests
- [ ] Existing tests focus on normal mode schedule. Need cold weather test scenarios.
- [ ] Test: toggle cold weather mode, verify editor shows correct options
- [ ] Test: save cold weather schedule, verify 10 blocks displayed
- [ ] Test: verify block durations show "5 min" not "30 min"

## Questions to Answer

1. Should cold weather be a simple toggle, or have configurable parameters?
2. How should the UI visually distinguish cold weather blocks from normal blocks?
3. Is 10 block entities enough for cold weather mode?
4. Should cost constraint be disabled/hidden in cold weather mode?
5. How should the schedule editor UX change for cold weather mode?
6. Should the mode be auto-detected from outdoor temperature, or manual only?

## Output Instructions

After completing this review, write findings to:
**`docs/reviews/04-web-ui-entities-findings.md`**

The findings file must contain:
1. **New Entities**: Complete list of new HA entities needed with types and ranges
2. **UI Changes**: Mockup descriptions of what the UI should look like in cold weather mode
3. **Editor Changes**: How ScheduleEditor.tsx needs to change
4. **Panel Changes**: How SchedulePanel.tsx needs to change
5. **Type Changes**: TypeScript type additions
6. **Mock Server Changes**: What to add to mock server
7. **E2E Test Scenarios**: List of test cases for cold weather mode
8. **Block Capacity Decision**: Whether 10 blocks is sufficient
