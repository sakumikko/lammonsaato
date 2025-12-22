# Codebase Cleanup Plan

**Created:** 2025-12-20
**Status:** Pending review

## Overview

Analysis of 8 files (5122 lines total) against PRODUCT_REQUIREMENTS.md revealed alignment with requirements but identified opportunities for cleanup.

## Files Reviewed

| File | Lines | Status | Implements |
|------|-------|--------|------------|
| `peak_power.yaml` | 148 | ✅ Clean | FR-33 to FR-39 |
| `pool_heating.yaml` | 1795 | ⚠️ Has legacy | FR-1 to FR-32 |
| `pool_temp_control.yaml` | 345 | ✅ Clean | FR-43 to FR-46 |
| `thermia_protection.yaml` | 241 | ✅ Keep | NFR-1 to NFR-4 (compressor safety) |
| `thermia_recording.yaml` | 185 | ⚠️ Broad scope | HA history recording |
| `firebase_sync.py` | 202 | ⚠️ Misnamed | FR-16 to FR-19 |
| `pool_heating.py` | 1770 | ⚠️ Has legacy | FR-1 to FR-5c |
| `pool_temp_control.py` | 436 | ✅ Clean | FR-43 to FR-46 |

## Cleanup Actions

### 1. Legacy Code in pool_heating.py (~80 lines)

**Location:** `scripts/pyscript/pool_heating.py`

**Items:**
- Lines 419-476: `find_best_heating_slots()` - Legacy wrapper function
- Lines 870-873: `calculate_schedule()` - Alias function

**Current callers:**
- Line 1426: Internal call from `find_best_heating_schedule()`
- `scripts/standalone/test_live_integration.py`: External test script

**Action:**
- [ ] Remove `calculate_schedule()` alias (line 870-873)
- [ ] Inline `find_best_heating_slots()` logic into caller OR keep as internal helper
- [ ] Update `test_live_integration.py` to use current API

**Risk:** Low - internal refactoring only

---

### 2. Rename firebase_sync.py

**Location:** `scripts/pyscript/firebase_sync.py`

**Problem:** File name references Firebase but Firebase was dropped. File now does local JSON logging.

**Evidence:** Docstring says "Local data logging for pool heating sessions"

**Action:**
- [ ] Rename to `data_logger.py` or `session_logger.py`
- [ ] Update imports in any files that reference it
- [ ] Update CLAUDE.md file references

**Risk:** Low - naming only

---

### 3. Update Hardcoded Block Count

**Location:** `scripts/pyscript/firebase_sync.py`

**Problem:** Hardcoded to 4 blocks, but system now supports 10 blocks

**Lines:**
- Line 118: `for i in range(1, 5):`
- Line 165: `for i in range(1, 5):`

**Action:**
- [ ] Change `range(1, 5)` to `range(1, 11)` in both locations
- [ ] Or use constant `BLOCK_COUNT = 10` from pool_heating.py

**Risk:** Low - extends capability

---

### 4. Narrow thermia_recording.yaml Entity Globs

**Location:** `homeassistant/packages/thermia_recording.yaml`

**Current state:** Uses broad entity_globs that capture ~400 Thermia entities

**Header comment lists only 6 required entities:**
```yaml
# Required entities:
# - sensor.condenser_out_temperature
# - sensor.condenser_in_temperature
# - sensor.system_supply_line_temperature
# - sensor.calculated_supply_temperature
# - number.fixed_system_supply_set_point
# - switch.enable_fixed_system_supply_set_point
```

**Action:**
- [ ] Consider replacing globs with explicit entity list
- [ ] OR keep globs if full Thermia history is desired for debugging

**Risk:** Medium - narrowing might exclude useful entities

---

### 5. Add thermia_protection.yaml to Requirements

**Location:** `homeassistant/packages/thermia_protection.yaml`

**Finding:** Provides critical compressor safety (discharge temp limits, cold weather tap water reduction) but NOT explicitly listed in PRODUCT_REQUIREMENTS.md

**Action:**
- [ ] Add NFR section for compressor protection in PRODUCT_REQUIREMENTS.md
- [ ] Document the 100°C warning / 110°C critical thresholds

**Risk:** None - documentation only

---

## Priority Order

1. **High priority:** Update hardcoded block count (functional bug)
2. **Medium priority:** Rename firebase_sync.py (clarity)
3. **Low priority:** Remove legacy functions (cleanup)
4. **Optional:** Narrow entity globs (depends on debug needs)
5. **Documentation:** Add thermia_protection to requirements

## Execution Checklist

When ready to execute cleanup:

```bash
# 1. Create cleanup branch
git checkout -b cleanup/legacy-code-removal

# 2. Make changes per section above

# 3. Run tests
make test
cd web-ui && npx playwright test

# 4. Verify no regressions
# All 226 Python tests should pass
# All E2E tests should pass

# 5. Commit with descriptive message
git commit -m "refactor: cleanup legacy code and rename firebase_sync"
```

## Notes

- Do NOT remove `thermia_protection.yaml` - it provides valuable compressor safety
- Do NOT narrow entity globs without testing impact on HA history/graphs
- Legacy function removal should wait until test_live_integration.py is updated
