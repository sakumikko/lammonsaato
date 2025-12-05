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
  total_energy: number;
  total_cost: number;
  total_duration: number;
  blocks_count: number;
  pool_temp_final: number;
  outdoor_temp_avg: number;
  avg_price: number;
  avg_window_price: number;
  baseline_cost: number;
  savings: number;
  savings_percent: number;
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
 */
function parseNightSummaryHistory(
  history: HAEntityState[]
): Map<string, NightSummaryData> {
  const result = new Map<string, NightSummaryData>();

  for (const state of history) {
    const attrs = state.attributes as Record<string, unknown>;
    const heatingDate = attrs.heating_date as string;

    if (heatingDate) {
      result.set(heatingDate, {
        heating_date: heatingDate,
        total_energy: (attrs.total_energy as number) ?? 0,
        total_cost: (attrs.total_cost as number) ?? 0,
        total_duration: (attrs.total_duration as number) ?? 0,
        blocks_count: (attrs.blocks_count as number) ?? 0,
        pool_temp_final: (attrs.pool_temp_final as number) ?? 0,
        outdoor_temp_avg: (attrs.outdoor_temp_avg as number) ?? 0,
        avg_price: (attrs.avg_price as number) ?? 0,
        avg_window_price: (attrs.avg_window_price as number) ?? 0,
        baseline_cost: (attrs.baseline_cost as number) ?? 0,
        savings: (attrs.savings as number) ?? 0,
        savings_percent: (attrs.savings_percent as number) ?? 0,
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
      const nightSummaries = summaryHistory[0]
        ? parseNightSummaryHistory(summaryHistory[0])
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
            electricEnergy: summary.total_energy,
            dailyCost: summary.total_cost,
            avgOutdoorTemp: summary.outdoor_temp_avg,
            poolTemp: summary.pool_temp_final,
            avgSpotPrice: summary.avg_price,
            baselineCost: summary.baseline_cost,
            savings: summary.savings,
            blocksCount: summary.blocks_count,
            duration: summary.total_duration,
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
