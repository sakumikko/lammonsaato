# Review Plan 02: HA Automations & Block Sequences for Cold Weather Mode

## Objective

Review Home Assistant automations and block start/stop sequences to determine what changes are needed for cold weather short-cycle heating. The current sequences have significant overhead (preheat, temp control ramp, post-mix) that exceeds the 5-minute block duration.

## Context

Current block sequence timeline for a 30-min block:
```
T-15min: Preheat (raise comfort wheel +3C)
T-0:     Start temp control (enable fixed supply, set gear)
T-0:     Switches on (prevention OFF, pump ON)
T+30min: Stop temp control (disable fixed supply, restore curve)
T+30min: Prevention ON
T+45min: Pump OFF (15 min post-mix)
T+45min: Log final temperature
```

For a 5-min block, 15 min preheat + 15 min post-mix = 30 min overhead for 5 min of heating. This is clearly wrong.

## Files to Review

| File | What to look for |
|------|-----------------|
| `homeassistant/packages/pool_heating.yaml` | All automations: block start/stop, preheat, post-mix, safety timeout |
| `homeassistant/packages/pool_temp_control.yaml` | Temp control automations: adjust interval, safety check interval |
| `scripts/pyscript/pool_heating.py` | `pool_heating_start_block`, `pool_heating_stop_block` service functions |

## Review Checklist

### 1. Block Start Sequence (pool_heating.yaml)
- [ ] `pool_heating_preheat` automation - triggers 15 min before block. For 5-min blocks, this means preheat starts at T-15, block runs T+0 to T+5. Is preheat needed at all?
- [ ] `pool_heating_start_temp_control` - enables fixed supply mode. For 5 min of heating, is PID-feedback control meaningful?
- [ ] `pool_heating_switches_on` - turns off prevention, turns on pump. This is still needed.
- [ ] Delay between preheat and switches_on: currently 15 min. Must be much shorter or eliminated.

### 2. Block Stop Sequence (pool_heating.yaml)
- [ ] `pool_heating_stop_temp_control` - disables fixed supply. For 5 min blocks, was it even useful to enable?
- [ ] `pool_heating_switches_off` - prevention ON, pump stays ON for mixing.
- [ ] Post-mix delay: currently 15 minutes of pump running after block ends. For 5-min blocks: should this be reduced to 5 min as user suggested?
- [ ] Temperature logging after mix: still relevant?

### 3. Circulation Pump Control
- [ ] User requirement: pump ON 5 min before and 5 min after heating.
- [ ] Current: pump ON at block start, OFF 15 min after block end.
- [ ] Need new pre-circulation phase (pump ON but no heat) before heating starts.
- [ ] Total pump runtime per cycle: 5 min pre + 5 min heat + 5 min post = 15 min per hour.

### 4. Safety Timeout
- [ ] `pool_heating_60min_timeout` - stops heating after 60 min continuous. Not relevant for 5-min blocks.
- [ ] Should there be a different timeout for cold weather mode?
- [ ] Consider: if something goes wrong and a 5-min block doesn't stop, what's the safety net?

### 5. Temperature Control During Short Blocks
- [ ] `pool_temp_control_adjust` runs every 5 min. For a 5-min block, it runs at most once.
- [ ] `pool_temp_control_safety_check` runs every 1 min. Gets ~5 checks per block. Still useful.
- [ ] PID feedback needs ~15-30 min to be meaningful. Pointless for 5-min blocks.
- [ ] Should cold weather mode skip temp control entirely and just run raw?

### 6. Automation Trigger Conditions
- [ ] Block start/stop automations trigger based on `input_datetime.pool_heat_block_X_start/end`.
- [ ] These must work the same way for cold weather blocks.
- [ ] Are there enough block entities? Currently 10 blocks. Cold weather 10 hours * 1/hour = 10 blocks. Just enough.

### 7. Nighttime Scheduling
- [ ] `pool_heating_calculate_schedule` triggers when Nordpool prices available.
- [ ] Must pass cold weather mode flag to pyscript.
- [ ] How does the automation know it's "cold weather"? Manual toggle? Outdoor temp sensor?

## Questions to Answer

1. Should cold weather mode skip preheat entirely, or use a shorter preheat?
2. Should cold weather mode skip PID temp control (fixed supply mode) entirely?
3. What is the minimum meaningful pump pre-circulation time?
4. Should the post-mix time be configurable or fixed at 5 min for cold weather?
5. Is the minimum compressor gear (FR-46) still needed for 5-min blocks?
6. Should there be a separate automation set for cold weather, or conditionals in existing ones?
7. How does the system determine it's in cold weather mode? (manual toggle vs. auto-detect from outdoor temp)

## Output Instructions

After completing this review, write findings to:
**`docs/reviews/02-ha-automations-sequences-findings.md`**

The findings file must contain:
1. **Current Sequence**: Full timeline of current block start/stop with line references
2. **Proposed Cold Weather Sequence**: New timeline for 5-min blocks
3. **Automations to Modify**: List of automations with specific changes needed
4. **New Automations Needed**: Any new automations for cold weather mode
5. **Conditional Logic**: How to switch between normal and cold weather sequences
6. **Entity Changes**: New input entities needed (mode toggle, pre/post circulation times)
7. **Risks**: What could break in existing normal-mode automations
