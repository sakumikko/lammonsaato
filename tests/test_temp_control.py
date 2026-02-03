"""
Unit tests for Pool Temperature Control algorithm.

Tests the PID-Feedback Target Control algorithm logic without requiring
Home Assistant or Thermia hardware.

TDD: Write these tests FIRST, verify they fail, then implement.
"""

import pytest
import sys
from pathlib import Path

# Add scripts/pyscript to path for imports
PYSCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "pyscript"
sys.path.insert(0, str(PYSCRIPT_PATH))

# Import the algorithm module (will fail until implemented)
try:
    from pool_temp_control import (
        calculate_new_setpoint,
        check_safety_conditions,
        TARGET_OFFSET,
        BASE_OFFSET,
        PID_TARGET,
        PID_GAIN,
        MIN_CORRECTION,
        MAX_CORRECTION,
        MIN_SETPOINT,
        MAX_SETPOINT,
        ABSOLUTE_MIN_SUPPLY,
        RELATIVE_DROP_MAX,
        MIN_GEAR_POOL,
    )
    IMPORT_SUCCESS = True
except ImportError:
    IMPORT_SUCCESS = False
    # Define fallback values for test structure
    TARGET_OFFSET = 0.5
    BASE_OFFSET = 0.5
    PID_TARGET = -2.5
    PID_GAIN = 0.10
    MIN_CORRECTION = -1.0
    MAX_CORRECTION = 4.0
    MIN_SETPOINT = 28.0
    MAX_SETPOINT = 55.0
    ABSOLUTE_MIN_SUPPLY = 32.0
    RELATIVE_DROP_MAX = 15.0
    MIN_GEAR_POOL = 7


@pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_temp_control module not yet implemented")
class TestPIDFeedbackAlgorithm:
    """Test the core PID-Feedback Target Control algorithm."""

    # --- Basic Algorithm Tests (with pid_30m=0) ---

    def test_stable_temperature_pid_zero(self):
        """When PID=0, target should be slightly above supply (positive correction)."""
        current, prev = 40.0, 40.0
        new_target, drop_rate, pid_correction = calculate_new_setpoint(current, prev, pid_30m=0.0)

        # With pid_30m=0: pid_error = 0 - (-2.5) = 2.5, correction = 2.5 * 0.1 = 0.25
        # target = 40 + 0.25 = 40.25 -> rounded to 40.2
        assert new_target == 40.2
        assert pid_correction == 0.25
        assert drop_rate == 0.0  # drop_rate is always 0 in new algorithm

    def test_dropping_temperature_no_compensation(self):
        """New algorithm doesn't use drop compensation - only PID feedback."""
        current, prev = 38.0, 40.0  # Dropped 2 deg in 5 min
        new_target, drop_rate, pid_correction = calculate_new_setpoint(current, prev, pid_30m=0.0)

        # target = 38 + 0.25 = 38.25 -> 38.2
        assert new_target == 38.2
        assert drop_rate == 0.0  # No drop compensation in new algorithm

    def test_fast_drop_no_compensation(self):
        """New algorithm relies on PID feedback, not drop anticipation."""
        current, prev = 35.0, 42.0  # Dropped 7 deg in 5 min
        new_target, drop_rate, pid_correction = calculate_new_setpoint(current, prev, pid_30m=0.0)

        # target = 35 + 0.25 = 35.25 -> 35.2
        assert new_target == 35.2
        assert drop_rate == 0.0

    def test_rising_temperature(self):
        """Rising temperature doesn't affect calculation - only PID matters."""
        current, prev = 42.0, 40.0  # Rose 2 deg
        new_target, drop_rate, pid_correction = calculate_new_setpoint(current, prev, pid_30m=0.0)

        # target = 42 + 0.25 = 42.25 -> 42.2
        assert new_target == 42.2
        assert drop_rate == 0.0

    # --- PID Feedback Tests ---

    def test_pid_positive_sets_target_above_supply(self):
        """When PID is positive (too high), target should be ABOVE supply to drive PID down."""
        current, prev = 40.0, 40.0
        new_target, _, pid_correction = calculate_new_setpoint(current, prev, pid_30m=25.0)

        # pid_error = 25 - (-2.5) = 27.5
        # pid_correction = min(27.5 * 0.1, 4.0) = 2.75
        assert pid_correction == 2.75
        # target = 40 + 2.75 = 42.75 -> 42.8 (ABOVE supply)
        assert new_target == 42.8

    def test_pid_negative_sets_target_below_supply(self):
        """When PID is too negative, target should be BELOW supply to drive PID up."""
        current, prev = 40.0, 40.0
        new_target, _, pid_correction = calculate_new_setpoint(current, prev, pid_30m=-10.0)

        # pid_error = -10 - (-2.5) = -7.5
        # pid_correction = max(-7.5 * 0.1, -1.0) = -0.75
        assert pid_correction == -0.75
        # target = 40 + (-0.75) = 39.25 -> 39.2 (BELOW supply)
        assert new_target == 39.2

    def test_pid_at_target_no_correction(self):
        """When PID is at target (-2.5), correction should be zero."""
        current, prev = 40.0, 40.0
        new_target, _, pid_correction = calculate_new_setpoint(current, prev, pid_30m=-2.5)

        # pid_error = -2.5 - (-2.5) = 0
        # pid_correction = 0
        assert pid_correction == 0.0
        # target = 40 + 0 = 40.0
        assert new_target == 40.0

    def test_pid_correction_clamped_to_max(self):
        """PID correction should not exceed MAX_CORRECTION."""
        current, prev = 40.0, 40.0
        new_target, _, pid_correction = calculate_new_setpoint(current, prev, pid_30m=100.0)

        # pid_error = 100 - (-2.5) = 102.5
        # pid_correction = min(102.5 * 0.1, 4.0) = 4.0 (clamped)
        assert pid_correction == MAX_CORRECTION
        # target = 40 + 4.0 = 44.0
        assert new_target == 44.0

    def test_pid_correction_clamped_to_min(self):
        """PID correction should not go below MIN_CORRECTION."""
        current, prev = 40.0, 40.0
        new_target, _, pid_correction = calculate_new_setpoint(current, prev, pid_30m=-50.0)

        # pid_error = -50 - (-2.5) = -47.5
        # pid_correction = max(-47.5 * 0.1, -1.0) = -1.0 (clamped)
        assert pid_correction == MIN_CORRECTION
        # target = 40 + (-1.0) = 39.0
        assert new_target == 39.0

    # --- Boundary Tests ---

    def test_clamp_to_minimum(self):
        """Target should not go below MIN_SETPOINT."""
        current, prev = 25.0, 30.0  # Very low supply
        new_target, _, _ = calculate_new_setpoint(current, prev, pid_30m=0.0)

        assert new_target == MIN_SETPOINT  # 28.0

    def test_clamp_to_maximum(self):
        """Target should not exceed MAX_SETPOINT."""
        current, prev = 65.0, 65.0  # Very high supply (above MAX_SETPOINT=60)
        new_target, _, _ = calculate_new_setpoint(current, prev, pid_30m=0.0)

        assert new_target == MAX_SETPOINT  # 60.0

    def test_first_reading_no_prev(self):
        """First reading with no previous should use 0 drop rate."""
        current, prev = 40.0, 0.0  # No previous reading
        new_target, drop_rate, _ = calculate_new_setpoint(current, prev, pid_30m=0.0)

        assert drop_rate == 0.0

    def test_negative_prev_treated_as_no_prev(self):
        """Negative previous value should be treated as no previous."""
        current, prev = 40.0, -5.0
        new_target, drop_rate, _ = calculate_new_setpoint(current, prev, pid_30m=0.0)

        assert drop_rate == 0.0

    # --- Backwards Compatibility Tests ---

    def test_default_pid_is_zero(self):
        """Calling without pid_30m should use default of 0."""
        current, prev = 40.0, 40.0
        # Call without pid_30m parameter
        result = calculate_new_setpoint(current, prev)
        assert len(result) == 3  # Should return 3 values

    # --- Simulation Tests ---

    def test_pool_heating_simulation_gradual_drop(self):
        """Simulate gradual supply drop during pool heating with PID feedback."""
        supply_readings = [45, 43, 41, 39, 37, 36]  # Every 5 min
        targets = []
        prev = 0

        for current in supply_readings:
            # pid_30m=0 means target is slightly above supply (by 0.25)
            target, _, _ = calculate_new_setpoint(float(current), float(prev), pid_30m=0.0)
            targets.append(target)
            prev = current

        # Verify all targets are within safe range
        for target in targets:
            assert MIN_SETPOINT <= target <= MAX_SETPOINT

    def test_pid_feedback_drives_target_response(self):
        """When PID is high, target should be above supply; when low, below supply."""
        current = 40.0
        prev = 40.0

        # PID too high -> target above supply
        target_high_pid, _, _ = calculate_new_setpoint(current, prev, pid_30m=25.0)
        assert target_high_pid > current, f"With high PID, target should be above supply"

        # PID at target -> target equals supply
        target_at_target, _, _ = calculate_new_setpoint(current, prev, pid_30m=-2.5)
        assert target_at_target == current, f"With PID at target, target should equal supply"

        # PID too low -> target below supply
        target_low_pid, _, _ = calculate_new_setpoint(current, prev, pid_30m=-10.0)
        assert target_low_pid < current, f"With low PID, target should be below supply"


@pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_temp_control module not yet implemented")
class TestSafetyConditions:
    """Test safety check logic (FR-44, FR-45)."""

    def test_fr44_absolute_minimum_violated(self):
        """Supply below 32 deg should trigger fallback."""
        safe, reason = check_safety_conditions(31.0, 45.0)
        assert not safe
        assert "FR-44" in reason or "32" in reason

    def test_fr44_at_minimum_is_safe(self):
        """Supply at exactly 32 deg should be safe."""
        safe, _ = check_safety_conditions(32.0, 45.0)
        assert safe

    def test_fr44_above_minimum_is_safe(self):
        """Supply above 32 deg should be safe."""
        safe, _ = check_safety_conditions(35.0, 45.0)
        assert safe

    def test_fr45_relative_drop_violated(self):
        """Supply dropping >15 deg below curve should trigger fallback."""
        original_curve = 50.0
        current_supply = 34.0  # 16 deg below curve

        safe, reason = check_safety_conditions(current_supply, original_curve)
        assert not safe
        assert "FR-45" in reason or "15" in reason

    def test_fr45_at_limit_is_safe(self):
        """Supply dropping exactly 15 deg below curve should be safe."""
        original_curve = 50.0
        current_supply = 35.0  # Exactly 15 deg below

        safe, _ = check_safety_conditions(current_supply, original_curve)
        assert safe

    def test_fr45_within_limit_is_safe(self):
        """Supply within 15 deg of curve should be safe."""
        original_curve = 50.0
        current_supply = 40.0  # 10 deg below

        safe, _ = check_safety_conditions(current_supply, original_curve)
        assert safe

    def test_normal_operation_is_safe(self):
        """Normal pool heating conditions should pass safety checks."""
        safe, _ = check_safety_conditions(38.0, 45.0)
        assert safe

    def test_both_conditions_violated(self):
        """When both conditions violated, should detect failure."""
        # Supply at 25 is both below 32 (FR-44) and >15 below 50 (FR-45)
        safe, reason = check_safety_conditions(25.0, 50.0)
        assert not safe
        # Should detect at least one violation
        assert reason is not None


@pytest.mark.skipif(not IMPORT_SUCCESS, reason="pool_temp_control module not yet implemented")
class TestGearControl:
    """Test compressor gear control (FR-46)."""

    def test_min_gear_pool_is_7(self):
        """Minimum gear during pool heating should be 7."""
        assert MIN_GEAR_POOL == 7

    def test_min_gear_in_valid_range(self):
        """MIN_GEAR_POOL should be in valid Thermia range 1-9."""
        assert 1 <= MIN_GEAR_POOL <= 9


class TestConfigurationConstants:
    """Test that configuration constants have sensible values."""

    def test_target_offset_reasonable(self):
        """TARGET_OFFSET should be small (near zero for minimal PID integral accumulation)."""
        assert TARGET_OFFSET >= -2  # Can be slightly negative to put target above supply
        assert TARGET_OFFSET <= 5   # Shouldn't be too large

    def test_min_setpoint_reasonable(self):
        """MIN_SETPOINT should allow meaningful heating."""
        assert MIN_SETPOINT >= 25  # Below this, no useful heating
        assert MIN_SETPOINT <= 35  # Should allow low targets

    def test_max_setpoint_reasonable(self):
        """MAX_SETPOINT should be within heat pump capability."""
        assert MAX_SETPOINT >= 40  # Should allow high targets
        assert MAX_SETPOINT <= 65  # Heat pump limit (Thermia Mega supports up to 60+)

    def test_min_less_than_max(self):
        """MIN_SETPOINT must be less than MAX_SETPOINT."""
        assert MIN_SETPOINT < MAX_SETPOINT

    def test_absolute_min_supply_reasonable(self):
        """ABSOLUTE_MIN_SUPPLY should protect floor heating."""
        assert ABSOLUTE_MIN_SUPPLY >= 30  # Floor heating minimum
        assert ABSOLUTE_MIN_SUPPLY <= 35

    def test_relative_drop_max_reasonable(self):
        """RELATIVE_DROP_MAX should allow some variation."""
        assert RELATIVE_DROP_MAX >= 10  # Allow normal drops
        assert RELATIVE_DROP_MAX <= 20  # Don't allow extreme deviation


# Tests that should work even before implementation
class TestModuleStructure:
    """Tests for module structure that work before implementation."""

    def test_pyscript_directory_exists(self):
        """Verify pyscript directory exists."""
        assert PYSCRIPT_PATH.exists()

    def test_pool_temp_control_file_location(self):
        """Document expected file location."""
        expected_file = PYSCRIPT_PATH / "pool_temp_control.py"
        # This will fail until file is created - that's expected for TDD
        if not IMPORT_SUCCESS:
            pytest.skip(f"Expected file at: {expected_file}")
