# Implementation Plan 02: Cold Weather Schedule Algorithm

**Depends on:** Plan 01 (entities exist)
**Findings source:** Review 01

## Goal

Add `find_cold_weather_schedule()` to both `scripts/lib/schedule_optimizer.py` and `scripts/pyscript/pool_heating.py`. This is a separate algorithm path -- the existing `find_best_heating_schedule()` is not modified.

## Algorithm: find_cold_weather_schedule()

**Input:**
- `prices_today`: list of 96 floats (15-min slot prices for today)
- `prices_tomorrow`: list of 96 floats (15-min slot prices for tomorrow)
- `block_duration_minutes`: int (5, 10, or 15)
- `pre_circ_minutes`: int (0-10, default 5)
- `post_circ_minutes`: int (0-10, default 5)

**Logic:**
1. Build the slot list for the heating window (21:00-07:00) -- reuse existing `_build_slot_list()` / `build_heating_window_slots()`.
2. Group slots into hours (4 slots per hour, 10 hours = 10 groups).
3. For each hour, pick the cheapest 15-min slot.
4. For each selected slot, create a block:
   - `start` = slot start time (block heating starts at this time; pre-circ is handled by the HA script before this)
   - `end` = start + block_duration_minutes
   - `duration_minutes` = block_duration_minutes
   - `avg_price` = slot price (single slot, so avg = that slot's price)
   - `cost_eur` = POWER_KW * (block_duration_minutes / 60) * avg_price
5. All blocks are enabled (no cost constraint in cold weather).
6. Return list of blocks (up to 10).

**Output:** Same structure as `find_best_heating_schedule()` -- list of block dicts.

## Files to Change

### scripts/lib/schedule_optimizer.py

Add after existing constants (~line 32):

```python
COLD_WEATHER_VALID_DURATIONS = [5, 10, 15]  # minutes
```

Add new function (~line 350, after `apply_cost_constraint`):

```python
def find_cold_weather_schedule(
    prices_today: list,
    prices_tomorrow: list,
    block_duration_minutes: int = 5,
    heating_window_start: int = HEATING_WINDOW_START,
    heating_window_end: int = HEATING_WINDOW_END,
) -> list:
    """Place one short block per hour in the cheapest 15-min slot.

    Args:
        prices_today: 96 prices (15-min intervals) for today
        prices_tomorrow: 96 prices for tomorrow
        block_duration_minutes: Duration of each block (5, 10, or 15 min)
        heating_window_start: Hour (21)
        heating_window_end: Hour (7)

    Returns:
        List of block dicts with keys: start, end, duration_minutes, avg_price, cost_eur
    """
```

Implementation steps inside the function:
1. Validate `block_duration_minutes` is in `COLD_WEATHER_VALID_DURATIONS`.
2. Build combined price list from today+tomorrow for the heating window (same slot-building as normal mode).
3. Iterate hours in the window. For each hour, find the 4 slots, pick the one with lowest price.
4. Create block dict for each hour. `cost_eur = POWER_KW * (block_duration_minutes / 60) * price`.
5. Return sorted by start time.

### scripts/pyscript/pool_heating.py

Mirror the same function. Add after `VALID_BLOCK_DURATIONS` (~line 33):

```python
COLD_WEATHER_VALID_DURATIONS = [5, 10, 15]
```

Add the same `find_cold_weather_schedule()` function (pyscript version -- use explicit loops, no generators per Known Issue #2).

Modify `calculate_pool_heating_schedule` service (~line 585):
1. Read `input_boolean.pool_heating_cold_weather_mode` state.
2. If cold weather mode ON:
   - Read `input_number.pool_heating_cold_block_duration` (default 5).
   - Call `find_cold_weather_schedule()` instead of `find_best_heating_schedule()`.
   - Skip preheat cost addition.
   - Skip cost constraint application.
3. Write results to same block entities (`pool_heat_block_X_*`).

### Schedule JSON overflow fix (pre-existing bug)

`input_text.pool_heating_schedule_json` has max_length 255 (pool_heating.yaml). With 10 blocks the JSON is ~800 chars. Fix: increase `max: 255` to `max: 1024` in the YAML entity definition. HA `input_text` supports up to 255 by default but can be set higher. Alternative: store JSON in a `pyscript` variable or use `input_text` with `max: 1024` (supported since HA 2023.x).

## Unit Tests (tests/test_cold_weather.py)

Write BEFORE implementation (TDD):

```python
def test_cold_weather_produces_10_blocks():
    """10-hour window with 1 block/hour = 10 blocks."""

def test_cold_weather_cheapest_quarter_per_hour():
    """Each block placed in the cheapest 15-min slot of its hour."""

def test_cold_weather_block_duration_5min():
    """All blocks have duration_minutes=5 when configured for 5."""

def test_cold_weather_block_duration_15min():
    """All blocks have duration_minutes=15 when configured for 15."""

def test_cold_weather_cost_calculation():
    """cost = POWER_KW * (5/60) * price. At 5c/kWh: 5 * (5/60) * 0.05 = 0.0208 EUR."""

def test_cold_weather_blocks_sorted_by_time():
    """Blocks returned in chronological order."""

def test_cold_weather_no_cost_constraint():
    """All blocks enabled regardless of price."""

def test_cold_weather_invalid_duration_falls_back():
    """Duration 20 falls back to 5."""

def test_normal_mode_unchanged():
    """Existing find_best_heating_schedule still works identically."""
```

Run tests BEFORE implementation -- all cold weather tests must FAIL. Then implement. Then all must PASS. Then run full regression (`make test`).
