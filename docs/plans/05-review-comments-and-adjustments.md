# Review Comments Summary & Plan Adjustments

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

## Questions for User Feedback

1. **Compressor safety (Issue #3):** Should we add a 3-min minimum run time check? If the block is interrupted before 3 min, should we:
   - Delay the stop by the remaining time?
   - Log a warning but stop anyway?
   - Something else?

2. **Pre-circulation timing (Issue #6):** The proposed Option C means the start automation triggers at `block_start - pre_circ_minutes`. This changes how the schedule is interpreted. Is this acceptable, or do you prefer Option A (algorithm calculates wall-clock totals)?

3. **Thermia response time (Issue #7):** Do you have observations on how quickly Thermia responds to fixed supply mode changes? Should we add lead time before the first block?

4. **Any other feedback** on the review findings or proposed adjustments?
