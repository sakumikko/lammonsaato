# Review 03: Temperature Control & Safety Findings for Cold Weather Mode

**Date:** 2026-02-02  **Reviewer:** Claude (Opus 4.5)

---

## 1. Current Control Flow Per Block

Today, each heating block follows this sequence (defined in `pool_heating.yaml:1318-1340`, `pool_heating_block_start`):

1. **Preheat** (line 1328): Calls `pool_temp_control_preheat()` (`pool_temp_control.py:425-469`) -- raises comfort wheel by +3C
2. **Wait 15 min** (line 1330-1331): Fixed delay for radiators to absorb heat
3. **Start temp control** (line 1333): Calls `pool_temp_control_start()` (`pool_temp_control.py:216-279`) -- stores originals, enables fixed supply mode, sets gear to 7
4. **Switches ON** (line 1335): Prevention OFF, circulation ON (`pool_heating.yaml:1243-1283`)

During the block:
- **Every 5 min**: `pool_temp_control_adjust` (`pool_temp_control.yaml:177-192`) calls `calculate_new_setpoint()` (`pool_temp_control.py:98-149`)
- **Every 1 min**: `pool_temp_control_safety_check` (`pool_temp_control.yaml:195-207`) calls `check_safety_conditions()` (`pool_temp_control.py:152-178`)

At block end (`pool_heating.yaml:1342-1373`, `pool_heating_block_stop`):
1. Stop temp control -- disables fixed supply, restores gear (`pool_temp_control.py:283-310`)
2. Switches OFF -- prevention ON
3. Log session end
4. **15-min circulation for mixing** (line 1360-1361)
5. Pump OFF, log final temp

---

## 2. CRITICAL: Block Start Sequence vs 5-Min Block Duration

**This is a showstopper.** The block start sequence takes ~15 minutes before switches actually turn on:

- `pool_heating_block_start` has a 15-min `delay` at line 1330-1331 (preheat wait)
- For a 5-min block scheduled 22:00-22:05, the start automation fires at 22:00
- Heating switches would not turn on until ~22:15
- But the stop automation (`pool_stop_heating_blocks`, line 980-1022) fires at 22:05
- **Result: heating never actually runs**

Additionally, the stop sequence has a 15-min mixing circulation (line 1360-1361). For 5-min blocks with 55-min breaks, the pump would run 15 min out of every 60 min just for mixing -- 25% of the break time.

**Recommendation:** Cold weather mode needs a simplified block sequence that skips preheat delay and reduces or eliminates mixing time.

---

## 3. Cold Weather Assessment Per Feature

### 3a. PID-Feedback Algorithm -- USELESS for 5-min blocks

The algorithm (`pool_temp_control.py:98-149`) reads `sensor.heating_season_integral_value` (PID Integral 30m). This is a 30-minute rolling average. In a 5-min block:
- The adjust automation fires at most once (every 5 min, line 182)
- The PID 30m value barely changes in 5 minutes
- The correction is effectively a static offset: `(pid_30m - (-2.5)) * 0.1`
- With PID=0: correction = +0.25C. With PID=-5: correction = -0.25C.

**Verdict: Adds complexity, no feedback benefit. A fixed offset would behave identically.**

### 3b. Fixed Supply Mode Toggling -- HARMFUL for 5-min blocks

Per block: `pool_temp_control_start()` (line 216) writes 4 Modbus values: fixed supply setpoint, fixed supply enable, min gear, and stores originals. `pool_temp_control_stop()` (line 283) writes 3 Modbus values back.

For 10 blocks/night: ~70 Modbus write operations just for mode management. Each Modbus write goes to `192.168.50.10:502`. Risk of:
- Thermia rejecting rapid mode changes
- Integration reload (`thermia_hourly_reload`, `pool_heating.yaml:833-844`) colliding with a write
- Stale sensor recovery (`pool_heating.yaml:846-876`) triggering during a block

**Verdict: Keep fixed supply enabled for the entire heating window (21:00-07:00) rather than toggling per block.**

### 3c. Comfort Wheel Preheat -- COUNTERPRODUCTIVE for 5-min blocks

`pool_temp_control_preheat()` (`pool_temp_control.py:425-469`) raises comfort wheel by `PREHEAT_OFFSET = 3.0` (line 63). Called 15 min before each block. For 10 blocks:
- 10 raises of +3C, 10 restores
- Comfort wheel changes every ~60 min
- The heat pump's response to comfort wheel changes is itself slow (multiple minutes)
- Net effect: oscillating radiator output with no time to stabilize

**Verdict: Either skip preheat entirely in cold weather, or raise comfort wheel once at window start and restore at window end.**

### 3d. Minimum Compressor Gear -- QUESTIONABLE for 5-min blocks

`MIN_GEAR_POOL = 7` (`pool_temp_control.py:56`) is set per-block at line 254-256 and restored at line 296-299. The compressor takes time to ramp to gear 7. In a 5-min window, it may not reach the target gear before the block ends.

**Verdict: If fixed supply mode is kept on for the whole window, gear setting could also persist. Otherwise, frequent gear toggling (10x/night) risks compressor wear.**

### 3e. Safety Thresholds -- TOO GENEROUS for cold weather

Current values (`pool_temp_control.py:67-68`):
- `ABSOLUTE_MIN_SUPPLY = 32.0` (FR-44)
- `RELATIVE_DROP_MAX = 15.0` (FR-45)

In cold weather (outdoor -20C), the heating curve target may be 45-50C. A 15C relative drop means supply could fall to 30-35C before safety triggers. At -20C outdoor, radiators at 35C provide inadequate heating. Even 32C absolute min is dangerously low for radiators in extreme cold.

In a 5-min block, thermal inertia means supply might drop 2-5C at most. The current thresholds would never trigger, making them effectively disabled.

**Recommendation:** Tighten for cold weather: `ABSOLUTE_MIN_SUPPLY = 38C`, `RELATIVE_DROP_MAX = 8C`. Consider outdoor-temp-dependent formula: `max_drop = 15 - (outdoor_below_zero * 0.5)`.

### 3f. Safety Check Frequency -- ADEQUATE

Every 1 min (`pool_temp_control.yaml:195-207`). For 5-min blocks, that is 5 checks. Sufficient.

### 3g. 60-Minute Timeout -- IRRELEVANT but harmless

`pool_heating_60min_timeout` (`pool_temp_control.yaml:209-225`) triggers after 60 continuous minutes. 5-min blocks will never trigger this. No change needed; it remains as protection against bugs.

### 3h. Recovery Between Blocks -- ADEQUATE

55-min breaks between 5-min blocks provide ample radiator recovery time. The question is whether 5 min of heating is enough to meaningfully heat the pool -- this requires physical testing.

---

## 4. Safety Threshold Recommendations

| Parameter | Current | Cold Weather Proposal | Rationale |
|-----------|---------|----------------------|-----------|
| ABSOLUTE_MIN_SUPPLY | 32C | 38C | Radiators need >35C at -20C outdoor |
| RELATIVE_DROP_MAX | 15C | 8C | 15C drop unreachable in 5 min; 8C is meaningful |
| Preheat offset | +3C | 0 (skip) or +1C once | Oscillation risk with frequent toggling |
| Min gear | 7 per block | 7 for window | Avoid toggling; let compressor stabilize |

Implement as conditional: if outdoor < -5C, use tighter thresholds. `check_safety_conditions()` (`pool_temp_control.py:152-178`) would need an outdoor temp or mode parameter.

---

## 5. Thermia Interaction Concerns

1. **Integration reload collision**: The hourly reload (`pool_heating.yaml:833`) could fire during a 5-min block. If Modbus reconnects during a block, `pool_temp_control_stop()` may fail to restore settings. Mitigation: add a condition to skip hourly reload while `pool_temp_control_active` is on.

2. **Stale sensor during block**: If `sensor.system_supply_line_temperature` goes unavailable mid-block, the safety check (`pool_temp_control.py:360-361`) returns early with no action. The block continues without safety monitoring. Consider: treat sensor unavailability as a safety trigger in cold weather.

3. **Fixed supply entity unavailability**: `pool_temp_control_start()` checks only the enable switch (line 227-229). If the setpoint entity is unavailable, `number.set_value` (line 268-270) fails silently. The block starts without proper setpoint control.

---

## 6. Simplified Cold Weather Sequence (Proposal)

For blocks <= 10 minutes, replace the full orchestration with:

**At heating window start (21:00):**
1. Store original curve target, gear, comfort wheel (once)
2. Enable fixed supply mode with conservative setpoint (curve_target - 2C)
3. Set min gear to 7
4. Optionally raise comfort wheel by +1C

**At each 5-min block start:**
1. Prevention OFF, circulation ON (switches only -- no Modbus writes)

**At each 5-min block end:**
1. Prevention ON (switches only)
2. Skip 15-min mixing (unnecessary for 5-min blocks)

**At heating window end (07:00):**
1. Disable fixed supply mode
2. Restore gear, comfort wheel (once)

**Modbus operations: 4 writes at start + 3 writes at end = 7 total** (vs ~70 with current per-block toggling).

Safety checks continue every 1 min with tightened thresholds. If triggered, disable fixed supply and set a flag to skip remaining blocks.

---

## 7. Open Questions (Require Physical Testing)

1. **Does 5 min of pool heating cause measurable supply line temperature drop?** If the drop is <2C, current safety checks are entirely irrelevant and the PID algorithm provides no value.

2. **How quickly does Thermia respond to fixed supply mode enable/disable?** If the response takes >2 min, per-block toggling wastes 40%+ of each 5-min block on transition.

3. **What is the compressor's ramp time to gear 7?** If >3 min, gear 7 is never reached in a 5-min block.

4. **Is 5 min enough to deliver meaningful heat to the pool?** At 45 L/min flow and typical 5C delta-T, thermal power is ~15.7 kW. In 5 min that is ~1.3 kWh thermal. For a large pool, this may be negligible per block but cumulative over 10 blocks (~13 kWh) could be useful.

5. **Does the heat pump have a minimum run time requirement?** Some heat pumps require minimum 3-5 min continuous operation. If Thermia requires >5 min, the entire cold weather short-cycle approach may need revision (e.g., 10-min blocks with 50-min breaks).
