import { useState, useEffect, useCallback } from 'react';
import { getHAWebSocket, HAEntityState } from '@/lib/ha-websocket';

export interface PoolTempDataPoint {
  timestamp: Date;
  temperature: number;
  isSmoothed: boolean; // true if this point was adjusted
}

export interface PoolTempHistoryState {
  data: PoolTempDataPoint[];
  rawData: PoolTempDataPoint[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Spike detection and smoothing for pool temperature data.
 *
 * Observed calibration spike pattern:
 * - Occurs at ~21:00 (heating window start) and ~08:00 (heating window end)
 * - Baseline: 24-26°C, Peak: 34-35°C
 * - Fast rise (~10 min), slow decay (~3.5 hours)
 * - Caused by heat exchanger backwash during thermal calibration
 *
 * Strategy:
 * 1. Use heating status to identify valid measurement periods
 * 2. During heating: show actual measured temps (valid readings)
 * 3. During non-heating: detect and remove calibration spikes
 * 4. Interpolate smoothly between valid readings
 */

export interface HeatingPeriod {
  start: Date;
  end: Date;
}

function smoothSpikes(
  data: PoolTempDataPoint[],
  heatingPeriods: HeatingPeriod[] = []
): PoolTempDataPoint[] {
  if (data.length < 3) return data;

  // Check if a timestamp is during active heating
  const isDuringHeating = (timestamp: Date): boolean => {
    for (const period of heatingPeriods) {
      if (timestamp >= period.start && timestamp <= period.end) {
        return true;
      }
    }
    return false;
  };

  // Find baseline temperature (stable readings before any spike)
  const findBaseline = (idx: number): number => {
    // Look back for stable readings below 26°C
    let sum = 0;
    let count = 0;
    for (let j = idx - 1; j >= Math.max(0, idx - 100) && count < 20; j--) {
      const temp = data[j].temperature;
      if (temp < 26) {
        sum += temp;
        count++;
      }
    }
    return count > 0 ? sum / count : 25;
  };

  const result: PoolTempDataPoint[] = [];

  for (let i = 0; i < data.length; i++) {
    const point = data[i];
    let smoothedTemp = point.temperature;
    let isSmoothed = false;

    // During heating, trust the measurements (up to reasonable max)
    if (isDuringHeating(point.timestamp)) {
      // During actual heating, pool temp shouldn't exceed ~28°C realistically
      if (smoothedTemp > 28) {
        smoothedTemp = Math.min(smoothedTemp, 28);
        isSmoothed = true;
      }
    } else {
      // Not during heating - this is where calibration spikes occur
      const baseline = findBaseline(i);

      // If temp is significantly above baseline, it's a spike
      if (smoothedTemp > baseline + 1) {
        smoothedTemp = baseline;
        isSmoothed = true;
      }
    }

    result.push({
      timestamp: point.timestamp,
      temperature: smoothedTemp,
      isSmoothed,
    });
  }

  return result;
}

/**
 * Parse history API response into data points
 */
function parseHistory(history: unknown, entityId: string): PoolTempDataPoint[] {
  const result: PoolTempDataPoint[] = [];

  // Handle WebSocket response format: {entity_id: [...states...]}
  let states: HAEntityState[] = [];
  if (history && typeof history === 'object') {
    if (Array.isArray(history)) {
      states = history[0] || [];
    } else {
      const historyObj = history as Record<string, HAEntityState[]>;
      states = historyObj[entityId] || [];
    }
  }

  for (let i = 0; i < states.length; i++) {
    const stateRaw = states[i];
    try {
      const state = stateRaw as Record<string, unknown>;
      const stateValue = (state.state ?? state.s) as string | undefined;
      // Minimal response uses: s=state, lu=last_updated (Unix timestamp in seconds)
      // Full response uses: state, last_changed (ISO string)
      const lastChangedRaw = state.last_changed ?? state.last_updated ?? state.lu;

      if (!stateValue || stateValue === 'unknown' || stateValue === 'unavailable') {
        continue;
      }

      const temp = parseFloat(stateValue);
      if (isNaN(temp)) continue;

      // Parse timestamp - handle both Unix timestamp (seconds) and ISO string
      let timestamp: Date;
      if (typeof lastChangedRaw === 'number') {
        // Unix timestamp in seconds
        timestamp = new Date(lastChangedRaw * 1000);
      } else if (typeof lastChangedRaw === 'string') {
        timestamp = new Date(lastChangedRaw);
      } else {
        // No valid timestamp, skip this entry
        continue;
      }

      result.push({
        timestamp,
        temperature: temp,
        isSmoothed: false,
      });
    } catch {
      continue;
    }
  }

  return result.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
}

/**
 * Parse heating active history into periods
 */
function parseHeatingPeriods(history: unknown): HeatingPeriod[] {
  const periods: HeatingPeriod[] = [];

  let states: HAEntityState[] = [];
  if (history && typeof history === 'object') {
    if (Array.isArray(history)) {
      states = history[0] || [];
    } else {
      const historyObj = history as Record<string, HAEntityState[]>;
      states = historyObj['binary_sensor.pool_heating_active'] || [];
    }
  }

  let currentPeriodStart: Date | null = null;

  for (const stateRaw of states) {
    try {
      const state = stateRaw as Record<string, unknown>;
      const stateValue = (state.state ?? state.s) as string | undefined;
      const lastChangedRaw = state.last_changed ?? state.last_updated ?? state.lu;

      let timestamp: Date;
      if (typeof lastChangedRaw === 'number') {
        timestamp = new Date(lastChangedRaw * 1000);
      } else if (typeof lastChangedRaw === 'string') {
        timestamp = new Date(lastChangedRaw);
      } else {
        continue;
      }

      const isOn = stateValue === 'on';

      if (isOn && !currentPeriodStart) {
        currentPeriodStart = timestamp;
      } else if (!isOn && currentPeriodStart) {
        periods.push({ start: currentPeriodStart, end: timestamp });
        currentPeriodStart = null;
      }
    } catch {
      continue;
    }
  }

  // If still heating at end of data, close the period
  if (currentPeriodStart) {
    periods.push({ start: currentPeriodStart, end: new Date() });
  }

  return periods;
}

export type TimeRangeHours = 24 | 48 | 168; // 24h, 48h, 7 days

export function usePoolTempHistory(hours: TimeRangeHours = 24): PoolTempHistoryState {
  const [data, setData] = useState<PoolTempDataPoint[]>([]);
  const [rawData, setRawData] = useState<PoolTempDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const ws = getHAWebSocket();

      if (!ws.connected) {
        await ws.connect();
      }

      const end = new Date();
      const start = new Date(end.getTime() - hours * 60 * 60 * 1000);

      // Fetch both sensors:
      // - pool_true_temp: calibrated true pool temp (updated at end of heating blocks & calibrations)
      // - pool_return_line_temperature_corrected: real-time sensor (for current reading)
      const history = await ws.getHistory(
        start,
        end,
        [
          'input_number.pool_true_temp',
          'sensor.pool_return_line_temperature_corrected',
          'binary_sensor.pool_heating_active'
        ],
        true // minimal response
      );

      // Use true temp sensor as primary data (clean, no spikes)
      const trueTempData = parseHistory(history, 'input_number.pool_true_temp');

      // Also get real-time sensor data
      const sensorData = parseHistory(history, 'sensor.pool_return_line_temperature_corrected');
      setRawData(sensorData);

      // Parse heating periods
      const heatingPeriods = parseHeatingPeriods(history);

      // Combine: use true temp values, but fill gaps with smoothed sensor data during heating
      let combined: PoolTempDataPoint[];
      if (trueTempData.length > 0) {
        // Start with true temp data
        combined = [...trueTempData];

        // Add sensor readings during heating periods (when true temp is being measured)
        const smoothedSensor = smoothSpikes(sensorData, heatingPeriods);
        for (const point of smoothedSensor) {
          // Only add if during heating and not too close to existing true temp reading
          const isDuringHeating = heatingPeriods.some(
            p => point.timestamp >= p.start && point.timestamp <= p.end
          );
          if (isDuringHeating) {
            const tooClose = combined.some(
              t => Math.abs(t.timestamp.getTime() - point.timestamp.getTime()) < 60000
            );
            if (!tooClose) {
              combined.push(point);
            }
          }
        }
        combined.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
      } else {
        // No true temp data yet, fall back to smoothed sensor data
        combined = smoothSpikes(sensorData, heatingPeriods);
      }

      setData(combined);

    } catch (err) {
      console.error('[usePoolTempHistory] Failed to fetch:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch temperature history');
    } finally {
      setLoading(false);
    }
  }, [hours]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return { data, rawData, loading, error, refetch: fetchHistory };
}
