import { useState, useEffect, useCallback } from 'react';
import { getHAWebSocket, StatisticsResult, HAEntityState } from '@/lib/ha-websocket';
import { TimeRange, TIME_RANGE_CONFIG } from '@/types/analytics';

// Entity IDs for analytics data
export const ANALYTICS_ENTITIES = {
  // Layer 4: Nightly summary (main source for analytics)
  nightSummary: 'sensor.pool_heating_night_summary',
  // Layer 3: Per-block sessions
  session: 'sensor.pool_heating_session',
  // Layer 2: 15-minute aggregation
  energy15min: 'sensor.pool_heating_15min_energy',
  // Layer 1: Raw sensors (for detailed views)
  electricEnergy: 'sensor.pool_heating_electricity_daily',
  dailyCost: 'sensor.pool_heating_cost_daily',
  outdoorTemp: 'sensor.outdoor_temperature',
  poolTemp: 'sensor.pool_return_line_temperature_corrected',
  spotPrice: 'sensor.nordpool_kwh_fi_eur_3_10_0255',
} as const;

export interface NightSummaryData {
  heating_date: string;
  energy: number;        // state value (kWh)
  cost: number;          // EUR
  baseline: number;      // EUR (baseline cost for comparison)
  savings: number;       // EUR (baseline - cost)
  duration: number;      // minutes
  blocks: number;        // count of heating blocks
  pool_temp: number;     // °C
  outdoor_temp: number;  // °C
  avg_price: number;     // EUR/kWh
}

export interface DailyHistoryData {
  date: string;
  electricEnergy: number | null;
  dailyCost: number | null;
  avgOutdoorTemp: number | null;
  poolTemp: number | null;
  avgSpotPrice: number | null;
  baselineCost: number | null;
  savings: number | null;
  blocksCount: number | null;
  duration: number | null;
}

export interface HAHistoryState {
  data: DailyHistoryData[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

function getDateRange(timeRange: TimeRange): { start: Date; end: Date } {
  const end = new Date();
  end.setHours(23, 59, 59, 999);

  const start = new Date();
  const { days } = TIME_RANGE_CONFIG[timeRange];
  start.setDate(start.getDate() - days);
  start.setHours(0, 0, 0, 0);

  return { start, end };
}

/**
 * Parse night summary history into daily data
 *
 * Sensor attributes use clean names without redundant prefixes:
 * - energy: from state value (kWh)
 * - cost, baseline, savings, duration, blocks, pool_temp, outdoor_temp, avg_price
 */
function parseNightSummaryHistory(
  history: HAEntityState[]
): Map<string, NightSummaryData> {
  const result = new Map<string, NightSummaryData>();

  for (const stateRaw of history) {
    // Handle both full and minimal response formats
    // Full: { state: "...", attributes: {...} }
    // Minimal: { s: "...", a: {...} }
    const state = stateRaw as Record<string, unknown>;
    const stateValue = (state.state ?? state.s) as string | undefined;
    const attrs = (state.attributes ?? state.a) as Record<string, unknown> | undefined;

    // Skip invalid states
    if (!stateValue || !attrs) {
      continue;
    }

    const heatingDate = attrs.heating_date as string;

    if (heatingDate) {
      // Energy comes from state value, not attribute
      const energy = parseFloat(stateValue) || 0;

      result.set(heatingDate, {
        heating_date: heatingDate,
        energy: energy,
        cost: (attrs.cost as number) ?? 0,
        baseline: (attrs.baseline as number) ?? 0,
        savings: (attrs.savings as number) ?? 0,
        duration: (attrs.duration as number) ?? 0,
        blocks: (attrs.blocks as number) ?? 0,
        pool_temp: (attrs.pool_temp as number) ?? 0,
        outdoor_temp: (attrs.outdoor_temp as number) ?? 0,
        avg_price: (attrs.avg_price as number) ?? 0,
      });
    }
  }

  return result;
}

/**
 * Parse statistics for sensors that report mean/state values (temperature, price)
 */
function parseMeanStatistics(
  statistics: Record<string, StatisticsResult[]>,
  entityId: string
): Map<string, number> {
  const result = new Map<string, number>();
  const entityStats = statistics[entityId] || [];

  for (const stat of entityStats) {
    const date = new Date(stat.start).toISOString().split('T')[0];
    const value = stat.mean ?? stat.state;
    if (value !== undefined && value !== null) {
      result.set(date, value);
    }
  }

  return result;
}

export function useHAHistory(timeRange: TimeRange): HAHistoryState {
  const [data, setData] = useState<DailyHistoryData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const ws = getHAWebSocket();

      // Ensure connected
      if (!ws.connected) {
        await ws.connect();
      }

      const { start, end } = getDateRange(timeRange);

      // Fetch night summary history (primary data source)
      const summaryHistory = await ws.getHistory(
        start,
        end,
        [ANALYTICS_ENTITIES.nightSummary],
        false // Get full attributes
      );

      // Also fetch temperature and price stats for filling gaps
      const statistics = await ws.getStatistics(
        start,
        end,
        [ANALYTICS_ENTITIES.outdoorTemp, ANALYTICS_ENTITIES.poolTemp, ANALYTICS_ENTITIES.spotPrice],
        'day'
      );

      // Parse night summary data
      // WebSocket returns object with entity_id as key: {entity_id: [...states...]}
      // Handle both object and array formats
      let summaryStates: HAEntityState[] = [];
      if (summaryHistory && typeof summaryHistory === 'object') {
        if (Array.isArray(summaryHistory)) {
          // Array format (REST API style): [[...states...]]
          summaryStates = summaryHistory[0] || [];
        } else {
          // Object format (WebSocket style): {entity_id: [...states...]}
          const historyObj = summaryHistory as Record<string, HAEntityState[]>;
          summaryStates = historyObj[ANALYTICS_ENTITIES.nightSummary] || [];
        }
      }

      const nightSummaries = summaryStates.length > 0
        ? parseNightSummaryHistory(summaryStates)
        : new Map<string, NightSummaryData>();

      // Parse fallback statistics
      const outdoorMap = parseMeanStatistics(statistics, ANALYTICS_ENTITIES.outdoorTemp);
      const poolMap = parseMeanStatistics(statistics, ANALYTICS_ENTITIES.poolTemp);
      const priceMap = parseMeanStatistics(statistics, ANALYTICS_ENTITIES.spotPrice);

      // Generate array of all dates in range
      const dailyData: DailyHistoryData[] = [];
      const currentDate = new Date(start);

      while (currentDate <= end) {
        const dateStr = currentDate.toISOString().split('T')[0];
        const summary = nightSummaries.get(dateStr);

        if (summary) {
          // Use night summary data (preferred)
          dailyData.push({
            date: dateStr,
            electricEnergy: summary.energy,
            dailyCost: summary.cost,
            avgOutdoorTemp: summary.outdoor_temp,
            poolTemp: summary.pool_temp,
            avgSpotPrice: summary.avg_price,
            baselineCost: summary.baseline,
            savings: summary.savings,
            blocksCount: summary.blocks,
            duration: summary.duration,
          });
        } else {
          // Fallback to raw statistics
          dailyData.push({
            date: dateStr,
            electricEnergy: null,
            dailyCost: null,
            avgOutdoorTemp: outdoorMap.get(dateStr) ?? null,
            poolTemp: poolMap.get(dateStr) ?? null,
            avgSpotPrice: priceMap.get(dateStr) ?? null,
            baselineCost: null,
            savings: null,
            blocksCount: null,
            duration: null,
          });
        }

        currentDate.setDate(currentDate.getDate() + 1);
      }

      setData(dailyData);
    } catch (err) {
      console.error('[useHAHistory] Failed to fetch history:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch history data');
    } finally {
      setLoading(false);
    }
  }, [timeRange]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return { data, loading, error, refetch: fetchHistory };
}
