# Implementation Plan 02: Cold Weather Schedule Algorithm (SIMPLIFIED)

**Depends on:** Plan 01 (entities exist)
**Findings source:** Review 01, GitHub PR feedback

## Goal

Add simple cold weather schedule generation to `scripts/pyscript/pool_heating.py` only. **No changes to `scripts/lib/schedule_optimizer.py`** -- that file is for normal mode price optimization only.

Cold weather mode uses fixed timing (no price optimization) to keep implementation dead simple.

## Algorithm: generate_cold_weather_schedule()

**Design principle:** Keep it dead simple. User picks which hours, no schedule calculation.

**Input:**
- `enabled_hours`: comma-separated string from `input_text.pool_heating_cold_enabled_hours` (e.g., "21,22,23,0,1,2,3,4,5,6")
- `block_duration_minutes`: int from `input_number.pool_heating_cold_block_duration` (5, 10, or 15)

**Logic:**
1. Parse enabled hours string into list of integers
2. For each enabled hour, create a block at **:05 past that hour** (hardcoded)
3. Block end = block start + block_duration_minutes
4. All blocks are enabled (no cost constraint)
5. Return list of blocks sorted by time

**Output:** List of block dicts with keys: `start`, `end`, `duration_minutes`, `enabled`

## Files to Change

### scripts/pyscript/pool_heating.py ONLY

**No changes to `scripts/lib/schedule_optimizer.py`** -- keep normal mode code untouched.

Add constants after existing ones (~line 33):

```python
COLD_WEATHER_VALID_DURATIONS = [5, 10, 15]  # minutes
COLD_WEATHER_BLOCK_OFFSET = 5  # Minutes past hour (hardcoded :05)
```

Add new function:

```python
def generate_cold_weather_schedule(enabled_hours_str, block_duration_minutes):
    """Generate fixed-time blocks for cold weather mode.

    Places one block at :05 past each user-selected hour.
    No price optimization, no window calculation - user picks the hours.

    Args:
        enabled_hours_str: Comma-separated hours, e.g., "21,22,23,0,1,2,3,4,5,6"
        block_duration_minutes: 5, 10, or 15

    Returns:
        List of block dicts with keys: start, end, duration_minutes, enabled
    """
    blocks = []

    # Validate duration
    if block_duration_minutes not in COLD_WEATHER_VALID_DURATIONS:
        block_duration_minutes = 5

    # Parse enabled hours
    enabled_hours = []
    if enabled_hours_str:
        for h in enabled_hours_str.split(','):
            h = h.strip()
            if h.isdigit():
                hour = int(h)
                if 0 <= hour <= 23:
                    enabled_hours.append(hour)

    if not enabled_hours:
        return blocks  # No hours selected

    # Build schedule for tonight/tomorrow
    now = datetime.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)

    # Sort hours and assign dates (hours >= 12 are today, hours < 12 are tomorrow)
    for hour in enabled_hours:
        if hour >= 12:
            date = today
        else:
            date = tomorrow

        block_start = datetime.combine(date, datetime.min.time().replace(
            hour=hour, minute=COLD_WEATHER_BLOCK_OFFSET))
        block_end = block_start + timedelta(minutes=block_duration_minutes)

        blocks.append({
            'start': block_start,
            'end': block_end,
            'duration_minutes': block_duration_minutes,
            'enabled': True,
            'avg_price': 0.0,
            'cost_eur': 0.0,
        })

    # Sort by start time
    blocks.sort(key=lambda b: b['start'])
    return blocks
```

Modify `calculate_pool_heating_schedule` service (~line 585):

```python
@service
def calculate_pool_heating_schedule():
    """Calculate optimal pool heating schedule."""

    # Check if cold weather mode is enabled
    cold_weather_mode = state.get("input_boolean.pool_heating_cold_weather_mode") == "on"

    if cold_weather_mode:
        # COLD WEATHER: User-selected hours, no optimization
        enabled_hours = state.get("input_text.pool_heating_cold_enabled_hours") or ""
        block_duration = int(float(state.get("input_number.pool_heating_cold_block_duration") or 5))

        blocks = generate_cold_weather_schedule(enabled_hours, block_duration)

        # Skip preheat cost, skip cost constraint
        # Write directly to block entities

    else:
        # NORMAL MODE: Existing price optimization (unchanged)
        # ... existing code ...

    # Write blocks to HA entities (same for both modes)
    write_blocks_to_entities(blocks)
```

## What Does NOT Change

- `scripts/lib/schedule_optimizer.py` -- completely untouched
- `find_best_heating_schedule()` -- normal mode only
- `apply_cost_constraint()` -- normal mode only
- Price optimization logic -- not used in cold weather

## Unit Tests (tests/test_cold_weather.py)

Write BEFORE implementation (TDD):

```python
def test_cold_weather_fixed_offset():
    """All blocks start at :05 past the hour."""
    blocks = generate_cold_weather_schedule("21,22,23,0,1", block_duration_minutes=5)
    for block in blocks:
        assert block['start'].minute == 5

def test_cold_weather_block_count():
    """Number of blocks matches enabled hours."""
    blocks = generate_cold_weather_schedule("21,22,23,0,1,2,3,4,5,6", block_duration_minutes=5)
    assert len(blocks) == 10

def test_cold_weather_block_duration():
    """Block duration matches configured value."""
    blocks = generate_cold_weather_schedule("21,22,23", block_duration_minutes=10)
    for block in blocks:
        assert block['duration_minutes'] == 10
        delta = (block['end'] - block['start']).total_seconds() / 60
        assert delta == 10

def test_cold_weather_all_enabled():
    """All cold weather blocks are enabled (no cost constraint)."""
    blocks = generate_cold_weather_schedule("21,22,23", block_duration_minutes=5)
    for block in blocks:
        assert block['enabled'] == True

def test_cold_weather_invalid_duration_fallback():
    """Invalid duration falls back to 5 min."""
    blocks = generate_cold_weather_schedule("21", block_duration_minutes=20)
    assert blocks[0]['duration_minutes'] == 5

def test_cold_weather_empty_hours():
    """Empty hours string returns empty list."""
    blocks = generate_cold_weather_schedule("", block_duration_minutes=5)
    assert len(blocks) == 0

def test_cold_weather_invalid_hours_ignored():
    """Invalid hour values are ignored."""
    blocks = generate_cold_weather_schedule("21,25,-1,abc,22", block_duration_minutes=5)
    assert len(blocks) == 2  # Only 21 and 22 are valid

def test_cold_weather_sorted_by_time():
    """Blocks are sorted chronologically."""
    blocks = generate_cold_weather_schedule("0,23,1,22", block_duration_minutes=5)
    times = [b['start'] for b in blocks]
    assert times == sorted(times)

def test_normal_mode_unchanged():
    """Normal mode find_best_heating_schedule still works."""
    # This is a regression test - import and call the existing function
    # to ensure cold weather changes didn't break it
```

Run tests BEFORE implementation -- all cold weather tests must FAIL. Then implement. Then all must PASS. Then run full regression (`make test`).
