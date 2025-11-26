# Pool Heating Automation - Project Plan

## Overview

Smart pool heating system that optimizes energy costs by:
- Using Nordpool electricity prices to find cheapest heating windows
- Controlling pool heating via Shelly switches
- Reading Thermia heat pump registers via Modbus
- Preventing simultaneous pool and radiator heating
- Logging temperature differentials for future optimization

## System Components

### Hardware
- **Thermia Mega Heat Pump** - Main heating source (Modbus TCP on 192.168.50.10:502)
- **Shelly Switch** - Controls pool heating circuit valve/pump
- **Temperature Sensors** - Heat exchanger inlet/outlet, pool water temperature

### Software Stack
- **Home Assistant OS** on Raspberry Pi
- **Python scripts** for complex calculations
- **Firebase** for long-term data storage and analysis

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      HOME ASSISTANT                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Nordpool    │    │   Thermia    │    │    Shelly    │      │
│  │ Integration  │    │   Modbus     │    │ Integration  │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              Python Script (pyscript)               │       │
│  │  - Price analysis                                   │       │
│  │  - Optimal hour calculation                         │       │
│  │  - Temperature logging                              │       │
│  │  - Firebase sync                                    │       │
│  └─────────────────────────────────────────────────────┘       │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              Automations & Scripts                  │       │
│  │  - Schedule heating windows                         │       │
│  │  - Control Shelly switch                            │       │
│  │  - Monitor and log temperatures                     │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │     Firebase     │
                    │  - Price history │
                    │  - Heating logs  │
                    │  - Temp deltas   │
                    └──────────────────┘
```

---

## What Can Be Done With Existing Add-ons & Integrations

### 1. Nordpool Integration (HACS)
- **Integration**: `custom_components/nordpool`
- **Provides**: Hourly electricity prices for Finland (FI zone)
- **Sensors**: `sensor.nordpool_kwh_fi_eur_3_10_024`
- **Attributes**: Today's prices, tomorrow's prices (available ~13:00 CET)

### 2. Shelly Integration (Native)
- **Integration**: Built-in `shelly` integration
- **Provides**: Switch control, power monitoring
- **Entities**: `switch.shelly_pool_heating`, `sensor.shelly_pool_power`

### 3. Modbus Integration (Native)
- **Integration**: Built-in `modbus` integration
- **Provides**: Direct Thermia register access
- **Alternative**: Use `pythermiagenesis` via pyscript/AppDaemon

### 4. Pyscript (HACS)
- **Add-on**: `pyscript` - Python scripting in HA
- **Use for**: Complex price calculations, scheduling logic

### 5. AppDaemon (Add-on)
- **Alternative to pyscript**: Full Python environment
- **Better for**: Long-running processes, complex state management

### 6. File Editor / VS Code Server (Add-ons)
- For editing configuration files on the Pi

### 7. InfluxDB + Grafana (Add-ons)
- **Local alternative to Firebase** for data storage and visualization

---

## Required Configurations

### 1. Nordpool Configuration
```yaml
# configuration.yaml or via UI
nordpool:
  region: "FI"
  currency: "EUR"
  VAT: true
  precision: 3
  price_in_cents: false
```

### 2. Modbus Configuration for Thermia
```yaml
# configuration.yaml
modbus:
  - name: thermia
    type: tcp
    host: 192.168.50.10
    port: 502
    sensors:
      - name: "Thermia Heat Water Supply"
        address: 1  # Verify register address
        input_type: input
        unit_of_measurement: "°C"
        scale: 0.01
        precision: 1
      - name: "Thermia Heat Water Return"
        address: 2  # Verify register address
        input_type: input
        unit_of_measurement: "°C"
        scale: 0.01
        precision: 1
    switches:
      - name: "Thermia Pool Heating Mode"
        address: 100  # Verify coil address
        write_type: coil
```

### 3. Shelly Configuration
```yaml
# Auto-discovered, or manual:
shelly:
  host: 192.168.50.XX
```

### 4. Input Helpers
```yaml
# For storing calculated values
input_datetime:
  pool_heat_slot_1:
    name: "Pool Heating Slot 1"
    has_date: true
    has_time: true
  pool_heat_slot_2:
    name: "Pool Heating Slot 2"
    has_date: true
    has_time: true

input_number:
  pool_heat_slot_1_price:
    name: "Slot 1 Price"
    min: 0
    max: 100
    unit_of_measurement: "c/kWh"
  pool_heat_slot_2_price:
    name: "Slot 2 Price"
    min: 0
    max: 100
    unit_of_measurement: "c/kWh"

input_boolean:
  pool_heating_enabled:
    name: "Pool Heating Enabled"
    icon: mdi:pool
```

---

## Python Scripts Architecture

### Option A: Pyscript (Recommended for HA integration)

```
/config/pyscript/
├── apps/
│   └── pool_heating/
│       ├── __init__.py
│       ├── price_optimizer.py    # Nordpool price analysis
│       ├── heating_scheduler.py  # Calculate best hours
│       ├── temperature_logger.py # Log temp differentials
│       └── firebase_sync.py      # External data sync
└── modules/
    └── thermia_client.py         # Modbus communication
```

### Option B: AppDaemon (More powerful Python)

```
/config/appdaemon/apps/
├── pool_heating.py      # Main application
├── price_optimizer.py   # Price calculations
├── firebase_client.py   # Firebase integration
└── apps.yaml           # App configuration
```

### Core Algorithm: Non-Consecutive Cheapest Hours

```python
def find_best_heating_slots(prices: dict, window_start: int = 21, window_end: int = 7, slots: int = 2):
    """
    Find N cheapest non-consecutive hours in the heating window.

    Args:
        prices: Dict of {hour: price} for 24 hours
        window_start: Start hour (21 = 9 PM)
        window_end: End hour (7 = 7 AM)
        slots: Number of heating slots needed

    Returns:
        List of (hour, price) tuples for best slots
    """
    # Extract valid hours (21-23, 0-6)
    valid_hours = []
    for hour, price in prices.items():
        if hour >= window_start or hour < window_end:
            valid_hours.append((hour, price))

    # Sort by price
    valid_hours.sort(key=lambda x: x[1])

    # Select non-consecutive hours
    selected = []
    for hour, price in valid_hours:
        if len(selected) >= slots:
            break
        # Check not adjacent to any selected hour
        is_adjacent = any(
            abs(hour - sel_hour) == 1 or
            (hour == 23 and sel_hour == 0) or
            (hour == 0 and sel_hour == 23)
            for sel_hour, _ in selected
        )
        if not is_adjacent:
            selected.append((hour, price))

    return sorted(selected, key=lambda x: x[0])
```

---

## Data Storage Strategy

### Option 1: Firebase Realtime Database (Recommended for external access)

**Pros:**
- Access data outside home network
- Easy visualization and analysis
- Free tier sufficient for this use case

**Structure:**
```json
{
  "heating_sessions": {
    "2024-01-15_22": {
      "start_time": "2024-01-15T22:00:00",
      "end_time": "2024-01-15T23:00:00",
      "electricity_price": 5.23,
      "heat_exchanger_in": 45.2,
      "heat_exchanger_out": 38.1,
      "delta_t": 7.1,
      "pool_temp_before": 28.5,
      "pool_temp_after": 29.1,
      "estimated_kwh": 12.5
    }
  },
  "daily_prices": {
    "2024-01-15": {
      "prices": [5.2, 4.8, 4.5, ...],
      "selected_hours": [2, 5],
      "avg_price": 5.01
    }
  }
}
```

**Python Integration:**
```python
import firebase_admin
from firebase_admin import credentials, db

# Initialize in pyscript/appdaemon
cred = credentials.Certificate("/config/secrets/firebase-key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://your-project.firebaseio.com'
})

def log_heating_session(session_data):
    ref = db.reference('heating_sessions')
    ref.push(session_data)
```

### Option 2: InfluxDB (Local, better for HA integration)

**Pros:**
- Native HA integration
- Grafana dashboards
- Time-series optimized

**Configuration:**
```yaml
# configuration.yaml
influxdb:
  host: a]b7d9c1_influxdb
  port: 8086
  database: pool_heating
  include:
    entities:
      - sensor.thermia_*
      - sensor.pool_*
      - sensor.nordpool_*
```

### Option 3: Hybrid Approach (Best of both)
- InfluxDB for real-time HA data
- Firebase sync for external analysis (daily batch)

---

## Wiring Everything Together

### Automation Flow

```yaml
# 1. Trigger: Tomorrow's prices available (~13:00)
automation:
  - alias: "Calculate Pool Heating Schedule"
    trigger:
      - platform: state
        entity_id: sensor.nordpool_kwh_fi_eur_3_10_024
        attribute: tomorrow_valid
        to: true
    action:
      - service: pyscript.calculate_heating_slots
        data:
          prices: "{{ state_attr('sensor.nordpool_kwh_fi_eur_3_10_024', 'tomorrow') }}"

# 2. Trigger: Scheduled heating time
  - alias: "Start Pool Heating Slot"
    trigger:
      - platform: time
        at: input_datetime.pool_heat_slot_1
      - platform: time
        at: input_datetime.pool_heat_slot_2
    condition:
      - condition: state
        entity_id: input_boolean.pool_heating_enabled
        state: 'on'
    action:
      - service: script.start_pool_heating

# 3. Script: Heating sequence
script:
  start_pool_heating:
    sequence:
      - service: pyscript.log_heating_start
      - service: switch.turn_on
        target:
          entity_id: switch.shelly_pool_heating
      - delay: "01:00:00"  # 1 hour heating
      - service: switch.turn_off
        target:
          entity_id: switch.shelly_pool_heating
      - service: pyscript.log_heating_end
```

---

## Project Structure

```
lammonsaato/
├── README.md                     # Project overview and setup guide
├── docs/
│   ├── PROJECT_PLAN.md          # This file
│   ├── SETUP_GUIDE.md           # Step-by-step installation
│   ├── THERMIA_REGISTERS.md     # Modbus register documentation
│   └── TROUBLESHOOTING.md       # Common issues and solutions
│
├── config/                       # Configuration templates
│   ├── configuration.yaml        # Main HA config additions
│   ├── secrets.yaml.template     # Secrets template
│   ├── modbus.yaml              # Thermia Modbus config
│   └── packages/
│       └── pool_heating.yaml    # Complete package config
│
├── homeassistant/
│   ├── packages/                # HA packages (copy to /config/packages/)
│   │   └── pool_heating.yaml
│   ├── automations/             # Automation YAML files
│   │   ├── calculate_schedule.yaml
│   │   ├── start_heating.yaml
│   │   └── log_temperatures.yaml
│   ├── scripts/                 # HA script YAML files
│   │   ├── start_pool_heating.yaml
│   │   └── stop_pool_heating.yaml
│   └── custom_components/       # If needed
│
├── scripts/                      # Python scripts
│   ├── pyscript/                # For pyscript integration
│   │   ├── pool_heating.py      # Main pyscript module
│   │   └── firebase_sync.py     # Firebase integration
│   ├── standalone/              # Standalone test scripts
│   │   ├── test_thermia.py      # Existing thermia test
│   │   ├── test_nordpool.py     # Test Nordpool API
│   │   └── test_firebase.py     # Test Firebase connection
│   └── appdaemon/               # Alternative: AppDaemon apps
│       ├── apps.yaml
│       └── pool_heating.py
│
├── tests/                        # Test utilities
│   ├── test_price_optimizer.py  # Unit tests for price algorithm
│   ├── mock_data/               # Mock data for testing
│   │   ├── sample_prices.json
│   │   └── sample_temperatures.json
│   └── conftest.py              # Pytest configuration
│
├── .env.template                # Environment variables template
├── requirements.txt             # Python dependencies
└── Makefile                     # Common commands
```

---

## Implementation Phases

### Phase 1: Foundation
1. Set up Nordpool integration
2. Configure Shelly integration
3. Test Thermia Modbus communication
4. Create input helpers for scheduling

### Phase 2: Core Logic
1. Implement price optimization algorithm
2. Create heating schedule calculator
3. Build automations for scheduled heating
4. Test heating control flow

### Phase 3: Monitoring
1. Add temperature sensor logging
2. Calculate energy consumption from delta-T
3. Store data locally (InfluxDB or file)

### Phase 4: External Storage
1. Set up Firebase project
2. Implement data sync
3. Create backup/export routines

### Phase 5: Optimization
1. Analyze historical data
2. Implement predictive heating (weather, usage patterns)
3. Add notifications and dashboards

---

## Key Thermia Registers to Monitor

Based on pythermiagenesis library, key registers:

| Register Name | Purpose |
|--------------|---------|
| `outdoor_temperature` | External temp for calculations |
| `supply_line_temperature` | Heat water going out |
| `return_line_temperature` | Heat water coming back |
| `hot_water_top` | DHW tank temperature |
| `compressor_speed` | Current load indicator |
| `heat_pump_running` | On/off status |

---

## Next Steps

1. **Verify Thermia registers** - Run test_thermia.py with full register read
2. **Install Nordpool** - Add via HACS
3. **Configure Shelly** - Ensure proper entity naming
4. **Create Firebase project** - Get credentials
5. **Start Phase 1 implementation**
