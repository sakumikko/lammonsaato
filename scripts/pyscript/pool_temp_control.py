"""
Pool Temperature Control - PID-Feedback Target Control Algorithm

Manages the fixed system supply setpoint during pool heating to keep
the PID integral in the target range [-5, 0] and prevent external heater activation.

Algorithm: new_target = current_supply + pid_correction

Where pid_correction = (pid_30m - PID_TARGET) * PID_GAIN, clamped to [MIN_CORRECTION, MAX_CORRECTION]

Key insight: Error = Target - Supply
  - Positive error (target > supply) → PID DECREASES
  - Negative error (target < supply) → PID INCREASES

So when PID is too high, we set target ABOVE supply to create positive error and drive PID down.

Safety:
- FR-44: Stop if supply < 32 deg C
- FR-45: Stop if supply < (original_target - 15 deg C)
- FR-46: Set minimum compressor gear to 7

Entities required from Thermia:
- switch.enable_fixed_system_supply_set_point
- number.fixed_system_supply_set_point
- sensor.system_supply_line_temperature
- sensor.system_supply_line_calculated_set_point
- sensor.heating_season_integral_value (PID Integral 30m)
- number.minimum_allowed_gear_in_pool
- number.comfort_wheel_setting

This module exports pure functions for unit testing:
- calculate_new_setpoint(current_supply, prev_supply, pid_30m) -> (new_target, drop_rate, pid_correction)
- check_safety_conditions(current_supply, original_curve) -> (safe, reason)

Pyscript services (require Home Assistant):
- pool_temp_control_start
- pool_temp_control_stop
- pool_temp_control_adjust
- pool_temp_control_safety_check
- pool_temp_control_timeout
- pool_temp_control_preheat
"""

# ============================================
# CONFIGURATION CONSTANTS
# ============================================

# PID-Feedback Algorithm parameters
# Goal: Keep PID Integral 30m in range [-5, 0]
PID_TARGET = -2.5        # Target PID30 value (middle of [-5, 0])
PID_GAIN = 0.10          # °C offset per unit of PID error
MIN_CORRECTION = -1.0    # Max 1°C below supply (when PID too negative, need to raise PID)
MAX_CORRECTION = 4.0     # Max 4°C above supply (when PID too positive, need to lower PID)
MIN_SETPOINT = 28.0      # Minimum allowed fixed setpoint
MAX_SETPOINT = 45.0      # Maximum allowed fixed setpoint
MIN_GEAR_POOL = 7        # Minimum compressor gear during pool heating (FR-46)

# Legacy constants for backwards compatibility with tests (not used in new algorithm)
BASE_OFFSET = 0.5
TARGET_OFFSET = 0.5

# Comfort wheel preheat settings
PREHEAT_OFFSET = 3.0     # Degrees to raise comfort wheel before pool heating
MAX_COMFORT_WHEEL = 30.0 # Maximum allowed comfort wheel setting (don't overshoot)

# Safety thresholds
ABSOLUTE_MIN_SUPPLY = 32.0  # Stop if supply drops below this (FR-44)
RELATIVE_DROP_MAX = 15.0    # Stop if supply drops this much below original target (FR-45)

# Thermia entity IDs
FIXED_SUPPLY_ENABLE = "switch.enable_fixed_system_supply_set_point"
FIXED_SUPPLY_SETPOINT = "number.fixed_system_supply_set_point"
SUPPLY_TEMP_SENSOR = "sensor.system_supply_line_temperature"
CURVE_TARGET_SENSOR = "sensor.system_supply_line_calculated_set_point"
PID_INTEGRAL_SENSOR = "sensor.heating_season_integral_value"  # PID Integral 30m
MIN_GEAR_ENTITY = "number.minimum_allowed_gear_in_pool"  # Pool-specific gear
COMFORT_WHEEL_ENTITY = "number.comfort_wheel_setting"

# State storage entities
ORIGINAL_CURVE_TARGET = "input_number.pool_heating_original_curve_target"
ORIGINAL_MIN_GEAR = "input_number.pool_heating_original_min_gear"
ORIGINAL_COMFORT_WHEEL = "input_number.pool_heating_original_comfort_wheel"
PREV_SUPPLY_TEMP = "input_number.pool_heating_prev_supply_temp"
CONTROL_ACTIVE = "input_boolean.pool_temp_control_active"
PREHEAT_ACTIVE = "input_boolean.pool_heating_preheat_active"
SAFETY_FALLBACK = "input_boolean.pool_heating_safety_fallback"
CONTROL_LOG = "input_text.pool_temp_control_log"

# Pool heating control entities
HEATING_PREVENTION = "switch.altaan_lammityksen_esto"
CIRCULATION_PUMP = "switch.altaan_kiertovesipumppu"


# ============================================
# PURE FUNCTIONS (for unit testing)
# ============================================

def calculate_new_setpoint(current_supply: float, prev_supply: float, pid_30m: float = 0.0) -> tuple:
    """
    PID-Feedback Target Control Algorithm.

    Calculates the new fixed supply setpoint based on current supply
    temperature and PID Integral 30m value.

    Formula: new_target = current_supply + pid_correction

    Where pid_correction = (pid_30m - PID_TARGET) * PID_GAIN, clamped to [MIN_CORRECTION, MAX_CORRECTION]

    Key insight from data analysis:
    - Error = Target - Supply
    - Positive error (target > supply) → PID DECREASES
    - Negative error (target < supply) → PID INCREASES

    The goal is to keep PID Integral 30m in range [-5, 0]:
    - If PID > 0: set target ABOVE supply (positive correction) to drive PID down
    - If PID < -5: set target BELOW supply (negative correction) to drive PID up
    - If PID = -2.5 (target): no correction needed

    Args:
        current_supply: Current system supply line temperature (deg C)
        prev_supply: Supply temperature from 5 minutes ago (deg C) - kept for API compatibility
        pid_30m: Current PID Integral 30m value (default 0.0 for backwards compatibility)

    Returns:
        tuple: (new_setpoint, drop_rate, pid_correction)
            new_setpoint: New fixed supply target, clamped to safe range
            drop_rate: Always 0.0 (kept for API compatibility)
            pid_correction: The PID-based correction applied (deg C)
    """
    # Calculate PID correction
    # pid_error > 0 when PID is above target (too positive) → need positive correction
    # pid_error < 0 when PID is below target (too negative) → need negative correction
    pid_error = pid_30m - PID_TARGET
    pid_correction = pid_error * PID_GAIN
    pid_correction = max(MIN_CORRECTION, min(pid_correction, MAX_CORRECTION))

    # CORRECTED: target = supply + correction
    # When PID is high (+25): correction = +2.75 → target ABOVE supply → positive error → PID decreases
    # When PID is low (-10): correction = -0.75 → target BELOW supply → negative error → PID increases
    new_target = current_supply + pid_correction

    # Clamp to safe range
    new_target = max(MIN_SETPOINT, min(new_target, MAX_SETPOINT))

    # Round to 1 decimal place
    new_target = round(new_target, 1)

    # drop_rate kept at 0.0 for API compatibility
    return new_target, 0.0, pid_correction


def check_safety_conditions(current_supply: float, original_curve: float) -> tuple:
    """
    Check safety conditions for pool heating.

    FR-44: Supply must not drop below ABSOLUTE_MIN_SUPPLY (32 deg C)
    FR-45: Supply must not drop more than RELATIVE_DROP_MAX (15 deg C) below curve

    Args:
        current_supply: Current system supply line temperature (deg C)
        original_curve: Original curve target at pool heating start (deg C)

    Returns:
        tuple: (safe, reason)
            safe: True if conditions are safe, False if fallback needed
            reason: Description of violation if not safe, None if safe
    """
    # FR-44: Absolute minimum check
    if current_supply < ABSOLUTE_MIN_SUPPLY:
        return False, f"FR-44: Supply {current_supply} deg C below minimum {ABSOLUTE_MIN_SUPPLY} deg C"

    # FR-45: Relative drop check
    max_allowed_drop = original_curve - RELATIVE_DROP_MAX
    if current_supply < max_allowed_drop:
        return False, (f"FR-45: Supply {current_supply} deg C dropped >{RELATIVE_DROP_MAX} deg C "
                       f"below curve target {original_curve} deg C")

    return True, None


# ============================================
# PYSCRIPT HELPER FUNCTIONS
# ============================================

def _safe_get_float(entity_id: str, default: float = 0.0) -> float:
    """Safely get float value from entity state."""
    try:
        val = state.get(entity_id)
        if val in ['unknown', 'unavailable', None, '']:
            return default
        return float(val)
    except (ValueError, TypeError, NameError):
        return default


def _log_action(message: str):
    """Log action to both HA log and control log entity."""
    try:
        log.info(f"[PoolTempControl] {message}")
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M")
        service.call("input_text", "set_value",
                     entity_id=CONTROL_LOG,
                     value=f"{timestamp}: {message}"[:255])
    except NameError:
        # Running in pytest without pyscript context
        pass


# ============================================
# PYSCRIPT SERVICES
# ============================================

try:
    @service
    def pool_temp_control_start():
        """
        Initialize temperature control at pool heating start.

        - Restores original comfort wheel (if preheat was active)
        - Stores original curve target for safety checks (FR-45)
        - Stores original minimum gear and sets to MIN_GEAR_POOL (FR-46)
        - Enables fixed supply mode with initial setpoint
        - Initializes previous supply temperature for drop rate calculation
        """
        # Check if fixed supply entities are available
        fixed_enable_state = state.get(FIXED_SUPPLY_ENABLE)
        if fixed_enable_state in ['unknown', 'unavailable', None]:
            log.error(f"Fixed supply enable switch not available: {fixed_enable_state}")
            return

        # Restore comfort wheel if preheat was active
        preheat_was_active = state.get(PREHEAT_ACTIVE) == 'on'
        if preheat_was_active:
            original_comfort = _safe_get_float(ORIGINAL_COMFORT_WHEEL, 20.0)
            service.call("number", "set_value",
                         entity_id=COMFORT_WHEEL_ENTITY,
                         value=original_comfort)
            service.call("input_boolean", "turn_off",
                         entity_id=PREHEAT_ACTIVE)
            _log_action(f"Preheat ended: comfort wheel restored to {original_comfort} deg C")

        # Store original curve target (for FR-45 safety check)
        original_curve = _safe_get_float(CURVE_TARGET_SENSOR, 40.0)
        service.call("input_number", "set_value",
                     entity_id=ORIGINAL_CURVE_TARGET,
                     value=original_curve)

        # Store and set minimum gear (FR-46)
        original_gear = _safe_get_float(MIN_GEAR_ENTITY, 1)
        service.call("input_number", "set_value",
                     entity_id=ORIGINAL_MIN_GEAR,
                     value=original_gear)
        service.call("number", "set_value",
                     entity_id=MIN_GEAR_ENTITY,
                     value=MIN_GEAR_POOL)

        # Get current supply and calculate initial setpoint
        current_supply = _safe_get_float(SUPPLY_TEMP_SENSOR, 40.0)
        initial_setpoint = max(MIN_SETPOINT, min(current_supply - TARGET_OFFSET, MAX_SETPOINT))

        # Store previous supply for first drop rate calculation
        service.call("input_number", "set_value",
                     entity_id=PREV_SUPPLY_TEMP,
                     value=current_supply)

        # Enable fixed supply mode and set initial setpoint
        service.call("number", "set_value",
                     entity_id=FIXED_SUPPLY_SETPOINT,
                     value=initial_setpoint)
        service.call("switch", "turn_on",
                     entity_id=FIXED_SUPPLY_ENABLE)

        # Mark control as active
        service.call("input_boolean", "turn_on",
                     entity_id=CONTROL_ACTIVE)

        _log_action(f"Started: supply={current_supply} deg C, target={initial_setpoint} deg C, "
                    f"curve={original_curve} deg C, gear->{MIN_GEAR_POOL}")


    @service
    def pool_temp_control_stop():
        """
        Disable temperature control at pool heating end.

        - Disables fixed supply mode
        - Restores original minimum gear
        - Clears control active flag
        """
        # Disable fixed supply mode
        service.call("switch", "turn_off",
                     entity_id=FIXED_SUPPLY_ENABLE)

        # Restore original minimum gear
        original_gear = _safe_get_float(ORIGINAL_MIN_GEAR, 1)
        service.call("number", "set_value",
                     entity_id=MIN_GEAR_ENTITY,
                     value=original_gear)

        # Clear control active flag
        service.call("input_boolean", "turn_off",
                     entity_id=CONTROL_ACTIVE)

        # Clear previous supply temp
        service.call("input_number", "set_value",
                     entity_id=PREV_SUPPLY_TEMP,
                     value=0)

        _log_action(f"Stopped: restored gear->{original_gear}")


    @service
    def pool_temp_control_adjust():
        """
        Adjust fixed supply setpoint using PID-Feedback Target Control algorithm.

        Called every 5 minutes during pool heating.
        new_target = current_supply - BASE_OFFSET - pid_correction - anticipated_drop
        """
        # Get current and previous supply temperatures
        current_supply = _safe_get_float(SUPPLY_TEMP_SENSOR, 0)
        prev_supply = _safe_get_float(PREV_SUPPLY_TEMP, 0)
        current_setpoint = _safe_get_float(FIXED_SUPPLY_SETPOINT, 30)
        pid_30m = _safe_get_float(PID_INTEGRAL_SENSOR, 0)

        if current_supply <= 0:
            log.warning("Supply temperature sensor unavailable, skipping adjustment")
            return

        # Calculate new setpoint with PID feedback
        new_setpoint, drop_rate, pid_correction = calculate_new_setpoint(
            current_supply, prev_supply, pid_30m
        )

        # Update setpoint if changed significantly
        if abs(new_setpoint - current_setpoint) >= 0.5:
            service.call("number", "set_value",
                         entity_id=FIXED_SUPPLY_SETPOINT,
                         value=new_setpoint)
            _log_action(f"Adjust: supply={current_supply:.1f}C, pid30={pid_30m:+.1f}, "
                        f"corr={pid_correction:+.1f}C, target={current_setpoint:.1f}->{new_setpoint:.1f}C")

        # Store current supply for next iteration
        service.call("input_number", "set_value",
                     entity_id=PREV_SUPPLY_TEMP,
                     value=current_supply)


    @service
    def pool_temp_control_safety_check():
        """
        Check safety conditions (FR-44, FR-45) and trigger fallback if needed.

        Called every minute during pool heating.
        """
        current_supply = _safe_get_float(SUPPLY_TEMP_SENSOR, 0)
        original_curve = _safe_get_float(ORIGINAL_CURVE_TARGET, 50)

        if current_supply <= 0:
            return  # Sensor unavailable, skip check

        safe, reason = check_safety_conditions(current_supply, original_curve)

        if not safe:
            _trigger_safety_fallback(reason)


    def _trigger_safety_fallback(reason: str):
        """
        Trigger safety fallback - stop pool heating, restore radiator heating.
        """
        log.warning(f"[PoolTempControl] SAFETY FALLBACK: {reason}")

        # Stop pool heating
        service.call("switch", "turn_on",
                     entity_id=HEATING_PREVENTION)
        service.call("switch", "turn_off",
                     entity_id=CIRCULATION_PUMP)

        # Disable fixed supply mode
        service.call("switch", "turn_off",
                     entity_id=FIXED_SUPPLY_ENABLE)

        # Restore original minimum gear
        original_gear = _safe_get_float(ORIGINAL_MIN_GEAR, 1)
        service.call("number", "set_value",
                     entity_id=MIN_GEAR_ENTITY,
                     value=original_gear)

        # Set fallback flag (prevents restart until cleared)
        service.call("input_boolean", "turn_on",
                     entity_id=SAFETY_FALLBACK)
        service.call("input_boolean", "turn_off",
                     entity_id=CONTROL_ACTIVE)

        # Notify user
        service.call("notify", "persistent_notification",
                     title="Pool Heating Safety Stop",
                     message=reason)

        _log_action(f"FALLBACK: {reason}")


    @service
    def pool_temp_control_timeout():
        """
        Handle 60-minute continuous heating timeout.

        Stop pool heating to allow radiators to recover.
        """
        log.warning("[PoolTempControl] 60-minute timeout triggered")

        # Stop pool heating (but don't set safety fallback - can restart next block)
        service.call("switch", "turn_on",
                     entity_id=HEATING_PREVENTION)

        # Stop temp control
        pool_temp_control_stop()

        _log_action("TIMEOUT: 60min max reached")


    @service
    def pool_temp_control_preheat():
        """
        Preheat radiators before pool heating.

        Called 15 minutes before scheduled pool heating block.
        Raises comfort wheel to boost radiator output before switching to pool.

        - Stores original comfort wheel setting
        - Raises comfort wheel by PREHEAT_OFFSET degrees (capped at MAX_COMFORT_WHEEL)
        - Sets preheat active flag (cleared when pool heating starts)
        """
        # Check if comfort wheel entity is available
        comfort_state = state.get(COMFORT_WHEEL_ENTITY)
        if comfort_state in ['unknown', 'unavailable', None]:
            log.warning(f"Comfort wheel entity not available: {comfort_state}")
            return

        # Don't preheat if already preheating or pool heating is active
        if state.get(PREHEAT_ACTIVE) == 'on':
            log.info("[PoolTempControl] Preheat already active, skipping")
            return

        if state.get(CONTROL_ACTIVE) == 'on':
            log.info("[PoolTempControl] Pool temp control already active, skipping preheat")
            return

        # Store original comfort wheel setting
        original_comfort = _safe_get_float(COMFORT_WHEEL_ENTITY, 20.0)
        service.call("input_number", "set_value",
                     entity_id=ORIGINAL_COMFORT_WHEEL,
                     value=original_comfort)

        # Calculate new comfort wheel setting (raised by PREHEAT_OFFSET, capped at MAX)
        new_comfort = min(original_comfort + PREHEAT_OFFSET, MAX_COMFORT_WHEEL)

        # Set raised comfort wheel
        service.call("number", "set_value",
                     entity_id=COMFORT_WHEEL_ENTITY,
                     value=new_comfort)

        # Mark preheat as active
        service.call("input_boolean", "turn_on",
                     entity_id=PREHEAT_ACTIVE)

        _log_action(f"Preheat started: comfort wheel {original_comfort}->{new_comfort} deg C")

except NameError:
    # Running in pytest without pyscript context - decorators not available
    pass
