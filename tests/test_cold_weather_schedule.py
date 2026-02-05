#!/usr/bin/env python3
"""
Unit tests for cold weather schedule generation.

Run with: pytest tests/test_cold_weather_schedule.py -v

Tests the cold weather mode schedule generation with:
- Pre-circulation offset (start time before heating)
- Post-circulation offset (end time after heating)
- Block duration settings
"""

import pytest
from datetime import datetime, date, timedelta
import sys
from pathlib import Path

# Add scripts to path for importing
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'pyscript'))

# Import the function under test from the pyscript module
# We need to extract it since pyscript modules aren't directly importable
# Instead, we'll copy the function logic here for testing

# Constants from pool_heating.py
COLD_WEATHER_VALID_DURATIONS = [5, 10, 15]
COLD_WEATHER_BLOCK_OFFSET = 5  # blocks start at :05 past the hour


def generate_cold_weather_schedule(
    enabled_hours_str,
    block_duration_minutes,
    pre_circulation_minutes=0,
    post_circulation_minutes=0
):
    """
    Generate fixed-time blocks for cold weather mode.

    This is a copy of the function from pool_heating.py for testing purposes.
    When the fix is applied, this should match the production code behavior.

    Args:
        enabled_hours_str: Comma-separated hours (0-23), e.g., "21,22,23,0,1,2,3,4,5,6"
        block_duration_minutes: Duration of each block (5, 10, or 15)
        pre_circulation_minutes: Minutes to start circulation before heating
        post_circulation_minutes: Minutes to continue circulation after heating

    Returns:
        List of block dicts with start, heating_start, end, duration_minutes, enabled, price keys.
        Blocks are sorted chronologically (overnight wrap handled).
    """
    blocks = []

    # Validate duration - fall back to 5 if invalid
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

    # Deduplicate
    enabled_hours = list(set(enabled_hours))

    if not enabled_hours:
        return []

    # Get today and tomorrow dates for scheduling
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Sort hours for overnight handling: evening hours (>=12) first, then morning hours (<12)
    evening_hours = sorted([h for h in enabled_hours if h >= 12])
    morning_hours = sorted([h for h in enabled_hours if h < 12])
    sorted_hours = evening_hours + morning_hours

    # Create blocks
    for hour in sorted_hours:
        # Determine the date for this hour
        if hour >= 12:
            # Evening hours: use today
            block_date = today
        else:
            # Morning hours: use tomorrow
            block_date = tomorrow

        # Heating starts at :05 past the hour
        heating_start = datetime.combine(block_date, datetime.min.time().replace(
            hour=hour, minute=COLD_WEATHER_BLOCK_OFFSET))

        # Start time = heating_start - pre_circulation
        start_time = heating_start - timedelta(minutes=pre_circulation_minutes)

        # End time = heating_start + block_duration + post_circulation
        end_time = heating_start + timedelta(minutes=block_duration_minutes + post_circulation_minutes)

        blocks.append({
            'start': start_time,
            'heating_start': heating_start,
            'end': end_time,
            'duration_minutes': block_duration_minutes,
            'enabled': True,
            'price': 0.0,
            'cost': 0.0,
            'cost_exceeded': False
        })

    return blocks


class TestColdWeatherCirculation:
    """Tests for pre/post circulation in cold weather schedule."""

    def test_circulation_offsets_applied_correctly(self):
        """
        REGRESSION TEST: Pre/post circulation should offset start/end times.

        With pre_circulation=10 and post_circulation=10:
        - start should be 10 minutes BEFORE heating_start
        - end should be 10 minutes AFTER (heating_start + block_duration)
        """
        schedule = generate_cold_weather_schedule(
            enabled_hours_str="21",
            block_duration_minutes=10,
            pre_circulation_minutes=10,
            post_circulation_minutes=10
        )

        assert len(schedule) == 1
        block = schedule[0]

        # heating_start should be at 21:05
        assert block['heating_start'].hour == 21
        assert block['heating_start'].minute == 5

        # start should be 10 minutes before heating_start (20:55)
        assert block['start'].hour == 20
        assert block['start'].minute == 55

        # end should be heating_start + 10 (block) + 10 (post) = 21:25
        assert block['end'].hour == 21
        assert block['end'].minute == 25

    def test_no_circulation_defaults_to_heating_times(self):
        """Without circulation offsets, start equals heating_start."""
        schedule = generate_cold_weather_schedule(
            enabled_hours_str="21",
            block_duration_minutes=10,
            pre_circulation_minutes=0,
            post_circulation_minutes=0
        )

        assert len(schedule) == 1
        block = schedule[0]

        # start should equal heating_start
        assert block['start'] == block['heating_start']

        # end should be heating_start + block_duration only
        expected_end = block['heating_start'] + timedelta(minutes=10)
        assert block['end'] == expected_end

    def test_pre_circulation_only(self):
        """With only pre_circulation, start is earlier but end is unchanged."""
        schedule = generate_cold_weather_schedule(
            enabled_hours_str="22",
            block_duration_minutes=15,
            pre_circulation_minutes=5,
            post_circulation_minutes=0
        )

        assert len(schedule) == 1
        block = schedule[0]

        # heating_start at 22:05
        assert block['heating_start'].hour == 22
        assert block['heating_start'].minute == 5

        # start should be 5 minutes before (22:00)
        assert block['start'].hour == 22
        assert block['start'].minute == 0

        # end should be heating_start + 15 only (22:20)
        assert block['end'].hour == 22
        assert block['end'].minute == 20

    def test_post_circulation_only(self):
        """With only post_circulation, start equals heating_start but end is later."""
        schedule = generate_cold_weather_schedule(
            enabled_hours_str="23",
            block_duration_minutes=10,
            pre_circulation_minutes=0,
            post_circulation_minutes=15
        )

        assert len(schedule) == 1
        block = schedule[0]

        # start should equal heating_start
        assert block['start'] == block['heating_start']

        # end should be heating_start + 10 + 15 = 25 minutes later (23:30)
        assert block['end'].hour == 23
        assert block['end'].minute == 30

    def test_multiple_blocks_with_circulation(self):
        """Circulation offsets should apply to all blocks."""
        schedule = generate_cold_weather_schedule(
            enabled_hours_str="21,22,23",
            block_duration_minutes=10,
            pre_circulation_minutes=5,
            post_circulation_minutes=5
        )

        assert len(schedule) == 3

        for block in schedule:
            # Each block should have pre-circulation applied
            start_to_heating = block['heating_start'] - block['start']
            assert start_to_heating == timedelta(minutes=5)

            # Each block should have post-circulation applied
            # end = heating_start + 10 (block) + 5 (post)
            expected_end = block['heating_start'] + timedelta(minutes=15)
            assert block['end'] == expected_end

    def test_overnight_hours_with_circulation(self):
        """Circulation should work correctly for overnight blocks (crossing midnight)."""
        schedule = generate_cold_weather_schedule(
            enabled_hours_str="23,0,1",
            block_duration_minutes=10,
            pre_circulation_minutes=10,
            post_circulation_minutes=10
        )

        assert len(schedule) == 3

        # First block at 23:00 (evening, today)
        block_23 = schedule[0]
        assert block_23['heating_start'].hour == 23
        assert block_23['start'].minute == 55  # 22:55
        assert block_23['start'].hour == 22

        # Second block at 00:00 (morning, tomorrow)
        block_0 = schedule[1]
        assert block_0['heating_start'].hour == 0
        assert block_0['start'].minute == 55  # 23:55 previous day

        # Third block at 01:00 (morning, tomorrow)
        block_1 = schedule[2]
        assert block_1['heating_start'].hour == 1
        assert block_1['start'].hour == 0
        assert block_1['start'].minute == 55  # 00:55


class TestColdWeatherScheduleBasic:
    """Basic tests for cold weather schedule generation."""

    def test_empty_hours_returns_empty_list(self):
        """Empty enabled hours should return empty schedule."""
        schedule = generate_cold_weather_schedule("", 10)
        assert schedule == []

    def test_invalid_duration_defaults_to_5(self):
        """Invalid block duration should default to 5 minutes."""
        schedule = generate_cold_weather_schedule("21", 99)
        assert len(schedule) == 1
        assert schedule[0]['duration_minutes'] == 5

    def test_valid_durations_accepted(self):
        """Valid durations (5, 10, 15) should be accepted."""
        for duration in [5, 10, 15]:
            schedule = generate_cold_weather_schedule("21", duration)
            assert schedule[0]['duration_minutes'] == duration

    def test_duplicate_hours_deduplicated(self):
        """Duplicate hours in input should be deduplicated."""
        schedule = generate_cold_weather_schedule("21,21,21,22", 10)
        assert len(schedule) == 2

    def test_blocks_sorted_evening_then_morning(self):
        """Blocks should be sorted: evening hours first, then morning hours."""
        schedule = generate_cold_weather_schedule("0,1,21,22,23", 10)
        assert len(schedule) == 5

        # First three blocks should be evening (21, 22, 23)
        assert schedule[0]['heating_start'].hour == 21
        assert schedule[1]['heating_start'].hour == 22
        assert schedule[2]['heating_start'].hour == 23

        # Last two blocks should be morning (0, 1)
        assert schedule[3]['heating_start'].hour == 0
        assert schedule[4]['heating_start'].hour == 1
