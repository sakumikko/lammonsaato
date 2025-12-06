"""
Tests for the Pool Heating Schedule Optimizer with Cost Constraint Feature.

Following TDD: Write tests first, then implement the feature.
"""

import pytest
import sys
from pathlib import Path
from datetime import date

# Add the lib directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent))

from schedule_optimizer import (
    find_best_heating_schedule,
    apply_cost_constraint,
    generate_15min_prices,
    calculate_schedule_stats,
    POWER_KW,
    ENERGY_PER_SLOT_KWH,
)


# Test data: Create predictable price patterns
def make_flat_prices(price: float) -> list[float]:
    """Create 96 slots of the same price."""
    return [price] * 96


def make_varying_prices() -> list[float]:
    """Create prices that vary by hour for testing."""
    # Hour 0-6: 0.05, Hour 7-12: 0.10, Hour 13-18: 0.15, Hour 19-23: 0.08
    prices = []
    for hour in range(24):
        if hour < 7:
            price = 0.05
        elif hour < 13:
            price = 0.10
        elif hour < 19:
            price = 0.15
        else:
            price = 0.08
        prices.extend([price] * 4)  # 4 slots per hour
    return prices


class TestEnergyConstants:
    """Test that energy constants are correctly defined."""

    def test_power_constant(self):
        """Pool heating power should be 5 kW."""
        assert POWER_KW == 5.0

    def test_energy_per_slot(self):
        """Energy per 15-min slot should be 1.25 kWh (5kW * 15/60)."""
        assert ENERGY_PER_SLOT_KWH == 1.25
        assert ENERGY_PER_SLOT_KWH == POWER_KW * 15 / 60


class TestCostCalculation:
    """Test cost calculation per block."""

    def test_cost_calculation_per_block(self):
        """Verify cost = slots × 1.25kWh × avg_price."""
        # Block: 30min = 2 slots, price = 0.10 €/kWh
        # Expected cost = 2 × 1.25 × 0.10 = €0.25
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=30,
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        assert len(schedule) == 1
        block = schedule[0]
        assert block['duration_minutes'] == 30
        assert 'cost_eur' in block
        # 2 slots × 1.25 kWh × 0.10 €/kWh = €0.25
        assert abs(block['cost_eur'] - 0.25) < 0.001

    def test_cost_45min_block(self):
        """Test cost for a 45-minute block."""
        # 45min = 3 slots, price = 0.20 €/kWh
        # Expected cost = 3 × 1.25 × 0.20 = €0.75
        prices = make_flat_prices(0.20)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=45,
            min_block_minutes=45,
            max_block_minutes=45,
            reference_date=date(2024, 12, 5),
        )

        assert len(schedule) == 1
        block = schedule[0]
        assert abs(block['cost_eur'] - 0.75) < 0.001

    def test_cost_60min_block(self):
        """Test cost for a 60-minute block."""
        # 60min = 4 slots, price = 0.15 €/kWh
        # Expected cost = 4 × 1.25 × 0.15 = €0.75
        prices = make_flat_prices(0.15)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=60,
            min_block_minutes=60,
            max_block_minutes=60,
            reference_date=date(2024, 12, 5),
        )

        assert len(schedule) == 1
        block = schedule[0]
        assert abs(block['cost_eur'] - 0.75) < 0.001


class TestCostConstraintNoLimit:
    """Test behavior when no cost limit is set."""

    def test_no_cost_limit_all_blocks_enabled(self):
        """When max_cost_eur is None, all blocks should be enabled."""
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=120,  # 2 hours = ~4 blocks
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        result = apply_cost_constraint(schedule, max_cost_eur=None)

        # All blocks should be enabled
        assert all(block['enabled'] for block in result['blocks'])
        assert not result['cost_limit_applied']
        assert result['enabled_count'] == len(schedule)


class TestCostConstraintWithLimit:
    """Test behavior when a cost limit is applied."""

    def test_cost_limit_disables_expensive_blocks(self):
        """Blocks exceeding cost limit should be marked cost_exceeded."""
        # Create schedule with 4 blocks
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=120,  # 4 × 30min blocks
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        # Each 30min block costs: 2 × 1.25 × 0.10 = €0.25
        # Total for all 4 blocks: €1.00
        # With €0.50 limit, only 2 blocks should be enabled

        result = apply_cost_constraint(schedule, max_cost_eur=0.50)

        enabled_blocks = [b for b in result['blocks'] if b['enabled']]
        exceeded_blocks = [b for b in result['blocks'] if b['cost_exceeded']]

        assert len(enabled_blocks) == 2
        assert len(exceeded_blocks) == 2
        assert result['cost_limit_applied']
        assert result['enabled_count'] == 2
        assert abs(result['total_cost'] - 0.50) < 0.001

    def test_zero_cost_limit_disables_all(self):
        """With €0 limit, all blocks should be cost_exceeded."""
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=60,
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        result = apply_cost_constraint(schedule, max_cost_eur=0.0)

        assert all(not block['enabled'] for block in result['blocks'])
        assert all(block['cost_exceeded'] for block in result['blocks'])
        assert result['cost_limit_applied']
        assert result['enabled_count'] == 0
        assert result['total_cost'] == 0

    def test_high_limit_enables_all(self):
        """With a very high limit, all blocks should be enabled."""
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=120,
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        # Total cost is ~€1.00, so €100 limit should enable all
        result = apply_cost_constraint(schedule, max_cost_eur=100.0)

        assert all(block['enabled'] for block in result['blocks'])
        assert not result['cost_limit_applied']


class TestCostConstraintPriority:
    """Test that cheapest blocks are enabled first."""

    def test_cheapest_blocks_enabled_first(self):
        """Cost limit should enable cheapest blocks first."""
        # Create prices where night hours are cheap, evening is expensive
        # 21:00-23:59 = expensive (0.20)
        # 00:00-06:59 = cheap (0.02)
        prices_today = [0.10] * 84 + [0.20] * 12  # Hours 0-20 cheap, 21-23 expensive
        prices_tomorrow = [0.02] * 28 + [0.10] * 68  # Hours 0-6 cheap, 7-23 normal

        schedule = find_best_heating_schedule(
            prices_today=prices_today,
            prices_tomorrow=prices_tomorrow,
            total_minutes=120,  # 4 blocks
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        # Set a cost limit that only allows ~2 blocks at cheap prices
        # Cheapest blocks: 2 × 1.25 × 0.02 = €0.05 per block
        # Allow €0.15 = should enable ~3 cheap blocks
        result = apply_cost_constraint(schedule, max_cost_eur=0.15)

        # Verify the cheapest blocks are enabled
        for block in result['blocks']:
            if block['enabled']:
                # Enabled blocks should be the cheap ones
                assert block['avg_price'] <= 0.05

    def test_blocks_sorted_by_price_for_allocation(self):
        """Blocks should be considered in price order for cost allocation."""
        # Create 3 blocks with different costs
        prices_today = [0.10] * 84 + [0.20] * 12  # Evening expensive
        prices_tomorrow = [0.05] * 28 + [0.15] * 68  # Morning cheap, day expensive

        schedule = find_best_heating_schedule(
            prices_today=prices_today,
            prices_tomorrow=prices_tomorrow,
            total_minutes=90,  # 3 × 30min blocks
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        # With a limit that allows only the cheapest 2, verify order
        result = apply_cost_constraint(schedule, max_cost_eur=0.50)

        enabled_prices = sorted([b['avg_price'] for b in result['blocks'] if b['enabled']])
        exceeded_prices = [b['avg_price'] for b in result['blocks'] if b['cost_exceeded']]

        # All enabled block prices should be less than or equal to exceeded prices
        if enabled_prices and exceeded_prices:
            assert max(enabled_prices) <= min(exceeded_prices)


class TestCostConstraintEdgeCases:
    """Test edge cases for cost constraint."""

    def test_exact_cost_limit_match(self):
        """Block exactly matching remaining budget should be enabled."""
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=60,  # 2 × 30min blocks
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        # Each block costs €0.25, set limit to exactly €0.50
        result = apply_cost_constraint(schedule, max_cost_eur=0.50)

        assert result['enabled_count'] == 2
        assert abs(result['total_cost'] - 0.50) < 0.001

    def test_blocks_all_or_nothing(self):
        """Blocks cannot be partially enabled - it's all or nothing."""
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=60,
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        # Set limit to €0.30 - can afford 1 block (€0.25) but not 2 (€0.50)
        result = apply_cost_constraint(schedule, max_cost_eur=0.30)

        enabled_count = sum(1 for b in result['blocks'] if b['enabled'])
        assert enabled_count == 1
        # Total cost should be exactly €0.25, not €0.30
        assert abs(result['total_cost'] - 0.25) < 0.001

    def test_empty_schedule(self):
        """Empty schedule should return empty result."""
        result = apply_cost_constraint([], max_cost_eur=1.0)

        assert result['blocks'] == []
        assert result['total_cost'] == 0
        assert result['scheduled_cost'] == 0
        assert not result['cost_limit_applied']


class TestCostConstraintMetadata:
    """Test that cost constraint returns correct metadata."""

    def test_returns_total_cost(self):
        """Result should include total cost of enabled blocks."""
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=60,
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        result = apply_cost_constraint(schedule, max_cost_eur=0.30)

        assert 'total_cost' in result
        assert isinstance(result['total_cost'], float)

    def test_returns_scheduled_cost(self):
        """Result should include cost if all blocks were enabled."""
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=60,
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        result = apply_cost_constraint(schedule, max_cost_eur=0.30)

        assert 'scheduled_cost' in result
        # 2 blocks × €0.25 = €0.50
        assert abs(result['scheduled_cost'] - 0.50) < 0.001

    def test_returns_cost_limit_applied_flag(self):
        """Result should indicate if cost limit was applied."""
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=60,
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        # With low limit - should apply
        result1 = apply_cost_constraint(schedule, max_cost_eur=0.30)
        assert result1['cost_limit_applied']

        # With no limit - should not apply
        result2 = apply_cost_constraint(schedule, max_cost_eur=None)
        assert not result2['cost_limit_applied']

    def test_blocks_have_cost_exceeded_flag(self):
        """Each block should have a cost_exceeded flag."""
        prices = make_flat_prices(0.10)
        schedule = find_best_heating_schedule(
            prices_today=prices,
            prices_tomorrow=prices,
            total_minutes=60,
            min_block_minutes=30,
            max_block_minutes=30,
            reference_date=date(2024, 12, 5),
        )

        result = apply_cost_constraint(schedule, max_cost_eur=0.30)

        for block in result['blocks']:
            assert 'cost_exceeded' in block
            assert isinstance(block['cost_exceeded'], bool)
            # cost_exceeded should be True only if enabled is False
            if block['enabled']:
                assert not block['cost_exceeded']


class TestIntegration:
    """Integration tests for the complete flow."""

    def test_full_flow_with_cost_constraint(self):
        """Test complete schedule generation with cost constraint."""
        # Typical winter prices - cheap at night
        prices_today = make_varying_prices()
        prices_tomorrow = make_varying_prices()

        schedule = find_best_heating_schedule(
            prices_today=prices_today,
            prices_tomorrow=prices_tomorrow,
            total_minutes=120,
            min_block_minutes=30,
            max_block_minutes=45,
            reference_date=date(2024, 12, 5),
        )

        # Apply a reasonable cost limit
        result = apply_cost_constraint(schedule, max_cost_eur=1.00)

        # Verify structure
        assert 'blocks' in result
        assert 'total_cost' in result
        assert 'scheduled_cost' in result
        assert 'cost_limit_applied' in result
        assert 'enabled_count' in result

        # Verify each block has required fields
        for block in result['blocks']:
            assert 'start' in block
            assert 'end' in block
            assert 'duration_minutes' in block
            assert 'avg_price' in block
            assert 'cost_eur' in block
            assert 'enabled' in block
            assert 'cost_exceeded' in block

        # Total cost should not exceed limit
        assert result['total_cost'] <= 1.00


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
