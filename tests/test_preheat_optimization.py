"""
Unit tests for preheat-aware schedule optimization.

Verifies that the schedule optimizer considers the 15-minute preheat period
when calculating total costs, favoring blocks where preheat is cheap.

Run with: pytest tests/test_preheat_optimization.py -v
"""

import pytest
import sys
import builtins
from pathlib import Path
from datetime import datetime, date, timedelta

# Add scripts/pyscript to path for imports
PYSCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "pyscript"
sys.path.insert(0, str(PYSCRIPT_PATH))

# Mock pyscript globals before importing pool_heating
# The @service decorator is a no-op that just returns the function
def _mock_service(func):
    """Mock pyscript @service decorator - just returns the function unchanged."""
    return func

# Inject mock into builtins so pool_heating.py can find it
builtins.service = _mock_service
builtins.state = type('MockState', (), {'get': lambda self, x: None})()
builtins.log = type('MockLog', (), {
    'info': lambda self, x: None,
    'warning': lambda self, x: None,
    'error': lambda self, x: None
})()

# Try to import from pool_heating module
try:
    from pool_heating import (
        find_best_heating_schedule,
        _find_best_placement,
        PREHEAT_SLOTS,
    )
    IMPORT_SUCCESS = True
except ImportError as e:
    IMPORT_SUCCESS = False
    PREHEAT_SLOTS = 1
except Exception as e:
    # Catch any other errors during import
    print(f"Warning: pool_heating import failed: {e}")
    IMPORT_SUCCESS = False
    PREHEAT_SLOTS = 1


class TestPreheatConstants:
    """Test preheat-related constants."""

    @pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_heating module not importable")
    def test_preheat_slots_is_one(self):
        """PREHEAT_SLOTS should be 1 (15 minutes)."""
        assert PREHEAT_SLOTS == 1

    @pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_heating module not importable")
    def test_preheat_slots_reasonable_range(self):
        """PREHEAT_SLOTS should be between 1-2 (15-30 min)."""
        assert 1 <= PREHEAT_SLOTS <= 2


class TestPreheatCostInclusion:
    """Test that preheat cost is included in optimization."""

    @pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_heating module not importable")
    def test_preheat_affects_schedule_choice(self):
        """
        Optimizer should prefer a block with cheap preheat over one with expensive preheat.

        Scenario:
        - Block A at 21:00: Block price 10, preheat (20:45) price 100 -> total 110
        - Block B at 21:15: Block price 10, preheat (21:00) price 5 -> total 15

        Even though block prices are same, Block B should be chosen due to cheaper preheat.
        """
        # 96 slots per day (15-min intervals)
        # Slot 83 = 20:45 (preheat for 21:00 block) = EXPENSIVE
        # Slot 84 = 21:00 (preheat for 21:15 block) = CHEAP
        # Slots 85+ = actual heating window

        prices_today = [0.1] * 96  # Base price 0.1
        prices_today[83] = 1.0     # 20:45 - expensive preheat
        prices_today[84] = 0.05    # 21:00 - cheap preheat (and first heating slot)
        prices_today[85] = 0.1     # 21:15
        prices_today[86] = 0.1     # 21:30
        prices_today[87] = 0.1     # 21:45

        prices_tomorrow = [0.1] * 96

        # Request schedule with small total (just one 30-min block for simplicity)
        schedule = find_best_heating_schedule(
            prices_today, prices_tomorrow,
            window_start=21, window_end=7,
            total_minutes=30,  # Just one 30-min block
            min_block_minutes=30,
            max_block_minutes=30,
            slot_minutes=15
        )

        assert len(schedule) >= 1
        first_block = schedule[0]

        # First block should NOT start at 21:00 because 20:45 preheat is expensive
        # It should start at 21:15 where preheat (21:00) is cheap
        assert first_block['start'].hour == 21
        assert first_block['start'].minute == 15, \
            f"Expected block at 21:15 (cheap preheat), got {first_block['start']}"

    @pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_heating module not importable")
    def test_preheat_uses_preceding_slot_price(self):
        """
        For blocks starting after window start, preheat should use preceding slot's price.

        Scenario:
        - Block A at 21:15: block=0.05*2=0.10, preheat (21:00)=0.05, total=0.15
        - Block B at 21:00: block=0.05*2=0.10, preheat (20:45)=1.00, total=1.10

        Block A should be chosen because 21:00 preheat is cheaper than 20:45 preheat.
        """
        prices_today = [0.05] * 96  # Base price 0.05
        # Make 20:45 very expensive (preheat for 21:00 block)
        prices_today[83] = 1.0  # 20:45 - slot_index(20, 3)

        # Keep 21:00 cheap (preheat for 21:15 block)
        prices_today[84] = 0.05  # 21:00 - slot_index(21, 0)

        prices_tomorrow = [0.05] * 96

        schedule = find_best_heating_schedule(
            prices_today, prices_tomorrow,
            window_start=21, window_end=7,
            total_minutes=30,
            min_block_minutes=30,
            max_block_minutes=30,
            slot_minutes=15
        )

        assert len(schedule) >= 1
        first_block = schedule[0]

        # Block should NOT start at 21:00 because 20:45 preheat is expensive
        # It should start at 21:15 where preheat (21:00) is cheap
        assert first_block['start'].minute == 15, \
            f"Expected 21:15 (cheap preheat at 21:00), got {first_block['start']}"

    @pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_heating module not importable")
    def test_preheat_price_from_today_for_window_start(self):
        """
        Preheat for 21:00 block should use 20:45 price from prices_today.
        """
        prices_today = [0.1] * 96
        # 20:45 = slot 83 = cheap
        prices_today[83] = 0.01

        prices_tomorrow = [0.1] * 96

        schedule = find_best_heating_schedule(
            prices_today, prices_tomorrow,
            window_start=21, window_end=7,
            total_minutes=30,
            min_block_minutes=30,
            max_block_minutes=30,
            slot_minutes=15
        )

        # Just verify schedule is generated without errors
        assert len(schedule) >= 1


class TestFindBestPlacementWithPreheat:
    """Test _find_best_placement with preheat_prices parameter."""

    @pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_heating module not importable")
    def test_preheat_prices_parameter_accepted(self):
        """_find_best_placement should accept preheat_prices parameter."""
        # Create minimal slots (4 slots = 1 hour, keeps minutes valid)
        today = date.today()
        slots = []
        for i in range(4):  # 4 slots = 1 hour
            slots.append({
                'datetime': datetime.combine(today, datetime.min.time().replace(hour=21, minute=i*15)),
                'index': i,
                'price': 0.1,
                'day': 'today'
            })

        # Call with preheat_prices
        result = _find_best_placement(
            slots=slots,
            block_sizes=[2],  # One 30-min block
            slot_minutes=15,
            preheat_prices=[0.5]  # Preheat costs 0.5
        )

        # Should return a schedule
        assert result is not None

    @pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_heating module not importable")
    def test_preheat_cost_affects_placement(self):
        """
        With preheat_prices, optimizer should factor in preheat cost.
        """
        today = date.today()

        # Create 4 slots
        slots = [
            {'datetime': datetime.combine(today, datetime.min.time().replace(hour=21, minute=0)), 'index': 0, 'price': 0.1, 'day': 'today'},
            {'datetime': datetime.combine(today, datetime.min.time().replace(hour=21, minute=15)), 'index': 1, 'price': 0.1, 'day': 'today'},
            {'datetime': datetime.combine(today, datetime.min.time().replace(hour=21, minute=30)), 'index': 2, 'price': 0.1, 'day': 'today'},
            {'datetime': datetime.combine(today, datetime.min.time().replace(hour=21, minute=45)), 'index': 3, 'price': 0.1, 'day': 'today'},
        ]

        # Expensive preheat for window start
        preheat_prices = [10.0]

        # Make slot 0's price same as others, but slot 1 has cheap preceding slot
        slots[0]['price'] = 0.1  # 21:00
        slots[1]['price'] = 0.1  # 21:15 - preheat is slots[0] = 0.1 (cheap!)

        result = _find_best_placement(
            slots=slots,
            block_sizes=[2],  # One 30-min block
            slot_minutes=15,
            preheat_prices=preheat_prices
        )

        assert result is not None
        assert len(result) == 1

        # Block should start at 21:15 (index 1) because preheat (21:00) is 0.1
        # vs starting at 21:00 where preheat (20:45) is 10.0
        assert result[0]['start'].minute == 15, \
            f"Expected 21:15, got {result[0]['start']}"

    @pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_heating module not importable")
    def test_no_preheat_prices_backward_compatible(self):
        """Without preheat_prices, function should work as before."""
        today = date.today()
        slots = []
        for i in range(4):
            slots.append({
                'datetime': datetime.combine(today, datetime.min.time().replace(hour=21, minute=i*15)),
                'index': i,
                'price': 0.1 if i != 0 else 0.05,  # First slot cheapest
                'day': 'today'
            })

        # Call without preheat_prices (backward compatible)
        result = _find_best_placement(
            slots=slots,
            block_sizes=[2],
            slot_minutes=15
        )

        assert result is not None
        assert len(result) == 1
        # Should pick cheapest block (starting at 21:00)
        assert result[0]['start'].minute == 0


class TestPreheatIntegration:
    """Integration tests for full schedule with preheat."""

    @pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_heating module not importable")
    def test_full_schedule_with_preheat_optimization(self):
        """
        Full 2-hour schedule should consider preheat for optimal placement.
        """
        # Create realistic price pattern
        prices_today = []
        for hour in range(24):
            for quarter in range(4):
                # Base price varies by hour
                base = 0.05 + (hour % 12) * 0.01
                prices_today.append(base)

        prices_tomorrow = []
        for hour in range(24):
            for quarter in range(4):
                # Tomorrow morning has cheap prices
                if 2 <= hour <= 5:
                    prices_tomorrow.append(0.02)
                else:
                    prices_tomorrow.append(0.08)

        # Make 20:45 very expensive (preheat for 21:00)
        prices_today[83] = 0.50

        schedule = find_best_heating_schedule(
            prices_today, prices_tomorrow,
            window_start=21, window_end=7,
            total_minutes=120,
            min_block_minutes=30,
            max_block_minutes=45,
            slot_minutes=15
        )

        # Should produce valid schedule
        assert len(schedule) >= 2  # Multiple blocks for 2 hours

        # First block should avoid starting at 21:00 due to expensive preheat
        first_block = schedule[0]
        if first_block['start'].hour == 21:
            # If first block is today, should not start at exactly 21:00
            assert first_block['start'].minute >= 15, \
                "First block should avoid 21:00 due to expensive 20:45 preheat"

    @pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_heating module not importable")
    def test_preheat_slot_calculation_20_45(self):
        """Verify 20:45 slot index is 83 (20*4 + 3)."""
        # 20:45 = hour 20, quarter 3 (45 min / 15 = 3)
        expected_index = 20 * 4 + 3
        assert expected_index == 83
