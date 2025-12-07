"""
Tests for Pool Thermal Calibration Functions

Tests the pure calculation logic for:
- Cooling model: exponential decay toward room temperature
- Confidence calculation: decreases over time since calibration
- Baseline temperature selection: based on time of day
- Temperature prediction after heating
"""

import math
import pytest
from datetime import datetime, timedelta


# Constants from pool_heating.py
ROOM_TEMP = 20  # Pool room temperature (°C)
TAU_COOL_HOURS = 20  # Cooling time constant (hours)
HEATING_RATE = 0.4  # °C per hour of heating
LOSS_RATE = 0.15  # °C per hour idle


def calculate_cooling(baseline_temp: float, hours_elapsed: float, room_temp: float = ROOM_TEMP) -> float:
    """
    Calculate pool temperature after cooling for given hours.

    Uses exponential decay model: T(t) = T_room + (T_0 - T_room) * e^(-t/τ)
    """
    return room_temp + (baseline_temp - room_temp) * math.exp(-hours_elapsed / TAU_COOL_HOURS)


def calculate_confidence(hours_since_calibration: float) -> float:
    """
    Calculate confidence level based on time since last calibration.

    Confidence is 1.0 at calibration, decays linearly to 0 at 12 hours.
    """
    return max(0, 1 - hours_since_calibration / 12)


def select_baseline_temp(hour: int, pre_heat: float, post_heat: float, daytime: float) -> tuple:
    """
    Select which baseline temperature to use based on time of day.

    Returns (temperature, type_name) tuple.
    """
    if 7 <= hour < 14:
        # Morning after heating - use post_heating
        baseline_temp = post_heat if post_heat > 0 else pre_heat
        baseline_type = "post_heating"
    elif 14 <= hour < 20:
        # Afternoon - use daytime if available, else post_heating
        if daytime > 0:
            baseline_temp = daytime
            baseline_type = "daytime"
        elif post_heat > 0:
            baseline_temp = post_heat
            baseline_type = "post_heating"
        else:
            baseline_temp = pre_heat
            baseline_type = "pre_heating"
    else:
        # Evening/night (20:00-06:59) - use pre_heating
        baseline_temp = pre_heat if pre_heat > 0 else post_heat
        baseline_type = "pre_heating"

    return baseline_temp, baseline_type


def predict_temp_after_heating(current_temp: float, heating_hours: float, window_hours: float = 10) -> dict:
    """
    Predict pool temperature after heating.

    Returns dict with predicted_temp, temp_gain, temp_loss.
    """
    idle_hours = window_hours - heating_hours
    temp_gain = heating_hours * HEATING_RATE
    temp_loss = idle_hours * LOSS_RATE
    predicted_temp = current_temp + temp_gain - temp_loss

    return {
        "predicted_temp": predicted_temp,
        "temp_gain": temp_gain,
        "temp_loss": temp_loss
    }


class TestCoolingModel:
    """Tests for the exponential cooling model."""

    def test_no_cooling_at_time_zero(self):
        """Temperature should equal baseline at t=0."""
        baseline = 25.0
        result = calculate_cooling(baseline, 0)
        assert result == baseline

    def test_approaches_room_temp_asymptotically(self):
        """After many hours, temp approaches room temp."""
        baseline = 26.0
        # After 100 hours (~5τ), should be very close to room temp
        result = calculate_cooling(baseline, 100)
        assert abs(result - ROOM_TEMP) < 0.1

    def test_half_decay_at_tau_ln2(self):
        """Temperature difference halves at t = τ * ln(2) ≈ 13.9 hours."""
        baseline = 26.0  # 6°C above room temp
        half_life_hours = TAU_COOL_HOURS * math.log(2)  # ~13.9 hours
        result = calculate_cooling(baseline, half_life_hours)
        # Difference from room temp should be halved
        expected_diff = (baseline - ROOM_TEMP) / 2  # 3°C
        actual_diff = result - ROOM_TEMP
        assert abs(actual_diff - expected_diff) < 0.01

    def test_typical_overnight_cooling(self):
        """Test realistic overnight cooling scenario."""
        # Pool at 25°C, 8 hours overnight
        baseline = 25.0
        result = calculate_cooling(baseline, 8)
        # Should cool about 1.5°C over 8 hours
        # T(8) = 20 + 5 * e^(-8/20) = 20 + 5 * 0.67 = 23.35
        assert 23.0 < result < 24.0

    def test_cooling_rate_depends_on_delta(self):
        """Warmer pool cools faster (larger delta)."""
        hot_pool = calculate_cooling(30.0, 5) - 30.0  # Cooling from 30°C
        warm_pool = calculate_cooling(25.0, 5) - 25.0  # Cooling from 25°C
        # Hot pool should lose more heat
        assert abs(hot_pool) > abs(warm_pool)


class TestConfidenceCalculation:
    """Tests for confidence decay over time."""

    def test_confidence_is_one_at_calibration(self):
        """Confidence should be 1.0 immediately after calibration."""
        assert calculate_confidence(0) == 1.0

    def test_confidence_is_zero_at_12_hours(self):
        """Confidence should be 0 at 12 hours."""
        assert calculate_confidence(12) == 0.0

    def test_confidence_stays_zero_after_12_hours(self):
        """Confidence should not go negative."""
        assert calculate_confidence(24) == 0.0
        assert calculate_confidence(100) == 0.0

    def test_confidence_at_6_hours(self):
        """Confidence should be 0.5 at 6 hours."""
        assert calculate_confidence(6) == 0.5

    def test_confidence_is_linear(self):
        """Confidence should decrease linearly."""
        # Check multiple points
        assert abs(calculate_confidence(3) - 0.75) < 0.001
        assert abs(calculate_confidence(9) - 0.25) < 0.001


class TestBaselineSelection:
    """Tests for selecting baseline temperature based on time of day."""

    def test_morning_uses_post_heating(self):
        """Morning (7-14) should prefer post_heating temp."""
        temp, type_name = select_baseline_temp(8, pre_heat=24.0, post_heat=25.5, daytime=0)
        assert temp == 25.5
        assert type_name == "post_heating"

    def test_morning_fallback_to_pre_heating(self):
        """Morning should fallback to pre_heating if post_heating unavailable."""
        temp, type_name = select_baseline_temp(10, pre_heat=24.0, post_heat=0, daytime=0)
        assert temp == 24.0
        assert type_name == "post_heating"  # Type name stays post_heating even with fallback

    def test_afternoon_prefers_daytime(self):
        """Afternoon (14-20) should prefer daytime temp."""
        temp, type_name = select_baseline_temp(15, pre_heat=24.0, post_heat=25.5, daytime=25.0)
        assert temp == 25.0
        assert type_name == "daytime"

    def test_afternoon_fallback_to_post_heating(self):
        """Afternoon should fallback to post_heating if no daytime reading."""
        temp, type_name = select_baseline_temp(16, pre_heat=24.0, post_heat=25.5, daytime=0)
        assert temp == 25.5
        assert type_name == "post_heating"

    def test_evening_uses_pre_heating(self):
        """Evening (20+) should prefer pre_heating temp."""
        temp, type_name = select_baseline_temp(21, pre_heat=24.5, post_heat=25.5, daytime=25.0)
        assert temp == 24.5
        assert type_name == "pre_heating"

    def test_night_uses_pre_heating(self):
        """Night (0-6) should prefer pre_heating temp."""
        temp, type_name = select_baseline_temp(3, pre_heat=24.5, post_heat=25.5, daytime=0)
        assert temp == 24.5
        assert type_name == "pre_heating"

    def test_evening_fallback_to_post_heating(self):
        """Evening should fallback to post_heating if no pre_heating."""
        temp, type_name = select_baseline_temp(22, pre_heat=0, post_heat=25.5, daytime=0)
        assert temp == 25.5
        assert type_name == "pre_heating"  # Type name stays pre_heating

    def test_boundary_at_7am(self):
        """Hour 7 should be morning (post_heating)."""
        temp, type_name = select_baseline_temp(7, pre_heat=24.0, post_heat=25.5, daytime=0)
        assert type_name == "post_heating"

    def test_boundary_at_14(self):
        """Hour 14 should be afternoon (daytime)."""
        temp, type_name = select_baseline_temp(14, pre_heat=24.0, post_heat=25.5, daytime=25.0)
        assert type_name == "daytime"

    def test_boundary_at_20(self):
        """Hour 20 should be evening (pre_heating)."""
        temp, type_name = select_baseline_temp(20, pre_heat=24.0, post_heat=25.5, daytime=25.0)
        assert type_name == "pre_heating"


class TestTemperaturePrediction:
    """Tests for predicting temperature after heating."""

    def test_no_heating_only_loss(self):
        """With 0 heating hours, only heat loss occurs."""
        result = predict_temp_after_heating(25.0, heating_hours=0)
        # 10 hours idle × 0.15 = 1.5°C loss
        assert result["predicted_temp"] == 23.5
        assert result["temp_gain"] == 0
        assert result["temp_loss"] == 1.5

    def test_full_heating_10_hours(self):
        """With 10 hours heating, no idle time."""
        result = predict_temp_after_heating(24.0, heating_hours=10)
        # 10 hours × 0.4 = 4°C gain, 0 loss
        assert result["predicted_temp"] == 28.0
        assert result["temp_gain"] == 4.0
        assert result["temp_loss"] == 0

    def test_typical_2_hour_heating(self):
        """Typical 2 hour heating scenario."""
        result = predict_temp_after_heating(24.0, heating_hours=2)
        # 2h × 0.4 = 0.8°C gain, 8h × 0.15 = 1.2°C loss
        # Net: -0.4°C (slight loss)
        expected = 24.0 + 0.8 - 1.2
        assert abs(result["predicted_temp"] - expected) < 0.001

    def test_break_even_heating_hours(self):
        """Calculate heating hours needed to break even."""
        # To break even: gain = loss
        # h × 0.4 = (10 - h) × 0.15
        # 0.4h = 1.5 - 0.15h
        # 0.55h = 1.5
        # h ≈ 2.73 hours
        result = predict_temp_after_heating(24.0, heating_hours=2.73)
        # Should be approximately break even
        assert abs(result["predicted_temp"] - 24.0) < 0.05

    def test_typical_scenario_with_gain(self):
        """Test scenario with net temperature gain."""
        # 3 hours heating
        result = predict_temp_after_heating(23.0, heating_hours=3)
        # 3h × 0.4 = 1.2°C gain, 7h × 0.15 = 1.05°C loss
        # Net: +0.15°C
        expected = 23.0 + 1.2 - 1.05
        assert abs(result["predicted_temp"] - expected) < 0.001
        assert result["predicted_temp"] > 23.0  # Should gain


class TestIntegratedScenarios:
    """Integration tests combining multiple calculations."""

    def test_full_day_cycle(self):
        """Test a complete day: evening calibration → overnight cooling → morning estimate."""
        # Evening calibration at 20:30
        calibrated_temp = 25.0

        # Estimate at 8:00 next morning (11.5 hours later)
        morning_estimate = calculate_cooling(calibrated_temp, 11.5)
        morning_confidence = calculate_confidence(11.5)

        # Should have cooled about 2°C
        assert 22.5 < morning_estimate < 24.0
        # Confidence should be very low
        assert morning_confidence < 0.1

    def test_prediction_accuracy_tracking(self):
        """Test scenario for validating predictions against actuals."""
        # Pre-heating calibration
        pre_heat_temp = 24.0

        # Predict result of 2 hours heating
        prediction = predict_temp_after_heating(pre_heat_temp, heating_hours=2)

        # Simulated post-heating measurement (would come from real data)
        # If prediction is correct, post_heat should match prediction
        simulated_post_heat = 23.6  # Actual measured

        prediction_error = abs(prediction["predicted_temp"] - simulated_post_heat)
        # Error tracking - in practice, use this to tune HEATING_RATE
        assert prediction_error < 1.0  # Within 1°C is acceptable initially

    def test_cold_pool_needs_more_heating(self):
        """Cold pool needs more heating hours to reach target."""
        cold_pool = predict_temp_after_heating(22.0, heating_hours=2)
        warm_pool = predict_temp_after_heating(24.0, heating_hours=2)

        # Same heating, both should gain/lose same net
        cold_final = cold_pool["predicted_temp"]
        warm_final = warm_pool["predicted_temp"]

        assert cold_final < warm_final
        assert warm_final - cold_final == 24.0 - 22.0  # Difference preserved
