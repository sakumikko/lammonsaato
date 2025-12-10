# Plan: Peak Power Settings UI

## Overview

Add configurable peak power avoidance settings to the web UI, allowing users to adjust:
- Daytime heater thresholds (during Helen peak hours 7-21)
- Nighttime heater thresholds (off-peak hours)
- Peak/off-peak time boundaries

## Current Implementation

Currently in `homeassistant/packages/peak_power.yaml`:
- Hardcoded values: daytime start=-10, stop=0; nighttime start=-6, stop=4
- Fixed times: daytime at 6:40, nighttime at 21:00

## Proposed Changes

### 1. Home Assistant Entities (`homeassistant/packages/peak_power.yaml`)

Add `input_number` entities for configurable thresholds:

```yaml
input_number:
  # Daytime settings (peak hours)
  peak_power_daytime_heater_start:
    name: "Peak Power: Daytime Heater Start"
    min: -15
    max: 0
    step: 1
    unit_of_measurement: "°C"
    icon: mdi:thermometer-low
    initial: -10

  peak_power_daytime_heater_stop:
    name: "Peak Power: Daytime Heater Stop"
    min: -10
    max: 10
    step: 1
    unit_of_measurement: "°C"
    icon: mdi:thermometer-high
    initial: 0

  # Nighttime settings (off-peak hours)
  peak_power_nighttime_heater_start:
    name: "Peak Power: Nighttime Heater Start"
    min: -15
    max: 0
    step: 1
    unit_of_measurement: "°C"
    icon: mdi:thermometer-low
    initial: -6

  peak_power_nighttime_heater_stop:
    name: "Peak Power: Nighttime Heater Stop"
    min: -10
    max: 10
    step: 1
    unit_of_measurement: "°C"
    icon: mdi:thermometer-high
    initial: 4

input_datetime:
  # Time boundaries
  peak_power_daytime_start:
    name: "Peak Power: Daytime Start Time"
    has_date: false
    has_time: true
    initial: "06:40:00"

  peak_power_nighttime_start:
    name: "Peak Power: Nighttime Start Time"
    has_date: false
    has_time: true
    initial: "21:00:00"
```

Update automations to use template values:

```yaml
automation:
  - id: peak_power_daytime_settings
    trigger:
      - platform: time
        at: input_datetime.peak_power_daytime_start
    action:
      - service: number.set_value
        target:
          entity_id: number.external_additional_heater_start
        data:
          value: "{{ states('input_number.peak_power_daytime_heater_start') | int }}"
      - service: number.set_value
        target:
          entity_id: number.external_additional_heater_stop
        data:
          value: "{{ states('input_number.peak_power_daytime_heater_stop') | int }}"

  - id: peak_power_nighttime_settings
    trigger:
      - platform: time
        at: input_datetime.peak_power_nighttime_start
    action:
      - service: number.set_value
        target:
          entity_id: number.external_additional_heater_start
        data:
          value: "{{ states('input_number.peak_power_nighttime_heater_start') | int }}"
      - service: number.set_value
        target:
          entity_id: number.external_additional_heater_stop
        data:
          value: "{{ states('input_number.peak_power_nighttime_heater_stop') | int }}"
```

### 2. TypeScript Types (`web-ui/src/hooks/useHomeAssistant.ts`)

Add types and state for peak power settings:

```typescript
export interface PeakPowerSettings {
  daytimeHeaterStart: number;   // Default: -10
  daytimeHeaterStop: number;    // Default: 0
  nighttimeHeaterStart: number; // Default: -6
  nighttimeHeaterStop: number;  // Default: 4
  daytimeStartTime: string;     // Default: "06:40"
  nighttimeStartTime: string;   // Default: "21:00"
}

export type PeakPowerSetting =
  | 'daytimeHeaterStart'
  | 'daytimeHeaterStop'
  | 'nighttimeHeaterStart'
  | 'nighttimeHeaterStop';

export type PeakPowerTime = 'daytimeStart' | 'nighttimeStart';
```

Add to `SystemState`:

```typescript
export interface SystemState {
  // ... existing fields
  peakPower: PeakPowerSettings;
}
```

### 3. Hook Methods (`web-ui/src/hooks/useHomeAssistant.ts`)

Add methods for updating peak power settings:

```typescript
const PEAK_POWER_ENTITY_MAP: Record<PeakPowerSetting, string> = {
  daytimeHeaterStart: 'input_number.peak_power_daytime_heater_start',
  daytimeHeaterStop: 'input_number.peak_power_daytime_heater_stop',
  nighttimeHeaterStart: 'input_number.peak_power_nighttime_heater_start',
  nighttimeHeaterStop: 'input_number.peak_power_nighttime_heater_stop',
};

const PEAK_POWER_TIME_MAP: Record<PeakPowerTime, string> = {
  daytimeStart: 'input_datetime.peak_power_daytime_start',
  nighttimeStart: 'input_datetime.peak_power_nighttime_start',
};

const setPeakPowerSetting = useCallback(async (
  setting: PeakPowerSetting,
  value: number
) => {
  const entityId = PEAK_POWER_ENTITY_MAP[setting];
  await ws.current.callService('input_number', 'set_value', {
    entity_id: entityId,
    value: value,
  });
}, []);

const setPeakPowerTime = useCallback(async (
  setting: PeakPowerTime,
  time: string  // "HH:MM" format
) => {
  const entityId = PEAK_POWER_TIME_MAP[setting];
  await ws.current.callService('input_datetime', 'set_datetime', {
    entity_id: entityId,
    time: time,
  });
}, []);
```

### 4. UI Component (`web-ui/src/components/heating/PeakPowerSettingsCard.tsx`)

Create new settings card component:

```typescript
interface PeakPowerSettingsCardProps {
  settings: PeakPowerSettings;
  onSettingChange: (setting: PeakPowerSetting, value: number) => void;
  onTimeChange: (setting: PeakPowerTime, time: string) => void;
}

export function PeakPowerSettingsCard({
  settings,
  onSettingChange,
  onTimeChange
}: PeakPowerSettingsCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Peak Power Avoidance</CardTitle>
        <CardDescription>
          Adjust additional heater thresholds to avoid Helen peak power charges (7-21)
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Daytime Section */}
        <div className="space-y-4">
          <h4 className="font-medium">Daytime (Peak Hours)</h4>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            <TimeInput
              value={settings.daytimeStartTime}
              onChange={(time) => onTimeChange('daytimeStart', time)}
              label="Start time"
            />
          </div>
          <SliderWithFeedback
            label="Heater Start Threshold"
            value={settings.daytimeHeaterStart}
            min={-15}
            max={0}
            step={1}
            unit="°C"
            onChange={(v) => onSettingChange('daytimeHeaterStart', v)}
          />
          <SliderWithFeedback
            label="Heater Stop Threshold"
            value={settings.daytimeHeaterStop}
            min={-10}
            max={10}
            step={1}
            unit="°C"
            onChange={(v) => onSettingChange('daytimeHeaterStop', v)}
          />
        </div>

        {/* Nighttime Section */}
        <div className="space-y-4">
          <h4 className="font-medium">Nighttime (Off-Peak)</h4>
          <div className="flex items-center gap-2">
            <Moon className="h-4 w-4" />
            <TimeInput
              value={settings.nighttimeStartTime}
              onChange={(time) => onTimeChange('nighttimeStart', time)}
              label="Start time"
            />
          </div>
          <SliderWithFeedback
            label="Heater Start Threshold"
            value={settings.nighttimeHeaterStart}
            min={-15}
            max={0}
            step={1}
            unit="°C"
            onChange={(v) => onSettingChange('nighttimeHeaterStart', v)}
          />
          <SliderWithFeedback
            label="Heater Stop Threshold"
            value={settings.nighttimeHeaterStop}
            min={-10}
            max={10}
            step={1}
            unit="°C"
            onChange={(v) => onSettingChange('nighttimeHeaterStop', v)}
          />
        </div>
      </CardContent>
    </Card>
  );
}
```

### 5. Integration into SettingsSheet

Add the new card to `SettingsSheet.tsx`:

```typescript
// In SettingsSheet component
<PeakPowerSettingsCard
  settings={state.peakPower}
  onSettingChange={setPeakPowerSetting}
  onTimeChange={setPeakPowerTime}
/>
```

### 6. Translations (`web-ui/src/i18n/locales/`)

Add to `en.json`:
```json
{
  "settings": {
    "peakPower": {
      "title": "Peak Power Avoidance",
      "description": "Adjust additional heater thresholds to avoid Helen peak power charges",
      "daytime": "Daytime (Peak Hours)",
      "nighttime": "Nighttime (Off-Peak)",
      "startTime": "Start time",
      "heaterStart": "Heater Start Threshold",
      "heaterStop": "Heater Stop Threshold"
    }
  }
}
```

Add to `fi.json`:
```json
{
  "settings": {
    "peakPower": {
      "title": "Tehohuippujen välttäminen",
      "description": "Säädä lisälämmittimen raja-arvoja Helenin tehomaksujen välttämiseksi",
      "daytime": "Päiväaika (huipputunnit)",
      "nighttime": "Yöaika (edullinen)",
      "startTime": "Alkamisaika",
      "heaterStart": "Lämmittimen käynnistysraja",
      "heaterStop": "Lämmittimen pysäytysraja"
    }
  }
}
```

### 7. Tests

#### Unit Tests (`tests/test_peak_power.py`)
- Add tests for template value rendering in automations
- Test that automations use `input_datetime` for triggers
- Test that actions use `input_number` states

#### E2E Tests (`web-ui/e2e/peak-power-settings.spec.ts`)
```typescript
test('should display peak power settings card', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('settings-button').click();
  await expect(page.getByText('Peak Power Avoidance')).toBeVisible();
});

test('should update daytime heater start threshold', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('settings-button').click();
  // ... interact with slider, verify API call
});
```

## Implementation Order

1. **HA Entities** - Update `peak_power.yaml` with input entities
2. **Update Automations** - Use templates instead of hardcoded values
3. **Python Tests** - Add/update tests for new YAML structure
4. **TypeScript Types** - Add interfaces and types
5. **Hook Methods** - Add setter functions to `useHomeAssistant`
6. **UI Component** - Create `PeakPowerSettingsCard`
7. **Integration** - Add to `SettingsSheet`
8. **Translations** - Add i18n strings
9. **E2E Tests** - Add Playwright tests

## Files to Modify/Create

| File | Action | Description |
|------|--------|-------------|
| `homeassistant/packages/peak_power.yaml` | Modify | Add input entities, update automations |
| `tests/test_peak_power.py` | Modify | Add tests for templated values |
| `web-ui/src/hooks/useHomeAssistant.ts` | Modify | Add types, state, methods |
| `web-ui/src/components/heating/PeakPowerSettingsCard.tsx` | Create | New settings card |
| `web-ui/src/components/heating/SettingsSheet.tsx` | Modify | Include new card |
| `web-ui/src/i18n/locales/en.json` | Modify | Add translations |
| `web-ui/src/i18n/locales/fi.json` | Modify | Add translations |
| `web-ui/e2e/peak-power-settings.spec.ts` | Create | E2E tests |

## Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│  PeakPowerSettingsCard (React UI)                            │
│  User adjusts slider for daytime heater start → -12°C        │
└──────────────────────┬───────────────────────────────────────┘
                       │ onSettingChange('daytimeHeaterStart', -12)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  useHomeAssistant.setPeakPowerSetting()                      │
│  → callService('input_number', 'set_value', {                │
│      entity_id: 'input_number.peak_power_daytime_heater_start',
│      value: -12                                              │
│    })                                                        │
└──────────────────────┬───────────────────────────────────────┘
                       │ WebSocket API
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Home Assistant                                               │
│  input_number.peak_power_daytime_heater_start = -12          │
└──────────────────────┬───────────────────────────────────────┘
                       │ At 06:40 (from input_datetime)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Automation: peak_power_daytime_settings                     │
│  → number.set_value(                                         │
│      entity_id: number.external_additional_heater_start,     │
│      value: {{ states('input_number...') }}  → -12           │
│    )                                                         │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Thermia Heat Pump                                           │
│  External additional heater start threshold = -12°C          │
└──────────────────────────────────────────────────────────────┘
```

## Validation Rules

1. **Heater Start < Heater Stop** - Start threshold must be lower than stop
2. **Daytime Start < Nighttime Start** - Daytime must begin before nighttime
3. **Time format** - Must be valid HH:MM format

## Rollback Plan

If issues arise:
1. Revert to hardcoded values in automations
2. Input entities can remain (won't affect hardcoded automations)
3. UI components can be hidden via feature flag
