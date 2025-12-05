# Thermia Temperature Protection System

This document describes the temperature monitoring and protection features for the Thermia Mega heat pump, designed to prevent compressor damage during extreme weather conditions.

## Problem Overview

When outdoor temperatures drop significantly (below -10°C), the heat pump experiences:

1. **Higher Compression Ratios** - Colder air means lower suction pressure, forcing the compressor to work harder
2. **Elevated Discharge Temperatures** - Higher compression = higher hot gas temperatures
3. **Increased Stress on Components** - Risk of compressor overheating and premature wear

### Safe Operating Ranges

| Temperature | Status | Action |
|-------------|--------|--------|
| < 85°C | Normal | No action needed |
| 85-100°C | Elevated | Monitor closely |
| 100-110°C | Warning | Reduce compressor gear |
| > 110°C | Critical | Emergency gear reduction |
| > 120°C | Danger | Risk of compressor damage |

**Rule of thumb**: Discharge temperature ≈ Outdoor temperature + 100°C under normal load.

## Available Controls

### Web UI Settings

Access via the Settings (gear) icon in the header:

#### Hot Gas Protection
- **HGW Pump Start** (50-100°C): Temperature at which hot gas water pump activates
- **Lower Stop Limit** (40-90°C): Lower threshold for HGW pump stop
- **Upper Stop Limit** (70-120°C): Upper threshold for HGW pump stop

#### Tap Water Settings
- **Start Temperature** (35-55°C): When to start heating DHW tank
- **Stop Temperature** (40-65°C): When to stop heating DHW tank

#### Heating Curve Limits
- **Maximum Supply Temp** (35-65°C): Upper limit for heating supply temperature
- **Minimum Supply Temp** (15-40°C): Lower limit for heating supply temperature

#### Compressor Gear Limits
- **Heating Circuit**: Min/Max gear (1-10) for space heating
- **Pool Circuit**: Min/Max gear (1-10) for pool heating
- **Tap Water Circuit**: Min/Max gear (1-10) for DHW

### Temperature Chart

The settings panel includes a real-time temperature chart showing:
- **Hot Gas (Discharge)** - Red/orange line with warning zones
- **Outdoor Temperature** - Blue line
- **Tap Water** - Teal line

Warning and danger zones are highlighted on the chart.

## Automated Protection (Home Assistant)

The `thermia_protection.yaml` package provides automatic protection:

### Automations

| Automation | Trigger | Action |
|------------|---------|--------|
| `thermia_high_discharge_temp_reduce_gear` | Discharge > 100°C for 2 min | Reduce max heating gear by 1 |
| `thermia_critical_discharge_temp` | Discharge > 110°C | Limit all gears to 5 |
| `thermia_restore_gear_limits` | Discharge < 85°C for 10 min | Restore max gears to 9 |
| `thermia_cold_weather_tap_water` | Outdoor < -15°C + High discharge | Reduce tap water to 50°C |
| `thermia_restore_tap_water` | Outdoor > -10°C for 30 min | Restore tap water to 55°C |

### Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.thermia_discharge_outdoor_delta` | Temperature difference between discharge and outdoor |
| `binary_sensor.thermia_discharge_temp_warning` | ON when discharge > 100°C |
| `binary_sensor.thermia_discharge_temp_critical` | ON when discharge > 110°C |
| `binary_sensor.thermia_cold_weather_mode` | ON when outdoor < -15°C |

## Installation

### 1. Enable Required Entities

In Home Assistant, go to **Settings → Devices → Thermia Genesis** and enable:

- `sensor.discharge_pipe_temperature`
- `sensor.suction_gas_temperature`
- `sensor.liquid_line_temperature`
- `sensor.tap_water_top_temperature`
- `sensor.tap_water_lower_temperature`
- `sensor.tap_water_weighted_temperature`
- `number.tap_water_start_temperature`
- `number.tap_water_stop_temperature`
- `number.hot_gas_pump_start_temperature`
- `number.hot_gas_pump_lower_stop_limit`
- `number.hot_gas_pump_upper_stop_limit`
- `number.heat_curve_max_limitation`
- `number.heat_curve_min_limitation`

### 2. Add Protection Package

Copy `homeassistant/packages/thermia_protection.yaml` to your Home Assistant config:

```bash
cp thermia_protection.yaml /config/packages/
```

Add to `configuration.yaml` if not already configured:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

### 3. Restart Home Assistant

Restart to load the new package and automations.

## Troubleshooting

### High Discharge Temperature

**Symptoms**: Discharge > 100°C during cold weather

**Possible Causes**:
1. Outdoor temperature very low (< -15°C)
2. High demand (heating + DHW simultaneously)
3. Heating curve set too steep
4. Blocked filters or restricted airflow

**Solutions**:
1. Reduce max gear limits temporarily
2. Lower tap water target temperature
3. Flatten heating curve
4. Check and clean filters

### Temperature Fluctuations

**Symptoms**: Rapid temperature swings

**Possible Causes**:
1. Cycling between heating modes
2. Short cycling due to oversized equipment
3. Incorrect heating curve

**Solutions**:
1. Adjust min/max gear ranges
2. Review heating curve settings
3. Increase hysteresis settings if available

## Thermia Modbus Registers Reference

| Register | Address | Type | Description |
|----------|---------|------|-------------|
| Discharge Pipe Temp | 7 | Input | Hot gas temperature (÷100) |
| Suction Gas Temp | 130 | Input | Compressor inlet temp (÷100) |
| Liquid Line Temp | 129 | Input | After condenser (÷100) |
| Tap Water Top | 15 | Input | DHW tank top (÷100) |
| Tap Water Lower | 16 | Input | DHW tank bottom (÷100) |
| Tap Water Weighted | 17 | Input | Calculated DHW temp (÷100) |
| Tap Water Start | 22 | Holding | DHW heating start (÷100) |
| Tap Water Stop | 23 | Holding | DHW heating stop (÷100) |
| HGW Pump Start | 99 | Holding | Hot gas pump start (÷100) |
| HGW Lower Stop | 100 | Holding | Hot gas pump lower limit (÷100) |
| HGW Upper Stop | 101 | Holding | Hot gas pump upper limit (÷100) |
| Heat Curve Max | 3 | Holding | Max supply temp limit (÷100) |
| Heat Curve Min | 4 | Holding | Min supply temp limit (÷100) |

## Further Reading

- [pythermiagenesis GitHub](https://github.com/CJNE/pythermiagenesis)
- [thermiagenesis Home Assistant integration](https://github.com/CJNE/thermiagenesis)
- [Thermia Modbus Protocol PDF](https://www.thermia.fi/media/70526/protocol_doc-00079973.pdf)
- [Understanding Heat Curves](https://www.imsheatpumps.co.uk/blog/understanding-your-heat-curve/)
