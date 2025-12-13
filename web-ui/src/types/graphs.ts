/**
 * Type definitions for multi-entity graph feature
 */

export type TimeRange = '1h' | '6h' | '24h' | '7d' | '30d';
export type AxisGroup =
  | 'left'
  | 'right'
  | 'right2'
  | 'delta'
  | 'control'
  | 'percent'
  | 'brine'
  | 'rpm'
  | 'gear'
  | 'refrigerant'
  | 'dhw'
  | 'outdoor'
  | 'pool'
  | 'power'
  | 'cost'
  | 'price'
  | 'raw'
  | 'pressure'
  | 'energy';
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
  timestamp: number; // Unix ms
  entityId: string;
  rawValue: number | null;
  normalizedValue: number | null;
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

// Type for ENTITY_PRESETS entries (without visible property)
export type EntityPreset = Omit<EntityConfig, 'visible'>;
