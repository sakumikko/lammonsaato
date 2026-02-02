# Review Plan 03: Temperature Control & Safety for Cold Weather Mode

## Objective

Review the PID-feedback temperature control and safety systems to determine what changes are needed for cold weather short-cycle heating. The current system was designed for 30-45 min continuous heating blocks and may not be appropriate for 5-min bursts.

## Context

The temperature control system manages the heat pump's fixed supply setpoint during pool heating to prevent the radiator circuit from cooling too much. In cold weather, this is especially critical because:
- Radiators need heat most of the time
- Even 5 minutes of diverting heat to the pool could cause noticeable radiator cooling
- The PID integral responds slowly (30-min averaging window)
- Safety thresholds (FR-44: 32C min, FR-45: 15C drop max) may be too generous for cold weather

## Files to Review

| File | What to look for |
|------|-----------------|
| `scripts/pyscript/pool_temp_control.py` | PID algorithm, safety checks, preheat, start/stop/adjust services |
| `homeassistant/packages/pool_temp_control.yaml` | Automation triggers, intervals, conditions |
| `homeassistant/packages/pool_heating.yaml` | Safety timeout, heating prevention logic |
| `tests/` | Any existing temperature control tests |

## Review Checklist

### 1. PID-Feedback Algorithm Relevance
- [ ] `calculate_new_setpoint()` uses PID Integral 30m sensor. With 5-min blocks, PID barely moves before block ends.
- [ ] The algorithm adjusts every 5 min (`pool_temp_control_adjust`). For a 5-min block, at most 1 adjustment.
- [ ] Is the PID correction meaningful in a single 5-min window? Or does it just add complexity?
- [ ] Alternative: For cold weather, don't adjust setpoint at all during the 5-min block. Just use a fixed offset.

### 2. Fixed Supply Mode Overhead
- [ ] Enabling/disabling fixed supply mode has Modbus write overhead to Thermia.
- [ ] For 10 cycles per night: 10 enable + 10 disable = 20 Modbus operations just for mode switching.
- [ ] Thermia may not respond well to rapid mode toggling. Check if there's a minimum stable time.
- [ ] Should cold weather mode keep fixed supply enabled for the entire heating window instead of per-block?

### 3. Comfort Wheel / Preheat
- [ ] `pool_temp_control_preheat()` raises comfort wheel by 3C.
- [ ] Called 15 min before each block. For 10 blocks/night = 10 preheat cycles.
- [ ] Constant comfort wheel toggling (+3C/-3C every hour) could cause oscillation in radiator output.
- [ ] Should cold weather mode skip preheat? Or keep comfort wheel permanently raised?

### 4. Minimum Compressor Gear (FR-46)
- [ ] `MIN_GEAR_POOL = 7` set during pool heating, restored after.
- [ ] For 5 min heating: set gear to 7, heat 5 min, restore. 10 times per night.
- [ ] Compressor may not reach gear 7 in 5 minutes. Is this setting useful?
- [ ] Risk: frequent gear changes could stress compressor.

### 5. Safety Thresholds
- [ ] `ABSOLUTE_MIN_SUPPLY = 32C` (FR-44) - appropriate for cold weather? Supply line may already be near this in extreme cold.
- [ ] `RELATIVE_DROP_MAX = 15C` (FR-45) - in cold weather, curve target could be 45-50C. A 15C drop to 30-35C is still dangerously cold for radiators.
- [ ] Should cold weather mode have tighter safety limits? E.g., max 5C drop instead of 15C?
- [ ] What is the typical supply temperature in extreme cold? Need to understand if 5 min of pool heating causes measurable supply drop.

### 6. Safety Check Frequency
- [ ] Currently every 1 minute. For 5-min blocks, that's 5 checks. Probably sufficient.
- [ ] `pool_temp_control_safety_check` calls `check_safety_conditions()`. No changes needed here.

### 7. 60-Minute Timeout
- [ ] `pool_temp_control_timeout()` - irrelevant for 5-min blocks.
- [ ] Should be automatically inactive for cold weather mode (blocks are always <60 min).
- [ ] But verify: is there a risk of multiple blocks running back-to-back in cold weather mode?

### 8. Recovery Between Blocks
- [ ] In normal mode: break = block duration (30-45 min). Radiators recover.
- [ ] In cold weather mode: break = 55 min. Radiators have plenty of time to recover.
- [ ] But: is 5 minutes of heating enough to meaningfully heat the pool?
- [ ] Trade-off: pool heating effectiveness vs. radiator protection.

### 9. Thermia Integration Stability
- [ ] `thermia_hourly_reload` and `thermia_stale_recovery` automations reload the integration.
- [ ] More frequent Modbus operations (10 cycles/night) could interact with reload timing.
- [ ] If integration reloads during a 5-min block, block may not stop properly.

## Questions to Answer

1. Should cold weather mode use PID-feedback control at all, or just raw heating?
2. Should fixed supply mode be toggled per-block or left enabled for the whole window?
3. Are current safety thresholds (FR-44, FR-45) appropriate for cold weather?
4. Should there be a cold-weather-specific safety threshold based on outdoor temperature?
5. Is the comfort wheel preheat useful for short blocks, or counterproductive?
6. What is the physical response time of the heat pump to mode changes? Can it meaningfully heat pool in 5 minutes?
7. Should minimum gear be set for the entire heating window rather than per-block?

## Output Instructions

After completing this review, write findings to:
**`docs/reviews/03-temperature-control-safety-findings.md`**

The findings file must contain:
1. **Current Control Flow**: How temp control works per block today (with line references)
2. **Cold Weather Assessment**: For each control feature, whether it's useful/harmful/neutral for 5-min blocks
3. **Recommended Changes**: Specific modifications to pool_temp_control.py
4. **Safety Threshold Recommendations**: Whether to tighten limits for cold weather
5. **Thermia Interaction Concerns**: Risks from frequent Modbus operations
6. **Simplified Cold Weather Sequence**: Proposed minimal control flow for short blocks
7. **Open Questions**: Things that need physical testing to determine
