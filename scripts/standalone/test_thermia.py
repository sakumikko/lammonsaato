from pythermiagenesis import ThermiaGenesis
from pythermiagenesis.const import REGISTERS, KEY_ADDRESS
from pythermiagenesis import ThermiaConnectionError
import asyncio
import logging
from pythermiagenesis.const import REG_INPUT, ATTR_COIL_ENABLE_BRINE_IN_MONITORING, ATTR_COIL_ENABLE_HEAT, ATTR_INPUT_POOL_SUPPLY_LINE_TEMPERATURE, ATTR_INPUT_POOL_RETURN_LINE_TEMPERATURE,ATTR_INPUT_CONDENSER_IN_TEMPERATURE, ATTR_INPUT_CONDENSER_OUT_TEMPERATURE, ATTR_INPUT_SYSTEM_SUPPLY_LINE_TEMPERATURE
from sys import argv
# heatpum IP address/hostname
HOST = "192.168.50.10"
# HOST = "10.0.20.8"
PORT = 502
KIND = "mega"
logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)
THERMIA_KEY_REGISTERS = [
    'input_outdoor_temperature',
    'input_system_supply_line_temperature',
    'input_brine_in_temperature',
    'input_brine_out_temperature',
    'input_compressor_speed_percent',
    'input_compressor_current_gear',
    'input_mix_valve_1_supply_line_temperature',
    # Pool registers (may show raw values if sensors not connected)
    'input_pool_supply_line_temperature',
    'input_pool_return_line_temperature',
    ATTR_INPUT_POOL_SUPPLY_LINE_TEMPERATURE,
    ATTR_INPUT_POOL_RETURN_LINE_TEMPERATURE
    ATTR_INPUT_CONDENSER_IN_TEMPERATURE,
    ATTR_INPUT_CONDENSER_OUT_TEMPERATURE,
    ATTR_INPUT_SYSTEM_SUPPLY_LINE_TEMPERATURE
]

async def main():
    host = argv[1] if len(argv) > 1 else HOST
    port = argv[2] if len(argv) > 2 else PORT
    kind = argv[3] if len(argv) > 3 else KIND

    # argument kind: inverter - for Diplomat Inverter
    #                mega     - for Mega
    thermia = ThermiaGenesis(host, port=port, kind=kind, delay=0.15)
    try:
        #Get all register types
        #await thermia.async_update()
        #Get only input registers
        # await thermia.async_update([REG_INPUT])
        #Get one specific register
        await thermia.async_update(only_registers=THERMIA_KEY_REGISTERS)
        # await thermia.async_update(None)

    except (ThermiaConnectionError) as error:
        print(f"Failed to connect: {error.message}")
        return
    except (ConnectionError) as error:
        print(f"Connection error {error}")
        return

    if thermia.available:
        print(f"Data available: {thermia.available}")
        print(f"Model: {thermia.model}")
        print(f"Firmware: {thermia.firmware}")
        for i, (name, val) in enumerate(thermia.data.items()):
            print(f"{REGISTERS[name][KEY_ADDRESS]}\t{name}\t{val}")

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()