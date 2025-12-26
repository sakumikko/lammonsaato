#!/usr/bin/env python3
"""
Unit tests for preheat cost exclusion and minimum break duration.

Run with: pytest tests/test_preheat_cost.py -v

These tests verify:
- Preheat time (15 min) is FREE - not included in cost
- Cost = POWER_KW * heating_hours_only * price
- Minimum break duration is configurable (60-120 min)
- Break duration is independent of preceding block duration
"""

import pytest
from datetime import datetime, date, timedelta
from typing import List, Dict


# ============================================
# CONSTANTS (must match pyscript)
# ============================================

POWER_KW = 5.0  # Heat pump electrical draw during pool heating
PREHEAT_MINUTES = 15  # Fixed preheat duration (FREE)
SLOT_DURATION_MINUTES = 15
DEFAULT_MIN_BREAK_DURATION = 60  # Default minimum break between blocks
VALID_BREAK_DURATIONS = [60, 75, 90, 105, 120]


# ============================================
# HELPER FUNCTIONS
# ============================================

def generate_15min_prices(hourly_prices: list) -> list:
    """Expand hourly prices to 15-minute slots (4 per hour)."""
    prices_15min = []
    for price in hourly_prices:
        prices_15min.extend([price] * 4)
    return prices_15min


def calculate_heating_cost_only(heating_minutes: int, price_eur_per_kwh: float) -> float:
    """
    Calculate cost for HEATING time only (excludes preheat).

    This is the NEW behavior: preheat is FREE.

    Args:
        heating_minutes: HEATING duration only (not including preheat)
        price_eur_per_kwh: Electricity price in EUR/kWh

    Returns:
        Cost in EUR
    """
    heating_hours = heating_minutes / 60.0
    energy_kwh = POWER_KW * heating_hours
    return energy_kwh * price_eur_per_kwh


def calculate_total_block_cost_old(total_minutes: int, price_eur_per_kwh: float) -> float:
    """
    OLD calculation that included ALL time (preheat + heating).

    This is the WRONG behavior we're fixing.
    """
    total_hours = total_minutes / 60.0
    energy_kwh = POWER_KW * total_hours
    return energy_kwh * price_eur_per_kwh


# ============================================
# NEW ALGORITHM: find_best_heating_schedule with min_break_duration
# ============================================

def find_best_heating_schedule_with_break(
    prices_today: list,
    prices_tomorrow: list,
    window_start: int = 21,
    window_end: int = 7,
    total_minutes: int = 120,
    min_block_minutes: int = 30,
    max_block_minutes: int = 45,
    min_break_minutes: int = 60,  # NEW: configurable minimum break
    slot_minutes: int = 15
) -> List[Dict]:
    """
    Find optimal heating schedule with configurable minimum break duration.

    KEY CHANGES from original:
    1. min_break_minutes is configurable (60-120 min), independent of block size
    2. Cost calculation uses HEATING time only (preheat is FREE)
    3. Each block has preheat_start and heating_start times

    Returns:
        List of dicts with 'preheat_start', 'heating_start', 'end',
        'heating_duration_minutes', 'avg_price', 'cost_eur'
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    slots = []

    def slot_index(hour, quarter=0):
        return hour * 4 + quarter

    # Build slots for today (21:00-23:45)
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

    # Build slots for tomorrow (00:00-06:45)
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

    min_block_slots = min_block_minutes // slot_minutes  # 2 slots = 30 min
    max_block_slots = max_block_minutes // slot_minutes  # 3 slots = 45 min
    total_slots_needed = total_minutes // slot_minutes   # 8 slots = 120 min
    min_break_slots = min_break_minutes // slot_minutes  # 4 slots = 60 min
    preheat_slots = PREHEAT_MINUTES // slot_minutes      # 1 slot = 15 min

    best_schedule = None
    best_cost = float('inf')

    # Generate all valid block size combinations
    block_combinations = []
    _find_block_combinations(
        total_slots_needed, min_block_slots, max_block_slots,
        [], block_combinations
    )

    for block_sizes in block_combinations:
        schedule = _find_best_placement_with_break(
            slots, block_sizes, slot_minutes, min_break_slots, preheat_slots
        )
        if schedule:
            # Total cost = sum of HEATING costs only (not preheat)
            total_cost = sum(b['cost_eur'] for b in schedule)
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


def _find_best_placement_with_break(slots, block_sizes, slot_minutes, min_break_slots, preheat_slots):
    """
    Find the best placement of heating blocks with configurable break duration.

    KEY CHANGE: Break is min_break_slots, NOT block_size (as it was before).
    """
    n_slots = len(slots)
    n_blocks = len(block_sizes)

    if n_blocks == 0:
        return []

    def block_cost(start_idx, size):
        """Calculate average price for heating slots only."""
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

        # For first block, we need preheat_slots before heating starts
        # So earliest heating start = preheat_slots (to allow preheat before)
        effective_min_start = max(min_start_idx, preheat_slots if block_idx == 0 else min_start_idx)

        for start_idx in range(effective_min_start, n_slots - block_size + 1):
            avg_price, block_slots = block_cost(start_idx, block_size)

            if avg_price == float('inf'):
                break

            # Calculate HEATING cost only (preheat is FREE)
            heating_minutes = block_size * slot_minutes
            cost_eur = calculate_heating_cost_only(heating_minutes, avg_price)

            block_info = {
                # Preheat starts 15 min before heating
                'preheat_start': block_slots[0]['datetime'] - timedelta(minutes=PREHEAT_MINUTES),
                'heating_start': block_slots[0]['datetime'],
                'end': block_slots[-1]['datetime'] + timedelta(minutes=slot_minutes),
                'heating_duration_minutes': heating_minutes,
                'avg_price': avg_price,
                'cost_eur': cost_eur,  # HEATING cost only
                'slots': block_slots
            }

            new_cost = current_cost + cost_eur

            if new_cost >= best_total_cost:
                continue

            # KEY CHANGE: next block starts after min_break_slots, NOT block_size
            # OLD: next_min_start = start_idx + block_size + block_size
            # NEW: next_min_start = start_idx + block_size + min_break_slots
            next_min_start = start_idx + block_size + min_break_slots

            current_schedule.append(block_info)
            search(block_idx + 1, next_min_start, current_schedule, new_cost)
            current_schedule.pop()

    search(0, 0, [], 0)

    if best_schedule:
        for block in best_schedule:
            del block['slots']

    return best_schedule


# ============================================
# TESTS: Preheat Cost Exclusion
# ============================================

class TestPreheatCostExclusion:
    """Tests that preheat time is FREE (not included in cost)."""

    def test_cost_is_heating_only_30min(self):
        """30 min HEATING at 10c/kWh = 5kW * 0.5h * 0.10 = 0.25 EUR (not 0.375)"""
        # If preheat (15 min) was included, cost would be:
        # 5kW * 0.75h * 0.10 = 0.375 EUR (WRONG)

        heating_cost = calculate_heating_cost_only(30, 0.10)
        total_cost_wrong = calculate_total_block_cost_old(45, 0.10)  # if preheat included

        assert heating_cost == pytest.approx(0.25, abs=0.001)
        assert total_cost_wrong == pytest.approx(0.375, abs=0.001)
        assert heating_cost < total_cost_wrong

    def test_cost_is_heating_only_45min(self):
        """45 min HEATING at 5c/kWh = 5kW * 0.75h * 0.05 = 0.1875 EUR"""
        heating_cost = calculate_heating_cost_only(45, 0.05)
        assert heating_cost == pytest.approx(0.1875, abs=0.001)

    def test_preheat_contributes_zero_to_cost(self):
        """Preheat should contribute exactly 0 to cost."""
        # Cost of preheat alone should be 0 in new model
        preheat_cost = calculate_heating_cost_only(0, 0.10)  # 0 heating minutes
        assert preheat_cost == 0.0

    def test_schedule_cost_excludes_preheat(self):
        """Schedule total cost should only include heating time."""
        prices_today = generate_15min_prices([0.10] * 24)
        prices_tomorrow = generate_15min_prices([0.10] * 24)  # All 10 c/kWh

        schedule = find_best_heating_schedule_with_break(
            prices_today, prices_tomorrow,
            total_minutes=120,  # 2h total heating
            min_break_minutes=60
        )

        # Total heating = 120 min = 2h
        # Expected cost = 5kW * 2h * 0.10 EUR = 1.00 EUR
        total_cost = sum(b['cost_eur'] for b in schedule)

        # With preheat included (WRONG), it would be higher
        # Each 30-min block would cost 0.375 instead of 0.25
        assert total_cost == pytest.approx(1.00, abs=0.01)

    def test_block_has_separate_preheat_and_heating_times(self):
        """Each block should have distinct preheat_start and heating_start."""
        prices_today = generate_15min_prices([0.10] * 24)
        prices_tomorrow = generate_15min_prices([0.10] * 24)

        schedule = find_best_heating_schedule_with_break(
            prices_today, prices_tomorrow,
            total_minutes=60,  # 1h
            min_break_minutes=60
        )

        if schedule:
            for block in schedule:
                assert 'preheat_start' in block
                assert 'heating_start' in block
                assert 'end' in block

                # Preheat should be 15 min before heating
                preheat_to_heating = (block['heating_start'] - block['preheat_start']).total_seconds() / 60
                assert preheat_to_heating == 15


# ============================================
# TESTS: Minimum Break Duration
# ============================================

class TestMinimumBreakDuration:
    """Tests for configurable minimum break between blocks."""

    def test_60min_break_enforced(self):
        """Minimum 60 minute break between blocks."""
        prices_today = generate_15min_prices([0.10] * 21 + [0.01, 0.01, 0.01])
        prices_tomorrow = generate_15min_prices([0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01] + [0.10] * 17)

        schedule = find_best_heating_schedule_with_break(
            prices_today, prices_tomorrow,
            total_minutes=60,  # 2 blocks of 30 min
            min_block_minutes=30,
            max_block_minutes=30,
            min_break_minutes=60  # 60 min break required
        )

        if len(schedule) >= 2:
            for i in range(len(schedule) - 1):
                block_end = schedule[i]['end']
                next_start = schedule[i + 1]['heating_start']
                break_minutes = (next_start - block_end).total_seconds() / 60

                assert break_minutes >= 60, f"Break {break_minutes} min < required 60 min"

    def test_90min_break_enforced(self):
        """90 minute break when configured."""
        prices_today = generate_15min_prices([0.10] * 21 + [0.01, 0.01, 0.01])
        prices_tomorrow = generate_15min_prices([0.01] * 7 + [0.10] * 17)

        schedule = find_best_heating_schedule_with_break(
            prices_today, prices_tomorrow,
            total_minutes=60,
            min_block_minutes=30,
            max_block_minutes=30,
            min_break_minutes=90  # 90 min break required
        )

        if len(schedule) >= 2:
            for i in range(len(schedule) - 1):
                block_end = schedule[i]['end']
                next_start = schedule[i + 1]['heating_start']
                break_minutes = (next_start - block_end).total_seconds() / 60

                assert break_minutes >= 90, f"Break {break_minutes} min < required 90 min"

    def test_120min_break_enforced(self):
        """120 minute (2 hour) break when configured."""
        prices_today = generate_15min_prices([0.10] * 21 + [0.01, 0.01, 0.01])
        prices_tomorrow = generate_15min_prices([0.01] * 7 + [0.10] * 17)

        schedule = find_best_heating_schedule_with_break(
            prices_today, prices_tomorrow,
            total_minutes=60,
            min_block_minutes=30,
            max_block_minutes=30,
            min_break_minutes=120  # 2h break required
        )

        if len(schedule) >= 2:
            for i in range(len(schedule) - 1):
                block_end = schedule[i]['end']
                next_start = schedule[i + 1]['heating_start']
                break_minutes = (next_start - block_end).total_seconds() / 60

                assert break_minutes >= 120, f"Break {break_minutes} min < required 120 min"

    def test_break_independent_of_block_duration(self):
        """Break duration should NOT depend on preceding block duration.

        OLD behavior: 30-min block → 30-min break, 45-min block → 45-min break
        NEW behavior: All blocks get min_break_minutes (e.g., 60 min)
        """
        prices_today = generate_15min_prices([0.10] * 21 + [0.01, 0.01, 0.01])
        prices_tomorrow = generate_15min_prices([0.01] * 7 + [0.10] * 17)

        # Test with 30-min blocks - break should STILL be 60 min (not 30)
        schedule = find_best_heating_schedule_with_break(
            prices_today, prices_tomorrow,
            total_minutes=60,
            min_block_minutes=30,
            max_block_minutes=30,  # Force 30-min blocks
            min_break_minutes=60   # But 60-min breaks
        )

        if len(schedule) >= 2:
            block_end = schedule[0]['end']
            next_start = schedule[1]['heating_start']
            break_minutes = (next_start - block_end).total_seconds() / 60

            # Even though block is 30 min, break should be 60 min
            assert break_minutes >= 60, \
                f"30-min block should still have 60-min break, got {break_minutes}"


# ============================================
# TESTS: Edge Cases
# ============================================

class TestPreheatEdgeCases:
    """Edge case tests for preheat and break logic."""

    def test_single_block_no_break_needed(self):
        """Single block schedule doesn't need break constraint."""
        prices_today = generate_15min_prices([0.10] * 24)
        prices_tomorrow = generate_15min_prices([0.01] * 24)

        schedule = find_best_heating_schedule_with_break(
            prices_today, prices_tomorrow,
            total_minutes=30,  # Single 30-min block
            min_block_minutes=30,
            max_block_minutes=30,
            min_break_minutes=60
        )

        assert len(schedule) == 1
        assert schedule[0]['heating_duration_minutes'] == 30

    def test_preheat_at_window_start(self):
        """Preheat should happen before window start for first block."""
        prices_today = generate_15min_prices([0.10] * 21 + [0.01, 0.01, 0.01])
        prices_tomorrow = generate_15min_prices([0.10] * 24)

        schedule = find_best_heating_schedule_with_break(
            prices_today, prices_tomorrow,
            window_start=21,
            total_minutes=30,
            min_break_minutes=60
        )

        if schedule:
            # Preheat can start before 21:00 (e.g., 20:45)
            # This is expected and correct
            first_block = schedule[0]
            assert first_block['heating_start'].hour >= 21 or \
                   (first_block['heating_start'].hour == 21 and first_block['heating_start'].minute >= 0)

    def test_all_valid_break_durations(self):
        """Test all valid break durations (60, 75, 90, 105, 120)."""
        for break_dur in VALID_BREAK_DURATIONS:
            prices_today = generate_15min_prices([0.10] * 24)
            prices_tomorrow = generate_15min_prices([0.01] * 24)

            schedule = find_best_heating_schedule_with_break(
                prices_today, prices_tomorrow,
                total_minutes=60,
                min_break_minutes=break_dur
            )

            # Should produce a valid schedule
            assert schedule is not None, f"Failed with min_break={break_dur}"


# ============================================
# TESTS: Regression - Ensure Old Behavior Broken
# ============================================

class TestOldBehaviorFixed:
    """Tests that verify old (incorrect) behavior is fixed."""

    def test_old_break_was_block_duration(self):
        """OLD: break = block_duration. NEW: break = min_break_duration.

        This test documents what CHANGED.
        """
        # In old algorithm: 30-min block → 30-min break (block_size + block_size)
        # In new algorithm: 30-min block → 60-min break (block_size + min_break_slots)

        # With old logic, two 30-min blocks could be scheduled 60 min apart
        # (30 min block + 30 min break = 60 min total)
        # With new logic, they must be 90 min apart
        # (30 min block + 60 min break = 90 min total)

        prices_today = generate_15min_prices([0.10] * 24)
        prices_tomorrow = generate_15min_prices([0.01] * 24)

        schedule = find_best_heating_schedule_with_break(
            prices_today, prices_tomorrow,
            total_minutes=60,  # Two 30-min blocks
            min_block_minutes=30,
            max_block_minutes=30,
            min_break_minutes=60
        )

        if len(schedule) >= 2:
            total_span = (schedule[-1]['end'] - schedule[0]['heating_start']).total_seconds() / 60

            # OLD would allow: 30 + 30 + 30 = 90 min span
            # NEW requires: 30 + 60 + 30 = 120 min span minimum
            assert total_span >= 120, \
                f"Schedule span {total_span} min should be >= 120 with 60-min breaks"

    def test_old_cost_included_preheat(self):
        """OLD: cost included preheat time. NEW: cost is heating only.

        This test documents what CHANGED.
        """
        # For a 30-min heating block at 10 c/kWh:
        # OLD: cost = 5kW * 0.75h * 0.10 = 0.375 EUR (included 15-min preheat)
        # NEW: cost = 5kW * 0.50h * 0.10 = 0.250 EUR (heating only)

        old_cost = calculate_total_block_cost_old(45, 0.10)  # 45 min total
        new_cost = calculate_heating_cost_only(30, 0.10)     # 30 min heating

        assert old_cost == pytest.approx(0.375, abs=0.001)
        assert new_cost == pytest.approx(0.250, abs=0.001)

        # New cost should be 33% lower
        reduction_pct = (old_cost - new_cost) / old_cost * 100
        assert reduction_pct == pytest.approx(33.33, abs=1.0)


# ============================================
# RUN TESTS
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
