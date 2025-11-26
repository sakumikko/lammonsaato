# Troubleshooting Guide

Common issues and solutions for the Pool Heating Optimizer.

## Connection Issues

### Thermia Heat Pump Not Responding

**Symptoms:**
- Modbus sensors show "unavailable"
- Connection timeout errors

**Solutions:**
1. Verify IP address is correct:
   ```bash
   ping 192.168.50.10
   ```

2. Check Modbus port is open:
   ```bash
   nc -zv 192.168.50.10 502
   ```

3. Verify heat pump has Modbus enabled:
   - Check heat pump settings menu
   - May require enabling TCP server in configuration

4. Check for firewall blocking port 502

5. Test with standalone script:
   ```bash
   python scripts/standalone/test_thermia.py 192.168.50.10
   ```

### Shelly Switch Not Controllable

**Symptoms:**
- Switch entity shows "unavailable"
- Commands don't work

**Solutions:**
1. Check Shelly device is online in Shelly app
2. Verify IP address hasn't changed (use static IP or DHCP reservation)
3. Re-add integration in Home Assistant
4. Check cloud vs local mode settings

## Nordpool Issues

### Tomorrow's Prices Not Available

**Symptoms:**
- `tomorrow_valid` attribute is false after 14:00 CET
- Schedule calculation fails

**Causes:**
- Nordpool API delay (usually available 13:00-14:00 CET)
- Integration needs refresh

**Solutions:**
1. Wait until 14:30 CET
2. Restart Nordpool integration
3. Check Nordpool website directly for issues
4. Verify your region is correctly set (FI for Finland)

### Wrong Prices Displayed

**Solutions:**
1. Verify region setting (FI, not FI-1 etc.)
2. Check VAT setting matches your needs
3. Verify currency (EUR)

## Automation Issues

### Heating Not Starting at Scheduled Time

**Symptoms:**
- Schedule shows correct times
- Shelly doesn't activate

**Check:**
1. `input_boolean.pool_heating_enabled` is ON
2. Automation is enabled (check automation list)
3. Date in schedule is correct (not yesterday)
4. Check automation trace for errors

**Debug steps:**
```yaml
# Add to automation for debugging
action:
  - service: persistent_notification.create
    data:
      title: "Pool Heating Debug"
      message: "Attempting to start heating at {{ now() }}"
```

### Schedule Not Calculated

**Symptoms:**
- Input helpers show old/no times
- Pyscript service not running

**Solutions:**
1. Check pyscript logs:
   - Settings > System > Logs > filter "pyscript"

2. Verify pyscript is loaded:
   - Developer Tools > Services > search "pyscript"

3. Check configuration:
   ```yaml
   pyscript:
     allow_all_imports: true
     hass_is_global: true
   ```

4. Test manually:
   - Developer Tools > Services
   - Call `pyscript.calculate_pool_heating_slots`

## Firebase Issues

### Connection Failed

**Symptoms:**
- sync_to_firebase errors
- No data in Firebase console

**Solutions:**
1. Verify Firebase URL is correct
2. Check service account key is valid
3. Verify database rules allow writes:
   ```json
   {
     "rules": {
       ".read": true,
       ".write": true
     }
   }
   ```
   (Note: Restrict rules for production)

4. Test with standalone script:
   ```bash
   python scripts/standalone/test_firebase.py --test-connection
   ```

### REST API Authentication Fails

**Solutions:**
1. Generate new database secret in Firebase console
2. Check secret is correctly set in configuration
3. Use service account key instead of secret

## Temperature Logging Issues

### Missing or Incorrect Temperature Data

**Symptoms:**
- Delta-T shows 0 or incorrect values
- Temperatures not logged during heating

**Solutions:**
1. Verify Modbus sensors are updating:
   - Check scan_interval is reasonable (60s)
   - Look at sensor history

2. Check template sensor calculation:
   ```yaml
   # In Developer Tools > Template
   {{ states('sensor.thermia_supply_temperature') }}
   {{ states('sensor.thermia_return_temperature') }}
   ```

3. Ensure recorder includes relevant entities

## Performance Issues

### High CPU Usage

**Causes:**
- Too frequent Modbus polling
- Large history database

**Solutions:**
1. Increase scan_interval for Modbus sensors
2. Configure recorder to limit history retention
3. Exclude unnecessary entities from recorder

### Slow Response

**Solutions:**
1. Use local API for Shelly (not cloud)
2. Ensure devices are on same network segment
3. Check Raspberry Pi SD card health

## Logging and Debugging

### Enable Debug Logging

Add to configuration.yaml:
```yaml
logger:
  default: info
  logs:
    custom_components.nordpool: debug
    pymodbus: debug
    homeassistant.components.modbus: debug
    pyscript: debug
```

### View Logs

- Settings > System > Logs
- SSH: `tail -f /config/home-assistant.log`

### Check Entity States

Developer Tools > States > filter by entity name

### Test Services Manually

Developer Tools > Services > select service > fill data > Call Service

## Recovery Procedures

### Factory Reset Heating Schedule

```yaml
# Call these services to reset
service: input_datetime.set_datetime
data:
  entity_id: input_datetime.pool_heat_slot_1
  datetime: "2000-01-01 00:00:00"

service: input_datetime.set_datetime
data:
  entity_id: input_datetime.pool_heat_slot_2
  datetime: "2000-01-01 00:00:00"
```

### Manually Trigger Heating

```yaml
# Direct Shelly control (bypass automation)
service: switch.turn_on
target:
  entity_id: switch.shelly_pool_heating
```

### Force Schedule Recalculation

```yaml
service: pyscript.calculate_pool_heating_slots
```

## Getting Help

1. Check Home Assistant logs first
2. Review automation traces
3. Test with standalone Python scripts
4. File issue with relevant logs at:
   - This project's issue tracker
   - Home Assistant community forums
