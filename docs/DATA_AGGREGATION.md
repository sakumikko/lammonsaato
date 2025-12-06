# Data Aggregation Framework

## Overview

Pool heating analytics data follows a hierarchical aggregation model with four levels. Each level aggregates data from the level below, ensuring accuracy and consistency.

## Aggregation Hierarchy

```
Raw Sensors (instantaneous, ~5s sampling)
    │
    ▼
15-Minute Sensors (aligned with Nordpool pricing periods)
    │
    ▼
Block/Session Sensors (per heating block execution)
    │
    ▼
Cycle Summary (24-hour heating cycle)
```

## Level 1: Raw Sensors (Instantaneous)

**Sampling Rate:** ~5 seconds (Thermia integration)

| Sensor | Unit | Description |
|--------|------|-------------|
| `sensor.pool_thermal_power` | kW | Thermal power output (from condenser ΔT × flow) |
| `sensor.pool_heating_electrical_power` | kW | Electrical power consumption (thermal / COP) |
| `sensor.pool_return_line_temperature_corrected` | °C | Pool water temperature |

**Calculation:**
```
thermal_power = ΔT × flow_rate × specific_heat
              = ΔT × 0.75 L/s × 4.186 kJ/(kg·K)
              = ΔT × 3.14 kW per °C

electrical_power = thermal_power / COP
                 = thermal_power / 3.0
```

## Level 2: 15-Minute Sensors (Nordpool Period)

**Aggregation Window:** 15 minutes (aligned with Nordpool pricing: XX:00, XX:15, XX:30, XX:45)

| Sensor | Unit | Description |
|--------|------|-------------|
| `sensor.pool_heating_15min_energy` | kWh | Electrical energy consumed in period |
| `sensor.pool_heating_15min_cost` | € | Cost for period (energy × price) |

**Calculation:**
```
15min_energy = ∫ electrical_power dt (over 15-minute window)
             = avg(electrical_power) × 0.25h

15min_cost = 15min_energy × nordpool_price[period]
```

**Trigger:** Every 15 minutes at XX:00, XX:15, XX:30, XX:45

## Level 3: Block/Session Sensors (Heating Block)

**Aggregation Window:** Duration of a single heating block (typically 30-60 minutes)

| Sensor | Unit | Description |
|--------|------|-------------|
| `sensor.pool_heating_session` | kWh | Total energy for the heating block |

**Attributes:**
- `block_number`: 1-10 (which block in the schedule)
- `heating_date`: YYYY-MM-DD of the cycle start
- `start_time`: ISO timestamp when block started
- `end_time`: ISO timestamp when block ended
- `duration_minutes`: Actual heating duration
- `energy_kwh`: Electrical energy consumed
- `thermal_kwh`: Thermal energy delivered
- `cost_eur`: Electricity cost for this block
- `price_eur_kwh`: Spot price during block
- `pool_temp_start`: Pool temperature at block start
- `pool_temp_end`: Pool temperature at block end
- `outdoor_temp`: Outdoor temperature during block

**Calculation:**
```
block_energy = Σ 15min_energy (for all 15-min periods within block)
block_cost = Σ 15min_cost (for all 15-min periods within block)
```

**Trigger:** When heating block ends (log_heating_end service)

## Level 4: Cycle Summary (24-Hour Heating Cycle)

**Aggregation Window:** 21:00 (inclusive) to 21:00+1 day (exclusive)

| Sensor | Unit | Description |
|--------|------|-------------|
| `sensor.pool_heating_night_summary` | kWh | Total energy for the cycle |
| `input_text.pool_heating_night_summary_data` | JSON | Raw data storage for persistence |

**Attributes:**
- `heating_date`: YYYY-MM-DD (date when 21:00 start occurred)
- `total_cost`: Total electricity cost (€)
- `baseline_cost`: What it would cost at average window price (€)
- `savings`: baseline_cost - total_cost (€)
- `duration_minutes`: Total heating time
- `blocks_count`: Number of heating blocks executed
- `outdoor_temp_avg`: Average outdoor temperature
- `pool_temp_final`: Pool temperature at cycle end
- `avg_price_cents`: Average electricity price (c/kWh)

**Calculation:**
```
cycle_energy = Σ block_energy (for all blocks in cycle)
cycle_cost = Σ block_cost (for all blocks in cycle)

baseline_cost = cycle_energy × avg(all_prices_in_window)
savings = baseline_cost - cycle_cost
```

**Cycle Window Definition:**
```
cycle_start = {heating_date} 21:00:00 (inclusive)
cycle_end   = {heating_date + 1 day} 21:00:00 (exclusive)

Example for heating_date = 2025-12-05:
  - Includes: 2025-12-05 21:00:00 to 2025-12-06 20:59:59
  - Duration: Exactly 24 hours
```

**Trigger:** Daily automation at 21:00 (to summarize the cycle that just ended)

## Data Flow Example

```
2025-12-05 21:00:00 - Cycle starts (heating_date = 2025-12-05)

2025-12-05 21:00 - 02:30: No heating (standby)

2025-12-06 02:30 - 03:00: Block 1 heating
  - 15min periods: 02:30-02:45 (1.2 kWh), 02:45-03:00 (1.3 kWh)
  - Block 1 total: 2.5 kWh, €0.03

2025-12-06 03:00 - 04:00: Break (no heating)

2025-12-06 04:00 - 04:30: Block 2 heating
  - 15min periods: 04:00-04:15 (1.1 kWh), 04:15-04:30 (1.2 kWh)
  - Block 2 total: 2.3 kWh, €0.02

... (more blocks) ...

2025-12-06 21:00:00 - Cycle ends
  - Cycle summary calculated
  - cycle_energy = 2.5 + 2.3 + ... = 9.8 kWh
  - cycle_cost = €0.03 + €0.02 + ... = €0.10
```

## Persistence

- **Raw sensors:** Stored in HA recorder (history)
- **15-min sensors:** Stored in HA recorder (trigger-based template sensor)
- **Block sensors:** `input_text` helper + template sensor (persists across restarts)
- **Cycle summary:** `input_text` helper + template sensor (persists across restarts)

## Important Notes

1. **Do NOT use utility meters** for analytics aggregation. Utility meters are for billing/display, not analytics.

2. **All timestamps are local time** (Europe/Helsinki timezone).

3. **Cycle boundary at 21:00** ensures the overnight heating window (21:00-07:00) is fully contained within a single cycle, plus captures any daytime activity.

4. **Energy calculations use electrical power**, not thermal power, since cost is based on electricity consumption.
