# Implementation Plan 01: HA Entities & YAML Configuration

**Depends on:** Nothing (first task)
**Findings source:** Reviews 02, 04

## Goal

Add new HA entities for cold weather mode and modify block start/stop scripts to use `choose` conditionals. No Python or UI changes in this plan.

## New Entities to Add (pool_heating.yaml)

Add these in the `input_boolean:` and `input_number:` sections alongside existing entities:

```yaml
input_boolean:
  pool_heating_cold_weather_mode:
    name: Pool Heating Cold Weather Mode
    icon: mdi:snowflake

input_number:
  pool_heating_cold_block_duration:
    name: Pool Cold Weather Block Duration
    min: 5
    max: 15
    step: 5
    unit_of_measurement: min
    icon: mdi:timer-outline

  pool_heating_cold_pre_circulation:
    name: Pool Cold Weather Pre-Circulation
    min: 0
    max: 10
    step: 1
    unit_of_measurement: min
    icon: mdi:pump

  pool_heating_cold_post_circulation:
    name: Pool Cold Weather Post-Circulation
    min: 0
    max: 10
    step: 1
    unit_of_measurement: min
    icon: mdi:pump
```

**Do NOT modify** existing entities (`pool_heating_min_block_duration`, `pool_heating_max_block_duration`, `pool_heating_total_hours`). They remain unchanged for normal mode.

## Modify script.pool_heating_block_start (pool_heating.yaml:1318)

Replace the sequence with a `choose` conditional:

```yaml
pool_heating_block_start:
  alias: Pool Heating Block Start
  mode: restart    # Important: allow restart if stop triggers during pre-circ
  sequence:
    - choose:
        - conditions:
            - condition: state
              entity_id: input_boolean.pool_heating_cold_weather_mode
              state: "on"
          sequence:
            # COLD WEATHER: simplified sequence
            # 1. Turn on circulation pump (pre-circulation)
            - service: switch.turn_on
              target:
                entity_id: switch.altaan_kiertovesipumppu
            # 2. Wait for pre-circulation (read from entity, template as seconds)
            - delay:
                seconds: >-
                  {{ (states('input_number.pool_heating_cold_pre_circulation') | int(5)) * 60 }}
            # 3. Start heating (prevention OFF)
            - service: switch.turn_off
              target:
                entity_id: switch.altaan_lammityksen_esto
            # 4. Log heating start
            - service: pyscript.log_heating_start
              continue_on_error: true
      default:
        # NORMAL MODE: existing sequence (preserve exactly as-is)
        - service: pyscript.pool_temp_control_preheat
          continue_on_error: true
        - delay:
            minutes: 15
        - service: pyscript.pool_temp_control_start
          continue_on_error: true
        - service: script.pool_heating_switches_on
```

## Modify script.pool_heating_block_stop (pool_heating.yaml:1342)

```yaml
pool_heating_block_stop:
  alias: Pool Heating Block Stop
  sequence:
    - choose:
        - conditions:
            - condition: state
              entity_id: input_boolean.pool_heating_cold_weather_mode
              state: "on"
          sequence:
            # COLD WEATHER: simplified sequence
            # 1. Stop heating (prevention ON)
            - service: switch.turn_on
              target:
                entity_id: switch.altaan_lammityksen_esto
            # 2. Log heating end
            - service: pyscript.log_heating_end
              continue_on_error: true
            # 3. Post-circulation delay (read from entity)
            - delay:
                seconds: >-
                  {{ (states('input_number.pool_heating_cold_post_circulation') | int(5)) * 60 }}
            # 4. Turn off pump
            - service: switch.turn_off
              target:
                entity_id: switch.altaan_kiertovesipumppu
            # 5. Log final temp
            - service: pyscript.log_session_final_temp
              continue_on_error: true
      default:
        # NORMAL MODE: existing sequence (preserve exactly as-is)
        - service: pyscript.pool_temp_control_stop
          continue_on_error: true
        - service: script.pool_heating_switches_off
        - service: pyscript.log_heating_end
          continue_on_error: true
        - delay:
            minutes: 15
        - service: switch.turn_off
          target:
            entity_id: switch.altaan_kiertovesipumppu
        - service: pyscript.log_session_final_temp
          continue_on_error: true
```

## Key design decisions

1. **`mode: restart`** on block_start prevents queue buildup if stop fires during pre-circ delay.
2. **No PID temp control** in cold weather path -- skipped entirely per Review 03 finding.
3. **No preheat** in cold weather path -- overhead exceeds block duration per Review 02 finding.
4. **No compressor gear override** in cold weather path -- can't ramp in 5 min per Review 03 finding.
5. **Pre/post circulation times read from entities** -- user-configurable via UI.
6. **Normal mode default branch** preserves existing behavior exactly. Zero regression risk.

## Verification

After deploying to HA:
1. Set `input_boolean.pool_heating_cold_weather_mode` to ON in Developer Tools
2. Manually run `script.pool_heating_block_start` -- verify pump turns ON, waits, then prevention turns OFF
3. Manually run `script.pool_heating_block_stop` -- verify prevention turns ON, waits, pump turns OFF
4. Set cold weather mode to OFF, repeat -- verify normal sequence runs unchanged
