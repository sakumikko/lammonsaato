/**
 * Hook for fetching history data for multiple entities from Home Assistant
 */

import { useState, useCallback } from 'react';
import { getHAWebSocket, HAEntityState } from '@/lib/ha-websocket';
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

interface ParsedHistoryPoint {
  timestamp: number;
  value: number | null;
}

function parseHistoryStates(states: unknown[]): ParsedHistoryPoint[] {
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

    let value: number | null = null;
    if (stateValue !== 'unknown' && stateValue !== 'unavailable') {
      const parsed = parseFloat(stateValue);
      if (!isNaN(parsed)) {
        value = parsed;
      }
    }

    return { timestamp, value };
  });
}

function alignTimeSeries(
  entityData: Record<string, ParsedHistoryPoint[]>,
  entities: EntityConfig[],
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

  // Create lookup for entity configs
  const entityConfigs = Object.fromEntries(entities.map(e => [e.entityId, e]));

  // Track last known values for each entity
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
      const entityData: Record<string, ParsedHistoryPoint[]> = {};

      // Handle both array and object response formats
      if (Array.isArray(history)) {
        // Array format: [[entity1_states], [entity2_states], ...]
        history.forEach((entityHistory, idx) => {
          if (!entityHistory) return;
          const entityId = entityIds[idx];
          entityData[entityId] = parseHistoryStates(entityHistory as unknown[]);
        });
      } else if (history && typeof history === 'object') {
        // Object format: { entity_id: [states], ... }
        for (const [entityId, states] of Object.entries(history as Record<string, HAEntityState[]>)) {
          entityData[entityId] = parseHistoryStates(states as unknown[]);
        }
      }

      // Align time series to common timestamps
      const aligned = alignTimeSeries(entityData, entities);

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
