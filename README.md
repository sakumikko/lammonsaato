# Lammonsaato - Pool Heating Optimizer

Smart pool heating automation for Home Assistant that schedules heating during the cheapest electricity hours using Nordpool spot prices.

## What is this?

This project automates pool heating for a small residential building with a ground-source heat pump. Instead of heating the pool at fixed times, it analyzes electricity spot prices and schedules heating during the cheapest hours of the night - typically saving 30-50% on pool heating electricity costs.

The system is designed for buildings where:
- Pool heating competes with space heating for heat pump capacity
- Electricity is purchased at spot prices (Nordpool)
- Heating can be flexibly scheduled during off-peak hours

## How it works

1. **Price fetching**: Every afternoon, tomorrow's Nordpool electricity prices become available
2. **Schedule optimization**: The system finds the cheapest time slots for 2 hours of heating between 21:00-07:00
3. **Smart scheduling**: Heating is split into 30-45 minute blocks with breaks, allowing space heating to run between pool heating cycles
4. **Energy monitoring**: Temperature sensors track heat transfer to calculate actual energy consumption and costs

## Hardware Setup

- **Heat pump**: Thermia Mega ground-source heat pump with Modbus TCP
- **Control**: Shelly Pro switch controlling the pool heating circuit
- **Platform**: Home Assistant OS running on Raspberry Pi
- **Sensors**: Heat pump's built-in condenser temperature sensors

## Features

- Automatic scheduling based on Nordpool spot prices (15-minute intervals)
- Configurable heating duration and block sizes
- Energy consumption calculation from condenser delta-T
- Cost tracking per heating session
- Prevents simultaneous pool and radiator heating
- Auto-recovery for Thermia integration stability issues
- Manual override controls

## Installation

See [Setup Guide](docs/SETUP_GUIDE.md) for detailed installation instructions.

### Quick Start

1. Install required Home Assistant integrations:
   - [Nordpool](https://github.com/custom-components/nordpool) (via HACS)
   - [Thermia Genesis](https://github.com/klejejs/ha-thermia-heat-pump-integration) (via HACS)
   - Shelly (built-in)
   - Pyscript (via HACS)

2. Copy files to Home Assistant:
   ```
   homeassistant/packages/pool_heating.yaml → /config/packages/
   scripts/pyscript/pool_heating.py → /config/pyscript/
   scripts/pyscript/firebase_sync.py → /config/pyscript/
   ```

3. Add to your `configuration.yaml`:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages

   pyscript:
     allow_all_imports: true
     hass_is_global: true
   ```

4. Restart Home Assistant and configure entity IDs

## Project Structure

```
lammonsaato/
├── homeassistant/
│   ├── packages/
│   │   └── pool_heating.yaml    # Main HA configuration
│   └── lovelace/
│       └── pool_heating_card.yaml  # Dashboard card
├── scripts/
│   ├── pyscript/                # Pyscript modules for HA
│   │   ├── pool_heating.py      # Price optimization & scheduling
│   │   └── firebase_sync.py     # Local session logging
│   └── standalone/              # Development & testing scripts
├── tests/                       # Unit tests
├── docs/                        # Documentation
└── Makefile                     # Development commands
```

## Documentation

- [Product Requirements](docs/PRODUCT_REQUIREMENTS.md) - What the system does and why
- [Technical Design](docs/TECHNICAL_DESIGN.md) - Architecture, components, entity reference
- [Setup Guide](docs/SETUP_GUIDE.md) - Step-by-step installation
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Thermia Registers](docs/THERMIA_REGISTERS.md) - Modbus register reference

## Development

```bash
# Create virtual environment
python -m venv env
source env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run unit tests
make test

# Test Thermia connection
make test-thermia

# Test HA integration (requires HA_URL and HA_TOKEN)
make test-ha-sensors
```

## Scheduling Algorithm

The optimizer finds the cheapest heating schedule with these constraints:

- **Total heating time**: 2 hours (configurable)
- **Block duration**: 30-45 minutes each
- **Break duration**: Equal to the preceding block (allows space heating)
- **Time window**: 21:00 - 07:00 (overnight when prices are typically lowest)
- **Price granularity**: 15-minute Nordpool intervals

Example schedule:
```
01:30-02:00 (30min) @ 2.0 c/kWh
02:30-03:00 (30min) @ 1.8 c/kWh
03:30-04:00 (30min) @ 1.8 c/kWh
05:00-05:30 (30min) @ 1.8 c/kWh
Average: 1.9 c/kWh
```

## Energy Calculation

Heat transfer is calculated from condenser temperatures:

```
Delta-T = condenser_out - condenser_in
Thermal Power (kW) = Delta-T × flow_rate × specific_heat
Electrical Power = Thermal Power / COP
```

Default assumptions:
- Flow rate: 45 L/min
- COP: 3.0
- Specific heat of water: 4.186 kJ/(kg·°C)

## License

MIT License - feel free to adapt this for your own setup.

## Acknowledgments

- [Nordpool integration](https://github.com/custom-components/nordpool) for electricity price data
- [Thermia Genesis integration](https://github.com/klejejs/ha-thermia-heat-pump-integration) for heat pump communication
- Home Assistant community for pyscript and automation patterns
