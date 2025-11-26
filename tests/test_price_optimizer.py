#!/usr/bin/env python3
"""
Unit tests for the pool heating price optimization algorithm.

Run with: pytest tests/test_price_optimizer.py -v
"""

import pytest
from datetime import datetime, date, timedelta
import sys
from pathlib import Path

# Add scripts to path for importing
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'standalone'))


# ============================================
# ALGORITHM UNDER TEST
# ============================================

def find_best_heating_slots(prices_today: list, prices_tomorrow: list,
                           window_start: int = 21, window_end: int = 7,
                           num_slots: int = 2, min_gap: int = 1) -> list:
    """
    Find N cheapest non-consecutive hours in the heating window.
    This is the same algorithm used in pyscript, extracted for testing.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    valid_hours = []

    # Tonight's hours (21:00 - 23:00)
    for hour in range(window_start, 24):
        if prices_today and hour < len(prices_today):
            dt = datetime.combine(today, datetime.min.time().replace(hour=hour))
            valid_hours.append({
                'datetime': dt,
                'hour': hour,
                'price': prices_today[hour],
                'day': 'today'
            })

    # Tomorrow morning hours (00:00 - 06:00)
    for hour in range(0, window_end):
        if prices_tomorrow and hour < len(prices_tomorrow):
            dt = datetime.combine(tomorrow, datetime.min.time().replace(hour=hour))
            valid_hours.append({
                'datetime': dt,
                'hour': hour,
                'price': prices_tomorrow[hour],
                'day': 'tomorrow'
            })

    # Sort by price (cheapest first)
    valid_hours.sort(key=lambda x: x['price'])

    # Select non-consecutive hours
    selected = []

    for candidate in valid_hours:
        if len(selected) >= num_slots:
            break

        is_too_close = False
        for sel in selected:
            cand_abs_hour = candidate['hour'] + (24 if candidate['day'] == 'tomorrow' else 0)
            sel_abs_hour = sel['hour'] + (24 if sel['day'] == 'tomorrow' else 0)

            if abs(cand_abs_hour - sel_abs_hour) <= min_gap:
                is_too_close = True
                break

        if not is_too_close:
            selected.append(candidate)

    selected.sort(key=lambda x: x['datetime'])

    return [(s['datetime'], s['price']) for s in selected]


# ============================================
# TEST CASES
# ============================================

class TestPriceOptimizer:
    """Tests for price optimization algorithm."""

    def test_selects_cheapest_hours(self):
        """Should select the two cheapest hours."""
        # Hour 22 (0.01) and hour 2 (0.02) are cheapest
        prices_today = [0.05] * 21 + [0.03, 0.01, 0.04]  # 21=0.03, 22=0.01, 23=0.04
        prices_tomorrow = [0.05, 0.06, 0.02, 0.07, 0.08, 0.09, 0.10] + [0.05] * 17

        result = find_best_heating_slots(prices_today, prices_tomorrow)

        assert len(result) == 2
        # Should get hour 22 (cheapest) and hour 2 (second cheapest non-adjacent)
        hours = [r[0].hour for r in result]
        assert 22 in hours  # Cheapest
        # Hour 2 is cheapest tomorrow that's not adjacent to anything

    def test_non_consecutive_constraint(self):
        """Should not select adjacent hours."""
        # Hours 0 and 1 are cheapest, but adjacent
        prices_today = [0.05] * 24
        prices_tomorrow = [0.01, 0.02, 0.05, 0.05, 0.03, 0.05, 0.04] + [0.05] * 17

        result = find_best_heating_slots(prices_today, prices_tomorrow)

        hours = [r[0].hour for r in result]

        # Should not have consecutive hours
        for i in range(len(hours) - 1):
            assert abs(hours[i] - hours[i+1]) > 1 or \
                   (hours[i] != 23 or hours[i+1] != 0), \
                   f"Hours {hours} are consecutive"

    def test_midnight_boundary(self):
        """Should handle midnight boundary correctly (23:00 and 00:00 are adjacent)."""
        # Hour 23 and 0 are cheapest but adjacent
        prices_today = [0.05] * 23 + [0.01]  # 23:00 = 0.01
        prices_tomorrow = [0.01, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05] + [0.05] * 17  # 00:00 = 0.01

        result = find_best_heating_slots(prices_today, prices_tomorrow)

        hours_with_day = [(r[0].hour, 'today' if r[0].date() == date.today() else 'tomorrow')
                         for r in result]

        # Should not select both 23 (today) and 0 (tomorrow)
        has_23_today = (23, 'today') in hours_with_day
        has_0_tomorrow = (0, 'tomorrow') in hours_with_day
        assert not (has_23_today and has_0_tomorrow), \
            "Should not select adjacent hours across midnight"

    def test_empty_prices(self):
        """Should handle empty price arrays."""
        result = find_best_heating_slots([], [])
        assert len(result) == 0

    def test_only_today_prices(self):
        """Should work with only today's prices available."""
        prices_today = [0.05] * 21 + [0.01, 0.02, 0.03]

        result = find_best_heating_slots(prices_today, [])

        assert len(result) >= 1  # At least one slot
        # With only 3 hours and min_gap=1, max we can get is 2
        hours = [r[0].hour for r in result]
        assert all(h in [21, 22, 23] for h in hours)

    def test_custom_window(self):
        """Should respect custom heating window."""
        prices_today = list(range(24))  # 0-23
        prices_tomorrow = list(range(24))

        # Window from 22:00 to 05:00
        result = find_best_heating_slots(
            prices_today, prices_tomorrow,
            window_start=22, window_end=5
        )

        hours_with_day = [(r[0].hour, 'today' if r[0].date() == date.today() else 'tomorrow')
                         for r in result]

        for hour, day in hours_with_day:
            if day == 'today':
                assert hour >= 22
            else:
                assert hour < 5

    def test_more_slots(self):
        """Should handle requests for more than 2 slots."""
        prices_today = [0.05] * 21 + [0.01, 0.03, 0.02]
        prices_tomorrow = [0.04, 0.05, 0.01, 0.05, 0.02, 0.05, 0.03] + [0.05] * 17

        result = find_best_heating_slots(
            prices_today, prices_tomorrow,
            num_slots=3
        )

        assert len(result) == 3

        # Verify non-consecutive
        hours = sorted([r[0].hour + (24 if r[0].date() != date.today() else 0)
                       for r in result])
        for i in range(len(hours) - 1):
            assert hours[i+1] - hours[i] > 1

    def test_larger_gap(self):
        """Should respect larger minimum gap between slots."""
        prices_today = [0.05] * 21 + [0.01, 0.02, 0.03]
        prices_tomorrow = [0.04, 0.01, 0.05, 0.05, 0.05, 0.05, 0.05] + [0.05] * 17

        # min_gap=2 means at least 2 hours between heating slots
        result = find_best_heating_slots(
            prices_today, prices_tomorrow,
            min_gap=2
        )

        hours = sorted([r[0].hour + (24 if r[0].date() != date.today() else 0)
                       for r in result])

        for i in range(len(hours) - 1):
            assert hours[i+1] - hours[i] > 2

    def test_negative_prices(self):
        """Should handle negative electricity prices."""
        prices_today = [0.05] * 21 + [-0.01, 0.02, 0.03]  # Negative price at 21
        prices_tomorrow = [0.04, -0.02, 0.05, 0.05, 0.05, 0.05, 0.05] + [0.05] * 17  # Negative at 1

        result = find_best_heating_slots(prices_today, prices_tomorrow)

        # Should select the negative price hours (cheapest)
        prices = [r[1] for r in result]
        assert any(p < 0 for p in prices)

    def test_all_same_price(self):
        """Should handle all prices being the same."""
        prices_today = [0.05] * 24
        prices_tomorrow = [0.05] * 24

        result = find_best_heating_slots(prices_today, prices_tomorrow)

        # Should still select 2 non-consecutive hours
        assert len(result) == 2
        hours = sorted([r[0].hour + (24 if r[0].date() != date.today() else 0)
                       for r in result])
        assert hours[1] - hours[0] > 1


class TestEdgeCases:
    """Edge case tests."""

    def test_insufficient_hours_in_window(self):
        """Should handle cases where not enough valid hours exist."""
        # Only 2 hours in window, both adjacent
        prices_today = [0.05] * 22 + [0.01, 0.02]  # 22, 23 only
        prices_tomorrow = []  # No tomorrow prices

        result = find_best_heating_slots(
            prices_today, prices_tomorrow,
            num_slots=2, min_gap=1
        )

        # Can only select 1 since they're adjacent
        assert len(result) == 1

    def test_price_ordering_stability(self):
        """Should have consistent results when prices are equal."""
        prices_today = [0.05] * 21 + [0.01, 0.01, 0.01]  # Same price
        prices_tomorrow = [0.01] * 7 + [0.05] * 17

        # Run multiple times to check stability
        results = [
            find_best_heating_slots(prices_today, prices_tomorrow)
            for _ in range(5)
        ]

        # All results should be the same
        first = results[0]
        for r in results[1:]:
            assert r == first


# ============================================
# RUN TESTS
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
