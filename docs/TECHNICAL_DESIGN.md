# Technical Design Document

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HOME ASSISTANT OS                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Nordpool    │    │ Thermia      │    │   Shelly     │          │
│  │ Integration  │    │ Genesis      │    │ Integration  │          │
│  │   (HACS)     │    │   (HACS)     │    │  (built-in)  │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│         ▼                   ▼                   ▼                   │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │                   Pyscript Modules                       │       │
│  │  pool_heating.py     │     firebase_sync.py              │       │
│  │  - Schedule calc     │     - Session logging             │       │
│  │  - Session tracking  │     - Daily summaries             │       │
│  └─────────────────────────────────────────────────────────┘       │
│                            │                                        │
│                            ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │            pool_heating.yaml Package                     │       │
│  │  - Input helpers (datetimes, numbers, booleans)          │       │
│  │  - Template sensors (power, cost, delta-T)               │       │
│  │  - Automations (schedule, start/stop blocks)             │       │
│  │  - Scripts (heating control sequences)                   │       │
│  └─────────────────────────────────────────────────────────┘       │
│                            │                                        │
│                            ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │              Lovelace Dashboard Card                     │       │
│  │  pool_heating_card.yaml                                  │       │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Local Storage   │
                    │  /config/pool_   │
                    │  heating_logs/   │
                    └──────────────────┘
```

## 2. Components

### 2.1 Home Assistant Package (`homeassistant/packages/pool_heating.yaml`)

Single YAML file containing all HA configuration:

**Input Helpers:**
| Entity | Type | Purpose |
|--------|------|---------|
| `input_boolean.pool_heating_enabled` | Boolean | Master enable/disable |
| `input_datetime.pool_heat_block_N_start` | DateTime | Block N start time (N=1-4) |
| `input_datetime.pool_heat_block_N_end` | DateTime | Block N end time (N=1-4) |
| `input_number.pool_heat_block_N_price` | Number | Block N electricity price |
| `input_number.pool_target_temperature` | Number | Target pool temp (unused) |
| `input_text.pool_heating_schedule_info` | Text | Human-readable schedule |
| `input_text.pool_heating_schedule_json` | Text | JSON schedule data |

**Template Sensors:**
| Entity | Unit | Calculation |
|--------|------|-------------|
| `sensor.pool_heat_exchanger_delta_t` | °C | condenser_out - condenser_in |
| `sensor.pool_thermal_power` | kW | delta_t × 0.75 × 4.186 (only when heating) |
| `sensor.pool_heating_electrical_power` | kW | thermal_power / 3.0 (COP) |
| `sensor.pool_heating_cost_rate` | €/h | electrical_power × price |
| `sensor.pool_next_heating` | timestamp | Next scheduled block start |
| `sensor.pool_heating_average_price` | c/kWh | Average of block prices |
| `sensor.pool_heating_block_count` | count | Number of scheduled blocks |

**Binary Sensors:**
| Entity | True When |
|--------|-----------|
| `binary_sensor.pool_heating_active` | Prevention OFF AND pump ON |
| `binary_sensor.nordpool_tomorrow_available` | Tomorrow's prices exist |
| `binary_sensor.pool_in_heating_window` | Currently in a scheduled block |

**Integration Sensors (Riemann Sum):**
| Entity | Tracks |
|--------|--------|
| `sensor.pool_heating_electricity` | Cumulative kWh (electrical) |
| `sensor.pool_heating_cumulative_cost` | Cumulative EUR |

**Utility Meters:**
| Entity | Cycle |
|--------|-------|
| `sensor.pool_heating_electricity_daily` | Daily kWh (electrical) |
| `sensor.pool_heating_electricity_monthly` | Monthly kWh (electrical) |
| `sensor.pool_heating_cost_daily` | Daily EUR |
| `sensor.pool_heating_cost_monthly` | Monthly EUR |

### 2.2 Pyscript Modules

#### `scripts/pyscript/pool_heating.py` - Schedule Optimization

**Services Exposed:**

| Service | Trigger | Purpose |
|---------|---------|---------|
| `pyscript.calculate_pool_heating_schedule` | Tomorrow prices available | Optimize and set schedule |
| `pyscript.log_heating_start` | Block start | Record initial temps |
| `pyscript.log_pool_temperatures` | Every 5 min during heating | Record temp readings |
| `pyscript.log_heating_end` | Block end | Calculate session totals |
| `pyscript.test_price_calculation` | Manual | Debug with mock data |

**Algorithm: Schedule Optimization**

```python
# Simplified algorithm flow:

1. Get prices for 21:00-07:00 window (40 × 15-min slots)
2. Generate all valid block configurations:
   - N blocks × 30-60 min each (configurable)
   - Break between blocks = preceding block duration
3. For each configuration:
   - Calculate total cost (sum of slot prices × slot duration)
4. Select configuration with lowest total cost
5. Set input_datetime entities with block times
6. Set input_number entities with block prices and costs
7. Apply cost constraint if configured (enable cheapest blocks up to EUR limit)
```

#### `scripts/pyscript/pool_temp_control.py` - PID Temperature Control

**Services Exposed:**

| Service | Trigger | Purpose |
|---------|---------|---------|
| `pyscript.pool_temp_control_start` | Block start | Store original settings, enable fixed supply |
| `pyscript.pool_temp_control_stop` | Block end | Restore settings, disable fixed supply |
| `pyscript.pool_temp_control_adjust` | Every 5 min during heating | Apply PID-feedback algorithm |
| `pyscript.pool_temp_control_safety_check` | Every 1 min during heating | Check FR-44/FR-45 conditions |
| `pyscript.pool_temp_control_timeout` | After 60 min continuous | Force stop for radiator recovery |
| `pyscript.pool_temp_control_preheat` | 15 min before block | Raise comfort wheel for preheat |

**Algorithm: PID-Feedback Target Control**

The algorithm keeps the PID Integral (30-min average) in target range [-5, 0] by adjusting the fixed supply setpoint.

```python
# Key insight: Error = Target - Supply
#   Positive error (target > supply) → PID DECREASES
#   Negative error (target < supply) → PID INCREASES

# Formula:
pid_error = pid_30m - PID_TARGET      # PID_TARGET = -2.5 (midpoint of [-5, 0])
pid_correction = pid_error * PID_GAIN  # PID_GAIN = 0.10
pid_correction = clamp(pid_correction, -1.0, +4.0)  # MIN/MAX correction
new_target = current_supply + pid_correction
new_target = clamp(new_target, 28.0, 45.0)  # MIN/MAX setpoint

# Examples:
# PID at +25: correction = (25 - (-2.5)) × 0.10 = +2.75 → target ABOVE supply → PID decreases
# PID at -10: correction = (-10 - (-2.5)) × 0.10 = -0.75 → target BELOW supply → PID increases
# PID at -2.5: correction = (-2.5 - (-2.5)) × 0.10 = 0 → target = supply (stable)
```

**Safety Conditions:**
- FR-44: Supply < 32°C → Trigger fallback
- FR-45: Supply < (original_curve - 15°C) → Trigger fallback
- FR-46: Set minimum compressor gear to 7

### 2.3 Data Logging Module (`scripts/pyscript/firebase_sync.py`)

Despite the name, this module logs to local JSON files (Firebase was disabled).

**Storage Location:** `/config/pool_heating_logs/`

**File Types:**
- `session_YYYYMMDD_HHMMSS.json` - Individual heating sessions
- `daily_YYYY-MM-DD.json` - Daily summaries with savings calculation

**Session Data Structure:**
```json
{
  "start_time": "2024-01-15T22:00:00",
  "end_time": "2024-01-15T22:45:00",
  "duration_hours": 0.75,
  "avg_price_cents": 3.2,
  "condenser_out_start": 45.2,
  "condenser_in_start": 38.1,
  "avg_delta_t": 7.1,
  "thermal_energy_kwh": 15.8,
  "electrical_energy_kwh": 5.3,
  "cost_eur": 0.17
}
```

### 2.4 Dashboard Card (`homeassistant/lovelace/pool_heating_card.yaml`)

Entities-based card showing:
1. Master enable toggle
2. 4 heating blocks (start, end, price for each)
3. Current status (heating active, next block)
4. Real-time metrics (delta-T, power, cost rate)
5. Daily/monthly totals

## 3. Entity Reference

### 3.1 External Entities (from integrations)

| Entity | Integration | Purpose |
|--------|-------------|---------|
| `sensor.nordpool_kwh_fi_eur_3_10_0255` | Nordpool | Electricity prices |
| `sensor.condenser_out_temperature` | Thermia Genesis | Hot water to pool |
| `sensor.condenser_in_temperature` | Thermia Genesis | Cool water from pool |
| `switch.altaan_lammityksen_esto` | Shelly | Heating prevention (OFF=allow) |
| `switch.altaan_kiertovesipumppu` | Shelly | Circulation pump (ON=heating) |

### 3.2 Thermia Integration Entry ID

Required for reload automations:
```
entry_id: ac1e4962ee893b58e6d2c1f95e4caeef
```

Find yours via Developer Tools → Services → Search "reload config entry"

## 4. Automations

| Automation | Trigger | Action |
|------------|---------|--------|
| `pool_calculate_heating_schedule` | Tomorrow prices available | Call pyscript.calculate_pool_heating_schedule |
| `pool_start_heating_blocks` | Block N start time (1-10) | Run script.pool_heating_block_start |
| `pool_stop_heating_blocks` | Block N end time (1-10) | Run script.pool_heating_block_stop |
| `pool_log_temperatures` | Every 5 min when heating | Call pyscript.log_pool_temperatures |
| `pool_temp_control_adjust` | Every 5 min when temp control active | Call pyscript.pool_temp_control_adjust |
| `pool_temp_control_safety_check` | Every 1 min when heating active | Call pyscript.pool_temp_control_safety_check |
| `thermia_hourly_reload` | Every hour | Reload Thermia integration |
| `thermia_stale_recovery` | Sensor stale >10 min | Reload Thermia integration |

## 4.1 Scripts

**Modular Scripts** (can be called individually from Developer Tools):

| Script | Purpose |
|--------|---------|
| `pool_heating_preheat` | Raise comfort wheel by 3°C to preheat radiators |
| `pool_heating_start_temp_control` | Enable fixed supply mode and start PID management |
| `pool_heating_switches_on` | Turn on pool heating switches (prevention OFF, pump ON) |
| `pool_heating_switches_off` | Turn off pool heating switches |
| `pool_heating_stop_temp_control` | Disable fixed supply mode and restore original settings |

**Orchestrator Scripts** (full sequences):

| Script | Sequence |
|--------|----------|
| `pool_heating_block_start` | preheat → 15min delay → temp control → switches ON |
| `pool_heating_block_stop` | temp control off → switches off → 15min mix → log final temp |
| `pool_heating_emergency_stop` | Immediately stop everything |
| `pool_heating_manual_start` | 30min heating session with logging |

**Heating Block Start Sequence:**
```
Block Start Trigger (at block_start time)
    │
    ▼
script.pool_heating_block_start
    │
    ├── script.pool_heating_preheat
    │   └── Raises comfort wheel +3°C
    │       ↓
    │   delay: 15 minutes (radiators warm up)
    │       ↓
    ├── script.pool_heating_start_temp_control
    │   └── Enables fixed supply mode
    │       ↓
    └── script.pool_heating_switches_on
        └── Prevention OFF, Circulation ON
```

## 5. Energy Calculation

### 5.1 Thermal Power

```
Q (kW) = ΔT × flow_rate × specific_heat

Where:
  ΔT = condenser_out - condenser_in (°C)
  flow_rate = 45 L/min = 0.75 L/s
  specific_heat = 4.186 kJ/(kg·K)

Therefore:
  Q = ΔT × 0.75 × 4.186 = ΔT × 3.14 kW
```

### 5.2 Electrical Power

```
P_electrical = Q_thermal / COP

Where:
  COP = 3.0 (assumed)

Therefore:
  P_electrical = Q_thermal / 3.0
```

### 5.3 Cost Rate

```
Cost (€/h) = P_electrical (kW) × Price (€/kWh)

Note: Nordpool prices are in c/kWh, divide by 100 for EUR
```

## 6. Testing Strategy

### 6.1 Unit Tests (`tests/`)

| Test File | Coverage |
|-----------|----------|
| `test_price_optimizer.py` | Algorithm: edge cases, midnight boundary, negative prices |
| `test_ha_yaml.py` | YAML syntax, template validation |

Run: `make test`

### 6.2 Standalone Scripts (`scripts/standalone/`)

**Core Utilities:**

| Script | Purpose | Usage |
|--------|---------|-------|
| `ha_client.py` | Reusable HA REST/WebSocket client | Library for other scripts |
| `read_thermia_registers.py` | Direct Modbus read to Thermia | `python scripts/standalone/read_thermia_registers.py` |

**System Monitoring & Debugging:**

| Script | Purpose | Usage |
|--------|---------|-------|
| `fetch_analytics.py` | Display all analytics sensors | `python scripts/standalone/fetch_analytics.py` |
| `fetch_blocks.py` | Show current heating schedule | `python scripts/standalone/fetch_blocks.py` |
| `test_condenser_sensors.py` | Validate condenser temp sensors | `python scripts/standalone/test_condenser_sensors.py` |
| `validate_graph_entities.py` | Validate web-ui graph entities | `python scripts/standalone/validate_graph_entities.py` |

**Thermia Entity Management:**

| Script | Purpose | Usage |
|--------|---------|-------|
| `check_thermia_availability.py` | Check entity availability | `python scripts/standalone/check_thermia_availability.py` |
| `enable_thermia_entities.py` | Bulk enable/disable entities | `python scripts/standalone/enable_thermia_entities.py` |
| `sync_thermia_entities.py` | Sync entities with config | `python scripts/standalone/sync_thermia_entities.py` |

**Development & Testing:**

| Script | Purpose | Usage |
|--------|---------|-------|
| `test_templates.py` | Validate Jinja2 templates via HA | `python scripts/standalone/test_templates.py` |
| `pid_simulation.py` | PID algorithm benchmarking | `python scripts/standalone/pid_simulation.py` |
| `pool_thermal_model.py` | Thermal model calibration | Reference implementation |

### 6.3 Template Testing

When modifying Jinja2 templates in pool_heating.yaml:
1. Update corresponding test in `test_templates.py`
2. Test via HA Developer Tools → Template
3. Run `python scripts/standalone/test_templates.py`

## 7. Known Limitations

### 7.1 Thermia Integration Freezes
**Problem:** thermiagenesis integration stops polling after idle time.
**Solution:** Hourly reload automation + stale sensor recovery automation.

### 7.2 Pyscript Generator Expressions
**Problem:** Pyscript doesn't support Python generators.
**Solution:** Use explicit for loops instead of `sum(x for x in list)`.

### 7.3 Missing Pool Temperature Sensor
**Problem:** No direct pool water temperature sensor.
**Solution:** Use condenser delta-T for energy calculations; pool temp logged as 0.

### 7.4 Nordpool Entity ID Varies
**Problem:** Entity ID depends on Nordpool configuration.
**Solution:** Check Developer Tools → States for actual ID; update in pyscript and yaml.

## 8. Configuration Values

| Parameter | Value | Location |
|-----------|-------|----------|
| Thermia Host | 192.168.50.10:502 | Thermia Genesis integration |
| Thermia Entry ID | ac1e4962ee893b58e6d2c1f95e4caeef | pool_heating.yaml automations |
| Nordpool Sensor | sensor.nordpool_kwh_fi_eur_3_10_0255 | Multiple files |
| Heating Window | 21:00 - 07:00 | pool_heating.py constants |
| Total Duration | 120 minutes | pool_heating.py constants |
| Block Duration | 30-45 minutes | pool_heating.py constants |
| Flow Rate | 45 L/min | Template sensors |
| COP | 3.0 | Template sensors |

## 9. File Structure

```
lammonsaato/
├── homeassistant/
│   ├── packages/
│   │   ├── pool_heating.yaml      # Schedule, blocks, energy tracking
│   │   └── pool_temp_control.yaml # PID temperature control
│   └── lovelace/
│       └── pool_heating_card.yaml # Dashboard card
├── scripts/
│   ├── pyscript/
│   │   ├── pool_heating.py        # Schedule optimization
│   │   ├── pool_temp_control.py   # PID temperature control
│   │   └── firebase_sync.py       # Local session logging
│   └── standalone/
│       ├── ha_client.py                  # HA API client library
│       ├── read_thermia_registers.py     # Modbus debugging tool
│       ├── fetch_analytics.py            # Display analytics sensors
│       ├── fetch_blocks.py               # Show heating schedule
│       ├── test_condenser_sensors.py     # Validate sensors
│       ├── test_templates.py             # Validate Jinja2 templates
│       ├── validate_graph_entities.py    # Validate web-ui entities
│       ├── check_thermia_availability.py # Check entity availability
│       ├── enable_thermia_entities.py    # Bulk entity management
│       ├── sync_thermia_entities.py      # Sync entities with config
│       ├── pid_simulation.py             # PID benchmarking
│       └── pool_thermal_model.py         # Thermal model reference
├── web-ui/                         # Real-time visualization UI
│   ├── src/
│   │   ├── components/heating/    # System diagram components
│   │   ├── hooks/useHomeAssistant.ts  # HA WebSocket hook
│   │   └── lib/ha-websocket.ts    # WebSocket client
│   ├── addon/                     # HA add-on files
│   │   ├── config.yaml            # Add-on metadata
│   │   ├── Dockerfile
│   │   ├── nginx.conf
│   │   └── run.sh
│   └── README.md
├── tests/
│   ├── test_price_optimizer.py
│   ├── test_ha_yaml.py
│   └── conftest.py
├── docs/
│   ├── PRODUCT_REQUIREMENTS.md
│   ├── TECHNICAL_DESIGN.md        # This file
│   ├── SETUP_GUIDE.md
│   ├── TROUBLESHOOTING.md
│   └── THERMIA_REGISTERS.md
├── CLAUDE.md                       # Developer context
├── README.md
├── Makefile
└── requirements.txt
```

## 10. Web UI Add-on

The `web-ui/` directory contains a React-based real-time visualization of the heating system.

### Architecture

- **Technology**: React 18 + TypeScript + Tailwind CSS + shadcn/ui
- **Communication**: Home Assistant WebSocket API
- **Deployment**: HA Add-on with nginx + ingress

### Key Components

| Component | Purpose |
|-----------|---------|
| `SystemDiagram` | Main layout with pipes and connections |
| `HeatPumpUnit` | Heat pump status and temperatures |
| `GroundLoop` | Brine circuit visualization |
| `PoolUnit` | Pool heating status |
| `RadiatorUnit` | Radiator circuit status |
| `ValveIndicator` | 3-way valve position control |
| `ControlPanel` | Enable/disable controls |
| `SchedulePanel` | Nordpool price schedule |

### Building

```bash
cd web-ui
npm install
npm run build
./build-addon.sh
```

See `web-ui/README.md` for detailed documentation.
