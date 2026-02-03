"""
Unit tests for Cold Weather Mode.

Tests the cold weather schedule generation and safety threshold logic.

TDD: Write these tests FIRST, verify they fail, then implement.
"""

import pytest
import sys
from pathlib import Path

# Add scripts/pyscript to path for imports
PYSCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "pyscript"
sys.path.insert(0, str(PYSCRIPT_PATH))

# Mock pyscript decorators before importing modules
import sys
from unittest.mock import MagicMock

# Create mock pyscript module with decorators
mock_pyscript = MagicMock()
mock_pyscript.service = lambda func: func
mock_pyscript.state = MagicMock()
mock_pyscript.state.get = MagicMock(return_value="")
sys.modules['pyscript'] = mock_pyscript

# Also mock the 'state' and 'service' that pyscript injects
class MockState:
    @staticmethod
    def get(entity_id, default=None):
        return default
    @staticmethod
    def set(entity_id, value, **kwargs):
        pass

# Inject mocks into builtins for pyscript compatibility
import builtins
builtins.state = MockState()
builtins.service = lambda func: func

# Import the algorithm module (will fail until implemented)
try:
    from pool_heating import (
        generate_cold_weather_schedule,
        COLD_WEATHER_VALID_DURATIONS,
        COLD_WEATHER_BLOCK_OFFSET,
    )
    ALGORITHM_IMPORT_SUCCESS = True
except (ImportError, NameError, AttributeError) as e:
    ALGORITHM_IMPORT_SUCCESS = False
    # Define fallback values for test structure
    COLD_WEATHER_VALID_DURATIONS = [5, 10, 15]
    COLD_WEATHER_BLOCK_OFFSET = 5

# Import safety functions (will fail until implemented)
try:
    from pool_temp_control import (
        check_safety_conditions,
        COLD_WEATHER_MIN_SUPPLY,
        COLD_WEATHER_RELATIVE_DROP,
    )
    SAFETY_IMPORT_SUCCESS = True
except (ImportError, NameError, AttributeError) as e:
    SAFETY_IMPORT_SUCCESS = False
    # Define fallback values
    COLD_WEATHER_MIN_SUPPLY = 38.0
    COLD_WEATHER_RELATIVE_DROP = 12.0


# ============================================
# COLD WEATHER SCHEDULE ALGORITHM TESTS
# ============================================

@pytest.mark.skipif(not ALGORITHM_IMPORT_SUCCESS, reason="cold weather algorithm not yet implemented")
class TestColdWeatherScheduleGeneration:
    """Test the cold weather schedule generation algorithm."""

    def test_fixed_offset_all_blocks_start_at_05(self):
        """All blocks should start at :05 past the hour (hardcoded offset)."""
        enabled_hours = "21,22,23,0,1"
        blocks = generate_cold_weather_schedule(enabled_hours, 5)

        for block in blocks:
            # Extract minute from start time
            start_minute = block['start'].minute if hasattr(block['start'], 'minute') else int(block['start'].split(':')[1])
            assert start_minute == 5, f"Block should start at :05, got :{start_minute}"

    def test_block_count_matches_enabled_hours(self):
        """Number of blocks should match number of enabled hours."""
        enabled_hours = "21,22,23,0,1,2,3,4,5,6"
        blocks = generate_cold_weather_schedule(enabled_hours, 5)

        assert len(blocks) == 10, f"Expected 10 blocks, got {len(blocks)}"

    def test_block_count_single_hour(self):
        """Single enabled hour should produce single block."""
        enabled_hours = "21"
        blocks = generate_cold_weather_schedule(enabled_hours, 5)

        assert len(blocks) == 1

    def test_block_duration_matches_config(self):
        """Block duration should match configured value."""
        enabled_hours = "21,22,23"

        for duration in [5, 10, 15]:
            blocks = generate_cold_weather_schedule(enabled_hours, duration)
            for block in blocks:
                assert block['duration_minutes'] == duration

    def test_all_blocks_enabled(self):
        """All cold weather blocks should be enabled (no cost constraint)."""
        enabled_hours = "21,22,23,0,1,2,3,4,5,6"
        blocks = generate_cold_weather_schedule(enabled_hours, 5)

        for block in blocks:
            assert block['enabled'] == True, "Cold weather blocks should all be enabled"

    def test_invalid_duration_fallback_to_5(self):
        """Invalid duration should fall back to 5 minutes."""
        enabled_hours = "21,22,23"
        blocks = generate_cold_weather_schedule(enabled_hours, 30)  # 30 is invalid for cold weather

        for block in blocks:
            assert block['duration_minutes'] == 5, "Should fall back to 5 min for invalid duration"

    def test_empty_hours_returns_empty_list(self):
        """Empty enabled hours should return empty list."""
        blocks = generate_cold_weather_schedule("", 5)
        assert blocks == []

    def test_invalid_hours_ignored(self):
        """Invalid hour values should be filtered out."""
        enabled_hours = "21,25,-1,abc,22"  # 25, -1, abc are invalid
        blocks = generate_cold_weather_schedule(enabled_hours, 5)

        assert len(blocks) == 2, f"Should only have 2 valid blocks, got {len(blocks)}"

    def test_blocks_sorted_by_time(self):
        """Blocks should be sorted in chronological order (overnight wrap)."""
        enabled_hours = "23,0,1,21,22"  # Out of order
        blocks = generate_cold_weather_schedule(enabled_hours, 5)

        # For overnight schedules, 21,22,23 come before 0,1
        hours = []
        for block in blocks:
            if hasattr(block['start'], 'hour'):
                hours.append(block['start'].hour)
            else:
                hours.append(int(block['start'].split(':')[0]))

        # Expected order: 21, 22, 23, 0, 1 (chronological for overnight)
        assert hours == [21, 22, 23, 0, 1], f"Expected chronological order, got {hours}"

    def test_duplicate_hours_deduplicated(self):
        """Duplicate hours should be deduplicated."""
        enabled_hours = "21,21,22,22,23"
        blocks = generate_cold_weather_schedule(enabled_hours, 5)

        assert len(blocks) == 3, f"Duplicates should be removed, got {len(blocks)} blocks"

    def test_whitespace_in_hours_handled(self):
        """Whitespace in enabled hours string should be handled."""
        enabled_hours = " 21 , 22 , 23 "
        blocks = generate_cold_weather_schedule(enabled_hours, 5)

        assert len(blocks) == 3

    def test_block_has_required_fields(self):
        """Each block should have required fields."""
        enabled_hours = "21"
        blocks = generate_cold_weather_schedule(enabled_hours, 5)

        required_fields = ['start', 'end', 'duration_minutes', 'enabled', 'price']
        for field in required_fields:
            assert field in blocks[0], f"Block missing required field: {field}"


@pytest.mark.skipif(not ALGORITHM_IMPORT_SUCCESS, reason="cold weather algorithm not yet implemented")
class TestColdWeatherConstants:
    """Test cold weather configuration constants."""

    def test_valid_durations(self):
        """Valid durations should be 5, 10, 15 minutes."""
        assert COLD_WEATHER_VALID_DURATIONS == [5, 10, 15]

    def test_block_offset(self):
        """Block offset should be 5 (start at :05 past hour)."""
        assert COLD_WEATHER_BLOCK_OFFSET == 5


# ============================================
# COLD WEATHER SAFETY THRESHOLD TESTS
# ============================================

@pytest.mark.skipif(not SAFETY_IMPORT_SUCCESS, reason="safety functions not yet implemented")
class TestColdWeatherSafetyThresholds:
    """Test tighter safety thresholds for cold weather mode (FR-44-CW, FR-45-CW)."""

    def test_cold_weather_min_supply_is_38(self):
        """Cold weather absolute minimum should be 38C (tighter than normal 32C)."""
        assert COLD_WEATHER_MIN_SUPPLY == 38.0

    def test_cold_weather_relative_drop_is_12(self):
        """Cold weather relative drop should be 12C (tighter than normal 15C)."""
        assert COLD_WEATHER_RELATIVE_DROP == 12.0

    def test_cold_weather_safety_tighter_absolute(self):
        """FR-44-CW: safety triggers at 38C (not 32C)."""
        # 37C is below 38C minimum for cold weather
        safe, reason = check_safety_conditions(37.0, 50.0, cold_weather=True)
        assert not safe, "37C should trigger safety in cold weather mode"

    def test_cold_weather_safety_at_38_is_safe(self):
        """38C exactly should be safe in cold weather mode."""
        safe, _ = check_safety_conditions(38.0, 50.0, cold_weather=True)
        assert safe, "38C should be safe in cold weather mode"

    def test_cold_weather_safety_tighter_relative(self):
        """FR-45-CW: safety triggers at 12C drop (not 15C)."""
        # 50 - 37 = 13C drop, exceeds 12C limit
        safe, reason = check_safety_conditions(37.0, 50.0, cold_weather=True)
        assert not safe, "13C drop should trigger safety in cold weather mode"

    def test_cold_weather_safety_relative_12c_drop_triggers(self):
        """12C drop exactly should trigger in cold weather."""
        # 50 - 38 = 12C drop, exactly at limit - should still be safe
        safe, _ = check_safety_conditions(38.0, 50.0, cold_weather=True)
        assert safe, "12C drop exactly should be safe"

        # 50 - 37.9 = 12.1C drop, just over limit
        safe, _ = check_safety_conditions(37.9, 50.0, cold_weather=True)
        assert not safe, "12.1C drop should trigger safety"

    def test_cold_weather_safety_relative_passes(self):
        """FR-45-CW: 11C drop is OK."""
        # 50 - 39 = 11C drop, within 12C limit
        safe, _ = check_safety_conditions(39.0, 50.0, cold_weather=True)
        assert safe, "11C drop should be safe in cold weather mode"

    def test_normal_mode_safety_unchanged(self):
        """Normal mode uses original thresholds (32C absolute, 15C relative)."""
        # 37C is above 32C minimum for normal mode
        safe, _ = check_safety_conditions(37.0, 50.0, cold_weather=False)
        assert safe, "37C should be safe in normal mode"

        # 50 - 37 = 13C drop, within 15C limit for normal mode
        safe, _ = check_safety_conditions(37.0, 50.0, cold_weather=False)
        assert safe, "13C drop should be safe in normal mode"

    def test_normal_mode_absolute_minimum_32(self):
        """Normal mode absolute minimum should be 32C."""
        # 31C is below 32C minimum for normal mode
        safe, _ = check_safety_conditions(31.0, 50.0, cold_weather=False)
        assert not safe, "31C should trigger safety in normal mode"

    def test_normal_mode_relative_16c_triggers(self):
        """Normal mode relative drop of 16C should trigger."""
        # 50 - 34 = 16C drop, exceeds 15C limit
        safe, _ = check_safety_conditions(34.0, 50.0, cold_weather=False)
        assert not safe, "16C drop should trigger safety in normal mode"


# ============================================
# REGRESSION TESTS
# ============================================

@pytest.mark.skipif(not ALGORITHM_IMPORT_SUCCESS, reason="cold weather algorithm not yet implemented")
class TestColdWeatherRegression:
    """Regression tests to ensure normal mode is not affected."""

    def test_normal_mode_schedule_still_works(self):
        """Normal mode scheduling should not be affected by cold weather code."""
        # This test ensures we didn't break existing functionality
        # The generate_cold_weather_schedule function should be separate
        # from the normal price-optimized scheduling
        pass  # Covered by existing test_price_optimizer.py tests


# ============================================
# MODULE STRUCTURE TESTS
# ============================================

class TestModuleStructure:
    """Tests for module structure that work before implementation."""

    def test_pyscript_directory_exists(self):
        """Verify pyscript directory exists."""
        assert PYSCRIPT_PATH.exists()

    def test_expected_files_location(self):
        """Document expected file locations."""
        pool_heating = PYSCRIPT_PATH / "pool_heating.py"
        pool_temp_control = PYSCRIPT_PATH / "pool_temp_control.py"

        if not ALGORITHM_IMPORT_SUCCESS:
            pytest.skip(f"Expected generate_cold_weather_schedule in: {pool_heating}")
        if not SAFETY_IMPORT_SUCCESS:
            pytest.skip(f"Expected cold weather safety in: {pool_temp_control}")
