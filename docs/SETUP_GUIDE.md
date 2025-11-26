# Setup Guide

## Prerequisites

- Home Assistant OS running on Raspberry Pi
- Network access to Thermia heat pump (Modbus TCP)
- Shelly switch installed and connected to WiFi
- Firebase account (for external data storage)

---

## Step 1: Install Required Integrations

### 1.1 Nordpool Integration (HACS)

1. Install HACS if not already installed:
   - Go to Settings > Add-ons > Add-on Store
   - Search for "HACS" and install

2. Install Nordpool:
   - Go to HACS > Integrations
   - Search for "Nordpool"
   - Click Install
   - Restart Home Assistant

3. Configure Nordpool:
   - Go to Settings > Devices & Services > Add Integration
   - Search for "Nordpool"
   - Configure:
     - Region: FI
     - Currency: EUR
     - Include VAT: Yes
     - Precision: 3

### 1.2 Shelly Integration (Native)

1. Ensure Shelly device is on your network
2. Go to Settings > Devices & Services
3. Shelly should auto-discover, or click Add Integration > Shelly
4. Note the entity names (e.g., `switch.shelly_pool_heating`)

### 1.3 Pyscript Integration (HACS)

1. In HACS, search for "Pyscript"
2. Install and restart Home Assistant
3. Add to configuration.yaml:
   ```yaml
   pyscript:
     allow_all_imports: true
     hass_is_global: true
   ```

### 1.4 Modbus Integration (Native)

Already included in Home Assistant. Configuration in Step 2.

---

## Step 2: Copy Configuration Files

### 2.1 Create Package Directory

```bash
# SSH into your Raspberry Pi or use File Editor add-on
mkdir -p /config/packages
mkdir -p /config/pyscript
```

### 2.2 Enable Packages in configuration.yaml

```yaml
homeassistant:
  packages: !include_dir_named packages
```

### 2.3 Copy Files

Copy the following files from this repository:

| Source | Destination |
|--------|-------------|
| `homeassistant/packages/pool_heating.yaml` | `/config/packages/pool_heating.yaml` |
| `scripts/pyscript/pool_heating.py` | `/config/pyscript/pool_heating.py` |
| `scripts/pyscript/firebase_sync.py` | `/config/pyscript/firebase_sync.py` |

---

## Step 3: Configure Secrets

### 3.1 Add to secrets.yaml

```yaml
# Thermia Heat Pump
thermia_host: "192.168.50.10"
thermia_port: 502

# Shelly
shelly_pool_ip: "192.168.50.XX"

# Firebase
firebase_url: "https://your-project.firebaseio.com"
firebase_api_key: "your-api-key"
```

### 3.2 Firebase Setup

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create new project "lammonsaato"
3. Create Realtime Database (start in test mode)
4. Go to Project Settings > Service Accounts
5. Generate new private key (JSON)
6. Save as `/config/secrets/firebase-key.json`

---

## Step 4: Verify Thermia Connection

### 4.1 Test from Development Machine

```bash
cd lammonsaato
python -m venv env
source env/bin/activate
pip install pythermiagenesis

python test_thermia.py 192.168.50.10
```

### 4.2 Check Modbus Entities

After configuration, verify in Developer Tools > States:
- `sensor.thermia_supply_temperature`
- `sensor.thermia_return_temperature`

---

## Step 5: Verify Nordpool Data

### 5.1 Check Sensor

In Developer Tools > States, find:
- `sensor.nordpool_kwh_fi_eur_3_10_024`

### 5.2 Check Attributes

Click on the sensor and verify attributes:
- `today`: Array of 24 prices
- `tomorrow`: Array of 24 prices (available after ~13:00)
- `tomorrow_valid`: true/false

---

## Step 6: Test Automations

### 6.1 Manual Test

1. Go to Developer Tools > Services
2. Call `pyscript.calculate_heating_slots` with test data
3. Verify input_datetime helpers are updated

### 6.2 Test Shelly Control

1. Go to Developer Tools > Services
2. Call `switch.turn_on` for your Shelly entity
3. Verify it switches on (check with multimeter if needed)

---

## Step 7: Enable Production Mode

### 7.1 Enable Automations

Go to Settings > Automations and enable:
- "Calculate Pool Heating Schedule"
- "Start Pool Heating Slot"
- "Log Heating Session"

### 7.2 Enable Input Boolean

Turn on `input_boolean.pool_heating_enabled`

---

## File Locations Reference

| Purpose | Location in HA |
|---------|----------------|
| Main config | `/config/configuration.yaml` |
| Packages | `/config/packages/*.yaml` |
| Pyscript | `/config/pyscript/*.py` |
| Secrets | `/config/secrets.yaml` |
| Firebase key | `/config/secrets/firebase-key.json` |
| Automations | `/config/automations.yaml` or UI |

---

## Verification Checklist

- [ ] Nordpool sensor shows today's prices
- [ ] Nordpool sensor shows tomorrow's prices (after 13:00)
- [ ] Thermia Modbus sensors show temperatures
- [ ] Shelly switch controllable from HA
- [ ] Pyscript loads without errors
- [ ] Input helpers created and visible
- [ ] Automations appear in automation list
- [ ] Firebase connection works (test with standalone script)

---

## Next Steps

After completing setup:
1. Monitor first automatic schedule calculation
2. Watch first heating cycle
3. Verify data logged to Firebase
4. Check HA logs for any errors

See [Troubleshooting](TROUBLESHOOTING.md) if you encounter issues.
