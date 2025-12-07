# Deployment Steps

## Prerequisites

- Home Assistant with pyscript integration installed
- Web server for hosting the UI (or HA ingress)

## 0. Run tests (recommended)

```bash
./env/bin/python -m pytest tests/ -v
```

All 61 tests should pass.

## 1. Copy pool_heating.yaml to Home Assistant

```bash
scp homeassistant/packages/pool_heating.yaml 192.168.50.11:/config/packages/
```

## 2. Copy pool_heating.py pyscript

```bash
scp scripts/pyscript/pool_heating.py 192.168.50.11:/config/pyscript/
```

## 3. Reload Home Assistant configuration

1. Developer Tools → YAML → Check Configuration
2. Reload the following:
   - Template entities
   - Automations
   - Utility Meters
3. Developer Tools → YAML → Reload Pyscript

## 4. Run backfill service (one-time)

Populate historical night summaries from existing sensor data:

1. Developer Tools → Services
2. Service: `pyscript.backfill_night_summaries`
3. Data:
   ```yaml
   days: 7
   ```
4. Check logs for progress: Developer Tools → Logs

## 5. Build and deploy web UI

```bash
cd web-ui
npm run build
ssh 192.168.50.11 "mkdir -p /addons/lammonsaato-ui/dist"
scp -r dist/* 192.168.50.11:/addons/lammonsaato-ui/dist/
```

Then rebuild the addon in HA: Settings → Add-ons → Lämmönsäätö UI → Rebuild

## 6. Verify deployment

- Open the web UI
- Check Analytics tab shows historical data
- Verify new entities exist in HA:
  - `sensor.pool_heating_15min_energy`
  - `sensor.pool_heating_session`
  - `sensor.pool_heating_night_summary`

## New Entities Created

| Entity | Description |
|--------|-------------|
| `sensor.pool_heating_15min_energy` | Energy per 15-min Nordpool period |
| `sensor.pool_heating_session` | Per-block heating stats |
| `sensor.pool_heating_night_summary` | Nightly aggregated stats (21:00-07:00) |

## Configuration Changes

- Utility meters now reset at 07:00 instead of midnight
- New automation: `pool_night_summary` runs at 07:00 daily
- Recorder includes new analytics entities
- **Post-heating mixing:** Circulation runs 15 minutes after heating stops to mix water before measuring final pool temperature

## Session Logging Flow

When a heating block ends, the following sequence runs:

1. **Heating stops** → `pyscript.log_heating_end` called immediately
   - Captures accurate heating duration
   - Calculates energy based on actual heating time
   - Records initial pool temp (near heat exchanger output)

2. **15-minute mixing** → circulation pump continues running
   - Mixes heated water throughout pool

3. **After mixing** → `pyscript.log_session_final_temp` called
   - Updates `pool_temp_end` with true mixed pool temperature
   - Sets `pool_temp_mixed: true` flag
   - Stops circulation pump

This ensures energy calculations use actual heating duration, while pool temperature reflects the whole pool (not just near output).

## New Pyscript Services

| Service | Description |
|---------|-------------|
| `pyscript.calculate_pool_heating_schedule` | Calculate optimal heating blocks from Nordpool prices |
| `pyscript.log_heating_start` | Log start of heating session |
| `pyscript.log_heating_end` | Log end of heating (energy, duration) |
| `pyscript.log_session_final_temp` | Update final pool temp after mixing |
| `pyscript.calculate_night_summary` | Aggregate night's heating data (runs at 07:00) |
| `pyscript.backfill_night_summaries` | Backfill historical data (one-time) |


⏺ Bash(./env/bin/python scripts/standalone/backfill_night_summaries.py findings/home-assistant_v2.db)
  ⎿  Opening database: findings/home-assistant_v2.db
     Found 5 days with data
     States metadata_id for sensor.pool_heating_night_summary: 101
     … +53 lines (ctrl+o to expand)

⏺ Bash(sqlite3 findings/home-assistant_v2.db "
      SELECT…)
  ⎿  2025-12-02 07:00:00|2.504|2025-12-01|0.1357|0.1147
     2025-12-03 07:00:00|6.849|2025-12-02|0.4422|0.2427
     2025-12-04 07:00:00|9.795|2025-12-03|0.0875|0.892
     … +2 lines (ctrl+o to expand)

⏺ Data inserted successfully. Deployment steps:

  # 1. Stop Home Assistant first (required - DB is locked while running)
  ssh root@192.168.50.11 "ha core stop"

  # 2. Backup original DB (just in case)
  ssh root@192.168.50.11 "cp /config/home-assistant_v2.db /config/home-assistant_v2.db.backup"

  # 3. Copy modified DB
  scp findings/home-assistant_v2.db root@192.168.50.11:/config/

  # 4. Start Home Assistant
  ssh root@192.168.50.11 "ha core start"

  Then verify in HA: Developer Tools → States → search night_summary

  You should see 5 historical entries with heating dates Dec 1-5.
