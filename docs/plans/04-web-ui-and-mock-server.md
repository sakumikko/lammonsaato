# Implementation Plan 04: Web UI & Mock Server

**Depends on:** Plan 01 (entities), Plan 02 (algorithm)
**Findings source:** Review 04

## Goal

Add cold weather mode toggle to the schedule editor, display cold weather blocks in a compact layout, and update the mock server to support the new entities and algorithm path.

## TypeScript Type Changes

### web-ui/src/types/heating.ts

Add to `ScheduleParameters` interface (~line 51):

```typescript
coldWeatherMode: boolean;
coldWindowStart: string;      // HH:MM:SS time string
coldWindowEnd: string;        // HH:MM:SS time string
coldBlockDuration: number;    // 5, 10, or 15
coldPreCirculation: number;   // 0-10 min
coldPostCirculation: number;  // 0-10 min
```

## Hook Changes (useHomeAssistant.ts)

### ENTITIES const (~line 59)

Add entity mappings:

```typescript
coldWeatherMode: 'input_boolean.pool_heating_cold_weather_mode',
coldWindowStart: 'input_datetime.pool_heating_cold_window_start',
coldWindowEnd: 'input_datetime.pool_heating_cold_window_end',
coldBlockDuration: 'input_number.pool_heating_cold_block_duration',
coldPreCirculation: 'input_number.pool_heating_cold_pre_circulation',
coldPostCirculation: 'input_number.pool_heating_cold_post_circulation',
```

### buildState (~line 442)

Parse cold weather fields into the parameters object:

```typescript
coldWeatherMode: parseBoolean(getState('coldWeatherMode')),
coldWindowStart: getState('coldWindowStart') || '21:00:00',
coldWindowEnd: getState('coldWindowEnd') || '07:00:00',
coldBlockDuration: parseNumber(getState('coldBlockDuration'), 5),
coldPreCirculation: parseNumber(getState('coldPreCirculation'), 5),
coldPostCirculation: parseNumber(getState('coldPostCirculation'), 5),
```

### setScheduleParameters (~line 709)

Add handlers for the 4 new entities when saving schedule parameters.

## ScheduleEditor.tsx Changes

### Constants (~line 34)

Add alongside existing `BLOCK_DURATIONS = [30, 45, 60]`:

```typescript
const COLD_BLOCK_DURATIONS = [5, 10, 15];
```

### Editor Panel Layout

When `coldWeatherMode` is toggled ON:
- **Show:** Cold weather toggle (always visible), window start/end time pickers, single block duration dropdown [5, 10, 15], pre/post circulation inputs, info text "1 block per hour at :05"
- **Hide:** Min block dropdown, Max block dropdown, Total hours dropdown, Cost constraint
- **Window times:** Two time picker inputs (HH:MM format) for start and end

When `coldWeatherMode` is toggled OFF:
- Show normal controls (existing behavior, unchanged)

### Toggle Implementation

Add a toggle switch at the top of the editor panel:

```tsx
<label className="flex items-center gap-2">
  <Switch
    checked={editParams.coldWeatherMode}
    onCheckedChange={(checked) => setEditParams(prev => ({
      ...prev,
      coldWeatherMode: checked
    }))}
  />
  <span>Cold Weather Mode</span>
  <Snowflake className="w-4 h-4 text-blue-400" />
</label>
```

### Save Action (~line 99)

Pass cold weather fields to `setScheduleParameters`. The service call triggers recalculation which now branches based on mode.

### Validation (~line 96)

In cold weather mode: always valid (single duration, no min/max constraint).

## SchedulePanel.tsx Changes

### Compact Layout for Many Blocks

When `coldWeatherMode` is active AND block count > 6:

```tsx
<div className={coldWeatherMode && blocks.length > 6
  ? "grid grid-cols-2 gap-2"   // compact 2-column
  : "flex flex-col gap-2"      // normal single column
}>
```

Each block in compact mode shows: time range, duration, price. No individual toggle switch (all-or-nothing for cold weather).

### Visual Distinction

When `coldWeatherMode` is active:
- Block background: `bg-blue-500/10 border-blue-500/30` instead of default
- Icon: Snowflake icon instead of Clock
- Header badge: "Cold Weather" indicator next to "Schedule"

### Data Test Attributes

Add `data-testid="cold-weather-toggle"` to the mode toggle and `data-cold-weather="true"` to the panel when active.

## Mock Server Changes

### scripts/mock_server/state_manager.py

Add defaults in `_get_default_state()`:

```python
"input_boolean.pool_heating_cold_weather_mode": {"state": "off", ...},
"input_datetime.pool_heating_cold_window_start": {"state": "21:00:00", ...},
"input_datetime.pool_heating_cold_window_end": {"state": "07:00:00", ...},
"input_number.pool_heating_cold_block_duration": {"state": "5", ...},
"input_number.pool_heating_cold_pre_circulation": {"state": "5", ...},
"input_number.pool_heating_cold_post_circulation": {"state": "5", ...},
```

### scripts/mock_server/server.py

Add fields to `ScheduleParameters` model:

```python
cold_weather_mode: bool = False
cold_window_start: str = "21:00:00"
cold_window_end: str = "07:00:00"
cold_block_duration: int = 5
cold_pre_circulation: int = 5
cold_post_circulation: int = 5
```

In `/api/calculate` handler: if `cold_weather_mode`, generate simple fixed-time blocks (no price optimization).

Fix pre-existing bug: `/api/block-enabled` hardcoded range `1-4` should be `1-10`.

### scripts/mock_server/entity_signatures.json

Add 6 new entity signatures matching the YAML definitions (mode toggle, 2 window times, 3 numbers).

## E2E Tests (web-ui/e2e/cold-weather.spec.ts)

Write BEFORE implementation (TDD). All must FAIL initially.

```typescript
import { test, expect } from '@playwright/test';

test.describe('Cold Weather Mode', () => {
  test('toggle shows cold weather controls', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();
    // Should show [5, 10, 15] duration options
    await expect(page.getByText('5 min')).toBeVisible();
    // Should hide normal mode controls
    await expect(page.getByTestId('select-min-block')).not.toBeVisible();
  });

  test('save produces 10 blocks', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();
    await page.getByTestId('schedule-editor-save').click();
    // Wait for recalculation
    const blocks = page.getByTestId('schedule-blocks');
    await expect(blocks).toHaveAttribute('data-block-count', '10');
  });

  test('blocks show short durations', async ({ page }) => {
    // After cold weather schedule calculated
    await expect(page.getByText('5min').first()).toBeVisible();
  });

  test('switching back to normal restores controls', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('schedule-editor-toggle').click();
    await page.getByTestId('cold-weather-toggle').click();  // ON
    await page.getByTestId('cold-weather-toggle').click();  // OFF
    await expect(page.getByTestId('select-min-block')).toBeVisible();
  });
});
```

## Implementation Order

1. Write E2E tests (must fail)
2. Add TypeScript types
3. Update useHomeAssistant.ts (entity mappings, buildState, setScheduleParameters)
4. Update ScheduleEditor.tsx (toggle, conditional controls)
5. Update SchedulePanel.tsx (compact layout, visual distinction)
6. Update mock server (entities, calculate endpoint)
7. Run E2E tests (must pass)
8. Run full regression
