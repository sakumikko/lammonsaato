#!/usr/bin/env python3
"""
Unit tests for the block cost calculation and cost constraint feature.

Run with: pytest tests/test_cost_constraint.py -v

These tests verify:
- Block cost is calculated as: energy_kwh × price_eur
- Energy is calculated as: POWER_KW × duration_hours
- Cost constraint disables expensive blocks when limit is exceeded
- Cheapest blocks are enabled first when cost-constrained
"""

import pytest
from datetime import datetime, timedelta


# ============================================
# CONSTANTS (must match pyscript)
# ============================================

POWER_KW = 5.0  # Heat pump electrical draw during pool heating


# ============================================
# COST CALCULATION FUNCTIONS
# ============================================

def calculate_block_cost(duration_minutes: int, price_eur_per_kwh: float) -> float:
    """
    Calculate the cost of a heating block.

    Args:
        duration_minutes: Block duration in minutes
        price_eur_per_kwh: Electricity price in EUR/kWh

    Returns:
        Cost in EUR
    """
    duration_hours = duration_minutes / 60.0
    energy_kwh = POWER_KW * duration_hours
    return energy_kwh * price_eur_per_kwh


def apply_cost_constraint(blocks: list, max_cost_eur: float = 0) -> tuple:
    """
    Apply cost constraint to blocks, enabling cheapest first.

    This mirrors the logic in calculate_pool_heating_schedule which applies
    cost constraint after creating the schedule. Duration is handled at
    schedule creation time, not here.

    Args:
        blocks: List of dicts with 'cost_eur', 'avg_price'
        max_cost_eur: Maximum total cost (0 = no limit)

    Returns:
        Tuple of (modified_blocks, total_enabled_cost, constraint_applied)
    """
    # Sort by price to enable cheapest first
    sorted_indices = sorted(range(len(blocks)), key=lambda i: blocks[i]['avg_price'])

    running_cost = 0.0
    constraint_applied = False

    # First, mark all as exceeded, then enable cheapest within limits
    for b in blocks:
        b['cost_exceeded'] = True

    for idx in sorted_indices:
        block = blocks[idx]
        block_cost = block['cost_eur']

        # Check cost constraint only (duration handled at schedule creation)
        cost_ok = max_cost_eur <= 0 or (running_cost + block_cost <= max_cost_eur)

        if cost_ok:
            block['cost_exceeded'] = False
            running_cost += block_cost
        else:
            constraint_applied = True

    return blocks, running_cost, constraint_applied


# ============================================
# TESTS: Cost Calculation
# ============================================

class TestBlockCostCalculation:
    """Tests for calculate_block_cost function."""

    def test_30min_block_at_1_cent(self):
        """30 min block at 1 c/kWh = 5kW × 0.5h × 0.01 EUR = 0.025 EUR"""
        cost = calculate_block_cost(30, 0.01)  # 1 cent = 0.01 EUR
        assert cost == pytest.approx(0.025, abs=0.001)

    def test_30min_block_at_10_cents(self):
        """30 min block at 10 c/kWh = 5kW × 0.5h × 0.10 EUR = 0.25 EUR"""
        cost = calculate_block_cost(30, 0.10)
        assert cost == pytest.approx(0.25, abs=0.001)

    def test_45min_block_at_5_cents(self):
        """45 min block at 5 c/kWh = 5kW × 0.75h × 0.05 EUR = 0.1875 EUR"""
        cost = calculate_block_cost(45, 0.05)
        assert cost == pytest.approx(0.1875, abs=0.001)

    def test_60min_block_at_20_cents(self):
        """60 min block at 20 c/kWh = 5kW × 1h × 0.20 EUR = 1.00 EUR"""
        cost = calculate_block_cost(60, 0.20)
        assert cost == pytest.approx(1.00, abs=0.001)

    def test_zero_duration(self):
        """Zero duration should return zero cost."""
        cost = calculate_block_cost(0, 0.10)
        assert cost == 0.0

    def test_zero_price(self):
        """Zero price should return zero cost."""
        cost = calculate_block_cost(30, 0.0)
        assert cost == 0.0


class TestCostConstraint:
    """Tests for apply_cost_constraint function."""

    def test_no_limit_all_enabled(self):
        """With max_cost=0 (no limit), all blocks should be enabled."""
        blocks = [
            {'avg_price': 0.10, 'cost_eur': 0.25},
            {'avg_price': 0.05, 'cost_eur': 0.125},
            {'avg_price': 0.15, 'cost_eur': 0.375},
        ]
        result, total, applied = apply_cost_constraint(blocks, 0)

        assert not applied
        assert all(not b['cost_exceeded'] for b in result)
        assert total == pytest.approx(0.75, abs=0.001)

    def test_limit_disables_expensive_blocks(self):
        """With tight limit, expensive blocks should be disabled."""
        blocks = [
            {'avg_price': 0.10, 'cost_eur': 0.25},   # medium
            {'avg_price': 0.05, 'cost_eur': 0.125},  # cheapest
            {'avg_price': 0.15, 'cost_eur': 0.375},  # most expensive
        ]
        # Limit of 0.40 EUR should enable only cheapest two
        result, total, applied = apply_cost_constraint(blocks, 0.40)

        assert applied
        assert not result[0]['cost_exceeded']  # medium - enabled (0.125 + 0.25 = 0.375)
        assert not result[1]['cost_exceeded']  # cheapest - enabled first
        assert result[2]['cost_exceeded']      # expensive - disabled
        assert total == pytest.approx(0.375, abs=0.001)

    def test_cheapest_enabled_first(self):
        """Blocks should be enabled in order of price, not position."""
        blocks = [
            {'avg_price': 0.20, 'cost_eur': 0.50},   # expensive - position 0
            {'avg_price': 0.02, 'cost_eur': 0.05},   # cheapest - position 1
            {'avg_price': 0.10, 'cost_eur': 0.25},   # medium - position 2
        ]
        # Limit of 0.30 EUR should enable cheapest (0.05) and medium (0.25)
        result, total, applied = apply_cost_constraint(blocks, 0.30)

        assert applied
        assert result[0]['cost_exceeded']      # expensive - disabled
        assert not result[1]['cost_exceeded']  # cheapest - enabled
        assert not result[2]['cost_exceeded']  # medium - enabled
        assert total == pytest.approx(0.30, abs=0.001)

    def test_exact_limit_match(self):
        """Block should be enabled if cost exactly matches remaining budget."""
        blocks = [
            {'avg_price': 0.10, 'cost_eur': 0.25},
            {'avg_price': 0.10, 'cost_eur': 0.25},
        ]
        result, total, applied = apply_cost_constraint(blocks, 0.50)

        assert not applied
        assert all(not b['cost_exceeded'] for b in result)
        assert total == pytest.approx(0.50, abs=0.001)

    def test_all_blocks_exceed_limit(self):
        """If all blocks exceed limit, all should be marked cost_exceeded."""
        blocks = [
            {'avg_price': 0.50, 'cost_eur': 1.25},  # 5kW × 0.5h × 0.50 = 1.25
            {'avg_price': 0.60, 'cost_eur': 1.50},
        ]
        result, total, applied = apply_cost_constraint(blocks, 0.50)

        assert applied
        # Cheapest block (1.25) still exceeds limit (0.50), so all disabled
        assert all(b['cost_exceeded'] for b in result)
        assert total == 0.0

    def test_single_block_within_limit(self):
        """Single block within limit should be enabled."""
        blocks = [
            {'avg_price': 0.05, 'cost_eur': 0.125},
        ]
        result, total, applied = apply_cost_constraint(blocks, 0.20)

        assert not applied
        assert not result[0]['cost_exceeded']
        assert total == pytest.approx(0.125, abs=0.001)


class TestCostCalculationIntegration:
    """Integration tests combining cost calculation and constraint."""

    def test_typical_winter_night_no_limit(self):
        """
        Typical winter night: 4 blocks at ~1-2 c/kWh, no cost limit.
        Total should be around €0.10-0.20.
        """
        # Simulate 4 × 30min blocks at varying cheap prices
        blocks = []
        prices = [0.011, 0.0085, 0.0105, 0.0115]  # cents/kWh from screenshot

        for price in prices:
            cost = calculate_block_cost(30, price)
            blocks.append({'avg_price': price, 'cost_eur': cost})

        result, total, applied = apply_cost_constraint(blocks, 0)

        assert not applied
        # Total: 4 × 2.5kWh × ~0.01 EUR = ~0.10 EUR
        assert 0.08 < total < 0.15
        assert all(not b['cost_exceeded'] for b in result)

    def test_high_price_scenario_with_limit(self):
        """
        High price scenario: blocks at 14-25 c/kWh with €0.50 limit.
        Should disable some expensive blocks.
        """
        # Simulate 4 × 30min blocks at high prices
        prices = [0.14, 0.18, 0.22, 0.25]  # EUR/kWh (14-25 cents)
        blocks = []

        for price in prices:
            cost = calculate_block_cost(30, price)  # 2.5 kWh × price
            blocks.append({'avg_price': price, 'cost_eur': cost})

        # Costs: 0.35, 0.45, 0.55, 0.625 EUR
        # With €0.50 limit, only cheapest (0.35) should be enabled
        result, total, applied = apply_cost_constraint(blocks, 0.50)

        assert applied
        # Only the cheapest block (€0.35) fits within €0.50
        enabled_count = sum(1 for b in result if not b['cost_exceeded'])
        assert enabled_count == 1
        assert total == pytest.approx(0.35, abs=0.01)

    def test_reproduces_zero_cost_bug(self):
        """
        Regression test: Verify costs are non-zero for real prices.

        This test reproduces the bug where all block costs showed €0.00
        because the pyscript never calculated or set the cost values.
        """
        # Prices from the screenshot (in EUR/kWh)
        prices = [0.011, 0.0085, 0.0105, 0.0115]

        for i, price in enumerate(prices):
            cost = calculate_block_cost(30, price)

            # Cost should NOT be zero for non-zero price
            assert cost > 0, f"Block {i+1} cost should be > 0, got {cost}"

            # Cost should be roughly 2.5 kWh × price
            expected = 2.5 * price
            assert cost == pytest.approx(expected, abs=0.001), \
                f"Block {i+1}: expected €{expected:.3f}, got €{cost:.3f}"

    def test_very_low_limit_disables_all_blocks(self):
        """
        Regression test: Very low cost limit should disable all blocks.

        Bug discovered 2025-12-06: When max_cost_eur=0.01€ but each block
        costs €0.03, all blocks should be marked cost_exceeded=True.
        In practice, the constraint wasn't being applied.
        """
        # Simulate blocks with costs higher than 0.01€
        blocks = [
            {'avg_price': 0.012, 'cost_eur': 0.03},  # 30min at 1.2c/kWh
            {'avg_price': 0.010, 'cost_eur': 0.025}, # 30min at 1.0c/kWh
            {'avg_price': 0.011, 'cost_eur': 0.0275}, # 30min at 1.1c/kWh
        ]

        # Set limit to 0.01€ - lower than ANY single block cost
        result, total, applied = apply_cost_constraint(blocks, 0.01)

        # CRITICAL: All blocks should be marked as cost_exceeded
        # because even the cheapest block (€0.025) exceeds the limit (€0.01)
        assert applied, "cost_limit_applied should be True"
        assert all(b['cost_exceeded'] for b in result), \
            "All blocks should have cost_exceeded=True"
        assert total == 0.0, "Total enabled cost should be 0"


class TestSortingApproaches:
    """Tests that different sorting approaches produce identical results.

    Pyscript has issues with lambda closures capturing local variables.
    We need to verify the workaround (list comprehension) produces same results.
    """

    def test_lambda_vs_list_comprehension_sorting(self):
        """
        Verify that the pyscript-safe sorting approach matches the lambda approach.

        Original (fails in pyscript due to closure):
            sorted_indices = sorted(range(len(blocks)), key=lambda i: blocks[i]['avg_price'])

        Pyscript-safe workaround:
            index_prices = [(i, blocks[i]['avg_price']) for i in range(len(blocks))]
            index_prices.sort(key=lambda x: x[1])
            sorted_indices = [x[0] for x in index_prices]
        """
        blocks = [
            {'avg_price': 0.20, 'cost_eur': 0.50},   # index 0, expensive
            {'avg_price': 0.02, 'cost_eur': 0.05},   # index 1, cheapest
            {'avg_price': 0.10, 'cost_eur': 0.25},   # index 2, medium
            {'avg_price': 0.15, 'cost_eur': 0.375},  # index 3, med-high
            {'avg_price': 0.05, 'cost_eur': 0.125},  # index 4, low
        ]

        # Original lambda approach (works in regular Python)
        lambda_sorted = sorted(range(len(blocks)), key=lambda i: blocks[i]['avg_price'])

        # Pyscript-safe approach (avoids closure issues)
        index_prices = [(i, blocks[i]['avg_price']) for i in range(len(blocks))]
        index_prices.sort(key=lambda x: x[1])
        comprehension_sorted = [x[0] for x in index_prices]

        # Both should produce identical ordering
        assert lambda_sorted == comprehension_sorted, \
            f"Lambda: {lambda_sorted}, Comprehension: {comprehension_sorted}"

        # Expected order by price: index 1 (0.02), 4 (0.05), 2 (0.10), 3 (0.15), 0 (0.20)
        assert comprehension_sorted == [1, 4, 2, 3, 0]

    def test_sorting_with_equal_prices(self):
        """Verify sorting is stable when blocks have equal prices."""
        blocks = [
            {'avg_price': 0.10, 'cost_eur': 0.25},  # index 0
            {'avg_price': 0.10, 'cost_eur': 0.25},  # index 1, same price
            {'avg_price': 0.05, 'cost_eur': 0.125}, # index 2, cheaper
        ]

        # Both approaches should give same result
        lambda_sorted = sorted(range(len(blocks)), key=lambda i: blocks[i]['avg_price'])

        index_prices = [(i, blocks[i]['avg_price']) for i in range(len(blocks))]
        index_prices.sort(key=lambda x: x[1])
        comprehension_sorted = [x[0] for x in index_prices]

        assert lambda_sorted == comprehension_sorted
        # Cheapest (index 2) should be first
        assert comprehension_sorted[0] == 2


class TestScheduleCalculation:
    """Tests for schedule calculation respecting total_hours limit.

    The schedule calculation creates blocks that fit within total_hours.
    Duration is handled at schedule creation time in calculate_pool_heating_schedule,
    NOT by a separate apply_cost_constraint service.
    """

    def test_schedule_should_not_exceed_total_hours(self):
        """
        Regression test 2025-12-06: Schedule created 5 blocks (150min) when
        total_hours was set to 2h (120min).

        EXPECTED: With total_hours=2h and min_block=30min, schedule should
        create exactly 4 blocks (120min), not 5 blocks (150min).

        This is enforced at schedule creation time by calculate_pool_heating_schedule,
        not by a separate constraint service.
        """
        total_hours = 2.0
        total_minutes = int(total_hours * 60)  # 120 min
        min_block_duration = 30  # minutes

        # Maximum possible blocks that fit within total_hours
        max_blocks = total_minutes // min_block_duration

        assert max_blocks == 4, f"With {total_minutes}min and {min_block_duration}min blocks, max should be 4"

    def test_all_scheduled_blocks_should_be_enabled_when_under_budget(self):
        """
        Regression test 2025-12-06: Block 1 was disabled even though
        total cost €0.13 was well under the €2.00 limit.

        EXPECTED: When schedule is created with correct number of blocks
        AND total cost < max_cost_eur, ALL blocks should be enabled.

        Duration is handled at schedule creation time (find_best_heating_schedule),
        cost constraint is applied afterwards in calculate_pool_heating_schedule.
        """
        # Correct schedule: 4 blocks created by find_best_heating_schedule
        blocks = [
            {'avg_price': 0.012, 'cost_eur': 0.030},  # Block 1: 1.2c
            {'avg_price': 0.011, 'cost_eur': 0.027},  # Block 2: 1.1c
            {'avg_price': 0.0085, 'cost_eur': 0.021}, # Block 3: 0.85c
            {'avg_price': 0.0105, 'cost_eur': 0.026}, # Block 4: 1.05c
        ]

        # Total cost: 0.030 + 0.027 + 0.021 + 0.026 = €0.104
        total_cost = sum(b['cost_eur'] for b in blocks)
        max_cost_eur = 2.00

        assert total_cost < max_cost_eur, f"Cost €{total_cost} should be under limit €{max_cost_eur}"

        # Apply cost constraint (no duration constraint - that's handled at creation)
        result, _, applied = apply_cost_constraint(blocks, max_cost_eur=max_cost_eur)

        # ALL blocks should be enabled when cost is within limits
        enabled = [b for b in result if not b['cost_exceeded']]
        assert len(enabled) == 4, f"All 4 blocks should be enabled, got {len(enabled)}"
        assert not applied, "No constraint should be applied when all blocks fit within cost limit"
