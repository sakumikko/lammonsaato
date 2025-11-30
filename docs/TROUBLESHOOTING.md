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

5. Test with integration test:
   ```bash
   make test-thermia
   ```

### Thermia Sensors Stop Updating (Flat Line in History)

**Symptoms:**
- Sensor values show flat line in history graph
- `last_updated` timestamp is hours old
- Other HA sensors still updating normally
- Log shows: `Updating thermiagenesis number took longer than scheduled update interval`

**Cause:**
This is a known bug in the `thermiagenesis` integration where Modbus polling stops after some idle time. The recorder is fine - the integration stops fetching new values.

**Solutions:**

1. **Check if integration is disabled:**
   - Go to Settings > Devices & Services
   - Look for Thermia/Pannuhuone integration
   - If there's an OFF toggle, turn it ON
   - **Prevention:** Take control of dashboard to remove the toggle (see Setup Guide 6.3)

2. **Manual reload:**
   - Settings > Devices & Services > Thermia
   - Click three dots > Reload

3. **Automatic reload (recommended):**
   The pool_heating.yaml package includes automations to:
   - Reload the integration every hour
   - Detect stale sensors and reload automatically

   Configure by setting your Thermia `entry_id` in the automations.

4. **Find your Thermia config entry ID:**
   - Go to Settings > Devices & Services
   - Click on Thermia integration
   - Look at browser URL: `.../config_entries/entry/<ENTRY_ID>`
   - Copy the entry ID and update `pool_heating.yaml`

5. **Downgrade thermiagenesis (alternative):**
   If the bug persists, consider rolling back to version 0.0.10:
   - Download older version from GitHub
   - Replace `/config/custom_components/thermiagenesis/`
   - Restart Home Assistant

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

### Nordpool Sensor Entity ID Mismatch

**Symptoms:**
- "Current Nordpool Price" shows 0
- "Nordpool Tomorrow Available" shows Unknown
- Schedule calculation doesn't work
- Nordpool integration works but pool heating doesn't see prices

**Cause:**
The Nordpool integration creates a sensor with a unique ID that may differ from what's configured in the pool heating scripts. The entity ID depends on your Nordpool configuration (region, currency, precision, VAT settings).

**Solution:**
1. Find your actual Nordpool sensor ID:
   - Developer Tools > States > search "nordpool"
   - Note the full entity ID (e.g., `sensor.nordpool_kwh_fi_eur_3_10_0255`)

2. Update the sensor ID in two files:

   **In `/config/pyscript/pool_heating.py`:**
   ```python
   # Find this line near the top and update:
   NORDPOOL_SENSOR = "sensor.nordpool_kwh_fi_eur_3_10_0255"  # Your actual ID
   ```

   **In `/config/packages/pool_heating.yaml`:**
   - Search for the old sensor ID and replace all occurrences
   - There are typically 3 places: current price template, tomorrow_valid template, and automation trigger

3. Restart Home Assistant

**Note:** The Nordpool entity ID may change if you reconfigure the integration. Keep this in mind when troubleshooting price-related issues.

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
   - Call `pyscript.calculate_pool_heating_schedule`

## Local Logging Issues

### Session Logs Not Created

**Symptoms:**
- No files in `/config/pool_heating_logs/`
- Session data not recorded

**Solutions:**
1. Check the logs directory exists:
   ```bash
   ls -la /config/pool_heating_logs/
   ```

2. Verify pyscript has write permissions

3. Check pyscript logs for errors:
   - Settings > System > Logs > filter "pyscript"

4. Test logging manually:
   - Developer Tools > Services
   - Call `pyscript.test_logging`

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
   {{ states('sensor.condenser_out_temperature') }}
   {{ states('sensor.condenser_in_temperature') }}
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
# Call these services to reset all blocks
service: input_datetime.set_datetime
data:
  entity_id: input_datetime.pool_heat_block_1_start
  datetime: "2000-01-01 00:00:00"

# Repeat for blocks 2-4
```

### Manually Trigger Heating

```yaml
# Use the manual start script (runs for 30 minutes)
service: script.pool_heating_manual_start
```

Or direct Shelly control (bypass automation):
```yaml
# Turn OFF prevention + ON circulation pump
service: switch.turn_off
target:
  entity_id: switch.altaan_lammityksen_esto

service: switch.turn_on
target:
  entity_id: switch.altaan_kiertovesipumppu
```

### Force Schedule Recalculation

```yaml
service: pyscript.calculate_pool_heating_schedule
```

## Getting Help

1. Check Home Assistant logs first
2. Review automation traces
3. Test with standalone Python scripts
4. File issue with relevant logs at:
   - This project's issue tracker
   - Home Assistant community forums
