# Setup Guide - Pool Heating Optimizer

Complete installation and verification guide for the Lammonsaato pool heating system.

## Overview

This system optimizes pool heating by:
- Fetching electricity prices from Nordpool (15-minute intervals)
- Scheduling 2 hours of heating during the cheapest night hours (21:00-07:00)
- Using 30-45 minute heating blocks with equal breaks between them
- Controlling the pool via two Shelly switches

## Prerequisites

- Home Assistant OS (tested on Raspberry Pi)
- Network access to Thermia heat pump (Modbus TCP on port 502)
- Two Shelly switches configured:
  - **Heating Prevention** (`switch.altaan_lammityksen_esto`) - OFF to allow heating
  - **Circulation Pump** (`switch.altaan_kiertovesipumppu`) - ON when heating
- Local storage for session logs (uses `/config/pool_heating_logs/`)

---

## Step 1: Install Required Integrations

### 1.1 Install HACS (if not installed)

HACS is required for Nordpool and Pyscript integrations.

1. Follow [HACS Installation Guide](https://hacs.xyz/docs/setup/download)
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration > HACS

### 1.2 Nordpool Integration (HACS)

1. Go to HACS > Integrations > Explore & Download
2. Search for "Nordpool"
3. Click Download, then Restart Home Assistant

4. Configure Nordpool:
   - Go to Settings > Devices & Services > Add Integration
   - Search for "Nordpool"
   - Configure:
     - **Region**: FI (Finland)
     - **Currency**: EUR
     - **Include VAT**: Yes (if applicable)
     - **Precision**: 3

5. Verify sensor exists (your entity ID may vary, e.g., `sensor.nordpool_kwh_fi_eur_3_10_0255`)

### 1.3 Pyscript Integration (HACS)

1. In HACS > Integrations, search for "Pyscript"
2. Download and restart Home Assistant
3. Add to `/config/configuration.yaml`:
   ```yaml
   pyscript:
     allow_all_imports: true
     hass_is_global: true
   ```
4. Restart Home Assistant again

### 1.4 Shelly Integration (Built-in)

1. Ensure both Shelly devices are on your network
2. Go to Settings > Devices & Services
3. Shelly devices should auto-discover
4. If not, click Add Integration > Shelly > Enter IP address
5. Note down the entity IDs:
   - `switch.altaan_lammityksen_esto` (heating prevention)
   - `switch.altaan_kiertovesipumppu` (circulation pump)

---

## Step 2: Build and Deploy

### 2.1 Build Distribution Package

On your development machine:

```bash
cd lammonsaato
make build
```

This creates the `dist/` folder with all necessary files.

### 2.2 Deploy to Home Assistant

**Option A: Using SCP (SSH)**
```bash
# Copy files to Home Assistant
scp -r dist/* root@homeassistant.local:/config/

# Or use the install script on HA
scp -r dist/* root@homeassistant.local:/tmp/lammonsaato/
ssh root@homeassistant.local "cd /tmp/lammonsaato && ./install.sh"
```

**Option B: Using File Editor Add-on**
1. Install "File Editor" from Add-on Store
2. Create directories:
   - `/config/packages/`
   - `/config/pyscript/`
3. Upload files manually from `dist/`

**Option C: Using Samba Share**
1. Install "Samba share" from Add-on Store
2. Access `\\homeassistant.local\config` from your computer
3. Copy files from `dist/` to appropriate folders

### 2.3 Enable Packages

Add to `/config/configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

---

## Step 3: Configure Secrets

Add to `/config/secrets.yaml`:

```yaml
# Thermia Heat Pump (configured via Thermia Genesis integration)
thermia_host: "192.168.X.X"    # Your Thermia IP
thermia_port: 502
```

Note: Session logs are stored locally in `/config/pool_heating_logs/` - no external database required.

---

## Step 4: Restart and Verify Installation

### 4.1 Restart Home Assistant

Go to Settings > System > Restart

### 4.2 Check for Errors

Go to Settings > System > Logs and look for:
- Pyscript loading errors
- YAML syntax errors
- Modbus connection errors

### 4.3 Verify Entities Created

Go to Developer Tools > States and search for:

**Input Helpers (should exist):**
- `input_boolean.pool_heating_enabled`
- `input_datetime.pool_heat_block_1_start`
- `input_datetime.pool_heat_block_1_end`
- `input_datetime.pool_heat_block_2_start`
- ... (blocks 1-4)
- `input_number.pool_heat_block_1_price`
- ... (prices 1-4)
- `input_text.pool_heating_schedule_info`

**Sensors (should show values):**
- `sensor.nordpool_kwh_fi_eur_3_10_0255` (your ID may vary)
- `sensor.condenser_out_temperature` (from Thermia Genesis)
- `sensor.condenser_in_temperature` (from Thermia Genesis)
- `sensor.pool_heat_exchanger_delta_t`

**Switches (should be controllable):**
- `switch.altaan_lammityksen_esto`
- `switch.altaan_kiertovesipumppu`

---

## Step 5: Test Components

### 5.1 Test from Development Machine

```bash
cd lammonsaato

# Run all unit tests
make test

# Test connection to Home Assistant
make test-ha

# Test Thermia Modbus connection
make test-thermia

# Test Nordpool API
make test-nordpool

# Full integration test
make test-integration
```

### 5.2 Test Schedule Calculation

In Home Assistant, go to Developer Tools > Services:

1. Call service: `pyscript.calculate_pool_heating_schedule`
2. No parameters needed
3. Check that `input_text.pool_heating_schedule_info` updates
4. Check that block datetime entities are populated

### 5.3 Test Switch Control (DRY RUN)

From development machine:
```bash
make test-ha-workflow
```

This tests the workflow without actually controlling switches.

### 5.4 Test Switch Control (LIVE)

**WARNING: This will actually turn switches on/off!**

```bash
make test-ha-workflow-live
```

Or manually in Home Assistant:

1. Go to Developer Tools > Services
2. Test heating START sequence:
   - Call `switch.turn_off` for `switch.altaan_lammityksen_esto`
   - Call `switch.turn_on` for `switch.altaan_kiertovesipumppu`
3. Verify `binary_sensor.pool_heating_active` shows `on`
4. Test heating STOP sequence:
   - Call `switch.turn_on` for `switch.altaan_lammityksen_esto`
   - Call `switch.turn_off` for `switch.altaan_kiertovesipumppu`
5. Verify `binary_sensor.pool_heating_active` shows `off`

---

## Step 6: Install Web UI Add-on (Optional)

The web-ui provides a real-time visualization of the heating system with live temperature readings, valve control, and schedule display.

### 6.1 Build the Add-on

On your development machine:

```bash
cd lammonsaato/web-ui

# Install dependencies
npm install

# Build the add-on
./build-addon.sh
```

### 6.2 Enable SSH Access

Local add-ons require SSH access to Home Assistant OS:

1. Go to **Settings → Add-ons → Add-on Store**
2. Search for **"Terminal & SSH"** (or "Advanced SSH & Web Terminal")
3. Install and configure with a password or authorized_keys
4. Start the add-on

### 6.3 Deploy to Home Assistant

**For Home Assistant OS:**

```bash
# The /addons folder is at root level (not in /config)
# First, create the directory
ssh root@homeassistant.local "mkdir -p /addons/lammonsaato-ui"

# Copy the add-on files
scp -r addon/* root@homeassistant.local:/addons/lammonsaato-ui/
```

**Alternative: Using Samba add-on:**

1. Install "Samba share" add-on
2. Access `\\homeassistant.local\addons` from your computer
3. Create folder `lammonsaato-ui`
4. Copy contents of `addon/` folder into it

### 6.4 Install the Add-on

1. Go to **Settings → Add-ons → Add-on Store**
2. Click the **three-dot menu** (top right) → **Check for updates**
3. Scroll down - you should see **"Local add-ons"** section
4. Find **"Lämmönsäätö UI"** and click it
5. Click **Install**
6. After installation, enable **"Show in sidebar"**
7. Click **Start**

**Troubleshooting: "Local add-ons" not appearing:**
- Ensure files are in `/addons/lammonsaato-ui/` (not `/config/addons/`)
- Verify `config.yaml` exists in the add-on folder
- Try restarting Home Assistant
- Check **Settings → System → Logs** for add-on errors

The UI will be accessible from the sidebar.

### 6.5 Development Mode (Optional)

To run the UI locally and connect to Home Assistant for testing:

```bash
cd lammonsaato/web-ui

# Create local environment file
cp .env.example .env.local

# Edit .env.local with your HA details:
# VITE_HA_URL=http://192.168.x.x:8123
# VITE_HA_TOKEN=your_long_lived_access_token

# Start development server
npm run dev
```

Create a long-lived access token in HA: **Profile → Security → Long-Lived Access Tokens → Create Token**

---

## Step 7: Configure Dashboard

### 7.1 Set 24-Hour Time Format

Home Assistant defaults to 12-hour AM/PM time format. To use 24-hour format:

1. Click your **username** (bottom left corner of HA)
2. Scroll to **"Time format"** under "Language & Region"
3. Change from "Auto" to **"24 hours"**

This displays all times as `00:45`, `13:30` instead of `12:45 AM`, `1:30 PM`.

### 6.2 Add Pool Heating Dashboard Card

For a properly organized dashboard with blocks in logical order (Start → End → Price):

1. Go to **Overview** dashboard
2. Click **three dots** (top right) → **Edit Dashboard**
3. Click **+ Add Card**
4. Choose **Manual** (at the bottom of card list)
5. Paste the contents from `homeassistant/lovelace/pool_heating_card.yaml`
6. Click **Save**

The card displays:
- Master enable switch
- Blocks 1-4 each with Start, End, Price in order
- Status section with current heating state and next scheduled time

### 6.3 Prevent Accidental Integration Disable

The auto-generated dashboard shows toggle switches for integrations like "Pannuhuone" (Thermia). If accidentally disabled, all Thermia sensors stop updating.

**To prevent this:**

1. **Take control of the dashboard:**
   - Go to **Overview** dashboard
   - Click **three dots** (top right) → **Edit Dashboard**
   - When prompted "Take control?", click **Take control**
   - This converts from auto-generated to manual dashboard

2. **Remove or hide the integration toggle:**
   - Find the Thermia/Pannuhuone card
   - Edit or delete the master toggle entity
   - Keep only the sensor entities you want to display

3. **Add an auto-recovery automation** (included in pool_heating.yaml):
   - The package includes `thermia_auto_recovery` automation
   - If Thermia sensors go stale, it reloads the integration automatically

### 6.4 Thermia Integration Stability (Known Issue)

The `thermiagenesis` integration has a known bug where Modbus polling stops after some idle time, causing sensors to freeze. This is **not** a recorder issue - the integration stops updating.

**Symptoms:**
- Thermia sensor values show flat line in history
- `last_updated` timestamp is hours old
- Log shows: `Updating thermiagenesis number took longer than scheduled update interval`

**Solution:** The pool_heating.yaml package includes two automations:
1. **Hourly reload** (`thermia_hourly_reload`) - Reloads Thermia integration every hour to prevent freezing
2. **Stale sensor recovery** (`thermia_stale_recovery`) - Reloads if sensors haven't updated in 10 minutes

**REQUIRED: Configure your Thermia entry ID:**

The automations need your specific Thermia config entry ID to work:

1. Go to **Settings > Devices & Services**
2. Click on your **Thermia** integration (may be called "Pannuhuone" or similar)
3. Look at the browser URL bar - it will show something like:
   ```
   /config/integrations/integration/thermiagenesis#config_entry-abc123def456
   ```
4. Copy the entry ID part (e.g., `abc123def456`)
5. Edit `pool_heating.yaml` and replace **both** occurrences of:
   ```yaml
   entry_id: "YOUR_THERMIA_ENTRY_ID_HERE"
   ```
   with your actual entry ID:
   ```yaml
   entry_id: "abc123def456"
   ```
6. Copy updated file to Home Assistant and restart

**Verify automations are working:**
- Go to **Settings > Automations & Scenes**
- Find "Thermia: Hourly Reload" and "Thermia: Stale Sensor Recovery"
- Both should be enabled (toggle ON)

---

## Step 8: Enable Production Mode

### 8.1 Verify Automations Exist

Go to Settings > Automations & Scenes and verify these exist:
- Pool: Calculate Heating Schedule
- Pool: Start Heating Block 1
- Pool: Start Heating Block 2
- Pool: Start Heating Block 3
- Pool: Start Heating Block 4
- Pool: Stop Heating Block 1
- Pool: Stop Heating Block 2
- Pool: Stop Heating Block 3
- Pool: Stop Heating Block 4
- Pool: Log Temperatures During Heating

### 8.2 Enable Master Switch

Turn on the master enable switch:
- Go to Settings > Devices & Services > Helpers
- Find `input_boolean.pool_heating_enabled`
- Turn it ON

Or via Developer Tools > States:
- Find `input_boolean.pool_heating_enabled`
- Set state to `on`

### 8.3 Wait for Schedule Calculation

The schedule will be calculated automatically when:
- Tomorrow's Nordpool prices become available (~13:00 CET)
- The `binary_sensor.nordpool_tomorrow_available` turns `on`

Or manually trigger:
- Developer Tools > Services > `pyscript.calculate_pool_heating_schedule`

---

## Step 9: Monitor First Night

### 9.1 Check Schedule

After prices are available, verify:
- `input_text.pool_heating_schedule_info` shows scheduled blocks
- `input_datetime.pool_heat_block_*_start/end` have valid times
- `input_number.pool_heat_block_*_price` show prices

### 9.2 Monitor Execution

During the night, monitor:
- `binary_sensor.pool_heating_active` - should turn on/off with blocks
- `sensor.condenser_out_temperature` - should rise when heating
- `sensor.pool_heat_exchanger_delta_t` - temperature difference

### 9.3 Check Logs

After first night, check:
- Settings > System > Logs for any errors
- Logbook for Pool Heating entries

---

## Verification Checklist

### Pre-deployment
- [ ] `make test` passes all 35 tests
- [ ] `make test-ha` connects successfully
- [ ] `make test-thermia` reads temperatures

### Post-deployment
- [ ] No errors in HA logs after restart
- [ ] All input helpers created
- [ ] Nordpool sensor shows prices
- [ ] Thermia sensors show temperatures
- [ ] Both Shelly switches controllable
- [ ] `pyscript.calculate_pool_heating_schedule` works
- [ ] Schedule info text updates with block times

### Production
- [ ] `input_boolean.pool_heating_enabled` is ON
- [ ] Schedule auto-calculates when tomorrow prices available
- [ ] Heating blocks execute at scheduled times
- [ ] `binary_sensor.pool_heating_active` reflects actual state

---

## File Locations Reference

| File | Home Assistant Location |
|------|------------------------|
| Main config | `/config/configuration.yaml` |
| Pool heating package | `/config/packages/pool_heating.yaml` |
| Pyscript optimizer | `/config/pyscript/pool_heating.py` |
| Pyscript logging | `/config/pyscript/firebase_sync.py` |
| Secrets | `/config/secrets.yaml` |
| Web UI add-on | `/addons/lammonsaato-ui/` |

---

## Troubleshooting

### Automations not triggering
1. Check `input_boolean.pool_heating_enabled` is ON
2. Check automation conditions in Settings > Automations
3. Check HA logs for errors

### Schedule not calculating
1. Verify Nordpool sensor has `tomorrow_valid: true`
2. Manually call `pyscript.calculate_pool_heating_schedule`
3. Check pyscript logs in HA

### Switches not responding
1. Test switches directly in Developer Tools > Services
2. Check Shelly device is online in Shelly app
3. Verify entity IDs match configuration

### Thermia not connecting
1. Verify IP address and port 502
2. Test with `make test-thermia`
3. Check firewall settings

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more detailed solutions.

---

## Quick Reference

### Start Heating Manually
```yaml
service: script.pool_heating_manual_start
```
Runs heating for 30 minutes.

### Emergency Stop
```yaml
service: script.pool_heating_stop
```
Immediately stops all heating.

### Force Schedule Recalculation
```yaml
service: pyscript.calculate_pool_heating_schedule
```

### Check Current Schedule
Look at `input_text.pool_heating_schedule_info` state.
