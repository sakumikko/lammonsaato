# Lammonsaato - Pool Heating Optimizer

Smart pool heating automation for Home Assistant that optimizes heating times based on Nordpool electricity prices.

## Features

- Fetches Nordpool electricity prices for Finland
- Calculates optimal heating windows (cheapest non-consecutive hours)
- Controls pool heating via Shelly switches
- Prevents simultaneous pool and radiator heating
- Monitors temperature differentials for energy calculation
- Stores historical data in Firebase for analysis

## System Requirements

- Home Assistant OS on Raspberry Pi
- Thermia Mega heat pump with Modbus TCP
- Shelly switch for pool heating circuit
- Temperature sensors (heat exchanger in/out, pool water)

## Quick Start

1. Copy configuration files to your Home Assistant
2. Install required integrations (see [Setup Guide](docs/SETUP_GUIDE.md))
3. Configure your secrets
4. Enable the automations

## Documentation

- [Project Plan](docs/PROJECT_PLAN.md) - Architecture and implementation details
- [Setup Guide](docs/SETUP_GUIDE.md) - Installation instructions
- [Thermia Registers](docs/THERMIA_REGISTERS.md) - Modbus register reference
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues

## Project Structure

```
lammonsaato/
├── config/                  # Configuration templates
├── homeassistant/          # HA packages, automations, scripts
├── scripts/                # Python scripts (pyscript, standalone)
├── tests/                  # Unit tests and mock data
└── docs/                   # Documentation
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Test Thermia connection
python scripts/standalone/test_thermia.py 192.168.50.10
```

## Heating Logic

The system selects two cheapest non-consecutive hours between 21:00-07:00:
- Hours must not be adjacent (no back-to-back heating)
- This allows radiator heating to run between pool heating cycles
- Prices are analyzed when tomorrow's Nordpool prices become available (~13:00)

## License

Private project for personal use.
