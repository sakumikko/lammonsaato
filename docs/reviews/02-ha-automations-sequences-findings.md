# Review 02 Findings: HA Automations & Block Sequences for Cold Weather Mode

## 1. Current Block Sequence

### Start (`script.pool_heating_block_start`, pool_heating.yaml:1318-1340)

```
T+0:00  preheat: comfort wheel +3C (pool_temp_control.py:425-469)
T+0:00  delay 15 min (pool_heating.yaml:1330)
T+15:00 start temp control: fixed supply mode, min gear 7 (pool_temp_control.py:216-279)
T+15:00 switches_on: prevention OFF, pump ON (pool_heating.yaml:1243-1283)
```

### Stop (`script.pool_heating_block_stop`, pool_heating.yaml:1342-1373)

```
T+0:00  stop temp control: disable fixed supply, restore gear (pool_temp_control.py:282-310)
T+0:00  switches_off: prevention ON (pool_heating.yaml:1285-1299)
T+0:00  log_heating_end
T+0:00  delay 15 min post-mix (pool_heating.yaml:1360)
T+15:00 pump OFF, log_session_final_temp
```

**Total overhead: 15 min preheat + 15 min post-mix = 30 min per block.** For a 5-min block this means 35 min wall-clock -- absurd.

## 2. Proposed Cold Weather Sequence (5-min Blocks)

```
T-5:00  Pump ON (pre-circulation, prevention stays ON)
T+0:00  Prevention OFF, log_heating_start (heat begins)
T+5:00  Prevention ON, log_heating_end (heat stops)
T+10:00 Pump OFF, log_session_final_temp
```

Total per cycle: 15 min (5 pre + 5 heat + 5 post). Fits 1/hour with 45 min idle.

Differences from normal mode: no preheat, no PID temp control, no gear override, pump-only pre-circulation, post-mix 5 min instead of 15.

## 3. Automations to Modify

**No changes needed** to these automations (triggers/conditions unchanged):
- `pool_start_heating_blocks` (pool_heating.yaml:925-978) -- calls script
- `pool_stop_heating_blocks` (pool_heating.yaml:980-1022) -- calls script
- `pool_temp_control_adjust` (pool_temp_control.yaml:177) -- condition checks `pool_temp_control_active`, which stays OFF
- `pool_temp_control_safety_check` (pool_temp_control.yaml:195) -- still useful, 5 checks per block
- `pool_heating_60min_timeout` (pool_temp_control.yaml:209) -- never triggers for 5-min blocks
- `pool_temp_control_preheat_timeout` (pool_temp_control.yaml:259) -- preheat never activated

**Must modify** these scripts with `choose` conditional:

**`script.pool_heating_block_start`** (pool_heating.yaml:1318): Cold weather path skips preheat, 15-min delay, and temp control. Instead: pump ON, wait 5 min pre-circ, then switches_on.

**`script.pool_heating_block_stop`** (pool_heating.yaml:1342): Cold weather path skips temp control stop. Reduces post-mix from 15 to 5 min.

## 4. New Entities & Script Logic

### New entity

| Entity | Type | Purpose |
|--------|------|---------|
| `input_boolean.pool_heating_cold_weather_mode` | input_boolean | Toggle normal vs cold weather sequences |

### Conditional script structure (both scripts)

Use HA `choose` action checking `input_boolean.pool_heating_cold_weather_mode`. Cold weather branch as described in Section 2. Default branch preserves existing sequences unchanged.

**Pre-circulation approach (Option A, recommended):** Embed 5-min pre-circ delay inside `block_start` script. Automation still triggers at `block_start` time. Pyscript sets `block_end = block_start + 10min` (5 pre-circ + 5 heat). The stop automation fires at block_end, runs 5-min post-mix, total 15 min wall-clock.

### Existing entity changes

- `input_number.pool_heating_min_block_duration` (pool_heating.yaml:386): lower `min` from 30 to 5
- `input_number.pool_heating_max_block_duration` (pool_heating.yaml:394): lower `min` from 30 to 5
- `VALID_BLOCK_DURATIONS` (pool_heating.py:33): add `5` (and `10`, `15`) to `[30, 45, 60]`

### Pyscript algorithm change needed

Break constraint in `_find_best_placement` (pool_heating.py:403): `next_min_start = start_idx + block_size + block_size` gives 5-min breaks for 5-min blocks, allowing 3/hour. Spec requires 1/hour (~55-min breaks). Need cold-weather override parameter for break duration.

## 5. Questions Answered

**Q1: Skip preheat entirely?** Yes. Radiators won't cool meaningfully in 5 min of pool heating. Preheat overhead (15 min) exceeds block duration.

**Q2: Skip PID temp control?** Yes. PID adjust runs every 5 min (pool_temp_control.yaml:181) -- gets at most 1 iteration. PID feedback needs 15-30 min to stabilize. No benefit for 5-min blocks.

**Q3: Minimum pre-circulation time?** 5 min. Pipe tau = 7 min (pool_heating.py:1558), so 5 min reaches ~50% of true temp. Adequate for protecting heat exchanger from stagnant water.

**Q4: Post-mix configurable or fixed?** Fixed at 5 min for cold weather. Adding a configurable parameter creates UI complexity for minimal gain.

**Q5: Min compressor gear (FR-46) needed?** No. Compressor won't fully ramp in 5 min regardless. Skipping avoids gear store/restore complexity.

**Q6: Separate automations or conditionals?** Conditionals in existing scripts using `choose`. Automations (with 10 trigger definitions each) stay unchanged. Much cleaner.

**Q7: How to determine cold weather mode?** Manual toggle. Auto-detect from outdoor temp is future work. Manual is simpler, user controls seasonal switching.

## 6. Risks

1. **Script blocking.** HA scripts with `delay` block the instance. If block_stop triggers during pre-circ delay, it queues. **Mitigation:** set `mode: restart` on block_start script.
2. **Pump double-ON.** `switches_on` turns pump ON (pool_heating.yaml:1260), but pump is already ON from pre-circ. This is a safe no-op.
3. **10-block limit.** 10 hours x 1/hour = exactly 10 blocks. No room if window expands or frequency changes.
4. **Break constraint.** Current `break = block_duration` gives 5-min breaks for 5-min blocks (3/hour possible). Must override to ~55-min breaks. This is a pyscript change, not automation.
5. **Normal mode regression.** `choose` defaults to existing sequences. If `cold_weather_mode` is OFF, behavior is identical. Low risk.
