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


def apply_cost_constraint(blocks: list, max_cost_eur: float = 0, max_total_minutes: int = 0) -> tuple:
    """
    Apply cost and duration constraints to blocks, enabling cheapest first.

    Args:
        blocks: List of dicts with 'cost_eur', 'avg_price', and optionally 'duration_minutes'
        max_cost_eur: Maximum total cost (0 = no limit)
        max_total_minutes: Maximum total duration in minutes (0 = no limit)

    Returns:
        Tuple of (modified_blocks, total_enabled_cost, total_enabled_minutes, constraint_applied)
    """
    # Sort by price to enable cheapest first
    sorted_indices = sorted(range(len(blocks)), key=lambda i: blocks[i]['avg_price'])

    running_cost = 0.0
    running_minutes = 0
    constraint_applied = False

    # First, mark all as exceeded, then enable cheapest within limits
    for b in blocks:
        b['cost_exceeded'] = True

    for idx in sorted_indices:
        block = blocks[idx]
        block_cost = block['cost_eur']
        block_duration = block.get('duration_minutes', 30)  # Default 30 min if not specified

        # Check cost constraint
        cost_ok = max_cost_eur <= 0 or (running_cost + block_cost <= max_cost_eur)
        # Check duration constraint
        duration_ok = max_total_minutes <= 0 or (running_minutes + block_duration <= max_total_minutes)

        if cost_ok and duration_ok:
            block['cost_exceeded'] = False
            running_cost += block_cost
            running_minutes += block_duration
        else:
            constraint_applied = True

    return blocks, running_cost, running_minutes, constraint_applied


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
        result, total, _mins, applied = apply_cost_constraint(blocks, 0)

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
        result, total, _mins, applied = apply_cost_constraint(blocks, 0.40)

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
        result, total, _mins, applied = apply_cost_constraint(blocks, 0.30)

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
        result, total, _mins, applied = apply_cost_constraint(blocks, 0.50)

        assert not applied
        assert all(not b['cost_exceeded'] for b in result)
        assert total == pytest.approx(0.50, abs=0.001)

    def test_all_blocks_exceed_limit(self):
        """If all blocks exceed limit, all should be marked cost_exceeded."""
        blocks = [
            {'avg_price': 0.50, 'cost_eur': 1.25},  # 5kW × 0.5h × 0.50 = 1.25
            {'avg_price': 0.60, 'cost_eur': 1.50},
        ]
        result, total, _mins, applied = apply_cost_constraint(blocks, 0.50)

        assert applied
        # Cheapest block (1.25) still exceeds limit (0.50), so all disabled
        assert all(b['cost_exceeded'] for b in result)
        assert total == 0.0

    def test_single_block_within_limit(self):
        """Single block within limit should be enabled."""
        blocks = [
            {'avg_price': 0.05, 'cost_eur': 0.125},
        ]
        result, total, _mins, applied = apply_cost_constraint(blocks, 0.20)

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

        result, total, _mins, applied = apply_cost_constraint(blocks, 0)

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
        result, total, _mins, applied = apply_cost_constraint(blocks, 0.50)

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
        result, total, _mins, applied = apply_cost_constraint(blocks, 0.01)

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


class TestDurationConstraint:
    """Tests for duration constraint in apply_cost_constraint."""

    def test_duration_limit_disables_excess_blocks(self):
        """
        Regression test: Duration limit should disable blocks beyond total_hours.

        Bug discovered 2025-12-06: User had 150 mins of heating instead of
        120 min limit. The apply_cost_constraint should respect total_hours.

        With 5 blocks of 30 mins each (150 mins total) and max_total_minutes=120,
        only the cheapest 4 blocks should be enabled (120 mins).
        """
        # 5 blocks × 30 min = 150 min total
        blocks = [
            {'avg_price': 0.05, 'cost_eur': 0.125, 'duration_minutes': 30},  # cheapest
            {'avg_price': 0.08, 'cost_eur': 0.20, 'duration_minutes': 30},
            {'avg_price': 0.06, 'cost_eur': 0.15, 'duration_minutes': 30},
            {'avg_price': 0.10, 'cost_eur': 0.25, 'duration_minutes': 30},   # most expensive
            {'avg_price': 0.07, 'cost_eur': 0.175, 'duration_minutes': 30},
        ]

        # max_cost_eur=0 means no cost limit, but max_total_minutes=120 (2h)
        result, total_cost, total_mins, applied = apply_cost_constraint(
            blocks, max_cost_eur=0, max_total_minutes=120
        )

        # Only 4 cheapest blocks should be enabled (120 mins)
        enabled_blocks = [b for b in result if not b.get('cost_exceeded', False)]
        enabled_mins = sum(b['duration_minutes'] for b in enabled_blocks)

        assert enabled_mins <= 120, f"Enabled {enabled_mins} mins, expected <= 120"
        assert len(enabled_blocks) == 4, f"Expected 4 blocks, got {len(enabled_blocks)}"
        # Most expensive block (0.10) should be disabled
        assert result[3]['cost_exceeded'], "Most expensive block should be disabled"

    def test_both_cost_and_duration_constraints(self):
        """
        Both cost and duration constraints should be applied.
        The stricter constraint should win.
        """
        # 4 blocks × 30 min = 120 min, total cost = €0.70
        blocks = [
            {'avg_price': 0.05, 'cost_eur': 0.125, 'duration_minutes': 30},
            {'avg_price': 0.10, 'cost_eur': 0.25, 'duration_minutes': 30},
            {'avg_price': 0.08, 'cost_eur': 0.20, 'duration_minutes': 30},
            {'avg_price': 0.05, 'cost_eur': 0.125, 'duration_minutes': 30},
        ]

        # Cost limit €0.30 is stricter than duration limit 120 mins
        result, total_cost, total_mins, applied = apply_cost_constraint(
            blocks, max_cost_eur=0.30, max_total_minutes=120
        )

        # Cost constraint kicks in: 0.125 + 0.125 = 0.25 (2 blocks)
        # Adding next cheapest (0.20) would be 0.45 > 0.30
        enabled_blocks = [b for b in result if not b.get('cost_exceeded', False)]
        assert total_cost <= 0.30, f"Total cost €{total_cost} exceeds limit €0.30"
        assert len(enabled_blocks) == 2, f"Expected 2 blocks, got {len(enabled_blocks)}"

    def test_duration_constraint_respects_120_min_limit(self):
        """
        Specific test for the 150 min -> 120 min bug.
        """
        # Simulate the exact user scenario: 150 mins scheduled, 120 min limit
        blocks = [
            {'avg_price': 0.011, 'cost_eur': 0.0275, 'duration_minutes': 30},
            {'avg_price': 0.0085, 'cost_eur': 0.021, 'duration_minutes': 30},
            {'avg_price': 0.0105, 'cost_eur': 0.026, 'duration_minutes': 30},
            {'avg_price': 0.0115, 'cost_eur': 0.029, 'duration_minutes': 30},
            {'avg_price': 0.012, 'cost_eur': 0.03, 'duration_minutes': 30},  # 5th block
        ]

        # No cost limit, but 120 min duration limit
        result, total_cost, total_mins, applied = apply_cost_constraint(
            blocks, max_cost_eur=0, max_total_minutes=120
        )

        enabled_mins = sum(
            b['duration_minutes'] for b in result if not b.get('cost_exceeded', False)
        )

        # CRITICAL: Total enabled minutes must not exceed 120
        assert enabled_mins == 120, f"Expected 120 mins, got {enabled_mins}"
        assert applied, "Constraint should be applied (one block disabled)"
