# Pool Thermal Model Calibration Plan

**Status:** Waiting for data collection (1 week minimum)
**Start Date:** 2025-12-07
**Review After:** 2025-12-14

## Current State

The thermal calibration system is deployed with **initial estimates**:

| Parameter | Current Value | Source |
|-----------|---------------|--------|
| Cooling τ | 20 hours | Theoretical estimate |
| Heating rate | 0.4 °C/hour | Based on 18kW thermal, 70% mixing |
| Loss rate (idle) | 0.15 °C/hour | Rough estimate |
| Confidence decay | 12 hours to zero | Arbitrary |

These need calibration from real measurements.

## Data Being Collected

The automations record daily:

| Time | Measurement | Entity |
|------|-------------|--------|
| 20:55 | Pre-heating true temp | `input_number.pool_true_temp_pre_heating` |
| 07:55 | Post-heating true temp | `input_number.pool_true_temp_post_heating` |
| 14:25 | Daytime true temp | `input_number.pool_true_temp_daytime` |

Plus events fired to `pool_thermal_calibration` with full context.

## Analysis Plan (After 1 Week)

### Phase 1: Extract Historical Data

```bash
# Query HA for calibration history
curl -s -H "Authorization: Bearer $HA_TOKEN" \
  "$HA_URL/api/history/period/2025-12-07T00:00:00?filter_entity_id=input_number.pool_true_temp_pre_heating,input_number.pool_true_temp_post_heating,input_number.pool_true_temp_daytime"
```

Expected data format:
```
Date       Pre-Heat  Post-Heat  Daytime  Heating Hours
2025-12-07   24.2      25.1      24.8       2.0
2025-12-08   24.5      25.3      25.0       2.0
...
```

### Phase 2: Calibrate Cooling Time Constant (τ)

**Method:** Measure temperature drop between post-heating and next pre-heating.

```
τ = -Δt / ln((T_pre - T_room) / (T_post - T_room))

Where:
  T_post = post-heating temp (e.g., 25.3°C at 08:00)
  T_pre  = next pre-heating temp (e.g., 24.5°C at 20:30)
  T_room = 20°C
  Δt     = 12.5 hours
```

**Example:**
```
τ = -12.5 / ln((24.5 - 20) / (25.3 - 20))
τ = -12.5 / ln(4.5 / 5.3)
τ = -12.5 / (-0.164)
τ ≈ 76 hours  (much slower cooling than estimated!)
```

### Phase 3: Calibrate Heating Efficiency

**Method:** Compare pre-heating vs post-heating temps with known heating duration.

```
heating_rate = (T_post - T_pre + overnight_loss) / heating_hours

Where:
  overnight_loss = estimated from τ for non-heating hours
```

**Example:**
```
If τ = 76 hours, loss over 10h idle = 5°C × (1 - e^(-10/76)) ≈ 0.6°C
heating_rate = (25.3 - 24.5 + 0.6) / 2.0 = 0.7 °C/hour
```

### Phase 4: Validate with Daytime Readings

Use daytime (14:00) readings to validate cooling model:
- Predict 14:00 temp from 08:00 post-heating using calibrated τ
- Compare prediction to actual
- Adjust τ if systematic error

### Phase 5: Update Model Parameters

After calibration, update:

1. **`scripts/pyscript/pool_heating.py`** - Update constants:
   ```python
   TAU_COOL_HOURS = 76  # Calibrated from data
   HEATING_RATE = 0.7   # °C per hour
   LOSS_RATE = 0.08     # °C per hour (derived from τ)
   ```

2. **`tests/test_thermal_calibration.py`** - Update test constants to match

3. **Confidence decay** - Adjust based on how accurate predictions are over time

## Prediction Models to Implement

### 1. True Temperature Estimator (exists, needs calibration)

**Current:** `estimate_true_pool_temp()` in pyscript
**Improvement:** Use calibrated τ instead of hardcoded 20 hours

### 2. Required Heating Hours Calculator

**New function needed:**
```python
def calculate_required_heating(current_temp: float, target_temp: float) -> float:
    """
    Calculate heating hours needed to reach target temperature.

    Accounts for:
    - Heat loss during overnight window
    - Heating efficiency (calibrated)
    - Maximum available heating time
    """
    # Iterative solver since loss depends on final temp
```

### 3. End Temperature Predictor (exists, needs calibration)

**Current:** `predict_temp_after_heating()` in pyscript
**Improvement:** Use calibrated heating_rate and loss_rate

### 4. Optimal Heating Duration Recommender

**New feature:**
```python
def recommend_heating_duration(
    current_temp: float,
    target_temp: float,
    prices: list[float]
) -> tuple[float, float]:
    """
    Recommend heating duration considering:
    - Temperature goal
    - Price constraints
    - Diminishing returns (can't heat forever)

    Returns: (recommended_hours, estimated_cost)
    """
```

## Success Criteria

After calibration, predictions should be:
- **True temp estimate:** Within ±0.5°C of actual (measured by circulation)
- **Post-heating prediction:** Within ±0.5°C of actual
- **Required heating calc:** Within ±15 min of actual needed

## Data Collection Checklist

Track these daily to ensure data quality:

- [ ] Pre-heating calibration ran (check logbook)
- [ ] Post-heating calibration ran
- [ ] Daytime calibration ran (optional)
- [ ] Heating hours recorded correctly
- [ ] No sensor failures during calibration windows

## Review Meeting Agenda (After 1 Week)

1. Export collected data from HA
2. Calculate actual τ from cooling curves
3. Calculate actual heating rate
4. Compare predictions vs actuals
5. Update model parameters
6. Re-run tests with new parameters
7. Deploy updated model
