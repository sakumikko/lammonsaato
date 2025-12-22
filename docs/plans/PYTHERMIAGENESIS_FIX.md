# pythermiagenesis KeyError Bug Fix

**Date:** 2024-12-14
**Branch:** `feature/fixed-supply-pool-heating`
**Related:** [FIXED_SUPPLY_INVESTIGATION.md](./FIXED_SUPPLY_INVESTIGATION.md)

## The Bug

### Symptom

When enabling `switch.enable_fixed_system_supply_set_point` and `number.fixed_system_supply_set_point` entities in Home Assistant, the Thermia Genesis integration crashes with:

```
Traceback (most recent call last):
  File "/config/custom_components/thermiagenesis/__init__.py", line 97, in _async_update_data
    data = await self.thermia.async_update(only_registers=registers)
  File "/usr/local/lib/python3.13/site-packages/pythermiagenesis/__init__.py", line 99, in async_update
    raw_data = await self._get_data(use_registers)
  File "/usr/local/lib/python3.13/site-packages/pythermiagenesis/__init__.py", line 194, in _get_data
    not raw_data[ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]
KeyError: 'coil_enable_fixed_system_supply_set_point'
```

### Root Cause

In `pythermiagenesis/__init__.py` around line 185-198, there's logic to skip reading the holding register for fixed supply setpoint if the enable coil is not set:

```python
if name == ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT:
    # This will give an error unless coil 42 is True, so skip if we don't know this or if it's false
    enableAttr = ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT
    if enableAttr not in raw_data and enableAttr not in self.data:
        _LOGGER.debug(...)
        continue
    if (
        not raw_data[ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]      # <-- BUG
        and not self.data[ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]  # <-- BUG
    ):
        _LOGGER.debug(...)
        continue
```

**The bug:** The first `if` correctly checks `enableAttr not in raw_data`, but the second `if` directly accesses `raw_data[enableAttr]` without checking if the key exists first. When the coil read fails or returns no data, `raw_data` doesn't contain the key, causing `KeyError`.

### Why It Happens

The coil read for `coil_enable_fixed_system_supply_set_point` (address 41) may fail because:
1. The register doesn't exist on this heat pump model
2. The Modbus read times out
3. The coil is processed after the holding register in the iteration order

In our case, direct Modbus reads via `test_fixed_supply.py` work, but the integration's batched read doesn't include the coil in `raw_data` when processing the holding register.

## The Fix

Change direct dictionary access to `.get()` with a default value:

```python
# Before (buggy):
if (
    not raw_data[ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]
    and not self.data[ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]
):

# After (fixed):
if (
    not raw_data.get(ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT, False)
    and not self.data.get(ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT, False)
):
```

This is safe because:
- If the key doesn't exist, `.get()` returns `False`
- `not False` = `True`, so the code continues to skip the holding register
- This matches the intended behavior: "skip if we don't know the coil state"

## Repositories

| Repo | Description | URL |
|------|-------------|-----|
| thermiagenesis | HA custom component | https://github.com/CJNE/thermiagenesis |
| pythermiagenesis | Python library | https://github.com/CJNE/pythermiagenesis |

The bug is in **pythermiagenesis** (the library), not the custom component.

## Testing Plan

### Phase 0: Local Reproduction & Validation (Using Cloned Library)

The library is cloned to `../pythermiagenesis`. Test directly against Thermia Mega before deploying to HA.

#### 0.1 Reproduce the Bug Locally

Create a test script that simulates the library's behavior:

```bash
cd /Users/sakumikko/code/lammonsaato
./env/bin/python scripts/standalone/test_pythermiagenesis_bug.py --reproduce
```

**Test script logic:**
1. Connect to Thermia Mega (192.168.50.10:502)
2. Request both registers: `coil_enable_fixed_system_supply_set_point` + `holding_fixed_system_supply_set_point`
3. Simulate the library's `_get_data()` iteration order where holding is processed before coil
4. Confirm `KeyError` is raised when accessing `raw_data[ATTR_COIL_...]`

**Expected output:**
```
Testing buggy code path...
KeyError raised as expected: 'coil_enable_fixed_system_supply_set_point'
Bug reproduced successfully!
```

#### 0.2 Validate the Fix Locally

```bash
./env/bin/python scripts/standalone/test_pythermiagenesis_bug.py --validate-fix
```

**Test script logic:**
1. Same setup as 0.1
2. Use `.get(..., False)` instead of direct access
3. Confirm no exception raised
4. Confirm correct behavior: skips holding register when coil is unknown/false

**Expected output:**
```
Testing fixed code path...
No exception raised
Holding register correctly skipped (coil unknown)
Fix validated successfully!
```

#### 0.3 Test Full Library with Fix Applied

```bash
# Install the cloned library in editable mode
cd ../pythermiagenesis
pip install -e .

# Apply the fix (edit pythermiagenesis/__init__.py)
# Then test against real Thermia

cd /Users/sakumikko/code/lammonsaato
./env/bin/python scripts/standalone/test_pythermiagenesis_integration.py
```

**Test script logic:**
1. Import `ThermiaGenesis` from the cloned library
2. Connect to Thermia Mega
3. Call `async_update()` with both fixed supply registers
4. Verify no crash and valid data returned

**Expected output:**
```
Connecting to Thermia Mega...
Requesting registers: coil_enable_fixed_system_supply_set_point, holding_fixed_system_supply_set_point
Data received:
  coil_enable_fixed_system_supply_set_point: False
  holding_fixed_system_supply_set_point: (skipped - coil is False)
Integration test passed!
```

### Phase 1: HA Verification (After Local Validation)

Once Phase 0 confirms the fix works locally:

1. **SSH into HA and find the installed library:**
   ```bash
   ssh root@192.168.50.11
   find /usr/local/lib -name "pythermiagenesis" -type d
   # Usually: /usr/local/lib/python3.13/site-packages/pythermiagenesis/
   ```

2. **Backup the original file:**
   ```bash
   cp /usr/local/lib/python3.13/site-packages/pythermiagenesis/__init__.py \
      /config/pythermiagenesis_init_backup.py
   ```

3. **Apply the fix directly:**
   ```bash
   # Find the exact line number
   grep -n "not raw_data\[ATTR_COIL" /usr/local/lib/python3.13/site-packages/pythermiagenesis/__init__.py

   # Edit the file (use vi or nano)
   vi /usr/local/lib/python3.13/site-packages/pythermiagenesis/__init__.py

   # Change line ~194 from:
   #   not raw_data[ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]
   # To:
   #   not raw_data.get(ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT, False)

   # And line ~195 from:
   #   and not self.data[ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT]
   # To:
   #   and not self.data.get(ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT, False)
   ```

4. **Restart HA:**
   ```bash
   ha core restart
   ```

5. **Test:**
   - Enable `switch.enable_fixed_system_supply_set_point` entity
   - Enable `number.fixed_system_supply_set_point` entity
   - Check HA logs for errors
   - Verify entities show valid states (not `unavailable`/`unknown`)

### Phase 2: Fork and Proper Fix

If Phase 1 confirms the fix works:

1. **Fork pythermiagenesis:**
   - Go to https://github.com/CJNE/pythermiagenesis
   - Click "Fork" to create your copy

2. **Clone and fix:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/pythermiagenesis.git
   cd pythermiagenesis
   # Make the fix in pythermiagenesis/__init__.py
   git add -A
   git commit -m "fix: use .get() to prevent KeyError on missing coil data"
   git push origin main
   ```

3. **Submit PR upstream:**
   - Create Pull Request to https://github.com/CJNE/pythermiagenesis
   - Reference this issue/bug description

## Installation Plan (Forked Version)

### Option A: Direct Pip Install on HA (Temporary)

After forking, install directly from your fork:

```bash
ssh root@192.168.50.11
pip install git+https://github.com/YOUR_USERNAME/pythermiagenesis.git
ha core restart
```

**Downsides:**
- Gets overwritten on HA updates
- Not persisted across container rebuilds

### Option B: Custom Component with Bundled Library (Recommended)

Fork the **thermiagenesis** custom component and bundle the fixed library:

1. **Fork thermiagenesis:**
   ```bash
   git clone https://github.com/CJNE/thermiagenesis.git
   cd thermiagenesis
   ```

2. **Modify `custom_components/thermiagenesis/manifest.json`:**

   Change the requirements to point to your fork:
   ```json
   {
     "requirements": [
       "pythermiagenesis @ git+https://github.com/YOUR_USERNAME/pythermiagenesis.git"
     ]
   }
   ```

3. **Install via HACS:**
   - Remove existing thermiagenesis from HACS
   - Add your fork as custom repository
   - Install from your fork

4. **Or install manually:**
   ```bash
   # Copy to HA config
   scp -r custom_components/thermiagenesis root@192.168.50.11:/config/custom_components/

   # Restart HA
   ssh root@192.168.50.11 "ha core restart"
   ```

### Option C: Local Package Override (Advanced)

Create a local override that HA loads instead of the pip package:

1. **Copy fixed library to HA config:**
   ```bash
   mkdir -p /config/deps/pythermiagenesis
   # Copy all files from forked pythermiagenesis to /config/deps/pythermiagenesis/
   ```

2. **Add to `configuration.yaml`:**
   ```yaml
   # This doesn't actually work for pip packages - just documenting for completeness
   ```

   Note: This approach is complex with HAOS. Option B is recommended.

## Verification Checklist

After installing the fix:

- [ ] HA logs show no `KeyError` for `coil_enable_fixed_system_supply_set_point`
- [ ] `switch.enable_fixed_system_supply_set_point` shows `off` (not `unavailable`)
- [ ] `number.fixed_system_supply_set_point` shows a temperature value
- [ ] Toggling the switch to `on` works without errors
- [ ] Setting the number value works without errors
- [ ] Other Thermia entities still work correctly
- [ ] Integration reload works without errors

## Files Modified

| File | Changes |
|------|---------|
| `pythermiagenesis/__init__.py` | Line ~194-195: `[]` → `.get(..., False)` |

## Rollback Plan

If something goes wrong:

1. **Restore backup:**
   ```bash
   ssh root@192.168.50.11
   cp /config/pythermiagenesis_init_backup.py \
      /usr/local/lib/python3.13/site-packages/pythermiagenesis/__init__.py
   ha core restart
   ```

2. **Or reinstall original:**
   ```bash
   pip install pythermiagenesis==0.1.8 --force-reinstall
   ha core restart
   ```

3. **Disable the entities:**
   - In HA, disable `switch.enable_fixed_system_supply_set_point`
   - Disable `number.fixed_system_supply_set_point`
   - This prevents the buggy code path from running
