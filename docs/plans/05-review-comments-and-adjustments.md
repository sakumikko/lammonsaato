# Review Comments Summary & Plan Adjustments

## GitHub PR Review Feedback (PR #2)

### GH-1: Configurable Heating Window Hours
**File:** `docs/plans/00-overview.md` line 14 (Blocks per night)
**Comment:** "There should be an easy way to set the hours of for cold weather mode at any time of the day"

**Impact:** Cold weather mode needs configurable start/end hours, not hardcoded 21:00-07:00.

**Proposed Change:**
- Add `input_datetime.pool_heating_cold_window_start` (time only)
- Add `input_datetime.pool_heating_cold_window_end` (time only)
- Algorithm uses these instead of hardcoded `HEATING_WINDOW_START/END`

---

### GH-2: Compressor Gear = max(9, current_gear)
**File:** `docs/plans/00-overview.md` line 20 (Compressor gear)
**Comment:** "has to be max(9, current_gear) for cold weather"

**Impact:** Plan 03 sets `MIN_GEAR_POOL = 7`. For cold weather, use gear 9 minimum.

**Proposed Change to Plan 03:**
```python
# Cold weather: use max(9, current_gear) instead of fixed 7
cold_weather_min_gear = max(9, _safe_get_float(MIN_GEAR_ENTITY, 1))
```

---

### GH-3: Safety Threshold = 12C Relative (not 8C)
**File:** `docs/plans/00-overview.md` line 21 (Safety thresholds)
**Comment:** "12C relative"

**Impact:** Plan 03 proposes `COLD_WEATHER_RELATIVE_DROP = 8.0`. User wants 12C.

**Proposed Change to Plan 03:**
```python
COLD_WEATHER_RELATIVE_DROP = 12.0  # Was 8.0
```

---

### GH-4: No Price Optimization - Fixed Time (e.g., :05 past hour)
**File:** `docs/plans/00-overview.md` line 23 (Price optimization)
**Comment:** "this is problematic as there needs to be at leas one 55 mins between so it could always just be 5 past hour"

**Impact:** The "cheapest quarter per hour" optimization is unnecessary complexity. Just run at a fixed offset each hour (e.g., HH:05).

**Proposed Change to Plan 02:**
- Remove `find_cold_weather_schedule()` price optimization logic
- Use fixed schedule: blocks at :05 past each hour within the window
- Simpler algorithm: `for hour in range(start_hour, end_hour): blocks.append(hour:05)`

---

### GH-5: Keep Cold Weather Mode Dead Simple
**File:** `docs/plans/00-overview.md` line 33 (Plan 02)
**Comment:** "what is the optimizer needed here? let's keep this dead simple as possible for cold weather mode"

**Impact:** Reinforces GH-4. No schedule_optimizer.py changes needed for cold weather.

**Proposed Change:**
- Plan 02 becomes trivial: generate fixed-time blocks in pyscript only
- No changes to `scripts/lib/schedule_optimizer.py` (normal mode only)
- Cold weather schedule is just a simple loop, not an optimization problem

---

## Discrepancies Found Between Reviews and Plans

### 1. Entity Type: input_select vs input_boolean

**Review 01 (line 65):** Proposes `input_select.pool_heating_mode` with values `normal, cold_weather`

**Plan 01 & Plan 04:** Uses `input_boolean.pool_heating_cold_weather_mode` (on/off toggle)

**Question:** Should we use:
- A) `input_boolean` (simple toggle, as in the plans)
- B) `input_select` (allows future expansion to more modes)

**Recommendation:** Stick with `input_boolean`. Two modes are sufficient. `input_select` adds complexity for no immediate benefit. If a third mode is needed later, we can migrate.

---

### 2. Entity Naming Inconsistency

**Review 01 (line 66-68):**
```
input_number.pool_heating_cold_block_minutes
input_number.pool_heating_cold_pre_circ_minutes
input_number.pool_heating_cold_post_circ_minutes
```

**Plan 01 & Plan 04:**
```
input_number.pool_heating_cold_block_duration
input_number.pool_heating_cold_pre_circulation
input_number.pool_heating_cold_post_circulation
```

**Question:** Which naming convention?

**Recommendation:** Use the plan names (longer, clearer). `_duration` and `_circulation` are more consistent with existing entities (`pool_heating_min_block_duration`).

---

### 3. Compressor Short-Cycling Safety Check (NEW)

**Review 01 (line 120, Risk #5):**
> 5-min runs are at the lower limit. Should add a minimum run-time safety check in the HA automation (do not stop heating if compressor has been running < 3 min).

**Review 03 (Section 7, Q5):**
> Does the heat pump have a minimum run time requirement? Some heat pumps require minimum 3-5 min continuous operation.

**Current Plans:** Do NOT include this safety check.

**Proposed Addition to Plan 01:**
In `script.pool_heating_block_stop` (cold weather branch), add a condition:
```yaml
- condition: template
  value_template: >-
    {{ (now() - states.switch.altaan_lammityksen_esto.last_changed).total_seconds() > 180 }}
```
If prevention switch was turned OFF less than 3 min ago, delay the stop or extend the block.

**Question:** Add this safety check? If so, how to handle the extension (delay stop, or warn user)?

---

### 4. Schedule JSON Overflow (PRE-EXISTING BUG)

**Review 01 (line 84, 118):**
> `input_text` max length 255 chars... This is already broken for any schedule with >4 blocks. Must fix by using a longer storage entity or splitting.

**Plan 02 mentions this but doesn't provide a concrete fix.**

**Proposed Addition to Plan 01 or Plan 02:**
Change in `homeassistant/packages/pool_heating.yaml`:
```yaml
input_text:
  pool_heating_schedule_json:
    name: Pool Heating Schedule JSON
    max: 1024  # Increased from 255 to support 10 blocks
```
Note: HA supports `max: 1024` since 2023.x versions.

**Question:** Fix this as part of Plan 01 (YAML changes) or Plan 02 (algorithm changes)?

---

### 5. Modify Existing Entity Ranges vs New Entities

**Review 02 (line 71-73):**
> Existing entity changes:
> - `input_number.pool_heating_min_block_duration`: lower `min` from 30 to 5
> - `input_number.pool_heating_max_block_duration`: lower `min` from 30 to 5

**Review 04 (line 24-25):**
> Do NOT change this entity's range. Cold weather uses `cold_block_duration` instead.

**Current Plans:** Follow Review 04's recommendation (separate entities, don't modify existing).

**Question:** Confirm this is the right approach? Modifying existing entities risks breaking normal mode validation.

---

### 6. Pre-circulation Timing: Embedded vs Offset

**Review 02 (line 67):**
> Pre-circulation approach (Option A, recommended): Embed 5-min pre-circ delay inside `block_start` script. Automation still triggers at `block_start` time. Pyscript sets `block_end = block_start + 10min` (5 pre-circ + 5 heat).

**Current Plan 02:** Does NOT account for pre-circulation in block timing. The algorithm sets `end = start + block_duration_minutes` (5 min).

**Issue:** If pre-circ is embedded in block_start script (5-min delay), then actual heating starts 5 min after `block_start`. But `block_end` is set to `start + 5min`. The stop automation fires while heating just started.

**Options:**
A) **Algorithm adjusts:** `block_end = block_start + pre_circ + heat_duration + post_circ`. HA entities store wall-clock total.
B) **Script handles it:** Algorithm stores just heating times. Scripts add pre/post internally. Stop automation uses `block_end` as heating end, then script adds post-circ.
C) **Separate timing:** Store `heat_start` and `heat_end` (actual heating times). Pre-circ and post-circ are handled by scripts without affecting these times.

**Recommendation:** Option C -- cleaner separation. `block_start` = when heating begins (prevention OFF). `block_end` = when heating ends (prevention ON). Pre-circ runs BEFORE `block_start`, post-circ runs AFTER `block_end`. The start automation triggers at `block_start - pre_circ`.

**This requires changing Plan 01:** The start automation trigger time calculation needs to account for pre-circ offset.

---

### 7. Window-Level vs Per-Block Temp Control

**Plan 03:** Proposes window-level fixed supply (enable at 21:00, disable at 07:00).

**Review 03 (Section 6):** Aligns with this -- "At heating window start (21:00): enable fixed supply..."

**No discrepancy.** But reviews raise a question:

**Review 03 (Section 7, Q2):**
> How quickly does Thermia respond to fixed supply mode enable/disable? If the response takes >2 min, per-block toggling wastes 40%+ of each 5-min block on transition.

**Question:** Do we have data on Thermia's response time? If it's >2 min, even window-level control may need lead time (enable at 20:58 instead of 21:00).

---

### 8. Safety Thresholds Conditional Logic

**Review 03 (line 119):**
> Implement as conditional: if outdoor < -5C, use tighter thresholds.

**Plan 03:** Uses mode flag (`cold_weather=True`) to select thresholds, not outdoor temp.

**Question:** Should thresholds be based on:
A) Mode flag only (simpler, as in Plan 03)
B) Outdoor temperature (more adaptive, as Review 03 suggests)
C) Both (mode selects base thresholds, outdoor temp adjusts further)

**Recommendation:** Start with A (mode flag). Outdoor-based adaptation is a future enhancement.

---

## Summary: Proposed Plan Adjustments

### From GitHub PR Review

| # | Issue | Adjustment | Affects |
|---|-------|------------|---------|
| GH-1 | Configurable window hours | ADD `input_datetime` for cold weather start/end times | Plan 01, Plan 02 |
| GH-2 | Compressor gear | CHANGE from fixed 7 to `max(9, current_gear)` | Plan 03 |
| GH-3 | Safety relative threshold | CHANGE from 8C to 12C | Plan 03 |
| GH-4 | No price optimization | SIMPLIFY to fixed time (e.g., :05 past hour) | Plan 02 |
| GH-5 | Keep it simple | REMOVE schedule_optimizer.py changes for cold weather | Plan 02 |

### From Internal Review

| # | Issue | Adjustment | Affects |
|---|-------|------------|---------|
| 1 | Entity type | Keep `input_boolean` (no change) | - |
| 2 | Entity naming | Keep plan names `_duration`, `_circulation` (no change) | - |
| 3 | Compressor min run time | ADD 3-min safety check to block_stop script | Plan 01 |
| 4 | Schedule JSON overflow | ADD `max: 1024` to input_text entity | Plan 01 |
| 5 | Existing entity ranges | Keep separate entities (no change to existing) | - |
| 6 | Pre-circ timing | REVISE to Option C: trigger start automation early | Plan 01, Plan 02 |
| 7 | Window-level control | No change | - |
| 8 | Safety thresholds | Use mode flag only for now | - |

---

## Revised Cold Weather Mode Summary

Based on GitHub feedback, cold weather mode becomes much simpler:

| Aspect | Original Plan | Revised |
|--------|---------------|---------|
| Heating window | Hardcoded 21:00-07:00 | **Configurable via input_datetime** |
| Block timing | Cheapest quarter per hour | **Fixed offset (e.g., :05 past hour)** |
| Compressor gear | Set to 7 | **max(9, current_gear)** |
| Safety relative drop | 8C | **12C** |
| Algorithm complexity | New `find_cold_weather_schedule()` | **Simple loop in pyscript only** |

---

## Questions for User Feedback

### Clarifications Needed on GitHub Feedback

1. **Window hours (GH-1):** Should cold weather mode use the SAME window entities as normal mode, or separate `input_datetime.pool_heating_cold_window_start/end` entities?

2. **Fixed time offset (GH-4):** You mentioned ":05 past hour" as example. Should this be:
   - A) Hardcoded to :05
   - B) Configurable (e.g., `input_number.pool_heating_cold_offset_minutes`)
   - C) User chooses which quarter (:00, :15, :30, :45)

3. **Gear formula (GH-2):** `max(9, current_gear)` -- is `current_gear` the value of `MIN_GEAR_ENTITY` at window start, or the live compressor gear sensor?

### Internal Review Questions

4. **Compressor safety (Issue #3):** Should we add a 3-min minimum run time check? If the block is interrupted before 3 min, should we delay the stop?

5. **Pre-circulation timing (Issue #6):** The proposed Option C means the start automation triggers at `block_start - pre_circ_minutes`. This changes how the schedule is interpreted. Is this acceptable?

6. **Thermia response time (Issue #7):** Do you have observations on how quickly Thermia responds to fixed supply mode changes? Should we add lead time?
