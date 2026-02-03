# Implementation Plan 02: Cold Weather Schedule Algorithm (SIMPLIFIED)

**Depends on:** Plan 01 (entities exist)
**Findings source:** Review 01, GitHub PR feedback

## Goal

Add simple cold weather schedule generation to `scripts/pyscript/pool_heating.py` only. **No changes to `scripts/lib/schedule_optimizer.py`** -- that file is for normal mode price optimization only.

Cold weather mode uses fixed timing (no price optimization) to keep implementation dead simple.

## Algorithm: generate_cold_weather_schedule()

**Design principle:** Keep it dead simple. No price optimization.

**Input:**
- `window_start`: time from `input_datetime.pool_heating_cold_window_start`
- `window_end`: time from `input_datetime.pool_heating_cold_window_end`
- `block_duration_minutes`: int from `input_number.pool_heating_cold_block_duration` (5, 10, or 15)

**Logic:**
1. Read window start/end times from separate cold weather entities
2. For each hour in the window, create a block at **:05 past the hour** (hardcoded)
3. Block end = block start + block_duration_minutes
4. All blocks are enabled (no cost constraint)
5. Return list of blocks

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
def generate_cold_weather_schedule(window_start_time, window_end_time, block_duration_minutes):
    """Generate fixed-time blocks for cold weather mode.

    Places one block at :05 past each hour within the window.
    No price optimization - keeps implementation simple.

    Args:
        window_start_time: datetime.time from input_datetime entity
        window_end_time: datetime.time from input_datetime entity
        block_duration_minutes: 5, 10, or 15

    Returns:
        List of block dicts with keys: start, end, duration_minutes, enabled
    """
    blocks = []

    # Validate duration
    if block_duration_minutes not in COLD_WEATHER_VALID_DURATIONS:
        block_duration_minutes = 5

    # Build schedule for tonight/tomorrow
    now = datetime.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)

    # Determine which hours are in the window
    # Window typically spans midnight (e.g., 21:00 - 07:00)
    if window_start_time > window_end_time:
        # Spans midnight: tonight's hours + tomorrow morning's hours
        schedule_date_start = today
        schedule_date_end = tomorrow
    else:
        # Same day window
        schedule_date_start = today
        schedule_date_end = today

    # Generate blocks at :05 past each hour
    current_hour = window_start_time.hour
    end_hour = window_end_time.hour

    # Handle midnight crossing
    hours_list = []
    if window_start_time > window_end_time:
        # e.g., 21:00 - 07:00
        for h in range(window_start_time.hour, 24):
            hours_list.append((today, h))
        for h in range(0, window_end_time.hour):
            hours_list.append((tomorrow, h))
    else:
        for h in range(window_start_time.hour, window_end_time.hour):
            hours_list.append((today, h))

    for date, hour in hours_list:
        block_start = datetime.combine(date, datetime.min.time().replace(
            hour=hour, minute=COLD_WEATHER_BLOCK_OFFSET))
        block_end = block_start + timedelta(minutes=block_duration_minutes)

        blocks.append({
            'start': block_start,
            'end': block_end,
            'duration_minutes': block_duration_minutes,
            'enabled': True,  # All blocks enabled in cold weather
            'avg_price': 0.0,  # No price tracking in cold weather
            'cost_eur': 0.0,
        })

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
        # COLD WEATHER: Simple fixed-time schedule
        window_start = state.get("input_datetime.pool_heating_cold_window_start")
        window_end = state.get("input_datetime.pool_heating_cold_window_end")
        block_duration = int(float(state.get("input_number.pool_heating_cold_block_duration") or 5))

        # Parse time strings to time objects
        start_time = datetime.strptime(window_start, "%H:%M:%S").time()
        end_time = datetime.strptime(window_end, "%H:%M:%S").time()

        blocks = generate_cold_weather_schedule(start_time, end_time, block_duration)

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
    blocks = generate_cold_weather_schedule(
        time(21, 0), time(7, 0), block_duration_minutes=5)
    for block in blocks:
        assert block['start'].minute == 5

def test_cold_weather_block_count():
    """10-hour window (21:00-07:00) produces 10 blocks."""
    blocks = generate_cold_weather_schedule(
        time(21, 0), time(7, 0), block_duration_minutes=5)
    assert len(blocks) == 10

def test_cold_weather_block_duration():
    """Block duration matches configured value."""
    blocks = generate_cold_weather_schedule(
        time(21, 0), time(7, 0), block_duration_minutes=10)
    for block in blocks:
        assert block['duration_minutes'] == 10
        delta = (block['end'] - block['start']).total_seconds() / 60
        assert delta == 10

def test_cold_weather_all_enabled():
    """All cold weather blocks are enabled (no cost constraint)."""
    blocks = generate_cold_weather_schedule(
        time(21, 0), time(7, 0), block_duration_minutes=5)
    for block in blocks:
        assert block['enabled'] == True

def test_cold_weather_invalid_duration_fallback():
    """Invalid duration falls back to 5 min."""
    blocks = generate_cold_weather_schedule(
        time(21, 0), time(7, 0), block_duration_minutes=20)
    assert blocks[0]['duration_minutes'] == 5

def test_cold_weather_custom_window():
    """Custom window hours work correctly."""
    blocks = generate_cold_weather_schedule(
        time(22, 0), time(6, 0), block_duration_minutes=5)
    assert len(blocks) == 8  # 22, 23, 0, 1, 2, 3, 4, 5

def test_normal_mode_unchanged():
    """Normal mode find_best_heating_schedule still works."""
    # This is a regression test - import and call the existing function
    # to ensure cold weather changes didn't break it
```

Run tests BEFORE implementation -- all cold weather tests must FAIL. Then implement. Then all must PASS. Then run full regression (`make test`).
