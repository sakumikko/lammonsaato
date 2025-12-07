#!/usr/bin/env python3
"""
Unit tests for schedule parameter validation.

Run with: pytest tests/test_schedule_parameters.py -v

Tests:
- Valid parameter loading
- Fallback to defaults on invalid values
- min_block > max_block conflict handling
- Edge cases (zero, out of range, unavailable entities)
"""

import pytest
from unittest.mock import MagicMock, patch


# ============================================
# PARAMETER VALIDATION LOGIC (extracted from pyscript)
# ============================================

# Default values
DEFAULT_TOTAL_HEATING_MINUTES = 120
DEFAULT_MIN_BLOCK_MINUTES = 30
DEFAULT_MAX_BLOCK_MINUTES = 45

# Valid ranges
VALID_BLOCK_DURATIONS = [30, 45, 60]
VALID_TOTAL_HOURS = [x * 0.5 for x in range(0, 13)]  # 0, 0.5, 1.0, ..., 6.0


class MockState:
    """Mock for pyscript state object."""

    def __init__(self, states=None):
        self._states = states or {}

    def get(self, entity_id):
        return self._states.get(entity_id, 'unavailable')

    def set(self, entity_id, value):
        self._states[entity_id] = value


def get_schedule_parameters(state):
    """
    Get and validate schedule parameters from input_number entities.

    This is the logic being tested, extracted from pyscript.
    """
    PARAM_MIN_BLOCK_DURATION = "input_number.pool_heating_min_block_duration"
    PARAM_MAX_BLOCK_DURATION = "input_number.pool_heating_max_block_duration"
    PARAM_TOTAL_HOURS = "input_number.pool_heating_total_hours"

    params = {
        'min_block_minutes': DEFAULT_MIN_BLOCK_MINUTES,
        'max_block_minutes': DEFAULT_MAX_BLOCK_MINUTES,
        'total_minutes': DEFAULT_TOTAL_HEATING_MINUTES,
    }

    fallback_used = []

    # Get min block duration
    try:
        min_block_val = state.get(PARAM_MIN_BLOCK_DURATION)
        if min_block_val not in ['unknown', 'unavailable', None]:
            min_block = int(float(min_block_val))
            if min_block in VALID_BLOCK_DURATIONS:
                params['min_block_minutes'] = min_block
            else:
                fallback_used.append(f"min_block={min_block} not in {VALID_BLOCK_DURATIONS}")
        else:
            fallback_used.append("min_block entity unavailable")
    except (ValueError, TypeError) as e:
        fallback_used.append(f"min_block parse error: {e}")

    # Get max block duration
    try:
        max_block_val = state.get(PARAM_MAX_BLOCK_DURATION)
        if max_block_val not in ['unknown', 'unavailable', None]:
            max_block = int(float(max_block_val))
            if max_block in VALID_BLOCK_DURATIONS:
                params['max_block_minutes'] = max_block
            else:
                fallback_used.append(f"max_block={max_block} not in {VALID_BLOCK_DURATIONS}")
        else:
            fallback_used.append("max_block entity unavailable")
    except (ValueError, TypeError) as e:
        fallback_used.append(f"max_block parse error: {e}")

    # Get total heating hours
    try:
        total_hours_val = state.get(PARAM_TOTAL_HOURS)
        if total_hours_val not in ['unknown', 'unavailable', None]:
            total_hours = float(total_hours_val)
            if 0 <= total_hours <= 6:
                total_hours = round(total_hours * 2) / 2
                params['total_minutes'] = int(total_hours * 60)
            else:
                fallback_used.append(f"total_hours={total_hours} not in 0-6 range")
        else:
            fallback_used.append("total_hours entity unavailable")
    except (ValueError, TypeError) as e:
        fallback_used.append(f"total_hours parse error: {e}")

    # Validate min <= max constraint
    if params['min_block_minutes'] > params['max_block_minutes']:
        params['min_block_minutes'] = DEFAULT_MIN_BLOCK_MINUTES
        params['max_block_minutes'] = DEFAULT_MAX_BLOCK_MINUTES
        fallback_used.append("min > max conflict")

    return params, fallback_used


# ============================================
# TEST CASES - VALID PARAMETERS
# ============================================

class TestValidParameters:
    """Tests for valid parameter combinations."""

    def test_default_values(self):
        """All defaults when entities unavailable."""
        state = MockState({})

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30
        assert params['max_block_minutes'] == 45
        assert params['total_minutes'] == 120
        assert len(fallbacks) == 3  # All three used fallback

    def test_valid_30_45_2h(self):
        """Valid: min=30, max=45, total=2h (default)."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "30",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30
        assert params['max_block_minutes'] == 45
        assert params['total_minutes'] == 120
        assert len(fallbacks) == 0

    def test_valid_45_60_3h(self):
        """Valid: min=45, max=60, total=3h."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "45",
            "input_number.pool_heating_max_block_duration": "60",
            "input_number.pool_heating_total_hours": "3",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 45
        assert params['max_block_minutes'] == 60
        assert params['total_minutes'] == 180
        assert len(fallbacks) == 0

    def test_valid_equal_min_max(self):
        """Valid: min=max=45."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "45",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 45
        assert params['max_block_minutes'] == 45
        assert len(fallbacks) == 0

    def test_valid_zero_hours(self):
        """Valid: total=0 hours (disabled)."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "30",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "0",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['total_minutes'] == 0
        assert len(fallbacks) == 0

    def test_valid_max_6_hours(self):
        """Valid: total=6 hours (maximum)."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "30",
            "input_number.pool_heating_max_block_duration": "60",
            "input_number.pool_heating_total_hours": "6",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['total_minutes'] == 360
        assert len(fallbacks) == 0

    def test_valid_half_hour_steps(self):
        """Valid: total=1.5 hours."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "30",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "1.5",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['total_minutes'] == 90

    def test_rounds_to_half_hour(self):
        """Should round to nearest 0.5 hour."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "30",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "1.7",  # Should round to 1.5
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['total_minutes'] == 90  # 1.5 hours

    def test_rounds_up_to_half_hour(self):
        """Should round 1.3 to 1.5."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "30",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "1.3",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['total_minutes'] == 90  # 1.5 hours rounded


# ============================================
# TEST CASES - FALLBACK BEHAVIOR
# ============================================

class TestFallbackBehavior:
    """Tests for fallback to defaults on invalid input."""

    def test_min_greater_than_max_conflict(self):
        """min_block > max_block should fallback both to defaults."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "60",
            "input_number.pool_heating_max_block_duration": "30",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30  # Default
        assert params['max_block_minutes'] == 45  # Default
        assert "min > max conflict" in str(fallbacks)

    def test_invalid_min_block_value(self):
        """Invalid min_block (not 30/45/60) should fallback."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "20",  # Invalid
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30  # Default
        assert params['max_block_minutes'] == 45
        assert any("min_block=20" in f for f in fallbacks)

    def test_invalid_max_block_value(self):
        """Invalid max_block (not 30/45/60) should fallback."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "30",
            "input_number.pool_heating_max_block_duration": "90",  # Invalid
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30
        assert params['max_block_minutes'] == 45  # Default
        assert any("max_block=90" in f for f in fallbacks)

    def test_total_hours_out_of_range_high(self):
        """total_hours > 6 should fallback to default."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "30",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "8",  # Invalid
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['total_minutes'] == 120  # Default 2h
        assert any("total_hours=8" in f for f in fallbacks)

    def test_total_hours_negative(self):
        """total_hours < 0 should fallback to default."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "30",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "-1",  # Invalid
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['total_minutes'] == 120  # Default 2h

    def test_unavailable_entity(self):
        """Unavailable entity should fallback to default."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "unavailable",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30  # Default
        assert "min_block entity unavailable" in fallbacks

    def test_unknown_entity(self):
        """Unknown entity should fallback to default."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "unknown",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30  # Default

    def test_non_numeric_value(self):
        """Non-numeric value should fallback to default."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "abc",  # Invalid
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30  # Default
        assert any("parse error" in f for f in fallbacks)

    def test_float_block_duration(self):
        """Float block duration should be converted to int."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "30.0",
            "input_number.pool_heating_max_block_duration": "45.0",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30
        assert params['max_block_minutes'] == 45
        assert len(fallbacks) == 0

    def test_partial_valid_params(self):
        """Some valid, some invalid params should partially fallback."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "45",  # Valid
            "input_number.pool_heating_max_block_duration": "99",  # Invalid
            "input_number.pool_heating_total_hours": "3",  # Valid
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 45  # Kept
        assert params['max_block_minutes'] == 45  # Default (but >= min so OK)
        assert params['total_minutes'] == 180  # Kept


# ============================================
# TEST CASES - EDGE CASES
# ============================================

class TestEdgeCases:
    """Edge case tests."""

    def test_none_state(self):
        """None state value should fallback."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": None,
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30  # Default

    def test_empty_string(self):
        """Empty string should trigger parse error and fallback."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30  # Default
        assert any("parse error" in f for f in fallbacks)

    def test_whitespace_value(self):
        """Whitespace should trigger parse error and fallback."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "  ",
            "input_number.pool_heating_max_block_duration": "45",
            "input_number.pool_heating_total_hours": "2",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30  # Default

    def test_all_entities_missing(self):
        """All entities missing should use all defaults."""
        state = MockState({})  # No entities

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 30
        assert params['max_block_minutes'] == 45
        assert params['total_minutes'] == 120
        assert len(fallbacks) == 3

    def test_boundary_min_equals_max_at_60(self):
        """min=max=60 should be valid."""
        state = MockState({
            "input_number.pool_heating_min_block_duration": "60",
            "input_number.pool_heating_max_block_duration": "60",
            "input_number.pool_heating_total_hours": "4",
        })

        params, fallbacks = get_schedule_parameters(state)

        assert params['min_block_minutes'] == 60
        assert params['max_block_minutes'] == 60
        assert params['total_minutes'] == 240
        assert len(fallbacks) == 0


# ============================================
# RUN TESTS
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
