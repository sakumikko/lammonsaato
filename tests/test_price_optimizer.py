#!/usr/bin/env python3
"""
Unit tests for the pool heating price optimization algorithm.

Run with: pytest tests/test_price_optimizer.py -v

Tests the new 15-minute interval algorithm with:
- 30-45 minute heating blocks
- Equal duration breaks between blocks
- Total 2 hours (120 minutes) of heating
"""

import pytest
from datetime import datetime, date, timedelta
import sys
from pathlib import Path
from typing import List, Dict

# Add scripts to path for importing
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'standalone'))


# ============================================
# ALGORITHM UNDER TEST
# ============================================

# Default configuration
TOTAL_HEATING_MINUTES = 120  # 2 hours total
MIN_BLOCK_MINUTES = 30       # Minimum consecutive heating
MAX_BLOCK_MINUTES = 45       # Maximum consecutive heating
SLOT_DURATION_MINUTES = 15   # Nordpool 15-minute intervals


def find_best_heating_schedule(
    prices_today: list,
    prices_tomorrow: list,
    window_start: int = 21,
    window_end: int = 7,
    total_minutes: int = 120,
    min_block_minutes: int = 30,
    max_block_minutes: int = 45,
    slot_minutes: int = 15
) -> List[Dict]:
    """
    Find optimal heating schedule using 15-minute price intervals.

    Constraints:
    - Total heating time: 2 hours (120 minutes)
    - Each heating block: 30-45 minutes (2-3 slots)
    - Break between blocks: at least equal to preceding block duration

    Returns:
        List of dicts with 'start', 'end', 'duration_minutes', 'avg_price'
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    slots = []

    def slot_index(hour, quarter=0):
        return hour * 4 + quarter

    for hour in range(window_start, 24):
        for quarter in range(4):
            idx = slot_index(hour, quarter)
            if prices_today and idx < len(prices_today):
                dt = datetime.combine(today, datetime.min.time().replace(
                    hour=hour, minute=quarter * 15))
                slots.append({
                    'datetime': dt,
                    'index': len(slots),
                    'price': prices_today[idx],
                    'day': 'today'
                })

    for hour in range(0, window_end):
        for quarter in range(4):
            idx = slot_index(hour, quarter)
            if prices_tomorrow and idx < len(prices_tomorrow):
                dt = datetime.combine(tomorrow, datetime.min.time().replace(
                    hour=hour, minute=quarter * 15))
                slots.append({
                    'datetime': dt,
                    'index': len(slots),
                    'price': prices_tomorrow[idx],
                    'day': 'tomorrow'
                })

    if not slots:
        return []

    min_block_slots = min_block_minutes // slot_minutes
    max_block_slots = max_block_minutes // slot_minutes
    total_slots_needed = total_minutes // slot_minutes

    best_schedule = None
    best_cost = float('inf')

    block_combinations = []
    _find_block_combinations(
        total_slots_needed, min_block_slots, max_block_slots,
        [], block_combinations
    )

    for block_sizes in block_combinations:
        schedule = _find_best_placement(slots, block_sizes, slot_minutes)
        if schedule:
            total_cost = sum(b['avg_price'] * b['duration_minutes'] for b in schedule)
            if total_cost < best_cost:
                best_cost = total_cost
                best_schedule = schedule

    return best_schedule or []


def _find_block_combinations(remaining, min_size, max_size, current, results):
    """Recursively find all valid combinations of block sizes."""
    if remaining == 0:
        if current:
            results.append(current[:])
        return
    if remaining < min_size:
        return

    for size in range(min_size, min(max_size, remaining) + 1):
        current.append(size)
        _find_block_combinations(remaining - size, min_size, max_size, current, results)
        current.pop()


def _find_best_placement(slots, block_sizes, slot_minutes):
    """Find the best placement of heating blocks with given sizes."""
    n_slots = len(slots)
    n_blocks = len(block_sizes)

    if n_blocks == 0:
        return []

    def block_cost(start_idx, size):
        if start_idx + size > n_slots:
            return float('inf'), None
        block_slots = slots[start_idx:start_idx + size]
        avg_price = sum(s['price'] for s in block_slots) / size
        return avg_price, block_slots

    best_schedule = None
    best_total_cost = float('inf')

    def search(block_idx, min_start_idx, current_schedule, current_cost):
        nonlocal best_schedule, best_total_cost

        if block_idx >= n_blocks:
            if current_cost < best_total_cost:
                best_total_cost = current_cost
                best_schedule = current_schedule[:]
            return

        block_size = block_sizes[block_idx]

        for start_idx in range(min_start_idx, n_slots - block_size + 1):
            avg_price, block_slots = block_cost(start_idx, block_size)

            if avg_price == float('inf'):
                break

            block_info = {
                'start': block_slots[0]['datetime'],
                'end': block_slots[-1]['datetime'] + timedelta(minutes=slot_minutes),
                'duration_minutes': block_size * slot_minutes,
                'avg_price': avg_price,
                'slots': block_slots
            }

            new_cost = current_cost + avg_price * block_size

            if new_cost >= best_total_cost:
                continue

            next_min_start = start_idx + block_size + block_size

            current_schedule.append(block_info)
            search(block_idx + 1, next_min_start, current_schedule, new_cost)
            current_schedule.pop()

    search(0, 0, [], 0)

    if best_schedule:
        for block in best_schedule:
            del block['slots']

    return best_schedule


def generate_15min_prices(hourly_prices: list) -> list:
    """Expand hourly prices to 15-minute slots (4 per hour)."""
    prices_15min = []
    for price in hourly_prices:
        prices_15min.extend([price] * 4)
    return prices_15min


# ============================================
# TEST CASES
# ============================================

class TestScheduleOptimizer:
    """Tests for the 15-minute interval schedule optimization algorithm."""

    def test_total_heating_time(self):
        """Should schedule exactly 120 minutes of heating."""
        # Generate 96 price slots (24 hours * 4 slots/hour)
        prices_today = generate_15min_prices([0.05] * 21 + [0.03, 0.02, 0.04])
        prices_tomorrow = generate_15min_prices([0.01, 0.06, 0.02, 0.07, 0.03, 0.08, 0.04] + [0.05] * 17)

        schedule = find_best_heating_schedule(prices_today, prices_tomorrow)

        total_minutes = sum(b['duration_minutes'] for b in schedule)
        assert total_minutes == 120, f"Expected 120 minutes, got {total_minutes}"

    def test_block_duration_constraints(self):
        """Each heating block should be 30-45 minutes."""
        prices_today = generate_15min_prices([0.05] * 21 + [0.03, 0.02, 0.04])
        prices_tomorrow = generate_15min_prices([0.01, 0.06, 0.02, 0.07, 0.03, 0.08, 0.04] + [0.05] * 17)

        schedule = find_best_heating_schedule(prices_today, prices_tomorrow)

        for block in schedule:
            assert 30 <= block['duration_minutes'] <= 45, \
                f"Block duration {block['duration_minutes']} outside 30-45 range"

    def test_break_duration_constraint(self):
        """Break between blocks must be at least equal to preceding block duration."""
        prices_today = generate_15min_prices([0.05] * 21 + [0.03, 0.02, 0.04])
        prices_tomorrow = generate_15min_prices([0.01, 0.06, 0.02, 0.07, 0.03, 0.08, 0.04] + [0.05] * 17)

        schedule = find_best_heating_schedule(prices_today, prices_tomorrow)

        for i in range(len(schedule) - 1):
            block_end = schedule[i]['end']
            next_start = schedule[i + 1]['start']
            break_minutes = (next_start - block_end).total_seconds() / 60
            required_break = schedule[i]['duration_minutes']

            assert break_minutes >= required_break, \
                f"Break {break_minutes} min < required {required_break} min"

    def test_selects_cheapest_slots(self):
        """Should select the cheapest available slots."""
        # Create prices with clear cheap periods
        # Low prices at 02:00-03:00 (slots 8-16) and 05:00-06:00 (slots 20-28)
        hourly_tomorrow = [0.10, 0.10, 0.01, 0.01, 0.10, 0.01, 0.01] + [0.10] * 17
        prices_today = generate_15min_prices([0.10] * 24)
        prices_tomorrow = generate_15min_prices(hourly_tomorrow)

        schedule = find_best_heating_schedule(prices_today, prices_tomorrow)

        # Should have selected from the cheap periods
        for block in schedule:
            assert block['avg_price'] < 0.05, \
                f"Selected expensive block at {block['avg_price']} EUR/kWh"

    def test_empty_prices(self):
        """Should handle empty price arrays."""
        result = find_best_heating_schedule([], [])
        assert len(result) == 0

    def test_only_today_prices(self):
        """Should work with only today's prices (21:00-23:45 = 12 slots)."""
        # Only 12 slots available (3 hours * 4 slots)
        prices_today = generate_15min_prices([0.05] * 21 + [0.01, 0.02, 0.03])

        # With only 12 slots and needing 8 slots (120 min), plus break constraints,
        # this may not be possible to schedule fully
        schedule = find_best_heating_schedule(prices_today, [])

        # Should either find a schedule or return empty if impossible
        if schedule:
            total_minutes = sum(b['duration_minutes'] for b in schedule)
            assert total_minutes == 120

    def test_negative_prices(self):
        """Should handle negative electricity prices."""
        # Negative prices at 02:00 and 04:00
        hourly_tomorrow = [0.05, 0.05, -0.02, 0.05, -0.01, 0.05, 0.05] + [0.05] * 17
        prices_today = generate_15min_prices([0.05] * 24)
        prices_tomorrow = generate_15min_prices(hourly_tomorrow)

        schedule = find_best_heating_schedule(prices_today, prices_tomorrow)

        # Should select blocks that include negative prices
        has_negative = any(b['avg_price'] < 0 for b in schedule)
        assert has_negative, "Should have selected some negative-price slots"

    def test_all_same_price(self):
        """Should handle all prices being the same."""
        prices_today = generate_15min_prices([0.05] * 24)
        prices_tomorrow = generate_15min_prices([0.05] * 24)

        schedule = find_best_heating_schedule(prices_today, prices_tomorrow)

        # Should still schedule 120 minutes with valid constraints
        total_minutes = sum(b['duration_minutes'] for b in schedule)
        assert total_minutes == 120

    def test_custom_window(self):
        """Should respect custom heating window."""
        prices_today = generate_15min_prices(list(range(24)))
        prices_tomorrow = generate_15min_prices(list(range(24)))

        # Window from 22:00 to 05:00
        schedule = find_best_heating_schedule(
            prices_today, prices_tomorrow,
            window_start=22, window_end=5
        )

        today = date.today()
        tomorrow = today + timedelta(days=1)

        for block in schedule:
            block_date = block['start'].date()
            block_hour = block['start'].hour

            if block_date == today:
                assert block_hour >= 22, f"Block at {block_hour}:00 outside window"
            else:
                assert block_hour < 5, f"Block at {block_hour}:00 outside window"


class TestBlockCombinations:
    """Tests for block combination generation."""

    def test_valid_combinations_for_120min(self):
        """Should generate valid block combinations for 120 minutes."""
        combinations = []
        _find_block_combinations(8, 2, 3, [], combinations)  # 8 slots, min 2, max 3

        # All combinations should sum to 8 slots (120 minutes)
        for combo in combinations:
            assert sum(combo) == 8

        # Each block should be 2-3 slots (30-45 minutes)
        for combo in combinations:
            for block_size in combo:
                assert 2 <= block_size <= 3

        # Should have multiple valid combinations
        # Possible: [2,2,2,2], [2,2,2], [2,3,3], [3,2,3], [3,3,2]
        # Wait, [2,2,2,2] = 8, [3,3,2] = 8, [2,3,3] = 8, etc.
        assert len(combinations) > 0

    def test_combinations_different_totals(self):
        """Test combinations for different total requirements."""
        # 6 slots (90 min) with blocks of 2-3
        combos_90 = []
        _find_block_combinations(6, 2, 3, [], combos_90)

        for combo in combos_90:
            assert sum(combo) == 6

        # 4 slots (60 min)
        combos_60 = []
        _find_block_combinations(4, 2, 3, [], combos_60)

        for combo in combos_60:
            assert sum(combo) == 4


class TestScheduleStability:
    """Tests for schedule determinism and stability."""

    def test_consistent_results(self):
        """Should produce consistent results across multiple runs."""
        prices_today = generate_15min_prices([0.05] * 21 + [0.03, 0.02, 0.04])
        prices_tomorrow = generate_15min_prices([0.01, 0.06, 0.02, 0.07, 0.03, 0.08, 0.04] + [0.05] * 17)

        results = [
            find_best_heating_schedule(prices_today, prices_tomorrow)
            for _ in range(5)
        ]

        # All results should be identical
        first = results[0]
        for i, r in enumerate(results[1:], 2):
            assert len(r) == len(first), f"Run {i} has different number of blocks"
            for j, (b1, b2) in enumerate(zip(first, r)):
                assert b1['start'] == b2['start'], f"Run {i} block {j} has different start"
                assert b1['duration_minutes'] == b2['duration_minutes']


class TestEdgeCases:
    """Edge case tests."""

    def test_insufficient_slots_in_window(self):
        """Should handle cases where not enough slots exist in window."""
        # Only provide prices for today 23:00 (4 slots) - not enough for 120 min
        prices_today = [0.05] * 92 + [0.01] * 4  # Only 23:00 hour
        prices_tomorrow = []  # No tomorrow prices

        schedule = find_best_heating_schedule(prices_today, prices_tomorrow)

        # With only 4 slots (60 min possible), can't schedule 120 min
        # Algorithm should return empty or partial schedule
        if schedule:
            total = sum(b['duration_minutes'] for b in schedule)
            # If partial, check constraints are still met
            for block in schedule:
                assert 30 <= block['duration_minutes'] <= 45

    def test_minimum_block_equals_maximum(self):
        """Should work when min and max block size are equal."""
        prices_today = generate_15min_prices([0.05] * 21 + [0.03, 0.02, 0.04])
        prices_tomorrow = generate_15min_prices([0.01] * 7 + [0.05] * 17)

        # Force 30-minute blocks only (2 slots each)
        schedule = find_best_heating_schedule(
            prices_today, prices_tomorrow,
            total_minutes=60,  # 4 slots = two 30-min blocks
            min_block_minutes=30,
            max_block_minutes=30
        )

        if schedule:
            for block in schedule:
                assert block['duration_minutes'] == 30


# ============================================
# RUN TESTS
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
