/**
 * Hook for fetching pool heating on/off periods from binary_sensor.pool_heating_active
 * Returns time ranges for when heating was active to display as chart overlays
 */

import { useState, useCallback } from 'react';
import { getHAWebSocket } from '@/lib/ha-websocket';
import { TimeRange } from '@/types/graphs';

const HEATING_ACTIVE_ENTITY = 'binary_sensor.pool_heating_active';

const TIME_RANGE_HOURS: Record<TimeRange, number> = {
  '1h': 1,
  '6h': 6,
  '24h': 24,
  '7d': 168,
  '30d': 720,
};

export interface HeatingPeriod {
  start: number;  // timestamp ms
  end: number;    // timestamp ms
}

export interface UseHeatingPeriodsReturn {
  periods: HeatingPeriod[];
  loading: boolean;
  error: string | null;
  fetchPeriods: (timeRange: TimeRange) => Promise<void>;
}

interface HistoryState {
  state: string;
  last_updated: string;
  // Compact format alternatives
  s?: string;
  lu?: string | number;
}

function parseHistoryToPeriods(states: HistoryState[], rangeEnd: Date): HeatingPeriod[] {
  const periods: HeatingPeriod[] = [];
  let currentPeriodStart: number | null = null;

  for (const state of states) {
    const stateValue = state.state ?? state.s;
    const lastUpdated = state.last_updated ?? state.lu;

    let timestamp: number;
    if (typeof lastUpdated === 'number') {
      timestamp = lastUpdated * 1000; // Unix seconds to ms
    } else {
      timestamp = new Date(lastUpdated as string).getTime();
    }

    if (stateValue === 'on') {
      // Heating turned on
      if (currentPeriodStart === null) {
        currentPeriodStart = timestamp;
      }
    } else {
      // Heating turned off (or unavailable/unknown)
      if (currentPeriodStart !== null) {
        periods.push({
          start: currentPeriodStart,
          end: timestamp,
        });
        currentPeriodStart = null;
      }
    }
  }

  // If still heating at end of range, close the period at range end
  if (currentPeriodStart !== null) {
    periods.push({
      start: currentPeriodStart,
      end: rangeEnd.getTime(),
    });
  }

  return periods;
}

export function useHeatingPeriods(): UseHeatingPeriodsReturn {
  const [periods, setPeriods] = useState<HeatingPeriod[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPeriods = useCallback(async (timeRange: TimeRange) => {
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

      const history = await ws.getHistory(start, end, [HEATING_ACTIVE_ENTITY], true);

      // Parse history response
      let states: HistoryState[] = [];

      if (Array.isArray(history) && history.length > 0 && Array.isArray(history[0])) {
        // Array format: [[entity_states]]
        states = history[0] as HistoryState[];
      } else if (history && typeof history === 'object' && !Array.isArray(history)) {
        // Object format: { entity_id: [states] }
        const entityHistory = (history as Record<string, HistoryState[]>)[HEATING_ACTIVE_ENTITY];
        if (entityHistory) {
          states = entityHistory;
        }
      }

      const parsedPeriods = parseHistoryToPeriods(states, end);
      setPeriods(parsedPeriods);
    } catch (err) {
      console.error('[useHeatingPeriods] Failed to fetch heating periods:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch heating periods');
      setPeriods([]);
    } finally {
      setLoading(false);
    }
  }, []);

  return { periods, loading, error, fetchPeriods };
}
