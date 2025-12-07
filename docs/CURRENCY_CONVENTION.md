# Currency & Price Convention

This document defines the consistent handling of prices and costs throughout the codebase.

## TL;DR

| What | Storage Unit | Display Unit | Example |
|------|--------------|--------------|---------|
| **Electricity prices** | cents/kWh | `X.XX c/kWh` | 2.60 c/kWh |
| **Block/session costs** | EUR | `€X.XX` | €0.13 |
| **Daily/monthly costs** | EUR | `€X.XX` | €2.50 |
| **Max cost limit** | EUR | `€X.XX` | €2.00 |

## Data Flow

```
Nordpool Sensor (EUR/kWh)
        │
        │ × 100
        ▼
Pyscript stores block price (cents/kWh)
        │
        │ direct read
        ▼
Web UI displays (cents/kWh)
```

## Layer-by-Layer Specification

### 1. External Sources

| Source | Format | Example |
|--------|--------|---------|
| Nordpool sensor (`sensor.nordpool_kwh_fi_eur_3_10_0255`) | EUR/kWh | `0.026` |

### 2. Home Assistant Entities (Storage Layer)

| Entity Pattern | Unit | Type | Example |
|----------------|------|------|---------|
| `input_number.pool_heat_block_N_price` | cents/kWh | float | `2.60` |
| `input_number.pool_heat_block_N_cost` | EUR | float | `0.065` |
| `input_number.pool_heating_max_cost_eur` | EUR | float | `2.00` |
| `input_number.pool_heating_total_cost` | EUR | float | `0.52` |
| `sensor.pool_heating_cost_daily` | EUR | float | `1.23` |
| `sensor.pool_heating_cost_monthly` | EUR | float | `45.67` |

**Naming Convention:**
- Prices: suffix `_price` (always cents/kWh)
- Costs: suffix `_cost` or `_cost_eur` (always EUR)

### 3. Pyscript (Calculation Layer)

```python
# Nordpool returns EUR/kWh, convert to cents for storage
block_price_cents = nordpool_eur_per_kwh * 100

# Store in HA entity
service.call("input_number", "set_value",
    entity_id=block_price_entity,
    value=round(block_price_cents, 2))

# Cost calculation (in EUR)
energy_kwh = power_kw * duration_hours
cost_eur = energy_kwh * nordpool_eur_per_kwh  # Keep in EUR
```

### 4. TypeScript Types

```typescript
interface PriceBlock {
  price: number;      // cents/kWh
  costEur: number;    // EUR
}

interface ScheduleParameters {
  maxCostEur: number | null;  // EUR, null = no limit
}
```

### 5. Web UI (Display Layer)

```typescript
// Nordpool sensor returns EUR/kWh, convert to cents
currentPrice: parseNumber(get(ENTITIES.nordpoolPrice)) * 100,

// Block prices already in cents, use directly
price: parseNumber(get(blockEntities.price)),

// Display formatting
<span>{price.toFixed(2)} c/kWh</span>
<span>€{costEur.toFixed(2)}</span>
```

### 6. Debug Scripts

```python
# fetch_blocks.py - prices are CENTS, no conversion needed
price_display = f"{price_value:.2f}c"

# Nordpool is EUR, convert to cents for display
nordpool_cents = float(nordpool_state) * 100
print(f"Current price: {nordpool_cents:.2f} c/kWh")
```

## Conversion Rules

| From → To | Operation |
|-----------|-----------|
| Nordpool EUR/kWh → cents/kWh | × 100 |
| cents/kWh → EUR/kWh | ÷ 100 |
| EUR → display | `€{value:.2f}` |
| cents → display | `{value:.2f} c/kWh` |

## Common Mistakes to Avoid

1. **Double conversion**: Don't multiply by 100 twice
2. **Missing conversion**: Nordpool is EUR, must convert to cents
3. **Wrong suffix**: Use `_eur` for EUR values, `_price` for cents
4. **Display confusion**: Always include unit (c/kWh or €)

## Validation Checklist

When adding price/cost handling:

- [ ] Is the source in EUR or cents?
- [ ] Is conversion needed?
- [ ] Is the storage entity named correctly?
- [ ] Does the display include the unit?
- [ ] Are TypeScript types documented?
