# Findings: Schedule Algorithm Review for Cold Weather Mode

**Review date:** 2026-02-02
**Reviewer:** Claude (automated review of 01-schedule-algorithm-review.md)

## 1. Current State

The schedule optimizer (`scripts/lib/schedule_optimizer.py`) finds price-optimal heating blocks within a nightly window (21:00-07:00). Core behavior:

- **Block durations** are constrained to `VALID_BLOCK_DURATIONS = [30, 45, 60]` minutes (line 28).
- **Price granularity** is 15-minute slots (`SLOT_DURATION_MINUTES = 15`, line 21).
- **Block combinations** are found recursively by `_find_block_combinations()` (line 141), generating all ways to partition `total_slots_needed` into blocks of `min_size..max_size` slots.
- **Placement** uses brute-force search in `_find_best_placement()` (line 157) with pruning. The break constraint is hardcoded as `next_min_start = start_idx + block_size + block_size` (line 228) -- break equals block duration.
- **Preheat** is handled in the pyscript version only (`pool_heating.py` lines 200-218, 384-395). It adds 1 slot (15 min) of preheat cost to the first block. The HA automation runs a 15-min preheat sequence before each block (`pool_heating.yaml` line 1320-1339).
- **Cost constraint** (`apply_cost_constraint`, line 343) enables cheapest blocks first up to a EUR limit.
- **Pyscript** duplicates the algorithm (`pool_heating.py` lines 157-416) rather than importing `schedule_optimizer.py`, so changes must be made in two places.

The heating window has 40 slots (10 hours x 4 slots/hour). For normal mode (120 min, 30-45 min blocks), the search space is small and fast.

## 2. Checklist Assessment

| Area | Current (file:line) | Cold Weather Issue | Fix |
|------|---------------------|-------------------|-----|
| Block durations | `[30, 45, 60]` (schedule_optimizer.py:28, pool_heating.py:33) | 5 min rejected by validation | New function + separate valid set |
| Slot granularity | 15-min (schedule_optimizer.py:21) | `5 // 15 = 0` slots | Keep 15-min slots; place block within chosen slot |
| Block combinations | `_find_block_combinations()` (line 141) | Irrelevant for 1-block/hr | Not used in cold weather path |
| Break logic | `break = block_size` (line 228, pool_heating.py:403) | Gives 5-min breaks, need ~55 min | Separate algorithm with hourly interval |
| Total hours | 0-5h / 0.5h steps (line 31) | 50 min = 0.833h rounds wrong | Auto-calculate: `duration * window_hours` |
| Price optimization | Brute-force (line 157) | 1 block/hr, 4 quarters | Per-hour cheapest-quarter selection |
| Cost constraint | `apply_cost_constraint()` (line 343) | Skipping defeats anti-freeze | Ignore in cold weather |
| Validation | Rejects min_block=5 (line 244) | Cold weather needs [5, 10, 15] | Mode-aware validation |
| Preheat | 15-min + cost (pool_heating.py:30, pool_heating.yaml:1328) | Overhead > block duration | Skip in cold weather |
| Post-circulation | 15-min mixing (pool_heating.yaml:1360) | Excessive for 5-min blocks | Reduce to 5 min |

## 3. Design Decisions

### Q1: Separate algorithm path or parameterize existing?

**Recommendation: Separate algorithm path.** The constraints are fundamentally different:
- Normal mode: variable block sizes, price-optimized placement, equal breaks, preheat.
- Cold weather: fixed block size, fixed interval (1/hour), no preheat, no cost constraint.

A shared `_find_block_combinations` adds no value for cold weather (always 1-slot blocks). A simple loop placing one block in the cheapest quarter of each hour is clearer and faster. The two modes should share the slot-building logic and cost calculation but diverge on placement strategy.

### Q2: Minimum block duration?

**5 minutes is reasonable.** Heat pump compressors typically need 3-5 min minimum run time. The Thermia Mega is an inverter unit; 5 min is at the lower bound but acceptable for anti-freeze protection. Going below 3 min risks short-cycling damage.

### Q3: Fixed schedule or cheapest quarter?

**Cheapest quarter within each hour.** Pick 1 of 4 quarters per hour independently. Trivial to implement, small savings.

### Q4: 15-min price slot vs 5-min block alignment?

Keep 15-min slots. Cold weather places blocks at the start of the cheapest 15-min slot in each hour. Cost = `POWER_KW * (5/60) * slot_price`. The schedule records the slot start; HA automation handles exact timing.

### Q5: Total heating time?

Auto-calculated: `block_duration * hours_in_window`. With 5 min/hour over 10 hours = 50 min. Not user-configured.

## 4. New Parameters Needed

| Parameter | Entity ID | Type | Values | Default |
|-----------|-----------|------|--------|---------|
| Heating mode | `input_select.pool_heating_mode` | select | normal, cold_weather | normal |
| Cold weather block duration | `input_number.pool_heating_cold_block_minutes` | number | 5-15 | 5 |
| Cold weather pre-circulation | `input_number.pool_heating_cold_pre_circ_minutes` | number | 0-15 | 5 |
| Cold weather post-circulation | `input_number.pool_heating_cold_post_circ_minutes` | number | 0-15 | 5 |

Normal-mode parameters (`min_block_duration`, `max_block_duration`, `total_hours`) remain unchanged and are ignored in cold weather mode.

## 5. Required Code Changes

### schedule_optimizer.py
1. **New function** `find_cold_weather_schedule()` -- places one short block per hour in cheapest quarter. ~30 lines.
2. **Line 28:** Add cold weather durations to `VALID_BLOCK_DURATIONS` or create separate constant.
3. **Line 244 (`validate_schedule_parameters`):** Accept `mode` parameter; skip normal validation in cold weather mode.
4. **Line 343 (`apply_cost_constraint`):** Add `mode` parameter; in cold weather, skip or warn instead of disabling blocks.

### pool_heating.py (pyscript)
1. **Line 33:** Mirror new valid durations.
2. **Lines 585-660 (`calculate_pool_heating_schedule`):** Read mode entity, branch to cold weather path.
3. **Lines 270-294 (preheat cost):** Skip preheat cost calculation when mode is cold_weather.
4. **Lines 862-866 (schedule JSON):** Ensure JSON handles 10 blocks (already supports up to 10, but `input_text` max length 255 chars at line 865 will be exceeded with 10 blocks). **This is a pre-existing bug for any schedule with >4 blocks.**

### pool_heating.yaml (HA automations)
1. **Lines 1318-1339 (`pool_heating_block_start`):** Make preheat conditional on mode. In cold weather, run only pre-circulation (pump ON, no comfort wheel preheat).
2. **Lines 1342-1373 (`pool_heating_block_stop`):** Make post-circulation duration configurable (5 min for cold weather vs 15 min for normal).
3. **Lines 1329-1331:** The 15-min delay should be 0 in cold weather mode.

### schedule_optimizer.py / pool_heating.py (code duplication)
The algorithm exists in both files. **Ideally consolidate**, but pyscript import constraints may prevent this. At minimum, document that changes must be mirrored.

## 6. Test Plan

### New unit tests (tests/test_cold_weather.py)
1. Cold weather schedule produces exactly 10 blocks for a 10-hour window with 5-min blocks.
2. Each block is placed in the cheapest 15-min quarter of its hour.
3. Blocks are spaced ~1 hour apart (55-min gap between block end and next block start).
4. Total heating time = 50 minutes (10 x 5 min).
5. Cost calculation uses correct duration (5 min, not 15 min).
6. Cost constraint is ignored/bypassed in cold weather mode.
7. Preheat cost is not added in cold weather mode.
8. Schedule fits within heating window boundaries.

### Regression tests
9. Normal mode behavior unchanged when mode="normal" (run all existing tests).
10. `validate_schedule_parameters()` still rejects invalid normal-mode values.

### E2E tests
11. Mode toggle in UI switches between normal and cold weather display.
12. Cold weather schedule shows 10 short blocks in the timeline.

## 7. Risks

1. **Entity ID stability:** Adding `input_select.pool_heating_mode` is safe (new entity). No existing entities change.
2. **Normal mode regression:** Highest risk. The `find_best_heating_schedule()` function must remain untouched. Cold weather should use a new function, not parameterize the existing one.
3. **Schedule JSON overflow:** `input_text` max 255 chars. With 10 blocks, the JSON will be ~800 chars. This is already broken for any schedule with >4 blocks. Must fix by using a longer storage entity or splitting.
4. **Preheat timing:** If the mode switch is not properly wired into the HA script, cold weather blocks could still trigger 15-min preheats, making 5-min heating pointless (20 min overhead per 5-min block).
5. **Compressor short-cycling:** 5-min runs are at the lower limit. Should add a minimum run-time safety check in the HA automation (do not stop heating if compressor has been running < 3 min).
