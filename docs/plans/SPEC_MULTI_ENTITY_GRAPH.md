# Multi-Entity Graph - Implementation Specification

## Overview

This document provides the detailed implementation specification for the Multi-Entity Graph feature.
See [PLAN_MULTI_ENTITY_GRAPH.md](./PLAN_MULTI_ENTITY_GRAPH.md) for the high-level design and requirements.

## Phase 1 Scope (MVP)

Phase 1 delivers a working multi-entity graph with:
- Normalized view (0-100% scaling)
- Pre-configured "External Heater Analysis" graph
- Time range selection (1h, 6h, 24h, 7d)
- Tooltip showing actual values
- Legend with entity visibility toggles

**Not in Phase 1:** Entity picker dialog, custom min/max, multi-axis mode, save/load configs.

---

## File Structure

```
web-ui/src/
├── types/
│   └── graphs.ts                    # Type definitions
├── constants/
│   └── entityPresets.ts             # Entity configurations
├── hooks/
│   └── useHistoryData.ts            # Fetch HA history for multiple entities
├── components/
│   └── graphs/
│       ├── MultiEntityChart.tsx     # Main chart component
│       ├── ChartLegend.tsx          # Legend with visibility toggles
│       ├── ChartTooltip.tsx         # Custom tooltip
│       └── TimeRangeSelector.tsx    # Time range buttons
├── pages/
│   └── GraphsPage.tsx               # /graphs route
└── App.tsx                          # Add route
```

---

## Type Definitions

### `types/graphs.ts`

```typescript
export type TimeRange = '1h' | '6h' | '24h' | '7d' | '30d';
export type AxisGroup = 'left' | 'right' | 'right2' | 'delta' | 'control' | 'percent';
export type ChartMode = 'normalized' | 'multi-axis';

export interface EntityConfig {
  entityId: string;
  label: string;
  color: string;
  minValue: number;
  maxValue: number;
  axisGroup: AxisGroup;
  unit: string;
  visible: boolean;
}

export interface GraphConfig {
  id: string;
  name: string;
  entities: EntityConfig[];
  timeRange: TimeRange;
  mode: ChartMode;
}

export interface HistoryPoint {
  timestamp: number;        // Unix ms
  entityId: string;
  rawValue: number | null;  // Original value
  normalizedValue: number | null;  // 0-100 scaled
}

export interface MultiEntityHistoryData {
  entities: Record<string, EntityConfig>;
  // Aligned time series: each entry has same timestamp for all entities
  series: Array<{
    timestamp: number;
    values: Record<string, { raw: number | null; normalized: number | null }>;
  }>;
  timeRange: { start: Date; end: Date };
}
```

---

## Constants

### `constants/entityPresets.ts`

```typescript
import { EntityConfig, AxisGroup } from '@/types/graphs';

type EntityPreset = Omit<EntityConfig, 'visible'>;

export const ENTITY_PRESETS: Record<string, EntityPreset> = {
  // Control values (left axis)
  'sensor.external_heater_pid_sum': {
    entityId: 'sensor.external_heater_pid_sum',
    label: 'PID Sum',
    color: '#ef4444', // red
    minValue: -20,
    maxValue: 20,
    axisGroup: 'control',
    unit: '',
  },
  'sensor.heating_season_integral_value': {
    entityId: 'sensor.heating_season_integral_value',
    label: 'Heating Integral',
    color: '#f97316', // orange
    minValue: -300,
    maxValue: 100,
    axisGroup: 'control',
    unit: '°min',
  },
  'number.external_additional_heater_start': {
    entityId: 'number.external_additional_heater_start',
    label: 'Start Threshold',
    color: '#dc2626', // red-600
    minValue: -20,
    maxValue: 20,
    axisGroup: 'control',
    unit: '',
  },
  'number.external_additional_heater_stop': {
    entityId: 'number.external_additional_heater_stop',
    label: 'Stop Threshold',
    color: '#16a34a', // green-600
    minValue: -20,
    maxValue: 20,
    axisGroup: 'control',
    unit: '',
  },

  // Delta temperatures
  'sensor.supply_line_temp_difference': {
    entityId: 'sensor.supply_line_temp_difference',
    label: 'Supply ΔT',
    color: '#22c55e', // green
    minValue: -10,
    maxValue: 10,
    axisGroup: 'delta',
    unit: '°C',
  },
  'sensor.pool_heat_exchanger_delta_t': {
    entityId: 'sensor.pool_heat_exchanger_delta_t',
    label: 'Condenser ΔT',
    color: '#f59e0b', // amber
    minValue: -10,
    maxValue: 10,
    axisGroup: 'delta',
    unit: '°C',
  },

  // Temperature values (right axis)
  'sensor.system_supply_line_temperature': {
    entityId: 'sensor.system_supply_line_temperature',
    label: 'Supply Actual',
    color: '#3b82f6', // blue
    minValue: 20,
    maxValue: 65,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.system_supply_line_calculated_set_point': {
    entityId: 'sensor.system_supply_line_calculated_set_point',
    label: 'Supply Target',
    color: '#06b6d4', // cyan
    minValue: 20,
    maxValue: 65,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.condenser_out_temperature': {
    entityId: 'sensor.condenser_out_temperature',
    label: 'Condenser Out',
    color: '#dc2626', // red-600
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.condenser_in_temperature': {
    entityId: 'sensor.condenser_in_temperature',
    label: 'Condenser In',
    color: '#2563eb', // blue-600
    minValue: 20,
    maxValue: 60,
    axisGroup: 'right',
    unit: '°C',
  },

  // Percentage values
  'sensor.external_additional_heater_current_demand': {
    entityId: 'sensor.external_additional_heater_current_demand',
    label: 'Heater Demand',
    color: '#a855f7', // purple
    minValue: 0,
    maxValue: 100,
    axisGroup: 'percent',
    unit: '%',
  },
};

export const DEFAULT_GRAPHS: GraphConfig[] = [
  {
    id: 'external-heater-analysis',
    name: 'External Heater Analysis',
    entities: [
      { ...ENTITY_PRESETS['sensor.external_heater_pid_sum'], visible: true },
      { ...ENTITY_PRESETS['sensor.heating_season_integral_value'], visible: true },
      { ...ENTITY_PRESETS['sensor.supply_line_temp_difference'], visible: true },
      { ...ENTITY_PRESETS['number.external_additional_heater_start'], visible: true },
      { ...ENTITY_PRESETS['sensor.external_additional_heater_current_demand'], visible: true },
    ],
    timeRange: '24h',
    mode: 'normalized',
  },
  {
    id: 'temperature-analysis',
    name: 'Temperature Analysis',
    entities: [
      { ...ENTITY_PRESETS['sensor.system_supply_line_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.system_supply_line_calculated_set_point'], visible: true },
      { ...ENTITY_PRESETS['sensor.supply_line_temp_difference'], visible: true },
      { ...ENTITY_PRESETS['sensor.condenser_out_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.condenser_in_temperature'], visible: true },
    ],
    timeRange: '24h',
    mode: 'normalized',
  },
];
```

---

## Hook: useHistoryData

### `hooks/useHistoryData.ts`

```typescript
import { useState, useCallback } from 'react';
import { getHAWebSocket } from '@/lib/ha-websocket';
import { EntityConfig, TimeRange, MultiEntityHistoryData } from '@/types/graphs';

const TIME_RANGE_HOURS: Record<TimeRange, number> = {
  '1h': 1,
  '6h': 6,
  '24h': 24,
  '7d': 168,
  '30d': 720,
};

/**
 * Normalize a value to 0-100 based on configured min/max
 */
export function normalize(value: number, min: number, max: number): number {
  if (max === min) return 50; // Avoid division by zero
  const normalized = ((value - min) / (max - min)) * 100;
  return Math.max(0, Math.min(100, normalized)); // Clamp to 0-100
}

/**
 * Denormalize a 0-100 value back to original scale
 */
export function denormalize(percent: number, min: number, max: number): number {
  return min + (percent / 100) * (max - min);
}

export interface UseHistoryDataReturn {
  data: MultiEntityHistoryData | null;
  loading: boolean;
  error: string | null;
  fetchData: (entities: EntityConfig[], timeRange: TimeRange) => Promise<void>;
}

export function useHistoryData(): UseHistoryDataReturn {
  const [data, setData] = useState<MultiEntityHistoryData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (entities: EntityConfig[], timeRange: TimeRange) => {
    if (entities.length === 0) {
      setData(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const ws = getHAWebSocket();
      if (!ws.connected) {
        await ws.connect();
      }

      const hours = TIME_RANGE_HOURS[timeRange];
      const end = new Date();
      const start = new Date(end.getTime() - hours * 60 * 60 * 1000);

      const entityIds = entities.map(e => e.entityId);
      const history = await ws.getHistory(start, end, entityIds, true);

      // Parse history data per entity
      const entityData: Record<string, Array<{ timestamp: number; value: number | null }>> = {};

      // Handle both array and object response formats
      if (Array.isArray(history)) {
        // Array format: [[entity1_states], [entity2_states], ...]
        history.forEach((entityHistory, idx) => {
          if (!entityHistory) return;
          const entityId = entityIds[idx];
          entityData[entityId] = parseHistoryStates(entityHistory);
        });
      } else {
        // Object format: { entity_id: [states], ... }
        for (const [entityId, states] of Object.entries(history)) {
          entityData[entityId] = parseHistoryStates(states);
        }
      }

      // Align time series to common timestamps
      const aligned = alignTimeSeries(entityData, entities, start, end);

      setData({
        entities: Object.fromEntries(entities.map(e => [e.entityId, e])),
        series: aligned,
        timeRange: { start, end },
      });
    } catch (err) {
      console.error('[useHistoryData] Failed to fetch history:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch history');
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, fetchData };
}

function parseHistoryStates(states: unknown[]): Array<{ timestamp: number; value: number | null }> {
  return states.map(state => {
    const s = state as Record<string, unknown>;
    const stateValue = (s.state ?? s.s) as string;
    const lastUpdated = s.last_updated ?? s.lu;

    let timestamp: number;
    if (typeof lastUpdated === 'number') {
      timestamp = lastUpdated * 1000; // Unix seconds to ms
    } else {
      timestamp = new Date(lastUpdated as string).getTime();
    }

    const value = stateValue !== 'unknown' && stateValue !== 'unavailable'
      ? parseFloat(stateValue)
      : null;

    return { timestamp, value: isNaN(value as number) ? null : value };
  });
}

function alignTimeSeries(
  entityData: Record<string, Array<{ timestamp: number; value: number | null }>>,
  entities: EntityConfig[],
  start: Date,
  end: Date,
): MultiEntityHistoryData['series'] {
  // Collect all unique timestamps
  const allTimestamps = new Set<number>();
  for (const data of Object.values(entityData)) {
    for (const point of data) {
      allTimestamps.add(point.timestamp);
    }
  }

  // Sort timestamps
  const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);

  // For each timestamp, get value for each entity (use last known value)
  const entityConfigs = Object.fromEntries(entities.map(e => [e.entityId, e]));
  const lastValues: Record<string, number | null> = {};

  return sortedTimestamps.map(timestamp => {
    const values: Record<string, { raw: number | null; normalized: number | null }> = {};

    for (const entity of entities) {
      const entityPoints = entityData[entity.entityId] || [];

      // Find the most recent value at or before this timestamp
      let value: number | null = lastValues[entity.entityId] ?? null;
      for (const point of entityPoints) {
        if (point.timestamp <= timestamp) {
          value = point.value;
        } else {
          break;
        }
      }
      lastValues[entity.entityId] = value;

      const config = entityConfigs[entity.entityId];
      const normalized = value !== null
        ? normalize(value, config.minValue, config.maxValue)
        : null;

      values[entity.entityId] = { raw: value, normalized };
    }

    return { timestamp, values };
  });
}
```

---

## Components

### `components/graphs/MultiEntityChart.tsx`

Uses Recharts `LineChart` with:
- X-axis: timestamps
- Y-axis: 0-100% (normalized mode)
- One `Line` per visible entity
- Custom tooltip showing actual values
- Step-after interpolation (matches HA behavior)

```typescript
// Key props
interface MultiEntityChartProps {
  data: MultiEntityHistoryData;
  visibleEntities: Set<string>;
  onToggleEntity: (entityId: string) => void;
}
```

### `components/graphs/ChartTooltip.tsx`

Custom tooltip that shows:
- Timestamp
- Actual value (denormalized) for each entity
- Unit for each entity

### `components/graphs/ChartLegend.tsx`

Legend items that:
- Show entity color and label
- Click to toggle visibility
- Show current value (latest)

### `components/graphs/TimeRangeSelector.tsx`

Button group for time range selection: 1h, 6h, 24h, 7d

---

## Page

### `pages/GraphsPage.tsx`

```typescript
export function GraphsPage() {
  const [activeGraph, setActiveGraph] = useState<GraphConfig>(DEFAULT_GRAPHS[0]);
  const [visibleEntities, setVisibleEntities] = useState<Set<string>>(
    new Set(DEFAULT_GRAPHS[0].entities.filter(e => e.visible).map(e => e.entityId))
  );
  const { data, loading, error, fetchData } = useHistoryData();

  useEffect(() => {
    const visibleConfigs = activeGraph.entities.filter(e => visibleEntities.has(e.entityId));
    fetchData(visibleConfigs, activeGraph.timeRange);
  }, [activeGraph.id, activeGraph.timeRange, visibleEntities]);

  // ... render
}
```

---

## Route

Add to `App.tsx`:

```typescript
import GraphsPage from './pages/GraphsPage';

// In Routes:
<Route path="/graphs" element={<GraphsPage />} />
```

---

## Data-testid Attributes

For E2E testing, add these data-testid attributes:

| Component | Attribute | Purpose |
|-----------|-----------|---------|
| GraphsPage container | `graphs-page` | Page identification |
| Graph selector | `graph-selector` | Switch between graphs |
| Time range button | `time-range-{range}` | e.g., `time-range-24h` |
| Chart container | `multi-entity-chart` | Main chart |
| Legend item | `legend-{entityId}` | Toggle visibility |
| Loading indicator | `chart-loading` | Loading state |
| Error message | `chart-error` | Error state |

---

## Mock Server Requirements

The mock server (`scripts/mock_server/server.py`) needs to support:

1. **History endpoint:** `/api/history/period/{start}` with `filter_entity_id` param
2. **Return format:** Array of arrays with entity states
3. **Test entities:** Include the preset entities with realistic sample data

---

## Acceptance Criteria

### Phase 1 MVP

1. Navigate to `/graphs` shows the Graphs page
2. Default "External Heater Analysis" graph loads automatically
3. Time range selector changes the data range (1h, 6h, 24h, 7d)
4. Chart displays normalized values (0-100% Y-axis)
5. Tooltip shows actual values with units
6. Legend shows all entities with visibility toggles
7. Clicking legend item toggles line visibility
8. Loading state shown while fetching
9. Error state shown if fetch fails
10. Responsive layout works on mobile

---

## Test Plan

See `web-ui/e2e/multi-entity-graph.spec.ts` for E2E tests.
See `web-ui/src/__tests__/normalize.test.ts` for unit tests.
