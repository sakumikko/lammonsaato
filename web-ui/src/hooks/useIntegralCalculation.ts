/**
 * Hook for calculating running integrals from time-series data
 *
 * Calculates the integral (cumulative sum) of sensor values over
 * specified time windows (15, 30, 60 minutes).
 *
 * Uses trapezoidal integration: integral = sum((v1 + v2) / 2 * dt)
 */

import { useMemo } from 'react';
import { MultiEntityHistoryData } from '@/types/graphs';

export interface IntegralResult {
  /** Integral over the last 15 minutes */
  integral15m: number;
  /** Integral over the last 30 minutes */
  integral30m: number;
  /** Integral over the last 60 minutes */
  integral60m: number;
}

const WINDOWS = {
  '15m': 15 * 60 * 1000, // 15 minutes in ms
  '30m': 30 * 60 * 1000, // 30 minutes in ms
  '60m': 60 * 60 * 1000, // 60 minutes in ms
} as const;

/**
 * Calculate trapezoidal integral for a time window
 * @param points Array of {timestamp, value} sorted by timestamp ascending
 * @param windowMs Time window in milliseconds from the end
 * @returns Integral value (units: value * minutes)
 */
function calculateIntegral(
  points: Array<{ timestamp: number; value: number | null }>,
  windowMs: number
): number {
  if (points.length < 2) return 0;

  const now = points[points.length - 1].timestamp;
  const windowStart = now - windowMs;

  // Filter points within the window
  const windowPoints = points.filter(
    p => p.timestamp >= windowStart && p.value !== null
  );

  if (windowPoints.length < 2) return 0;

  let integral = 0;

  for (let i = 1; i < windowPoints.length; i++) {
    const p1 = windowPoints[i - 1];
    const p2 = windowPoints[i];

    if (p1.value === null || p2.value === null) continue;

    // Time difference in minutes
    const dtMinutes = (p2.timestamp - p1.timestamp) / (60 * 1000);

    // Trapezoidal rule: (v1 + v2) / 2 * dt
    const avgValue = (p1.value + p2.value) / 2;
    integral += avgValue * dtMinutes;
  }

  return integral;
}

/**
 * Hook to calculate running integrals for an entity from history data
 *
 * @param data History data from useHistoryData
 * @param entityId Entity ID to calculate integral for
 * @returns IntegralResult with 15m, 30m, 60m integrals
 */
export function useIntegralCalculation(
  data: MultiEntityHistoryData | null,
  entityId: string
): IntegralResult | null {
  return useMemo(() => {
    if (!data || !data.series || data.series.length === 0) {
      return null;
    }

    // Extract raw values for the entity
    const points: Array<{ timestamp: number; value: number | null }> = [];

    for (const point of data.series) {
      const entityData = point.values[entityId];
      if (entityData) {
        points.push({
          timestamp: point.timestamp,
          value: entityData.raw,
        });
      }
    }

    if (points.length < 2) {
      return null;
    }

    return {
      integral15m: calculateIntegral(points, WINDOWS['15m']),
      integral30m: calculateIntegral(points, WINDOWS['30m']),
      integral60m: calculateIntegral(points, WINDOWS['60m']),
    };
  }, [data, entityId]);
}
