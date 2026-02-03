# Cold Weather Mode - Implementation Tasks

**Branch:** `claude/cold-weather-heating-cycles-FiiJZ`
**TDD Required:** Yes - all tests must fail before implementation

## Task Execution Order

Based on plan dependencies:
- Plan 01 (HA entities) → first, no dependencies
- Plan 02 (algorithm) → depends on 01
- Plan 03 (temp control) → depends on 01, parallel with 02
- Plan 04 (UI) → depends on 01 and 02

---

## Phase 1: Write Tests First (TDD)

### Task 1.1: Write Python unit tests for cold weather algorithm
**Plan:** 02
**File:** `tests/test_cold_weather.py`
**Tests to write:**
- [ ] `test_cold_weather_fixed_offset` - all blocks start at :05
- [ ] `test_cold_weather_block_count` - count matches enabled hours
- [ ] `test_cold_weather_block_duration` - duration matches config
- [ ] `test_cold_weather_all_enabled` - no cost constraint
- [ ] `test_cold_weather_invalid_duration_fallback` - falls back to 5 min
- [ ] `test_cold_weather_empty_hours` - returns empty list
- [ ] `test_cold_weather_invalid_hours_ignored` - filters bad values
- [ ] `test_cold_weather_sorted_by_time` - chronological order
- [ ] `test_normal_mode_unchanged` - regression test

**Verification:** Run `pytest tests/test_cold_weather.py` - all must FAIL

### Task 1.2: Write Python unit tests for temperature control safety
**Plan:** 03
**File:** `tests/test_cold_weather.py` (same file)
**Tests to write:**
- [ ] `test_cold_weather_safety_tighter_absolute` - 38C threshold
- [ ] `test_cold_weather_safety_tighter_relative` - 12C drop threshold
- [ ] `test_cold_weather_safety_relative_passes` - 11C drop OK
- [ ] `test_normal_mode_safety_unchanged` - regression test

**Verification:** Run `pytest tests/test_cold_weather.py` - all must FAIL

### Task 1.3: Write E2E tests for cold weather UI
**Plan:** 04
**File:** `web-ui/e2e/cold-weather.spec.ts`
**Tests to write:**
- [ ] `toggle shows cold weather controls` - shows 5/10/15 duration, hides normal controls
- [ ] `hour grid toggles correctly` - can select/deselect hours
- [ ] `save produces blocks for selected hours` - block count matches
- [ ] `blocks show short durations` - 5min displayed
- [ ] `switching back to normal restores controls` - normal mode still works

**Verification:** Run `npx playwright test e2e/cold-weather.spec.ts` - all must FAIL

---

## Phase 2: Home Assistant Entities (Plan 01)

### Task 2.1: Add new entities to pool_heating.yaml
**File:** `homeassistant/packages/pool_heating.yaml`
**Changes:**
- [ ] Add `input_boolean.pool_heating_cold_weather_mode`
- [ ] Add `input_text.pool_heating_cold_enabled_hours` (max: 100)
- [ ] Add `input_number.pool_heating_cold_block_duration` (5/10/15)
- [ ] Add `input_number.pool_heating_cold_pre_circulation` (0-10)
- [ ] Add `input_number.pool_heating_cold_post_circulation` (0-10)

### Task 2.2: Fix schedule JSON overflow bug
**File:** `homeassistant/packages/pool_heating.yaml`
**Change:**
- [ ] Update `input_text.pool_heating_schedule_json` max from 255 to 1024

### Task 2.3: Modify block start script with choose conditional
**File:** `homeassistant/packages/pool_heating.yaml` (~line 1318)
**Changes:**
- [ ] Wrap existing sequence in `choose` conditional
- [ ] Add cold weather branch: pre-circ → wait → prevention OFF → log
- [ ] Keep normal mode as `default` branch unchanged
- [ ] Set `mode: restart` on script

### Task 2.4: Modify block stop script with choose conditional
**File:** `homeassistant/packages/pool_heating.yaml` (~line 1342)
**Changes:**
- [ ] Wrap existing sequence in `choose` conditional
- [ ] Add cold weather branch: prevention ON → log → post-circ → pump OFF
- [ ] Keep normal mode as `default` branch unchanged

---

## Phase 3: Schedule Algorithm (Plan 02)

### Task 3.1: Add cold weather constants to pyscript
**File:** `scripts/pyscript/pool_heating.py` (~line 33)
**Changes:**
- [ ] Add `COLD_WEATHER_VALID_DURATIONS = [5, 10, 15]`
- [ ] Add `COLD_WEATHER_BLOCK_OFFSET = 5`

### Task 3.2: Implement generate_cold_weather_schedule function
**File:** `scripts/pyscript/pool_heating.py`
**Function:**
- [ ] Parse enabled_hours_str to list of integers
- [ ] Validate and filter invalid hours (0-23 only)
- [ ] Create block at :05 past each enabled hour
- [ ] Set duration from block_duration_minutes
- [ ] All blocks enabled (no cost constraint)
- [ ] Sort blocks by start time
- [ ] Return list of block dicts

### Task 3.3: Modify calculate_pool_heating_schedule service
**File:** `scripts/pyscript/pool_heating.py` (~line 585)
**Changes:**
- [ ] Check `input_boolean.pool_heating_cold_weather_mode` state
- [ ] If on: read enabled hours and duration, call generate_cold_weather_schedule
- [ ] If off: existing price optimization (unchanged)
- [ ] Write blocks to entities (same for both modes)

### Task 3.4: Run algorithm unit tests
**Verification:** `pytest tests/test_cold_weather.py -v` - algorithm tests must PASS

---

## Phase 4: Temperature Control & Safety (Plan 03)

### Task 4.1: Add cold weather safety constants
**File:** `scripts/pyscript/pool_temp_control.py`
**Changes:**
- [ ] Add `COLD_WEATHER_MIN_SUPPLY = 38.0`
- [ ] Add `COLD_WEATHER_RELATIVE_DROP = 12.0`

### Task 4.2: Modify check_safety_conditions for cold weather
**File:** `scripts/pyscript/pool_temp_control.py`
**Changes:**
- [ ] Add `cold_weather=False` parameter
- [ ] Use tighter thresholds when cold_weather=True

### Task 4.3: Implement pool_cold_weather_start service
**File:** `scripts/pyscript/pool_temp_control.py`
**Function:**
- [ ] Store original curve target, min gear, comfort wheel
- [ ] Enable fixed supply with conservative setpoint
- [ ] Set min gear to max(9, MIN_GEAR_ENTITY, live_compressor_gear)
- [ ] Set CONTROL_ACTIVE = on
- [ ] Log action

### Task 4.4: Implement pool_cold_weather_stop service
**File:** `scripts/pyscript/pool_temp_control.py`
**Function:**
- [ ] Disable fixed supply mode
- [ ] Restore original min gear
- [ ] Restore original comfort wheel
- [ ] Set CONTROL_ACTIVE = off
- [ ] Log action

### Task 4.5: Add cold weather mode automations
**File:** `homeassistant/packages/pool_heating.yaml`
**Changes:**
- [ ] Add `pool_cold_weather_mode_on` automation (triggers pyscript.pool_cold_weather_start)
- [ ] Add `pool_cold_weather_mode_off` automation (triggers pyscript.pool_cold_weather_stop)

### Task 4.6: Run safety unit tests
**Verification:** `pytest tests/test_cold_weather.py -v` - safety tests must PASS

---

## Phase 5: Web UI & Mock Server (Plan 04)

### Task 5.1: Add TypeScript types
**File:** `web-ui/src/types/heating.ts`
**Changes:**
- [ ] Add `coldWeatherMode: boolean` to ScheduleParameters
- [ ] Add `coldEnabledHours: string`
- [ ] Add `coldBlockDuration: number`
- [ ] Add `coldPreCirculation: number`
- [ ] Add `coldPostCirculation: number`

### Task 5.2: Update useHomeAssistant hook - entity mappings
**File:** `web-ui/src/hooks/useHomeAssistant.ts` (~line 59)
**Changes:**
- [ ] Add `coldWeatherMode` entity mapping
- [ ] Add `coldEnabledHours` entity mapping
- [ ] Add `coldBlockDuration` entity mapping
- [ ] Add `coldPreCirculation` entity mapping
- [ ] Add `coldPostCirculation` entity mapping

### Task 5.3: Update useHomeAssistant hook - buildState
**File:** `web-ui/src/hooks/useHomeAssistant.ts` (~line 442)
**Changes:**
- [ ] Parse `coldWeatherMode` as boolean
- [ ] Parse `coldEnabledHours` with default
- [ ] Parse `coldBlockDuration` as number
- [ ] Parse `coldPreCirculation` as number
- [ ] Parse `coldPostCirculation` as number

### Task 5.4: Update useHomeAssistant hook - setScheduleParameters
**File:** `web-ui/src/hooks/useHomeAssistant.ts` (~line 709)
**Changes:**
- [ ] Add handler for cold weather mode toggle
- [ ] Add handler for enabled hours text
- [ ] Add handler for block duration
- [ ] Add handler for pre/post circulation

### Task 5.5: Update ScheduleEditor - cold weather toggle
**File:** `web-ui/src/components/ScheduleEditor.tsx`
**Changes:**
- [ ] Add cold weather toggle switch with `data-testid="cold-weather-toggle"`
- [ ] Add Snowflake icon
- [ ] Conditionally show/hide controls based on mode

### Task 5.6: Update ScheduleEditor - hour checkbox grid
**File:** `web-ui/src/components/ScheduleEditor.tsx`
**Changes:**
- [ ] Add 24-hour checkbox grid (4x6 layout)
- [ ] Parse enabled hours from string to Set
- [ ] Implement toggleHour function
- [ ] Style selected/unselected hours

### Task 5.7: Update ScheduleEditor - cold weather controls
**File:** `web-ui/src/components/ScheduleEditor.tsx`
**Changes:**
- [ ] Add COLD_BLOCK_DURATIONS = [5, 10, 15]
- [ ] Show block duration dropdown (5/10/15) when cold weather mode
- [ ] Show pre/post circulation inputs
- [ ] Hide min/max block, total hours, cost constraint when cold weather mode

### Task 5.8: Update SchedulePanel - compact layout
**File:** `web-ui/src/components/SchedulePanel.tsx`
**Changes:**
- [ ] Add compact 2-column grid when coldWeatherMode && blocks > 6
- [ ] Add `data-cold-weather="true"` attribute when active
- [ ] Use blue styling for cold weather blocks
- [ ] Use Snowflake icon instead of Clock

### Task 5.9: Update mock server - state defaults
**File:** `scripts/mock_server/state_manager.py`
**Changes:**
- [ ] Add cold weather mode entity (default: off)
- [ ] Add enabled hours entity (default: "21,22,23,0,1,2,3,4,5,6")
- [ ] Add block duration entity (default: 5)
- [ ] Add pre/post circulation entities (default: 5)

### Task 5.10: Update mock server - ScheduleParameters model
**File:** `scripts/mock_server/server.py`
**Changes:**
- [ ] Add `cold_weather_mode: bool = False`
- [ ] Add `cold_enabled_hours: str`
- [ ] Add `cold_block_duration: int = 5`
- [ ] Add `cold_pre_circulation: int = 5`
- [ ] Add `cold_post_circulation: int = 5`

### Task 5.11: Update mock server - calculate endpoint
**File:** `scripts/mock_server/server.py`
**Changes:**
- [ ] If cold_weather_mode: generate fixed-time blocks at :05 past each enabled hour
- [ ] Skip price optimization for cold weather
- [ ] Fix `/api/block-enabled` range from 1-4 to 1-10

### Task 5.12: Update mock server - entity signatures
**File:** `scripts/mock_server/entity_signatures.json`
**Changes:**
- [ ] Add 5 new entity signatures matching YAML definitions

---

## Phase 6: Verification

### Task 6.1: Run E2E tests
**Command:** `cd web-ui && npx playwright test e2e/cold-weather.spec.ts`
**Expected:** All cold weather E2E tests PASS

### Task 6.2: Run full Python regression
**Command:** `./env/bin/python -m pytest tests/ -v`
**Expected:** All tests PASS (including new cold weather tests)

### Task 6.3: Run full E2E regression
**Command:** `cd web-ui && npx playwright test`
**Expected:** All E2E tests PASS

---

## Phase 7: Commit and Push

### Task 7.1: Commit implementation
**Files to stage:**
- `homeassistant/packages/pool_heating.yaml`
- `scripts/pyscript/pool_heating.py`
- `scripts/pyscript/pool_temp_control.py`
- `web-ui/src/types/heating.ts`
- `web-ui/src/hooks/useHomeAssistant.ts`
- `web-ui/src/components/ScheduleEditor.tsx`
- `web-ui/src/components/SchedulePanel.tsx`
- `scripts/mock_server/state_manager.py`
- `scripts/mock_server/server.py`
- `scripts/mock_server/entity_signatures.json`
- `tests/test_cold_weather.py`
- `web-ui/e2e/cold-weather.spec.ts`

### Task 7.2: Push to branch
**Command:** `git push -u origin claude/cold-weather-heating-cycles-FiiJZ`

---

## Summary

| Phase | Tasks | Files Changed |
|-------|-------|---------------|
| 1. Tests First | 3 tasks | 2 new test files |
| 2. HA Entities | 4 tasks | pool_heating.yaml |
| 3. Algorithm | 4 tasks | pool_heating.py, tests |
| 4. Temp Control | 6 tasks | pool_temp_control.py, pool_heating.yaml, tests |
| 5. Web UI | 12 tasks | 7 UI/mock server files |
| 6. Verification | 3 tasks | - |
| 7. Commit | 2 tasks | - |
| **Total** | **34 tasks** | **~12 files** |
