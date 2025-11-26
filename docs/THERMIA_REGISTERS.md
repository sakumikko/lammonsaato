# Thermia Heat Pump Modbus Registers

Reference documentation for Thermia Mega heat pump Modbus TCP communication.

## Connection Details

- **Protocol**: Modbus TCP
- **Default Port**: 502
- **Default IP**: 192.168.50.10 (check your installation)

## Register Types

| Type | Modbus Function | Description |
|------|----------------|-------------|
| Input Register | 0x04 | Read-only sensor values |
| Holding Register | 0x03 | Read/write configuration |
| Coil | 0x01/0x05 | Boolean on/off controls |

## Key Input Registers (Read-Only)

Based on `pythermiagenesis` library:

| Address | Name | Unit | Scale | Description |
|---------|------|------|-------|-------------|
| 0 | outdoor_temperature | °C | 0.01 | Outside air temperature |
| 1 | supply_line_temperature | °C | 0.01 | Water temp to heating system |
| 2 | return_line_temperature | °C | 0.01 | Water temp from heating system |
| 3 | brine_in_temperature | °C | 0.01 | Ground loop incoming |
| 4 | brine_out_temperature | °C | 0.01 | Ground loop outgoing |
| 5 | hot_water_top | °C | 0.01 | DHW tank top sensor |
| 6 | hot_water_bottom | °C | 0.01 | DHW tank bottom sensor |
| 10 | compressor_speed | % | 1 | Current compressor speed |
| 15 | current_power | W | 1 | Current power consumption |

## Key Holding Registers (Read/Write)

| Address | Name | Unit | Description |
|---------|------|------|-------------|
| 100 | target_supply_temp | °C | Target supply temperature |
| 101 | target_hot_water | °C | Target DHW temperature |
| 110 | heating_curve | - | Heating curve setting |

## Coils (Boolean Controls)

| Address | Name | Description |
|---------|------|-------------|
| 0 | enable_heat | Enable/disable heating |
| 1 | enable_hot_water | Enable/disable DHW |
| 10 | aux_heater_enable | Enable auxiliary heater |

## Registers for Pool Heating Monitoring

For calculating energy transfer to pool:

### Required Readings:
1. **Supply Temperature** - Water going to heat exchanger
2. **Return Temperature** - Water coming back from heat exchanger
3. **Flow Rate** - If available, or estimate from pump specs

### Energy Calculation:
```
Q (kW) = flow_rate (l/s) × ΔT (°C) × 4.186 (specific heat)
```

Where:
- ΔT = Supply Temperature - Return Temperature
- flow_rate depends on circulation pump

## Testing Connection

```python
from pythermiagenesis import ThermiaGenesis
import asyncio

async def read_registers():
    thermia = ThermiaGenesis("192.168.50.10", port=502, kind="mega")
    await thermia.async_update()

    print(f"Outdoor: {thermia.data.get('outdoor_temperature')}°C")
    print(f"Supply: {thermia.data.get('supply_line_temperature')}°C")
    print(f"Return: {thermia.data.get('return_line_temperature')}°C")

asyncio.run(read_registers())
```

## Notes

- Register addresses may vary by firmware version
- Always verify addresses against your specific model
- Scale factors convert raw register values to engineering units
- Some registers require specific access permissions

## References

- [pythermiagenesis GitHub](https://github.com/CJNE/pythermiagenesis)
- Thermia Mega Installation Manual (contact dealer)
- Modbus TCP/IP Specification
