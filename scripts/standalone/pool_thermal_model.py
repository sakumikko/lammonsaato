#!/usr/bin/env python3
"""
Pool Temperature Thermal Model

This script analyzes historical data to calibrate a thermal model that:
1. Estimates true pool temperature from sensor readings
2. Predicts temperature after scheduled heating
3. Calculates heating hours needed to reach target

Based on calibration from circulation test (Dec 5, 2025):
- Pipe time constant τ = 7 minutes
- Sensor offset when idle: ~2°C below true temp
- Pool volume: 32,000 liters
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

# =============================================================================
# CALIBRATED PARAMETERS (from Dec 5 circulation test)
# =============================================================================

POOL_VOLUME_LITERS = 32000  # User provided
WATER_SPECIFIC_HEAT = 4.186  # kJ/(kg·K)
FLOW_RATE_LPS = 0.75  # 45 L/min = 0.75 L/s

# Pipe thermal lag (time for sensor to reach 63% of true temp)
TAU_PIPE_MINUTES = 7  # From circulation test: 20 min to stabilize = 3τ

# Sensor offset when pipes are at room temperature
IDLE_SENSOR_OFFSET = 2.3  # °C below true pool temp when no circulation

# Room temperature (pool room)
ROOM_TEMP = 20  # °C

# Heat loss coefficient (W/°C difference from ambient)
# Estimated from cooling curve: ~0.3°C/hour at ΔT=5°C
# Q = k × ΔT → dT/dt = k × ΔT / (m × c_p)
# 0.3°C/h = k × 5 / (32000 × 4186) → k ≈ 8000 W/°C
# This seems high - covered pool should be lower. Using 3000 W/°C
HEAT_LOSS_COEFFICIENT = 3000  # W/°C (conservative estimate for covered pool)

# Mixing efficiency (fraction of heat that reaches bulk pool)
# Some water short-circuits due to inlet/outlet in same corner
MIXING_EFFICIENCY = 0.7


@dataclass
class PoolState:
    """Current state of the pool thermal system."""
    sensor_temp: float  # What the sensor reads
    true_temp: float    # Estimated true pool temperature
    pipe_temp: float    # Estimated pipe temperature
    is_heating: bool    # Whether heating is active
    is_circulating: bool  # Whether pump is running
    time_since_state_change: float  # Minutes since heating/pump state changed


def estimate_true_temp(
    sensor_temp: float,
    is_heating: bool,
    is_circulating: bool,
    minutes_since_change: float,
    outdoor_temp: float = ROOM_TEMP
) -> float:
    """
    Estimate true pool temperature from sensor reading.

    The sensor is 20m from the pool. When circulation is off, it reads
    the pipe temperature (close to room temp). When circulation is on,
    it gradually approaches true pool temp with time constant τ.

    Args:
        sensor_temp: Current sensor reading (°C)
        is_heating: Whether heating is currently active
        is_circulating: Whether circulation pump is running
        minutes_since_change: Minutes since last heating/pump state change
        outdoor_temp: Room temperature (°C)

    Returns:
        Estimated true pool temperature (°C)
    """
    tau = TAU_PIPE_MINUTES

    if not is_circulating:
        # No circulation - sensor reads pipe temp, not pool temp
        # True temp is higher by the idle offset
        # But offset decays over time as pool cools toward room temp
        return sensor_temp + IDLE_SENSOR_OFFSET

    if is_heating:
        # During heating, sensor reads higher than pool due to hot pipes
        # The offset is: (condenser_out - pool) × (1 - e^(-t/τ))
        # Simplified: sensor overshoots by ~3-5°C initially, decays to ~1°C
        overshoot = 3.0 * math.exp(-minutes_since_change / tau)
        return sensor_temp - overshoot

    else:
        # Circulation but no heating
        # Sensor approaches true pool temp exponentially
        # After long circulation, sensor ≈ true pool temp
        convergence = 1 - math.exp(-minutes_since_change / tau)

        if minutes_since_change > 3 * tau:
            # Fully converged
            return sensor_temp
        else:
            # Still converging - estimate offset
            initial_offset = IDLE_SENSOR_OFFSET * (1 - convergence)
            return sensor_temp + initial_offset


def calculate_heat_input(
    condenser_out_temp: float,
    condenser_in_temp: float,
    duration_hours: float
) -> float:
    """
    Calculate thermal energy added to pool during heating.

    Args:
        condenser_out_temp: Hot water temperature going to pool (°C)
        condenser_in_temp: Return water temperature from pool (°C)
        duration_hours: Heating duration (hours)

    Returns:
        Thermal energy added (kWh)
    """
    delta_t = condenser_out_temp - condenser_in_temp

    # Thermal power: P = flow × ΔT × c_p
    # P (kW) = 0.75 L/s × ΔT × 4.186 kJ/(kg·K) = 3.14 × ΔT kW
    power_kw = FLOW_RATE_LPS * delta_t * WATER_SPECIFIC_HEAT

    # Apply mixing efficiency
    effective_power = power_kw * MIXING_EFFICIENCY

    return effective_power * duration_hours


def predict_temp_after_heating(
    current_true_temp: float,
    heating_hours: float,
    avg_delta_t: float = 6.0,  # Typical condenser delta-T
    outdoor_temp: float = ROOM_TEMP
) -> float:
    """
    Predict pool temperature after scheduled heating.

    Args:
        current_true_temp: Current true pool temperature (°C)
        heating_hours: Total heating duration (hours)
        avg_delta_t: Average condenser temperature difference (°C)
        outdoor_temp: Ambient temperature (°C)

    Returns:
        Predicted pool temperature after heating (°C)
    """
    # Thermal mass of pool
    thermal_mass = POOL_VOLUME_LITERS * WATER_SPECIFIC_HEAT  # kJ/°C

    # Heat input
    power_kw = FLOW_RATE_LPS * avg_delta_t * WATER_SPECIFIC_HEAT * MIXING_EFFICIENCY
    heat_input_kj = power_kw * heating_hours * 3600  # kWh to kJ

    # Heat loss during heating (simplified - assumes constant temp)
    avg_temp = current_true_temp + heat_input_kj / (2 * thermal_mass)
    heat_loss_kw = HEAT_LOSS_COEFFICIENT * (avg_temp - outdoor_temp) / 1000
    heat_loss_kj = heat_loss_kw * heating_hours * 3600

    # Net temperature change
    net_heat_kj = heat_input_kj - heat_loss_kj
    delta_temp = net_heat_kj / thermal_mass

    return current_true_temp + delta_temp


def calculate_hours_to_target(
    current_true_temp: float,
    target_temp: float,
    avg_delta_t: float = 6.0,
    outdoor_temp: float = ROOM_TEMP
) -> float:
    """
    Calculate heating hours needed to reach target temperature.

    Args:
        current_true_temp: Current true pool temperature (°C)
        target_temp: Target pool temperature (°C)
        avg_delta_t: Average condenser temperature difference (°C)
        outdoor_temp: Ambient temperature (°C)

    Returns:
        Required heating hours (may be fractional)
    """
    if current_true_temp >= target_temp:
        return 0.0

    # Thermal mass
    thermal_mass = POOL_VOLUME_LITERS * WATER_SPECIFIC_HEAT  # kJ/°C

    # Required temperature rise
    delta_temp_needed = target_temp - current_true_temp

    # Heating power
    power_kw = FLOW_RATE_LPS * avg_delta_t * WATER_SPECIFIC_HEAT * MIXING_EFFICIENCY

    # Heat loss rate at average temperature
    avg_temp = (current_true_temp + target_temp) / 2
    heat_loss_kw = HEAT_LOSS_COEFFICIENT * (avg_temp - outdoor_temp) / 1000

    # Net heating power
    net_power_kw = power_kw - heat_loss_kw

    if net_power_kw <= 0:
        return float('inf')  # Can't reach target - heat loss too high

    # Time = Energy / Power
    # Energy = thermal_mass × delta_temp (in kJ)
    energy_needed_kj = thermal_mass * delta_temp_needed
    hours = energy_needed_kj / (net_power_kw * 3600)

    return hours


def predict_cooling_curve(
    start_temp: float,
    hours: float,
    outdoor_temp: float = ROOM_TEMP,
    time_step_minutes: float = 15
) -> list[tuple[float, float]]:
    """
    Predict temperature decay over time (no heating).

    Args:
        start_temp: Initial pool temperature (°C)
        hours: Duration to simulate (hours)
        outdoor_temp: Ambient temperature (°C)
        time_step_minutes: Simulation time step (minutes)

    Returns:
        List of (hours_elapsed, temperature) tuples
    """
    thermal_mass = POOL_VOLUME_LITERS * WATER_SPECIFIC_HEAT * 1000  # J/°C
    dt = time_step_minutes * 60  # seconds

    results = []
    temp = start_temp
    time_elapsed = 0.0

    while time_elapsed <= hours:
        results.append((time_elapsed, temp))

        # Heat loss
        heat_loss_w = HEAT_LOSS_COEFFICIENT * (temp - outdoor_temp)
        energy_loss_j = heat_loss_w * dt

        # Temperature drop
        temp -= energy_loss_j / thermal_mass
        time_elapsed += time_step_minutes / 60

    return results


# =============================================================================
# EXAMPLE USAGE / TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Pool Thermal Model - Parameter Summary")
    print("=" * 60)
    print(f"Pool volume:          {POOL_VOLUME_LITERS:,} liters")
    print(f"Pipe time constant:   {TAU_PIPE_MINUTES} minutes")
    print(f"Idle sensor offset:   {IDLE_SENSOR_OFFSET}°C")
    print(f"Heat loss coefficient:{HEAT_LOSS_COEFFICIENT} W/°C")
    print(f"Mixing efficiency:    {MIXING_EFFICIENCY * 100}%")
    print()

    # Example: Estimate true temp from sensor
    print("=" * 60)
    print("Example: True Temperature Estimation")
    print("=" * 60)

    scenarios = [
        ("Idle (no circulation)", 22.0, False, False, 60),
        ("Just started circulation", 22.0, False, True, 5),
        ("Circulation 20 min", 24.5, False, True, 20),
        ("During heating (5 min)", 26.0, True, True, 5),
        ("During heating (30 min)", 27.0, True, True, 30),
    ]

    for name, sensor, heating, circ, minutes in scenarios:
        true_temp = estimate_true_temp(sensor, heating, circ, minutes)
        print(f"{name}:")
        print(f"  Sensor: {sensor}°C → True: {true_temp:.1f}°C")
    print()

    # Example: Predict temperature after heating
    print("=" * 60)
    print("Example: Temperature Prediction")
    print("=" * 60)

    current = 22.0  # Current true temp
    for hours in [1.0, 1.5, 2.0, 2.5]:
        predicted = predict_temp_after_heating(current, hours)
        print(f"After {hours}h heating: {current}°C → {predicted:.1f}°C")
    print()

    # Example: Hours to reach target
    print("=" * 60)
    print("Example: Hours to Reach Target")
    print("=" * 60)

    current = 22.0
    for target in [24.0, 25.0, 26.0, 27.0]:
        hours_needed = calculate_hours_to_target(current, target)
        print(f"From {current}°C to {target}°C: {hours_needed:.1f} hours")
    print()

    # Example: Cooling curve
    print("=" * 60)
    print("Example: Cooling Curve (no heating)")
    print("=" * 60)

    cooling = predict_cooling_curve(26.0, 6.0)
    for hours, temp in cooling[::4]:  # Every hour
        print(f"  {hours:.0f}h: {temp:.1f}°C")
