# Cold Weather Heating Cycles - Implementation Overview

## Problem

During extremely cold weather, the radiator circuit cools too quickly for 30-45 min heating blocks to make sense. The system needs a "cold weather mode" that runs short 5-min heating cycles once per hour, with brief circulation pump runs before and after each cycle.

## Solution Summary

Add a cold weather mode toggle that changes the entire heating behavior:

| Aspect | Normal Mode | Cold Weather Mode |
|--------|-------------|-------------------|
| Block duration | 30-45 min | 5 min (configurable 5/10/15) |
| Blocks per night | 2-6 | 1/hour within window |
| Heating window | Hardcoded 21:00-07:00 | **Configurable via input_datetime** |
| Block timing | Price-optimized | **Fixed :05 past each hour** |
| Break between blocks | Equal to block | ~55 min (rest of hour) |
| Pre-circulation | None (preheat instead) | 5 min pump-only (configurable) |
| Post-circulation | 15 min mixing | 5 min mixing (configurable) |
| Preheat (comfort wheel) | +3C, 15 min wait | Skipped |
| PID temp control | Per-block toggle | Window-level |
| Compressor gear | Set to 7 per block | **max(9, MIN_GEAR, live_gear)** |
| Safety thresholds | 32C abs / 15C relative | 38C abs / **12C relative** |
| Cost constraint | Active | Ignored (anti-freeze priority) |
| Price optimization | Brute-force best placement | **None (dead simple)** |
| Modbus writes/night | ~70 | ~7 |

## Implementation Plans

Execute in order. Each plan is self-contained with specific file changes, tests, and verification steps.

| Plan | What | Key Files | Depends On |
|------|------|-----------|------------|
| [01](01-ha-entities-and-yaml.md) | New HA entities + conditional scripts | pool_heating.yaml | - |
| [02](02-schedule-algorithm.md) | Simple fixed-time schedule (pyscript only) | pool_heating.py | 01 |
| [03](03-temperature-control-safety.md) | Window-level temp control + tighter safety | pool_temp_control.py, pool_temp_control.yaml | 01 |
| [04](04-web-ui-and-mock-server.md) | UI toggle, window times, compact display | ScheduleEditor.tsx, SchedulePanel.tsx, server.py | 01, 02 |

Plans 02 and 03 can be implemented in parallel after Plan 01. Plan 04 depends on both 01 and 02.

**Key simplification:** No changes to `scripts/lib/schedule_optimizer.py` -- cold weather uses a simple loop in pyscript only.

## New Entities (6 total)

| Entity | Type | Default |
|--------|------|---------|
| `input_boolean.pool_heating_cold_weather_mode` | boolean | off |
| `input_datetime.pool_heating_cold_window_start` | time | 21:00 |
| `input_datetime.pool_heating_cold_window_end` | time | 07:00 |
| `input_number.pool_heating_cold_block_duration` | number (5/10/15) | 5 |
| `input_number.pool_heating_cold_pre_circulation` | number (0-10 min) | 5 |
| `input_number.pool_heating_cold_post_circulation` | number (0-10 min) | 5 |

No existing entities are modified. Entity ID stability is preserved.

## Pre-existing Issues Found During Review

1. **Schedule JSON overflow**: `input_text.pool_heating_schedule_json` max_length 255 chars. Already broken for >4 blocks. Must fix to support 10 blocks.
2. **Mock server block range**: `/api/block-enabled` hardcoded to blocks 1-4. Should be 1-10.
3. **ScheduleEditor hooks**: `useScheduleEditor` called conditionally (React Rules of Hooks violation). Works but should be refactored.

## Risk Mitigations

1. **Normal mode regression**: All changes use `choose` conditionals or `if cold_weather` branches. Default paths preserve existing behavior exactly.
2. **Valve switching**: Compressor always runs; we only switch valve positions. No short-cycling concern.
3. **Thermia reload collision**: Add condition to skip hourly reload when cold weather control is active.

## Testing Strategy

Per CLAUDE.md TDD requirements:
1. Write unit tests for `generate_cold_weather_schedule()` FIRST
2. Write E2E tests for cold weather UI FIRST
3. Verify all tests FAIL before implementation
4. Implement
5. Verify tests PASS
6. Run full regression (`make test` + E2E)
