# Lämmönsäätö UI

Real-time heat flow visualization for the pool heating optimization system. Runs as a Home Assistant add-on.

## Features

- Live system diagram showing heat pump, ground loop, pool, and radiators
- Real-time temperature readings from Thermia Genesis heat pump
- Pool heating controls (enable/disable, target temperature)
- Electricity price schedule display
- Connection status indicator

## Architecture

```
┌─────────────────────────────────────────────┐
│              Home Assistant                  │
│  ┌─────────────────────────────────────────┐│
│  │         Lämmönsäätö Add-on              ││
│  │  ┌─────────────┐  ┌─────────────────┐   ││
│  │  │   nginx     │  │   React App     │   ││
│  │  │   :8099     │──│   (SPA)         │   ││
│  │  └──────┬──────┘  └─────────────────┘   ││
│  │         │                                ││
│  │         │ WebSocket                      ││
│  │         ▼                                ││
│  │  ┌─────────────────────────────────┐    ││
│  │  │    HA WebSocket API             │    ││
│  │  │    /api/websocket               │    ││
│  │  └─────────────────────────────────┘    ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

## Development

### Prerequisites

- Node.js 18+
- npm
- Access to Home Assistant with long-lived access token

### Setup

```bash
# Install dependencies
npm install

# Copy environment template
cp .env.example .env.local

# Edit .env.local with your HA details
# VITE_HA_URL=http://your-ha-ip:8123
# VITE_HA_TOKEN=your_long_lived_token

# Start development server
npm run dev
```

The app will be available at http://localhost:8080

### Building

```bash
# Build for production
npm run build

# Build add-on package
./build-addon.sh
```

## Installation as HA Add-on

1. Build the add-on:
   ```bash
   ./build-addon.sh
   ```

2. Copy the `addon/` directory to your Home Assistant config:
   ```bash
   scp -r addon/ user@homeassistant:/config/addons/lammonsaato-ui/
   ```

3. In Home Assistant:
   - Go to **Settings → Add-ons → Add-on Store**
   - Click the three-dot menu → **Check for updates**
   - Find "Lämmönsäätö UI" in Local add-ons
   - Click Install

4. Start the add-on and enable "Show in sidebar"

## Entity Mappings

The UI connects to these Home Assistant entities:

### Heat Pump (Thermia Genesis)
| UI Field | Entity |
|----------|--------|
| Condenser Out | `sensor.condenser_out_temperature` |
| Condenser In | `sensor.condenser_in_temperature` |
| Brine In | `sensor.brine_in_temperature` |
| Brine Out | `sensor.brine_out_temperature` |
| Compressor RPM | `sensor.compressor_speed` |
| Brine Pump | `sensor.brine_circulation_pump_speed` |
| Outdoor Temp | `sensor.outdoor_temperature` |

### Pool Heating
| UI Field | Entity |
|----------|--------|
| Enabled | `input_boolean.pool_heating_enabled` |
| Active | `binary_sensor.pool_heating_active` |
| Target Temp | `input_number.pool_target_temperature` |
| Delta T | `sensor.pool_heat_exchanger_delta_t` |
| Power | `sensor.pool_heating_electrical_power` |
| Daily Electricity | `sensor.pool_heating_electricity_daily` |
| Daily Cost | `sensor.pool_heating_cost_daily` |

### Valve Control (Shelly)
| UI Field | Entity |
|----------|--------|
| Position | `switch.altaan_lammityksen_esto` (inverted) |
| | `switch.altaan_kiertovesipumppu` |

### Schedule
| UI Field | Entity |
|----------|--------|
| Current Price | `sensor.nordpool_kwh_fi_eur_3_10_0255` |
| Prices Available | `binary_sensor.nordpool_tomorrow_available` |
| Block N Start | `input_datetime.pool_heat_block_N_start` |
| Block N End | `input_datetime.pool_heat_block_N_end` |
| Block N Price | `input_number.pool_heat_block_N_price` |

## Tech Stack

- React 18
- TypeScript
- Tailwind CSS
- shadcn/ui components
- Vite build tool
- Home Assistant WebSocket API
