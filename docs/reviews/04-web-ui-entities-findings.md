# Review 04 Findings: Web UI & HA Entities for Cold Weather Mode

**Date:** 2026-02-02
**Reviewer:** Claude (automated review)
**Files reviewed:** pool_heating.yaml, SchedulePanel.tsx, ScheduleEditor.tsx, useHomeAssistant.ts, types/heating.ts, mock server, E2E tests

---

## 1. New HA Entities Needed

### Recommended: Simple toggle + fixed cold weather parameters

| Entity ID | Type | Range/Values | Purpose |
|-----------|------|-------------|---------|
| `input_boolean.pool_heating_cold_weather_mode` | input_boolean | on/off | Master toggle for cold weather mode |
| `input_number.pool_heating_cold_block_duration` | input_number | min:5, max:15, step:5 | Block duration in cold weather (5/10/15 min) |
| `input_number.pool_heating_cold_pre_circulation` | input_number | min:0, max:10, step:1 | Pre-circulation time (minutes) |
| `input_number.pool_heating_cold_post_circulation` | input_number | min:0, max:10, step:1 | Post-circulation time (minutes) |

**Rationale:** A simple toggle is better than auto-detection for now. The user knows when cold weather protection is needed. Fixed parameters are too rigid since 5/10/15 min are all valid choices.

### Existing entities -- no changes needed to definitions

- `input_number.pool_heating_min_block_duration` (line 384-390): min:30, max:60. Do NOT change this entity's range. Cold weather uses `cold_block_duration` instead. The normal-mode entity stays unchanged.
- `input_number.pool_heating_max_block_duration` (line 392-398): Same -- leave unchanged.
- `input_number.pool_heating_total_hours` (line 400-405): step:0.5, max:5. For cold weather 50 min = 0.833h which does not align with 0.5 step. **Decision: cold weather mode should compute total from block count and duration, not use this entity.** The pyscript algorithm will derive total_minutes = cold_block_duration * num_slots (1 per hour in heating window).

---

## 2. Block Capacity Decision

**Current:** 10 block entities (`pool_heat_block_1` through `pool_heat_block_10`).

| Mode | Blocks needed | Fits in 10? |
|------|--------------|-------------|
| Normal (2-5h, 30-60 min blocks) | 2-10 | Yes |
| Cold weather, 1 block/hour, 10h window | 10 | Exactly, tight |
| Cold weather, 2 blocks/hour | 20 | No |

**Decision: Limit cold weather to 1 block per hour (max 10 blocks).** Expanding to 20 block entities doubles the entity count (120+ entities to add to YAML, mock server, recorder, etc.) for minimal benefit. One 5-15 min pump cycle per hour is sufficient for freeze prevention.

---

## 3. UI Changes -- SchedulePanel.tsx

**Current state** (line 115-211): Renders blocks in a vertical list with switch toggle, time range, duration, price, and cost. Each block takes ~40px height.

### Changes needed for cold weather mode:

**A. Compact block rendering for 10 blocks:** The current layout works but will be tall (400px+ for 10 blocks). Options:
- **Recommended:** Add a compact mode when block count > 6. Show blocks in a 2-column grid instead of single column. Remove individual toggle switches (all-or-nothing for cold weather). Keep time, duration, and price.
- Line 175-177: Duration display `{block.duration}min` already handles any value. "5min" will render fine.

**B. Visual distinction for cold weather blocks:** Add a snowflake icon or blue tint when `coldWeatherMode` is active.
- Line 151-155: Icon selection logic. Add cold weather branch: if `coldWeatherMode`, show `Snowflake` icon instead of `Clock`.
- Line 126-133: Block styling. Add a cold weather CSS class (e.g., `bg-blue-500/10 border-blue-500/30`).

**C. Cost display for tiny blocks:** At 5 min and 5 kW, each block costs ~0.42 kWh * price. At 3c/kWh this is ~1.3 cents per block. The `costEur?.toFixed(2)` on line 205 would show "0.01" which is fine.

**D. Total minutes display (line 216):** Already works -- will show "50 min" or whatever the total is.

---

## 4. Editor Changes -- ScheduleEditor.tsx

**Current state** (line 34): `BLOCK_DURATIONS = [30, 45, 60]` -- hardcoded normal-mode durations.

### Changes needed:

**A. Cold weather mode toggle:** Add a toggle/switch at the top of the editor panel (above the parameter row on line 175). When toggled:
- Hide min/max block dropdowns (lines 176-224). Cold weather uses a single `cold_block_duration` dropdown.
- Show single "Block duration" dropdown with options [5, 10, 15] (minutes).
- Hide "Total hours" dropdown (lines 226-253). Total is computed automatically (1 block per hour * window hours).
- Show pre/post circulation time inputs (if configurable).
- Cost constraint (lines 255-287) can remain visible -- still relevant for deciding how many hourly slots to skip.

**B. Conditional duration constants:** Add `COLD_BLOCK_DURATIONS = [5, 10, 15]` alongside existing `BLOCK_DURATIONS`.

**C. Save action (line 99-121):** Must pass cold weather mode flag to pyscript. The `setScheduleParameters` call needs to include `coldWeatherMode: boolean` and `coldBlockDuration: number`.

**D. getValidTotalHours (line 41-47):** Not used in cold weather mode. Total is automatic.

**E. Validation (line 96):** `isValid = editParams.minBlockDuration <= editParams.maxBlockDuration` -- not applicable in cold weather mode where there is only one duration. Override to `isValid = true` when cold weather.

---

## 5. Data Flow Changes -- useHomeAssistant.ts

**ENTITIES const (line 59-144):** Add `coldWeatherMode`, `coldBlockDuration`, `coldPreCirculation`, `coldPostCirculation` mapped to the 4 new HA entities.

**ScheduleParameters type (types/heating.ts line 51-56):** Add `coldWeatherMode: boolean`, `coldBlockDuration: number`, `coldPreCirculation: number`, `coldPostCirculation: number`.

**ScheduleState type (line 58-66):** No change needed. Blocks array already handles variable counts.

**buildState (line 442-447):** Parse cold weather fields into `parameters` using `parseBoolean`/`parseNumber`.

**setScheduleParameters (line 709-750):** Add handlers for the 4 new entities.

**New function:** `setColdWeatherMode(enabled: boolean)` -- toggles the input_boolean and triggers recalculation.

---

## 6. Mock Server Changes

### state_manager.py

- `_get_default_state` (line 61-186): Add defaults for new cold weather entities. `cold_weather_mode` defaults to "off", `cold_block_duration` to "5", circulation times to "2".
- `update_schedule_parameters` (line 429-434): Add cold weather parameters.

### server.py

- `MockState` class (line 148-217): Add `cold_weather_mode: bool = False`, `cold_block_duration: int = 5`.
- `/api/block-enabled` (line 500): Bug -- hardcoded `1-4` range. Should be `1-10`. This is a pre-existing bug.
- `ScheduleParameters` model (line 233-237): Add cold weather fields.
- `/api/calculate` (line 340): Must handle cold weather mode by calling a different algorithm path (1 block/hour with short duration).

### entity_signatures.json

Add 4 new entity signatures for the cold weather entities.

---

## 7. E2E Test Scenarios

Existing tests (13 spec files) cover normal-mode schedule. New cold weather tests needed:

| Test | Description |
|------|-------------|
| Toggle cold weather mode | Open editor, toggle cold weather, verify editor shows [5,10,15] duration options |
| Save cold weather schedule | Toggle cold weather, set 10min duration, save, verify 10 blocks displayed |
| Block duration display | In cold weather mode, verify blocks show "5 min" or "10 min" not "30 min" |
| Compact layout trigger | With 10 cold weather blocks, verify blocks render in compact mode |
| Total minutes calculation | 10 blocks * 5 min = 50 min total displayed |
| Mode persistence | Toggle cold weather on, reload page, verify mode is still on |
| Switch back to normal | Toggle cold weather off, verify editor shows [30,45,60] durations |
| Cost constraint in cold weather | Set cost limit, verify some cold weather blocks disabled |

---

## 8. Answers to Review Questions

**Q1: Simple toggle or configurable parameters?**
Toggle + configurable block duration (5/10/15). Pre/post circulation can default to 2 min each and be configurable for power users.

**Q2: Visual distinction for cold weather blocks?**
Snowflake icon + blue-tinted background. Compact 2-column layout when >6 blocks.

**Q3: 10 block entities enough?**
Yes, if limited to 1 block/hour. This is the recommended approach.

**Q4: Cost constraint in cold weather mode?**
Keep it available but not prominent. In cold weather the priority is freeze prevention, not cost savings. The UI should show it collapsed/secondary.

**Q5: Schedule editor UX for cold weather?**
Toggle at top of editor. When cold weather: single duration dropdown [5/10/15], hide min/max/total. Show pre/post circulation fields.

**Q6: Auto-detect from outdoor temp or manual only?**
Manual only for now. Auto-detection could be added later as `automation` in YAML that toggles `input_boolean.pool_heating_cold_weather_mode` based on outdoor temp threshold (e.g., below -5C). This keeps the UI and pyscript simple.

---

## 9. Pre-existing Issues Found

1. **server.py line 500:** Block enabled endpoint hardcoded to `1-4` range. Should be `1-10` to match actual entity count.
2. **ScheduleEditor.tsx line 43:** `useScheduleEditor` called conditionally inside a component (`if onScheduleParametersChange && onRecalculate`). This violates React's Rules of Hooks. Works in practice because the condition is stable, but should be refactored.
3. **SchedulePanel.tsx line 139:** `onBlockEnabledChange(index + 1, checked)` -- block number derived from rendered index, not from original entity index. If blocks are filtered (e.g., only valid blocks shown), this could map to the wrong entity. Currently safe because `useHomeAssistant.ts` only includes valid blocks sequentially.
