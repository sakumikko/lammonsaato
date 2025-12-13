# Multi-Entity Graph Visualization Plan

## Problem Statement

Users need to visualize multiple Thermia entities on the same time-series graph to understand correlations (e.g., how PID sum relates to supply temperature difference). However, entities have vastly different scales:

| Entity | Typical Range | Unit |
|--------|---------------|------|
| Supply actual temp | 20-65 | °C |
| Supply target temp | 20-65 | °C |
| Condenser out temp | 20-70 | °C |
| Condenser in temp | 20-60 | °C |
| Temperature difference | -5 to +5 | °C |
| PID sum | -20 to +20 | - |
| Heating integral | -300 to +100 | °min |
| External heater demand | 0-100 | % |
| Compressor RPM | 0-6000 | rpm |
| Compressor gear | 1-10 | - |

Plotting these on a single Y-axis makes small-range values invisible.

## Solution: Normalized Multi-Axis Chart

### Approach: Dual Strategy

1. **Normalization Mode** (default) - All values scaled to 0-100% of their configured range
2. **Multi-Axis Mode** - Up to 3 Y-axes (left, right, far-right) for different scale groups

### Data Model

```typescript
interface EntityConfig {
  entityId: string;
  label: string;
  color: string;
  // For normalization
  minValue: number;
  maxValue: number;
  // For multi-axis
  axisGroup: 'left' | 'right' | 'right2';
  // Display
  unit: string;
  visible: boolean;
}

interface GraphConfig {
  id: string;
  name: string;
  entities: EntityConfig[];
  timeRange: '1h' | '6h' | '24h' | '7d' | '30d';
  mode: 'normalized' | 'multi-axis';
}
```

### Preset Entity Configurations

```typescript
const ENTITY_PRESETS: Record<string, Omit<EntityConfig, 'visible'>> = {
  'sensor.external_heater_pid_sum': {
    label: 'PID Sum',
    color: '#ef4444', // red
    minValue: -20,
    maxValue: 20,
    axisGroup: 'left',
    unit: '',
  },
  'sensor.heating_season_integral_value': {
    label: 'Heating Integral',
    color: '#f97316', // orange
    minValue: -300,
    maxValue: 100,
    axisGroup: 'left',
    unit: '°min',
  },
  'sensor.supply_line_temp_difference': {
    label: 'Supply ΔT',
    color: '#22c55e', // green
    minValue: -10,
    maxValue: 10,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.system_supply_line_temperature': {
    label: 'Supply Actual',
    color: '#3b82f6', // blue
    minValue: 20,
    maxValue: 65,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.system_supply_line_calculated_set_point': {
    label: 'Supply Target',
    color: '#06b6d4', // cyan
    minValue: 20,
    maxValue: 65,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.condenser_out_temperature': {
    label: 'Condenser Out',
    color: '#dc2626', // red-600
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.condenser_in_temperature': {
    label: 'Condenser In',
    color: '#2563eb', // blue-600
    minValue: 20,
    maxValue: 60,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.external_additional_heater_current_demand': {
    label: 'Heater Demand',
    color: '#a855f7', // purple
    minValue: 0,
    maxValue: 100,
    axisGroup: 'right2',
    unit: '%',
  },
  'number.external_additional_heater_start': {
    label: 'Start Threshold',
    color: '#ef4444', // red dashed
    minValue: -20,
    maxValue: 20,
    axisGroup: 'left',
    unit: '',
  },
};
```

## UI Components

### 1. EntityGraphPage (`/graphs` or `/analysis`)

```
┌─────────────────────────────────────────────────────────────┐
│  External Heater Analysis              [1h] [6h] [24h] [7d] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  100% ┤                      ╭──╮                           │
│       │                   ╭──╯  ╰──╮        ← PID Sum       │
│   50% ┤    ╭─────────────╯         ╰───                     │
│       │ ───╯                            ← Start Threshold   │
│    0% ┤─────────────────────────────────────────────────    │
│       │                                                     │
│  -50% ┤                                                     │
│       └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴───  │
│         08:00   09:00   10:00   11:00   12:00              │
│                                                             │
│  Legend: [●] PID Sum  [●] Integral  [○] Start Threshold    │
├─────────────────────────────────────────────────────────────┤
│  + Add Entity    [Normalized ▼]    [Save Graph]            │
└─────────────────────────────────────────────────────────────┘
```

### 2. Entity Picker Dialog

```
┌─────────────────────────────────────────┐
│  Add Entity to Graph                    │
├─────────────────────────────────────────┤
│  🔍 Search entities...                  │
│                                         │
│  ── External Heater ──                  │
│  [ ] sensor.external_heater_pid_sum     │
│  [✓] sensor.heating_season_integral     │
│  [ ] sensor.external_heater_demand      │
│                                         │
│  ── Supply Line ──                      │
│  [✓] sensor.supply_line_temp_diff       │
│  [ ] sensor.system_supply_line_temp     │
│                                         │
│  ── Thresholds ──                       │
│  [ ] number.external_heater_start       │
│  [ ] number.external_heater_stop        │
│                                         │
│           [Cancel]  [Add Selected]      │
└─────────────────────────────────────────┘
```

### 3. Entity Configuration Popover

Click on legend item to configure:

```
┌─────────────────────────────────┐
│  PID Sum                    [×] │
├─────────────────────────────────┤
│  Color:  [████▼]                │
│  Min:    [-200    ]             │
│  Max:    [100     ]             │
│  Axis:   [Left ▼]               │
│  Line:   [Solid ▼]              │
│                                 │
│  [Remove from graph]            │
└─────────────────────────────────┘
```

## Implementation

### Phase 1: Basic Multi-Entity Chart

1. Create `useHistoryData` hook to fetch from HA history API
2. Create `MultiEntityChart` component using Recharts
3. Support normalized mode only
4. Hardcoded entity presets for external heater analysis

### Phase 2: Entity Picker & Configuration

1. Add entity search/picker dialog
2. Allow custom min/max ranges
3. Color picker
4. Save/load graph configurations to localStorage

### Phase 3: Multi-Axis Mode

1. Support up to 3 Y-axes
2. Axis group assignment per entity
3. Smart axis scaling

### Phase 4: Advanced Features

1. Save graphs to HA (input_text entity with JSON)
2. Threshold lines (horizontal reference lines)
3. Annotations (mark events on timeline)
4. Export to CSV/PNG

## HA History API

```typescript
// Fetch history for multiple entities
const fetchHistory = async (
  entityIds: string[],
  startTime: Date,
  endTime: Date
): Promise<HistoryData[]> => {
  const params = new URLSearchParams({
    filter_entity_id: entityIds.join(','),
    minimal_response: 'true',
    no_attributes: 'true',
  });

  const response = await fetch(
    `${HA_URL}/api/history/period/${startTime.toISOString()}?${params}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );

  return response.json();
};

// Response format
type HistoryData = Array<{
  entity_id: string;
  state: string;
  last_changed: string; // ISO timestamp
}>;
```

## Normalization Formula

```typescript
const normalize = (value: number, min: number, max: number): number => {
  // Returns 0-100 percentage
  return ((value - min) / (max - min)) * 100;
};

const denormalize = (percent: number, min: number, max: number): number => {
  return min + (percent / 100) * (max - min);
};
```

## Tooltip Display

When hovering, show actual values (not normalized):

```
┌─────────────────────────┐
│  10:45:30               │
│  ─────────────────────  │
│  PID Sum:      -45.2    │
│  Integral:     -150     │
│  Supply ΔT:    -1.2°C   │
│  Start Thresh: -10      │
└─────────────────────────┘
```

## File Structure

```
web-ui/src/
  components/
    graphs/
      MultiEntityChart.tsx      # Main chart component
      EntityPicker.tsx          # Entity selection dialog
      EntityConfigPopover.tsx   # Per-entity settings
      GraphControls.tsx         # Time range, mode selector
      NormalizedTooltip.tsx     # Custom tooltip
  hooks/
    useHistoryData.ts           # Fetch HA history
    useGraphConfig.ts           # Manage graph configuration
  pages/
    GraphsPage.tsx              # /graphs route
  types/
    graphs.ts                   # Type definitions
  constants/
    entityPresets.ts            # Default entity configurations
```

## Default Graph: External Heater Analysis

Pre-configured graph available on first load:

```typescript
const DEFAULT_GRAPHS: GraphConfig[] = [
  {
    id: 'external-heater',
    name: 'External Heater Analysis',
    entities: [
      { entityId: 'sensor.external_heater_pid_sum', ...PRESETS['...'], visible: true },
      { entityId: 'sensor.heating_season_integral_value', ...PRESETS['...'], visible: true },
      { entityId: 'sensor.supply_line_temp_difference', ...PRESETS['...'], visible: true },
      { entityId: 'number.external_additional_heater_start', ...PRESETS['...'], visible: true },
      { entityId: 'sensor.external_additional_heater_current_demand', ...PRESETS['...'], visible: true },
    ],
    timeRange: '24h',
    mode: 'normalized',
  },
];
```

## Questions to Resolve

1. Should graph configs be stored in localStorage or HA (input_text)?
2. Maximum number of entities per graph? (Suggest 8 for readability)
3. Should we support real-time updates or just historical view?
4. Mobile-friendly design considerations?
