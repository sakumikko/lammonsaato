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

### 2.2 Pyscript Module (`scripts/pyscript/pool_heating.py`)

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
   - 4 blocks × 30-45 min each = 120 min total
   - Break between blocks = preceding block duration
3. For each configuration:
   - Calculate total cost (sum of slot prices × slot duration)
4. Select configuration with lowest total cost
5. Set input_datetime entities with block times
6. Set input_number entities with block prices
```

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
| `pool_start_heating_block_N` | Block N start time | Run script.pool_heating_block_start |
| `pool_stop_heating_block_N` | Block N end time | Run script.pool_heating_block_stop |
| `pool_log_temperatures` | Every 5 min when heating | Call pyscript.log_pool_temperatures |
| `thermia_hourly_reload` | Every hour | Reload Thermia integration |
| `thermia_stale_recovery` | Sensor stale >10 min | Reload Thermia integration |

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

### 6.2 Integration Tests (`scripts/standalone/`)

| Test File | Requirements | Command |
|-----------|--------------|---------|
| `test_live_integration.py` | Network access | `make test-thermia`, `make test-nordpool` |
| `test_ha_automation.py` | HA_URL, HA_TOKEN | `make test-ha` |
| `test_condenser_sensors.py` | HA_URL, HA_TOKEN | `make test-ha-sensors` |
| `test_templates.py` | HA_URL, HA_TOKEN | `python scripts/standalone/test_templates.py` |
| `test_firebase.py` | Firebase credentials | `make test-firebase` |

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
│   │   └── pool_heating.yaml      # All HA config in one file
│   └── lovelace/
│       └── pool_heating_card.yaml # Dashboard card
├── scripts/
│   ├── pyscript/
│   │   ├── pool_heating.py        # Schedule optimization
│   │   └── firebase_sync.py       # Local session logging
│   └── standalone/
│       ├── ha_client.py           # HA API client library
│       ├── test_live_integration.py
│       ├── test_ha_automation.py
│       ├── test_condenser_sensors.py
│       ├── test_templates.py
│       ├── test_firebase.py
│       └── find_thermia_sensors.py
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
