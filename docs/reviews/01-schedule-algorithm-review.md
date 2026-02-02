# Review Plan 01: Schedule Algorithm for Cold Weather Mode

## Objective

Review the schedule optimizer algorithm to determine what changes are needed to support cold weather short-cycle heating (e.g., 5 min heating per hour) alongside the existing normal heating mode (30-45 min blocks).

## Context

In extremely cold weather, the radiator circuit cools down so quickly that running 30-minute heating cycles is counterproductive. Instead, short bursts (~5 minutes per hour) are needed, with circulation pump running ~5 minutes before and after each burst.

## Files to Review

| File | What to look for |
|------|-----------------|
| `scripts/lib/schedule_optimizer.py` | Core algorithm: block combinations, placement, break logic, valid durations |
| `scripts/pyscript/pool_heating.py` | Pyscript wrapper: parameter reading, entity updates, service calls |
| `tests/test_price_optimizer.py` | Existing tests for schedule algorithm |
| `tests/test_cost_constraint.py` | Cost constraint tests |

## Review Checklist

### 1. Block Duration Support (schedule_optimizer.py)
- [ ] `VALID_BLOCK_DURATIONS = [30, 45, 60]` - What values are needed for cold weather? (5, 10, 15 min?)
- [ ] `SLOT_DURATION_MINUTES = 15` - Can 5-min blocks work with 15-min price slots? Need finer granularity?
- [ ] `_find_block_combinations()` - Does the recursive search scale with many small blocks?
- [ ] `_find_best_placement()` - Break constraint is `next_min_start = start_idx + block_size + block_size`. For cold weather, breaks should be ~55 min (rest of the hour), not equal to block.

### 2. Break Logic
- [ ] Current: break = block duration. For cold weather: break = (60 - block_duration) or similar "once per hour" pattern.
- [ ] Should cold weather mode use a completely different scheduling strategy (fixed interval) vs. price-optimized placement?
- [ ] If heating 5 min/hour for 10 hours = 50 min total. Does cost optimization even matter, or is the schedule fixed?

### 3. Total Heating Time
- [ ] `VALID_TOTAL_HOURS` currently maxes at 5h. Cold weather 5min/hr over 10hr window = 50 min. This is within range.
- [ ] Or should total_hours be replaced by a "minutes per hour" parameter in cold weather mode?

### 4. Price Optimization Relevance
- [ ] For cold weather mode with 1 block per hour, every hour must be heated regardless of price. Price optimization becomes irrelevant.
- [ ] Alternative: still optimize which 5-min window within each hour is cheapest (4 options per hour with 15-min slots).
- [ ] If blocks are 5 min, they don't align with 15-min price slots. How to handle?

### 5. Cost Constraint Interaction
- [ ] `apply_cost_constraint()` - Does it still make sense for cold weather mode?
- [ ] With fixed interval heating, skipping blocks due to cost defeats the purpose.

### 6. Parameter Validation
- [ ] `validate_schedule_parameters()` - Must accept new cold weather values.
- [ ] Need a mode flag: normal vs. cold_weather.

### 7. Ramping/Preheat
- [ ] 15-minute preheat before each block - makes no sense for 5-min blocks.
- [ ] Should cold weather mode skip preheat entirely?

## Questions to Answer

1. Should cold weather mode be a separate algorithm path, or parameterize the existing one?
2. What is the minimum block duration that makes physical sense? (compressor startup time, valve switching)
3. Should the schedule be "5 min every hour, fixed" or "5 min every hour, cheapest quarter"?
4. How does the 15-min price slot granularity interact with 5-min blocks?
5. What total heating time makes sense? Is it always 5min/hr * hours-in-window?

## Output Instructions

After completing this review, write findings to:
**`docs/reviews/01-schedule-algorithm-findings.md`**

The findings file must contain:
1. **Current State**: How the algorithm works today (brief)
2. **Required Changes**: Specific code changes needed, with file:line references
3. **Design Decisions**: Answers to the questions above with rationale
4. **New Parameters**: Any new configuration values needed
5. **Test Plan**: What new tests are needed
6. **Risks**: What could break in the existing normal-mode behavior
