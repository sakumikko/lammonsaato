/**
 * Hook for calculating rolling integrals from time-series data
 *
 * For each point in time, calculates the integral over the preceding
 * 15, 30, and 60 minute windows. This produces time series data that
 * can be graphed.
 */

import { useMemo } from 'react';
import { MultiEntityHistoryData, EntityConfig } from '@/types/graphs';

export interface RollingIntegralSeries {
  /** Rolling integral series data merged into history format */
  data: MultiEntityHistoryData;
  /** Entity configs for the integral lines */
  entities: EntityConfig[];
}

const WINDOWS = {
  '15m': { ms: 15 * 60 * 1000, label: 'PID Integral 15m', color: '#f97316' }, // orange-500
  '30m': { ms: 30 * 60 * 1000, label: 'PID Integral 30m', color: '#eab308' }, // yellow-500
  '60m': { ms: 60 * 60 * 1000, label: 'PID Integral 60m', color: '#22c55e' }, // green-500
} as const;

// Virtual entity IDs for the rolling integrals
export const ROLLING_INTEGRAL_ENTITIES = {
  '15m': 'virtual.pid_integral_15m',
  '30m': 'virtual.pid_integral_30m',
  '60m': 'virtual.pid_integral_60m',
} as const;

/**
 * Calculate trapezoidal integral for points within a window ending at targetTime
 */
function calculateIntegralAtPoint(
  points: Array<{ timestamp: number; value: number }>,
  targetTime: number,
  windowMs: number
): number {
  const windowStart = targetTime - windowMs;

  // Get points within the window
  const windowPoints = points.filter(
    p => p.timestamp >= windowStart && p.timestamp <= targetTime
  );

  if (windowPoints.length < 2) return 0;

  let integral = 0;

  for (let i = 1; i < windowPoints.length; i++) {
    const p1 = windowPoints[i - 1];
    const p2 = windowPoints[i];

    // Time difference in minutes
    const dtMinutes = (p2.timestamp - p1.timestamp) / (60 * 1000);

    // Trapezoidal rule: (v1 + v2) / 2 * dt
    const avgValue = (p1.value + p2.value) / 2;
    integral += avgValue * dtMinutes;
  }

  return integral;
}

/**
 * Hook to calculate rolling integrals for PID sum entity
 *
 * @param data History data from useHistoryData
 * @param entityId Source entity ID to calculate integral for
 * @param enabled Whether rolling integrals should be calculated
 * @returns RollingIntegralSeries with data and entity configs
 */
export function useRollingIntegrals(
  data: MultiEntityHistoryData | null,
  entityId: string,
  enabled: boolean = true
): RollingIntegralSeries | null {
  return useMemo(() => {
    if (!enabled || !data || !data.series || data.series.length < 2) {
      return null;
    }

    // Extract raw values for the source entity
    const sourcePoints: Array<{ timestamp: number; value: number }> = [];

    for (const point of data.series) {
      const entityData = point.values[entityId];
      if (entityData && entityData.raw !== null) {
        sourcePoints.push({
          timestamp: point.timestamp,
          value: entityData.raw,
        });
      }
    }

    if (sourcePoints.length < 2) {
      return null;
    }

    // Calculate rolling integrals at each timestamp
    const integralSeries15m: number[] = [];
    const integralSeries30m: number[] = [];
    const integralSeries60m: number[] = [];

    // Find min/max for normalization
    let min15 = Infinity, max15 = -Infinity;
    let min30 = Infinity, max30 = -Infinity;
    let min60 = Infinity, max60 = -Infinity;

    for (const point of sourcePoints) {
      const int15 = calculateIntegralAtPoint(sourcePoints, point.timestamp, WINDOWS['15m'].ms);
      const int30 = calculateIntegralAtPoint(sourcePoints, point.timestamp, WINDOWS['30m'].ms);
      const int60 = calculateIntegralAtPoint(sourcePoints, point.timestamp, WINDOWS['60m'].ms);

      integralSeries15m.push(int15);
      integralSeries30m.push(int30);
      integralSeries60m.push(int60);

      min15 = Math.min(min15, int15);
      max15 = Math.max(max15, int15);
      min30 = Math.min(min30, int30);
      max30 = Math.max(max30, int30);
      min60 = Math.min(min60, int60);
      max60 = Math.max(max60, int60);
    }

    // Normalize function
    const normalize = (val: number, min: number, max: number): number => {
      if (max === min) return 50;
      return Math.max(0, Math.min(100, ((val - min) / (max - min)) * 100));
    };

    // Build merged data series with integral values added
    const mergedSeries = data.series.map((point, idx) => {
      // Find corresponding source point index
      const sourceIdx = sourcePoints.findIndex(sp => sp.timestamp === point.timestamp);

      const newValues = { ...point.values };

      if (sourceIdx !== -1) {
        const int15 = integralSeries15m[sourceIdx];
        const int30 = integralSeries30m[sourceIdx];
        const int60 = integralSeries60m[sourceIdx];

        newValues[ROLLING_INTEGRAL_ENTITIES['15m']] = {
          raw: int15,
          normalized: normalize(int15, min15, max15),
        };
        newValues[ROLLING_INTEGRAL_ENTITIES['30m']] = {
          raw: int30,
          normalized: normalize(int30, min30, max30),
        };
        newValues[ROLLING_INTEGRAL_ENTITIES['60m']] = {
          raw: int60,
          normalized: normalize(int60, min60, max60),
        };
      }

      return {
        ...point,
        values: newValues,
      };
    });

    // Entity configs for the integral lines
    const integralEntities: EntityConfig[] = [
      {
        entityId: ROLLING_INTEGRAL_ENTITIES['15m'],
        label: WINDOWS['15m'].label,
        color: WINDOWS['15m'].color,
        min: min15,
        max: max15,
        unit: '°min',
        axisGroup: 'control',
        visible: false, // Off by default
      },
      {
        entityId: ROLLING_INTEGRAL_ENTITIES['30m'],
        label: WINDOWS['30m'].label,
        color: WINDOWS['30m'].color,
        min: min30,
        max: max30,
        unit: '°min',
        axisGroup: 'control',
        visible: false,
      },
      {
        entityId: ROLLING_INTEGRAL_ENTITIES['60m'],
        label: WINDOWS['60m'].label,
        color: WINDOWS['60m'].color,
        min: min60,
        max: max60,
        unit: '°min',
        axisGroup: 'control',
        visible: false,
      },
    ];

    return {
      data: {
        ...data,
        series: mergedSeries,
      },
      entities: integralEntities,
    };
  }, [data, entityId, enabled]);
}
